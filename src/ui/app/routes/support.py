from io import BytesIO
from json import dumps
from os import sep
from pathlib import Path
from re import compile as re_compile, escape
from zipfile import ZipFile
from flask import Blueprint, render_template, request, send_file
from flask_login import login_required

from app.dependencies import BW_CONFIG, DB


support = Blueprint("support", __name__)


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
    service = request.args.get("service")

    if service:
        if service not in BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split():
            return "Service not found", 404

        service_config = DB.get_config(methods=True, with_drafts=True, service=service)
        return send_file(
            BytesIO(dumps(service_config, indent=2).encode()), mimetype="application/json", as_attachment=True, download_name=f"{service}_config.json"
        )

    db_config = DB.get_config(methods=True, with_drafts=True)
    return send_file(BytesIO(dumps(db_config, indent=2).encode()), mimetype="application/json", as_attachment=True, download_name="bunkerweb_config.json")
