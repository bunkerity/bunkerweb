from datetime import datetime, timezone
from io import BytesIO
from json import dumps
from os import environ, getpid, sep
from pathlib import Path
from re import VERBOSE as re_X, compile as re_compile
from zipfile import ZipFile
from flask import Blueprint, abort, current_app, render_template, request, send_file
from flask_login import current_user, login_required
from sqlalchemy import text

from common_utils import get_integration  # type: ignore

from app.dependencies import BW_CONFIG, CORE_PLUGINS_PATH, DB, EXTERNAL_PLUGINS_PATH, PRO_PLUGINS_PATH
from app.support_bundle import RING_HANDLER, Anonymizer, build_environment, build_plugins_report, build_support_bundle

support = Blueprint("support", __name__)


def service_domains() -> set:
    config = BW_CONFIG.get_config(methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))
    return {domain for key, value in config.items() if key == "SERVER_NAME" or key.endswith("_SERVER_NAME") for domain in value.split()}


def alembic_revision():
    try:
        with DB._db_session() as session:
            row = session.execute(text("SELECT version_num FROM alembic_version")).first()
        return row[0] if row else None
    except Exception:
        return None


@support.route("/support")
@login_required
def support_page():
    return render_template(
        "support.html",
        services=BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(),
    )


@support.route("/support/logs")
@login_required
def support_logs():
    logs_path = Path(sep, "var", "log", "bunkerweb")

    # If no files are in the directory, return an error message
    if not any(logs_path.glob("*.log")):
        return "No log files found", 404

    anonymizer = Anonymizer(service_domains())

    # Create zip buffer
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as zip_file:
        for file in logs_path.glob("*.log"):
            if file.is_file():
                # Process file line by line to reduce memory usage
                with file.open("rb") as f:
                    content = [anonymizer.redact(line.decode("utf-8", errors="replace")) for line in f]
                    zip_file.writestr(file.name, "".join(content))

    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype="application/zip", as_attachment=True, download_name="logs.zip")


REDACTED = "[REDACTED]"
MULTIPLE_SUFFIX = re_compile(r"_\d+$")
# Scheme and userinfo part of sqlalchemy.engine.url._parse_url, so the password span is the one SQLAlchemy parses
URL_USERINFO = re_compile(
    r"""
    (?P<name>[\w\+]+)://
    (?:
        (?P<username>[^:/]*)
        (?::(?P<password>[^@]*))?
    @)
    """,
    re_X,
)
URI_SETTINGS = ("DATABASE_URI", "DATABASE_URI_READONLY")


def setting_names(key: str, names) -> set:
    """Return every known setting name a config key (``[service_]SETTING[_N]``) can stand for.

    A service name can contain ``_``, so every ``_`` boundary is a candidate, on the raw key and on the key without its ``_N`` suffix.
    The caller masks when any candidate is sensitive, so the result never depends on which candidate would be the "right" one.
    """
    found = set()
    for base in {key, MULTIPLE_SUFFIX.sub("", key)}:
        found.update(
            candidate for candidate in (base, *(base[index + 1 :] for index, char in enumerate(base) if char == "_")) if candidate in names  # noqa: E203
        )  # noqa: E203
    return found


def mask_uri(uri: str) -> str:
    """Redact the password of a SQLAlchemy URL, keeping every other character as is."""
    match = URL_USERINFO.match(uri)
    if not match or not match["password"]:
        return uri
    # SQLAlchemy ends the password at the first "@", the host part may still hold some, so redact up to the last one before the path or query
    authority_end = min((i for i in (uri.find("/", match.end()), uri.find("?", match.end())) if i >= 0), default=len(uri))
    end = max(match.end(), uri.rfind("@", match.end() - 1, authority_end) + 1)
    return f"{uri[: match.start('password')]}{REDACTED}{uri[end - 1 :]}"


def mask_config(config: dict) -> dict:
    """Redact the value and the default of every password setting and the password part of the database URIs."""
    settings = BW_CONFIG.get_plugins_settings()
    for key, data in config.items():
        if not isinstance(data, dict):
            continue

        names = setting_names(key, settings)
        is_password = any(settings[name].get("type") == "password" for name in names)
        is_uri = any(name in URI_SETTINGS for name in names)
        for field in ("value", "default"):
            content = data.get(field)
            if not content or not isinstance(content, str):
                continue
            if is_uri and not is_password:
                data[field] = mask_uri(content)
            elif is_password:
                data[field] = REDACTED
    return config


@support.route("/support/config")
@login_required
def support_config():
    service = request.args.get("service")
    # Only an admin can ask for the clear values, everyone else always gets the masked export
    mask = not (current_user.admin and request.args.get("mask_passwords") == "no")

    if service:
        if service not in BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split():
            return "Service not found", 404

        service_config = DB.get_config(methods=True, with_drafts=True, service=service)
        if mask:
            mask_config(service_config)
        return send_file(
            BytesIO(dumps(service_config, indent=2).encode()), mimetype="application/json", as_attachment=True, download_name=f"{service}_config.json"
        )

    db_config = DB.get_config(methods=True, with_drafts=True)
    if mask:
        mask_config(db_config)
    return send_file(BytesIO(dumps(db_config, indent=2).encode()), mimetype="application/json", as_attachment=True, download_name="bunkerweb_config.json")


@support.route("/support/ui_bundle")
@login_required
def support_ui_bundle():
    # The PRO user manager does not know /support/*, so this check is the only gate
    if not current_user.admin:
        abort(403)

    worker = {"pid": getpid(), "started": RING_HANDLER.started.isoformat()}
    integration = get_integration()
    plugins = build_plugins_report(
        DB.get_plugins(_type="all"),
        {"core": CORE_PLUGINS_PATH, "external": EXTERNAL_PLUGINS_PATH, "pro": PRO_PLUGINS_PATH},
        [
            {
                "name": blueprint.name,
                "plugin_priority": getattr(blueprint, "plugin_priority", None),
                "root_path": blueprint.root_path,
                "import_path": blueprint.import_path,
                "plugin_version": getattr(blueprint, "plugin_version", None),
            }
            for blueprint in current_app.blueprints.values()
            if getattr(blueprint, "import_path", None)
        ],
        worker,
    )
    environment = build_environment(
        metadata=DB.get_metadata(),
        integration=integration,
        instances=DB.get_instances(),
        service_count=len(DB.get_services()),
        db_dialect=DB.sql_engine.dialect.name,
        db_revision=alembic_revision(),
        worker=worker,
    )
    bundle = build_support_bundle(
        domains=service_domains(),
        environ=environ,
        integration=integration,
        ring=RING_HANDLER.snapshot(),
        plugins=plugins,
        environment=environment,
    )
    return send_file(
        BytesIO(bundle),
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"bunkerweb-ui-support-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.zip",
    )
