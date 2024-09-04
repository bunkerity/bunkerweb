from flask import Blueprint, Response, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DB

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

    return render_template("services.html")  # TODO


@services.route("/services/<string:service>", methods=["GET", "POST"])
@login_required
def services_service_page(service: str):
    services = BW_CONFIG.get_config(global_only=True, methods=False, filtered_settings=("SERVER_NAME"))["SERVER_NAME"].split(" ")
    if service not in services:
        return Response("Service not found", status=404)
    mode = request.args.get("mode", "easy")
    keywords = request.args.get("keywords", "")
    search_type = request.args.get("type", "all")
    db_config = DB.get_config(methods=True, with_drafts=True, service=service)
    plugins = BW_CONFIG.get_plugins()
    return render_template("service_settings.html", config=db_config, plugins=plugins, mode=mode, keywords=keywords, type=search_type)
