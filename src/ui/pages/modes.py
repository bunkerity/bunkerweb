from base64 import b64encode
from json import dumps

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from builder.advanced_mode import advanced_mode_builder  # type: ignore
from builder.easy_mode import easy_mode_builder  # type: ignore
from builder.raw_mode import raw_mode_builder  # type: ignore

from dependencies import BW_CONFIG, DB

from pages.utils import get_service_data, handle_error, update_service

modes = Blueprint("modes", __name__)


@modes.route("/modes", methods=["GET", "POST"])
@login_required
def services_modes():
    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "services")

        config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged, mode = get_service_data("modes")
        message = update_service(config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged)
        # print(message, flush=True)
        # print("mode", mode, "service name", server_name, flush=True)
        # TODO: redirect to /mode?service_name=my_service&mode=my_mode
        # Following is not working :
        # return redirect(url_for("loading", next=url_for("modes", mode=mode, service_name=server_name), message=message))
        # or
        # return redirect(url_for("loading", next=url_for(f"modes?service_name={server_name}&mode={mode}"), message=message))
        return redirect(url_for("loading", next=url_for(request.endpoint), message=message))

    if not request.args.get("mode"):
        return handle_error("Mode type is missing to access /modes.", "services")

    mode = request.args.get("mode")
    service_name = request.args.get("service_name")
    total_config = DB.get_config(methods=True, with_drafts=True)
    service_names = total_config["SERVER_NAME"]["value"].split(" ")

    if service_name and service_name not in service_names:
        return handle_error("Service name not found to access advanced mode.", "services")

    global_config = BW_CONFIG.get_config(global_only=True, methods=True)
    plugins = BW_CONFIG.get_plugins()

    builder = None
    templates_db = DB.get_templates()

    if mode == "raw":
        builder = raw_mode_builder(templates_db, plugins, global_config, total_config, service_name or "new", not service_name)
    elif mode == "advanced":
        builder = advanced_mode_builder(templates_db, plugins, global_config, total_config, service_name or "new", not service_name)
    elif mode == "easy":
        builder = easy_mode_builder(templates_db, plugins, global_config, total_config, service_name or "new", not service_name)

    return render_template("modes.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))
