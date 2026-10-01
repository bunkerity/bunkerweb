from io import BytesIO
from json import dumps
from os import sep
from pathlib import Path
from re import compile as re_compile, escape
from zipfile import ZipFile
from flask import Blueprint, render_template, request, send_file
from flask_login import current_user, login_required

from app.dependencies import API_CLIENT, BW_CONFIG
from app.api_client import ApiClientError, ApiUnavailableError
from app.i18n import translated
from app.models.biscuit import render_error_page
from app.models.secret_settings import REDACTED, redact_secrets, secret_setting_names

support = Blueprint("support", __name__)


def _may_download() -> bool:
    """The bundles hold every setting and every log line: same `write` gate as the pages that edit them."""
    return "write" in current_user.list_permissions


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

    # Get services once
    db_services = BW_CONFIG.get_config(methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))
    services = {domain for key, value in db_services.items() if key.endswith("_SERVER_NAME") for domain in value.split()}

    # Compile regex patterns for IPv4, IPv6, and domain names
    ipv4_pattern = r"(?:\d{1,3}\.){3}\d{1,3}"
    ipv6_pattern = r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"
    domains_pattern = "|".join(map(escape, services))

    pattern = re_compile(rf"\b(?:(?P<domain>{domains_pattern})|(?P<ipv4>{ipv4_pattern})|(?P<ipv6>{ipv6_pattern}))\b")

    # Create zip buffer
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as zip_file:
        for file in logs_path.glob("*.log"):
            if file.is_file():
                # Process file line by line to reduce memory usage
                with file.open("rb") as f:
                    content = []
                    for line in f:
                        line = line.decode("utf-8", errors="replace")
                        line = pattern.sub(
                            lambda m: "[ANONYMIZED_DOMAIN]" if m.group("domain") else ("[ANONYMIZED_IPv4]" if m.group("ipv4") else "[ANONYMIZED_IPv6]"),
                            line,
                        )
                        content.append(line)
                    zip_file.writestr(file.name, "".join(content))

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
            service_config = redact_secrets(API_CLIENT.get_service(service, full=True, methods=True), secrets, REDACTED)
        except (ApiClientError, ApiUnavailableError):
            return "Could not retrieve service config", 500
        return send_file(
            BytesIO(dumps(service_config, indent=2).encode()), mimetype="application/json", as_attachment=True, download_name=f"{service}_config.json"
        )

    db_config = redact_secrets(BW_CONFIG.get_config(methods=True, with_drafts=True), secrets, REDACTED)
    return send_file(BytesIO(dumps(db_config, indent=2).encode()), mimetype="application/json", as_attachment=True, download_name="bunkerweb_config.json")
