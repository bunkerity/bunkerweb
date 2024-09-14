from re import match
from threading import Thread
from time import time
from typing import Dict, List
from flask import Blueprint, Response, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DATA, DB

from app.routes.utils import handle_error, manage_bunkerweb, verify_data_in_form, wait_applying

services = Blueprint("services", __name__)


@services.route("/services", methods=["GET"])
@login_required
def services_page():
    return render_template("services.html", services=DB.get_services(with_drafts=True))


@services.route("/services/convert", methods=["POST"])
@login_required
def services_convert():
    verify_data_in_form(
        data={"services": None},
        err_message="Missing services parameter on /services/convert.",
        redirect_url="services",
        next=True,
    )
    verify_data_in_form(
        data={"convert_to": None},
        err_message="Missing convert_to parameter on /services/convert.",
        redirect_url="services",
        next=True,
    )

    services = request.form["services"].split(",")
    if not services:
        return handle_error("No services selected.", "services", True)

    convert_to = request.form["convert_to"]
    if convert_to not in ("online", "draft"):
        return handle_error("Invalid convert_to parameter.", "services", True)
    DATA.load_from_file()

    def convert_services(services: List[str], convert_to: str):
        wait_applying()

        db_services = DB.get_services(with_drafts=True)
        services_to_convert = set()
        non_ui_services = set()
        non_convertible_services = set()

        for db_service in db_services:
            if db_service["id"] in services:
                if db_service["method"] != "ui":
                    non_ui_services.add(db_service["id"])
                    continue
                if db_service["is_draft"] == (convert_to == "draft"):
                    non_convertible_services.add(db_service["id"])
                    continue
                services_to_convert.add(db_service["id"])

        for non_ui_service in non_ui_services:
            DATA["TO_FLASH"].append({"content": f"Service {non_ui_service} is not a UI service and will not be converted.", "type": "error"})

        for non_convertible_service in non_convertible_services:
            DATA["TO_FLASH"].append(
                {"content": f"Service {non_convertible_service} is already a {convert_to} service and will not be converted.", "type": "error"}
            )

        if not services_to_convert:
            DATA["TO_FLASH"].append({"content": "All selected services could not be found, are not UI services or are already converted.", "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            return

        db_config = DB.get_config(with_drafts=True)
        for service in services_to_convert:
            db_config[f"{service}_IS_DRAFT"] = "yes" if convert_to == "draft" else "no"

        ret = DB.save_config(db_config, "ui", changed=True)
        if isinstance(ret, str):
            DATA["TO_FLASH"].append({"content": ret, "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            return
        DATA["TO_FLASH"].append({"content": f"Converted services: {', '.join(services_to_convert)}", "type": "success"})
        DATA["RELOADING"] = False

    DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
    Thread(target=convert_services, args=(services, convert_to)).start()

    return redirect(
        url_for(
            "loading",
            next=url_for("services.services_page"),
            message=f"Converting service{'s' if len(services) > 1 else ''} {', '.join(services)} to {convert_to}",
        )
    )


@services.route("/services/delete", methods=["POST"])
@login_required
def services_delete():
    verify_data_in_form(
        data={"services": None},
        err_message="Missing services parameter on /services/delete.",
        redirect_url="services",
        next=True,
    )
    services = request.form["services"].split(",")
    if not services:
        return handle_error("No services selected.", "services", True)
    DATA.load_from_file()

    def delete_services(services: List[str]):
        wait_applying()

        db_config = BW_CONFIG.get_config(methods=False, with_drafts=True)
        db_services = DB.get_services(with_drafts=True)
        all_drafts = True
        services_to_delete = set()
        non_ui_services = set()

        for db_service in db_services:
            if db_service["id"] in services:
                if db_service["method"] != "ui":
                    non_ui_services.add(db_service["id"])
                    continue
                if not db_service["is_draft"]:
                    all_drafts = False
                services_to_delete.add(db_service["id"])

        for non_ui_service in non_ui_services:
            DATA["TO_FLASH"].append({"content": f"Service {non_ui_service} is not a UI service and will not be deleted.", "type": "error"})

        if not services_to_delete:
            DATA["TO_FLASH"].append({"content": "All selected services could not be found or are not UI services.", "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            return

        db_config["SERVER_NAME"] = " ".join([service["id"] for service in db_services if service["id"] not in services_to_delete])
        new_env = db_config.copy()

        for setting in db_config:
            for service in services_to_delete:
                if setting.startswith(f"{service}_"):
                    del new_env[setting]

        ret = BW_CONFIG.gen_conf(new_env, [], check_changes=not all_drafts)
        if isinstance(ret, str):
            DATA["TO_FLASH"].append({"content": ret, "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            return
        DATA["TO_FLASH"].append({"content": f"Deleted services: {', '.join(services_to_delete)}", "type": "success"})
        DATA["RELOADING"] = False

    DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
    Thread(target=delete_services, args=(services,)).start()

    return redirect(
        url_for(
            "loading",
            next=url_for("services.services_page"),
            message=f"Deleting service{'s' if len(services) > 1 else ''} {', '.join(services)}",
        )
    )


@services.route("/services/<string:service>", methods=["GET", "POST"])
@login_required
def services_service_page(service: str):
    services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME"))["SERVER_NAME"].split(" ")
    service_exists = service in services

    if service != "new" and not service_exists:
        return Response("Service not found", status=404)

    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "services")
        DATA.load_from_file()

        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]

        mode = request.args.get("mode", "easy")
        is_draft = variables.pop("IS_DRAFT", "no") == "yes"

        def update_service(service: str, variables: Dict[str, str], is_draft: bool, mode: str):  # TODO: handle easy mode
            wait_applying()

            # Edit check fields and remove already existing ones
            if service != "new":
                config = DB.get_config(methods=True, with_drafts=True, filtered_settings=list(variables.keys()), service=service)
            else:
                config = DB.get_config(global_only=True, methods=True, filtered_settings=list(variables.keys()))
            was_draft = config.get("IS_DRAFT", {"value": "no"})["value"] == "yes"

            old_server_name = variables.pop("OLD_SERVER_NAME", "")
            ignored_multiples = set()

            # Edit check fields and remove already existing ones
            if mode != "easy":
                for variable, value in variables.copy().items():
                    if (mode == "raw" or variable != "SERVER_NAME") and value == config.get(variable, {"value": None})["value"]:
                        if match(r"^.+_\d+$", variable):
                            ignored_multiples.add(variable)
                        del variables[variable]

            variables = BW_CONFIG.check_variables(variables, config, ignored_multiples=ignored_multiples, new=service == "new", threaded=True)

            if service != "new" and was_draft == is_draft and not variables:
                content = f"The service {service} was not edited because no values were changed."
                DATA["TO_FLASH"].append({"content": content, "type": "warning"})
                DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                return

            if "SERVER_NAME" not in variables:
                if service == "new":
                    DATA["TO_FLASH"].append({"content": "The service was not created because the server name was not provided.", "type": "error"})
                    DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                    return
                variables["SERVER_NAME"] = old_server_name

            if service == "new":
                old_server_name = variables["SERVER_NAME"]

            manage_bunkerweb(
                "services",
                variables,
                old_server_name,
                operation="edit" if service != "new" else "new",
                is_draft=is_draft,
                was_draft=was_draft,
                threaded=True,
            )

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        Thread(target=update_service, args=(service, variables, is_draft, mode)).start()

        if service == "new":
            service = variables["SERVER_NAME"].split(" ")[0]

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
                message=f"{'Saving' if service != 'new' else 'Creating'} configuration for {'draft ' if is_draft else ''}service {service}",
            )
        )

    mode = request.args.get("mode", "easy")
    search_type = request.args.get("type", "all")
    template = request.args.get("template", "high")
    db_templates = DB.get_templates()
    if service == "new":
        clone = request.args.get("clone", "")
        if clone:
            db_config = DB.get_config(methods=True, with_drafts=True, service=clone)
            db_config["SERVER_NAME"]["value"] = ""
            return render_template(
                "service_settings.html",
                config=db_config,
                templates=db_templates,
                mode=mode,
                type=search_type,
                current_template=template,
            )

        db_config = DB.get_config(global_only=True, methods=True)
        return render_template(
            "service_settings.html",
            config=db_config,
            templates=db_templates,
            mode=mode,
            type=search_type,
            current_template=template,
        )

    db_config = DB.get_config(methods=True, with_drafts=True, service=service)
    return render_template(
        "service_settings.html",
        config=db_config,
        templates=db_templates,
        mode=mode,
        type=search_type,
        current_template=template,
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
