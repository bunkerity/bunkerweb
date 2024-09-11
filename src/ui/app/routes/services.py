from re import match
from threading import Thread
from time import time
from typing import Dict
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DATA, DB

from app.routes.utils import handle_error, manage_bunkerweb, wait_applying

services = Blueprint("services", __name__)


@services.route("/services", methods=["GET", "POST"])
@login_required
def services_page():
    if request.method == "POST":  # TODO: Handle creation and deletion of services
        if DB.readonly:
            return handle_error("Database is in read-only mode", "services")

        # config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged, mode = get_service_data("services")

        # message = update_service(config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged)

        # return redirect(url_for("loading", next=url_for("services.services_page"), message=message))

    return render_template("services.html")  # TODO


@services.route("/services/<string:service>", methods=["GET", "POST"])
@login_required
def services_service_page(service: str):
    services = BW_CONFIG.get_config(global_only=True, methods=False, filtered_settings=("SERVER_NAME"))["SERVER_NAME"].split(" ")
    service_exists = service in services

    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "services")
        DATA.load_from_file()

        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]

        mode = request.args.get("mode", "easy")
        is_draft = variables.get("IS_DRAFT", "no") == "yes"

        def update_service(variables: Dict[str, str], is_draft: bool, threaded: bool = False):  # TODO: handle easy and raw modes
            wait_applying()

            # Edit check fields and remove already existing ones
            if service_exists:
                config = DB.get_config(methods=True, with_drafts=True, filtered_settings=list(variables.keys()), service=service)
            else:
                config = DB.get_config(methods=True, with_drafts=True, filtered_settings=list(variables.keys()))
            was_draft = config.get(f"{service}_IS_DRAFT", {"value": "no"})["value"] == "yes"

            old_server_name = variables.pop("OLD_SERVER_NAME", "")
            ignored_multiples = set()

            # Edit check fields and remove already existing ones
            for variable, value in variables.copy().items():
                if variable != "SERVER_NAME" and value == config.get(f"{service}_{variable}", {"value": None})["value"]:
                    if match(r"^.+_\d+$", variable):
                        ignored_multiples.add(variable)
                    del variables[variable]

            variables = BW_CONFIG.check_variables(variables, config, ignored_multiples=ignored_multiples, threaded=threaded)

            if was_draft == is_draft and not variables:
                content = f"The service {service} was not edited because no values were changed."
                if threaded:
                    DATA["TO_FLASH"].append({"content": content, "type": "warning"})
                else:
                    flash(content, "warning")
                DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                return

            if "SERVER_NAME" not in variables:
                variables["SERVER_NAME"] = old_server_name

            manage_bunkerweb(
                "services",
                variables,
                old_server_name,
                operation="edit" if service_exists else "new",
                is_draft=is_draft,
                was_draft=was_draft,
                threaded=threaded,
            )

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        Thread(target=update_service, args=(variables, is_draft, True)).start()

        arguments = {}
        if mode != "easy":
            arguments["mode"] = mode
        if request.args.get("type", "all") != "all":
            arguments["type"] = request.args["type"]

        return redirect(
            url_for(
                "loading",
                next=url_for(
                    "services.services_service_page",
                    service=service,
                )
                + f"?{'&'.join([f'{k}={v}' for k, v in arguments.items()])}",
                message=f"Saving configuration for {'draft ' if is_draft else ''}service {service}",
            )
        )

    services = BW_CONFIG.get_config(global_only=True, methods=False, filtered_settings=("SERVER_NAME"))["SERVER_NAME"].split(" ")
    if not service_exists:
        db_config = DB.get_config(global_only=True, methods=True)
        return render_template("service_settings.html", config=db_config)

    mode = request.args.get("mode", "easy")
    search_type = request.args.get("type", "all")
    db_config = DB.get_config(methods=True, with_drafts=True, service=service)
    return render_template(
        "service_settings.html",
        config=db_config,
        mode=mode,
        type=search_type,
    )


# def update_service(config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged):
#     if request.form["operation"] == "edit":
#         if is_draft_unchanged and len(variables) == 1 and "SERVER_NAME" in variables and server_name == old_server_name:
#             return handle_error("The service was not edited because no values were changed.", "services", True)

#     if request.form["operation"] == "new" and not variables:
#         return handle_error("The service was not created because all values had the default value.", "services", True)

#     # Delete
#     if request.form["operation"] == "delete":

#         is_service = BW_CONFIG.check_variables({"SERVER_NAME": request.form["SERVER_NAME"]}, config)

#         if not is_service:
#             error_message(f"Error while deleting the service {request.form['SERVER_NAME']}")

#         if config.get(f"{request.form['SERVER_NAME'].split(' ')[0]}_SERVER_NAME", {"method": "scheduler"})["method"] != "ui":
#             return handle_error("The service cannot be deleted because it has not been created with the UI.", "services", True)

#     db_metadata = DB.get_metadata()

#     def update_services(threaded: bool = False):
#         wait_applying()

#         manage_bunkerweb(
#             "services",
#             variables,
#             old_server_name,
#             variables.get("SERVER_NAME", ""),
#             operation=operation,
#             is_draft=is_draft,
#             was_draft=was_draft,
#             threaded=threaded,
#         )

#         if any(
#             v
#             for k, v in db_metadata.items()
#             if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
#         ):
#             DATA["RELOADING"] = True
#             DATA["LAST_RELOAD"] = time()
#             Thread(target=update_services, args=(True,)).start()
#         else:
#             update_services()

#         DATA["CONFIG_CHANGED"] = True

#     message = ""

#     if request.form["operation"] == "new":
#         message = f"Creating {'draft ' if is_draft else ''}service {variables.get('SERVER_NAME', '').split(' ')[0]}"
#     elif request.form["operation"] == "edit":
#         message = f"Saving configuration for {'draft ' if is_draft else ''}service {old_server_name.split(' ')[0]}"
#     elif request.form["operation"] == "delete":
#         message = f"Deleting {'draft ' if was_draft and is_draft else ''}service {request.form.get('SERVER_NAME', '').split(' ')[0]}"

#     return message
