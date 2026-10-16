from datetime import datetime, timezone
from io import BytesIO
from json import dumps
from os import environ, getpid, sep
from pathlib import Path
from zipfile import ZipFile
from flask import Blueprint, current_app, render_template, request, send_file
from flask_login import current_user, login_required

from common_utils import get_integration  # type: ignore
from logger import getLogger  # type: ignore

from app.dependencies import API_CLIENT, BW_CONFIG
from app.api_client import ApiClientError, ApiUnavailableError
from app.i18n import translated
from app.models.biscuit import render_error_page
from app.models.secret_settings import REDACTED, mask_uri_settings, redact_secrets, secret_setting_names
from app.support_bundle import RING_HANDLER, Anonymizer, build_environment, build_plugins_report, build_support_bundle, install_ring_handler

support = Blueprint("support", __name__)

# The diagnostics bundle carries the recent records of this worker
install_ring_handler(getLogger("UI"))


def _may_download() -> bool:
    """The bundles hold every setting and every log line: same `write` gate as the pages that edit them."""
    return "write" in current_user.list_permissions


def service_domains() -> set:
    config = BW_CONFIG.get_config(methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))
    return {domain for key, value in config.items() if key == "SERVER_NAME" or key.endswith("_SERVER_NAME") for domain in value.split()}


def _api(call, default):
    """A diagnostics bundle is most needed when the API is struggling: a failed call leaves its part empty instead of failing the download."""
    try:
        return call()
    except (ApiClientError, ApiUnavailableError):
        return default


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
    if not _may_download():
        return render_error_page(403, translated("flash.do_not_have_write_permission") or "You do not have the write permission")

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
                # Redacted as one text: a secret value can span lines (YAML block scalar, bracketed structure)
                zip_file.writestr(file.name, anonymizer.redact(file.read_bytes().decode("utf-8", errors="replace")))

    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype="application/zip", as_attachment=True, download_name="logs.zip")


@support.route("/support/config")
@login_required
def support_config():
    if not _may_download():
        return render_error_page(403, translated("flash.do_not_have_write_permission") or "You do not have the write permission")

    # Meant to be attached to a support request: no secret value leaves, whoever downloads it.
    secrets = secret_setting_names(BW_CONFIG.get_plugins_settings())
    service = request.args.get("service")

    if service:
        if service not in BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split():
            return "Service not found", 404

        try:
            service_config = mask_uri_settings(redact_secrets(API_CLIENT.get_service(service, full=True, methods=True), secrets, REDACTED))
        except (ApiClientError, ApiUnavailableError):
            return "Could not retrieve service config", 500
        return send_file(
            BytesIO(dumps(service_config, indent=2).encode()), mimetype="application/json", as_attachment=True, download_name=f"{service}_config.json"
        )

    db_config = mask_uri_settings(redact_secrets(BW_CONFIG.get_config(methods=True, with_drafts=True), secrets, REDACTED))
    return send_file(BytesIO(dumps(db_config, indent=2).encode()), mimetype="application/json", as_attachment=True, download_name="bunkerweb_config.json")


@support.route("/support/ui_bundle")
@login_required
def support_ui_bundle():
    # The owner flag, like the other admin-only routes: a "write" role is not enough to read the plugin inventory and recent errors
    if not current_user.admin:
        return render_error_page(403, translated("support.card.ui_bundle.admin_only") or "The Web UI diagnostics bundle is restricted to administrators")

    # Imported here: the paths belong to dependencies, which the other routes of this module do not need
    from app.dependencies import CORE_PLUGINS_PATH, EXTERNAL_PLUGINS_PATH, PRO_PLUGINS_PATH

    worker = {"pid": getpid(), "started": RING_HANDLER.started.isoformat()}
    integration = get_integration()
    plugins = build_plugins_report(
        _api(lambda: API_CLIENT.get_plugins(type="all", with_settings=False), []),
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
        metadata=_api(API_CLIENT.get_metadata, {}),
        integration=integration,
        instances=_api(API_CLIENT.get_instances, []),
        service_count=len(_api(API_CLIENT.get_services, [])),
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
