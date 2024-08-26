from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import DB

from app.routes.utils import get_service_data, handle_error, update_service

services = Blueprint("services", __name__)


@services.route("/services", methods=["GET", "POST"])
@login_required
def services_page():
    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "services")

        config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged, mode = get_service_data("services")

        message = update_service(config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged)

        return redirect(url_for("loading", next=url_for("services.services_page"), message=message))

    # Display services
    services = []
    tmp_config = DB.get_config(methods=True, with_drafts=True).copy()
    service_names = tmp_config["SERVER_NAME"]["value"].split(" ")

    table_settings = (
        "USE_REVERSE_PROXY",
        "IS_DRAFT",
        "SERVE_FILES",
        "REMOTE_PHP",
        "AUTO_LETS_ENCRYPT",
        "USE_CUSTOM_SSL",
        "USE_MODSECURITY",
        "USE_BAD_BEHAVIOR",
        "USE_LIMIT_REQ",
        "USE_DNSBL",
        "SERVER_NAME",
    )

    for service in service_names:
        service_settings = {}

        # For each needed setting, get the service value if one, else the global (value), else default value
        for setting in table_settings:
            value = tmp_config.get(f"{service}_{setting}", tmp_config.get(setting, {"value": None}))["value"]
            method = tmp_config.get(f"{service}_{setting}", tmp_config.get(setting, {"method": None}))["method"]
            is_global = tmp_config.get(f"{service}_{setting}", tmp_config.get(setting, {"global": None}))["global"]
            service_settings[setting] = {"value": value, "method": method, "global": is_global}

        services.append(service_settings)

    services.sort(key=lambda x: x["SERVER_NAME"]["value"])

    # builder = services_builder(services)
    # return render_template("services.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))
    return render_template("services.html")
