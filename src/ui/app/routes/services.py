from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from itertools import chain
from os import getenv, sep
from os.path import join
from sys import path as sys_path
from threading import Thread
from time import time
from typing import Dict, List

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for services module")

from flask import Blueprint, redirect, render_template, request, send_file, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DATA, DB

from app.routes.utils import CUSTOM_CONF_RX, handle_error, verify_data_in_form, wait_applying
from app.utils import get_blacklisted_settings

services = Blueprint("services", __name__)


# Display services management page with list of configured services.
# Shows all services including draft and published configurations
# for administration and monitoring purposes.
@services.route("/services", methods=["GET"])
@login_required
def services_page():
    if DEBUG_MODE:
        logger.debug("services_page() called")
    return render_template("services.html", services=DB.get_services(with_drafts=True))


# Redirect trailing slash requests to proper services page.
# Handles URL normalization for consistent routing behavior
# when users access /services/ instead of /services.
@services.route("/services/", methods=["GET"])
@login_required
def services_redirect():
    if DEBUG_MODE:
        logger.debug("services_redirect() called")
    return redirect(url_for("services.services_page"))


# Convert services between draft and published states.
# Processes bulk service conversion requests and manages state
# transitions with proper validation and error handling.
@services.route("/services/convert", methods=["POST"])
@login_required
def services_convert():
    if DEBUG_MODE:
        logger.debug("services_convert() called")
    
    if DB.readonly:
        return handle_error("Database is in read-only mode", "services")

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
        DATA["TO_FLASH"].append({"content": f"Converted to \"{convert_to.title()}\" services: {', '.join(services_to_convert)}", "type": "success"})
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


# Delete selected services from BunkerWeb configuration.
# Handles bulk service deletion with validation and proper cleanup
# of associated configuration settings and custom configs.
@services.route("/services/delete", methods=["POST"])
@login_required
def services_delete():
    if DEBUG_MODE:
        logger.debug("services_delete() called")
    
    if DB.readonly:
        return handle_error("Database is in read-only mode", "services")

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
        DATA["TO_FLASH"].append({"content": f"Deleted service{'s' if len(services_to_delete) > 1 else ''}: {', '.join(services_to_delete)}", "type": "success"})
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


# Handle individual service configuration page and updates.
# Manages service creation, editing, and configuration validation
# with support for both easy and raw configuration modes.
@services.route("/services/<string:service>", methods=["GET", "POST"])
@login_required
def services_service_page(service: str):
    if DEBUG_MODE:
        logger.debug(f"services_service_page() called for service: {service}")
    
    services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(" ")
    service_exists = service in services

    if service != "new" and not service_exists:
        return redirect(url_for("services.services_page"))

    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "services")

        DATA.load_from_file()

        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]

        mode = request.args.get("mode", "easy")

        if mode == "raw":
            server_name = variables.get("SERVER_NAME", variables.get("OLD_SERVER_NAME", "")).split(" ")[0]
            for variable, value in variables.copy().items():
                if variable.endswith("_SERVER_NAME") and variable != "OLD_SERVER_NAME":
                    server_name = value.split(" ")[0]
            for variable in variables.copy():
                if variable.startswith(f"{server_name}_"):
                    variables[variable.replace(f"{server_name}_", "", 1)] = variables.pop(variable)

        is_draft = variables.pop("IS_DRAFT", "no") == "yes"

        def update_service(service: str, variables: Dict[str, str], is_draft: bool, mode: str):
            wait_applying()

            # Edit check fields and remove already existing ones
            if service != "new":
                db_config = DB.get_config(methods=True, with_drafts=True, service=service)
            else:
                db_config = DB.get_config(global_only=True, methods=True)

            was_draft = db_config.get("IS_DRAFT", {"value": "no"})["value"] == "yes"

            old_server_name = variables.pop("OLD_SERVER_NAME", "")
            db_custom_configs = {}
            new_configs = set()
            configs_changed = False

            if mode == "easy":
                db_templates = DB.get_templates()
                db_custom_configs = DB.get_custom_configs(with_drafts=True, as_dict=True)

                for variable, value in variables.copy().items():
                    conf_match = CUSTOM_CONF_RX.match(variable)
                    if conf_match:
                        del variables[variable]
                        key = f"{conf_match['type'].lower()}_{conf_match['name']}"
                        if value == db_templates.get(f"{key}.conf"):
                            if db_custom_configs.pop(f"{service}_{key}", None):
                                configs_changed = True
                            continue
                        value = value.replace("\r\n", "\n").strip().encode("utf-8")

                        new_configs.add(key)
                        db_custom_config = db_custom_configs.get(f"{service}_{key}", {"data": None, "method": "ui"})

                        if db_custom_config["method"] != "ui" and db_custom_config["template"] != variables.get("USE_TEMPLATE", ""):
                            DATA["TO_FLASH"].append(
                                {"content": f"The template Custom config {key} cannot be edited because it has not been created with the UI.", "type": "error"}
                            )
                            continue
                        elif value == db_custom_config["data"].strip():
                            continue

                        configs_changed = True
                        db_custom_configs[f"{service}_{key}"] = {
                            "service_id": variables.get("SERVER_NAME", old_server_name).split(" ")[0],
                            "type": conf_match["type"].lower(),
                            "name": conf_match["name"],
                            "data": value,
                            "method": "ui",
                        }

                for db_custom_config, data in db_custom_configs.copy().items():
                    if data["method"] == "default" and data["template"]:
                        del db_custom_configs[db_custom_config]
                        continue

                    if db_custom_config.startswith(f"{service}_") and db_custom_config.replace(f"{service}_", "", 1) not in new_configs:
                        configs_changed = True
                        del db_custom_configs[db_custom_config]
                        continue
                    db_custom_configs[db_custom_config] = {
                        "service_id": data["service_id"],
                        "type": data["type"],
                        "name": data["name"],
                        "data": data["data"],
                        "method": data["method"],
                    }
                    if "checksum" in data:
                        db_custom_configs[db_custom_config]["checksum"] = data["checksum"]

            variables_to_check = variables.copy()

            for variable, value in variables.items():
                if value == db_config.get(variable, {"value": None})["value"]:
                    del variables_to_check[variable]

            variables = BW_CONFIG.check_variables(variables, db_config, variables_to_check, new=service == "new", threaded=True)

            no_removed_settings = True
            blacklist = get_blacklisted_settings()
            for setting in db_config:
                if setting not in blacklist and setting not in variables:
                    no_removed_settings = False
                    break

            if no_removed_settings and service != "new" and was_draft == is_draft and not variables_to_check and not configs_changed:
                DATA["TO_FLASH"].append(
                    {
                        "content": f"The service {service} was not edited because no values{' or custom configs' if mode == 'easy' else ''} were changed.",
                        "type": "warning",
                    }
                )
                DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                return

            if "SERVER_NAME" not in variables:
                if service == "new":
                    DATA["TO_FLASH"].append({"content": "The service was not created because the server name was not provided.", "type": "error"})
                    DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                    return
                variables["SERVER_NAME"] = old_server_name

            operation = None
            error = None

            if new_configs or configs_changed:
                error = DB.save_custom_configs(db_custom_configs.values(), "ui", changed=service != "new" and (was_draft != is_draft or not is_draft))
                if error:
                    DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {error}", "type": "error"})

            if service == "new":
                old_server_name = variables["SERVER_NAME"]
                operation, error = BW_CONFIG.new_service(variables, is_draft=is_draft)
            else:
                operation, error = BW_CONFIG.edit_service(old_server_name, variables, check_changes=(was_draft != is_draft or not is_draft), is_draft=is_draft)

            if operation.endswith("already exists."):
                DATA["TO_FLASH"].append({"content": operation, "type": "warning"})
                operation = None
            elif not error:
                operation = f"Configuration successfully {'created' if service == 'new' else 'saved'} for service {variables['SERVER_NAME'].split(' ')[0]}."

            if operation:
                if operation.startswith(("Can't", "The database is read-only")):
                    DATA["TO_FLASH"].append({"content": operation, "type": "error"})
                else:
                    DATA["TO_FLASH"].append({"content": operation, "type": "success"})
                    DATA["TO_FLASH"].append({"content": "The Scheduler will be in charge of applying the changes.", "type": "success", "save": False})

            DATA["RELOADING"] = False

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        Thread(target=update_service, args=(service, variables.copy(), is_draft, mode)).start()

        new_service = False
        if service == "new":
            if "SERVER_NAME" not in variables:
                return redirect(url_for("loading", next=url_for("services.services_page")))
            new_service = True
            service = variables["SERVER_NAME"].split(" ")[0]

        arguments = {}
        if mode != "easy":
            arguments["mode"] = mode
        if request.args.get("type", "all") != "all":
            arguments["type"] = request.args["type"]

        return redirect(
            url_for(
                "loading",
                next=(
                    url_for(
                        "services.services_service_page",
                        service=service,
                    )
                    + f"?{'&'.join([f'{k}={v}' for k, v in arguments.items()])}"
                    if new_service or variables.get("SERVER_NAME", "").split(" ")[0] == variables.get("OLD_SERVER_NAME", "").split(" ")[0]
                    else url_for("services.services_page")
                ),
                message=f"{'Saving' if service != 'new' else 'Creating'} configuration for {'draft ' if is_draft else ''}service {service}",
            )
        )

    mode = request.args.get("mode", "easy")
    search_type = request.args.get("type", "all")
    template = request.args.get("template", "low")
    db_templates = DB.get_templates()
    db_custom_configs = DB.get_custom_configs(with_drafts=True, as_dict=True)
    clone = None
    if service == "new":
        clone = request.args.get("clone", "")
        db_config = DB.get_config(global_only=True, methods=True)
        if clone:
            for key, setting in DB.get_config(methods=True, with_drafts=True, service=clone).items():
                original_value = db_config.get(key, {}).get("value")
                db_config[key] = setting | {"clone": original_value != setting.get("value")}
            db_config["SERVER_NAME"].update({"value": "", "clone": False})
    else:
        db_config = DB.get_config(methods=True, with_drafts=True, service=service)

    return render_template(
        "service_settings.html",
        config=db_config,
        templates=db_templates,
        configs=db_custom_configs,
        clone=clone,
        mode=mode,
        type=search_type,
        current_template=template,
    )


# Export selected services configuration as environment file.
# Generates downloadable .env file containing service-specific settings
# for backup, migration, or external configuration management.
@services.route("/services/export", methods=["GET"])
@login_required
def services_service_export():
    if DEBUG_MODE:
        logger.debug("services_service_export() called")
    
    services = request.args.get("services", "").split(",")
    if not services:
        return handle_error("No services selected.", "services", True)

    db_config = BW_CONFIG.get_config(methods=False, with_drafts=True)

    def export_service(service: str) -> List[str]:
        if service not in db_config["SERVER_NAME"].split(" "):
            return [f"# Configuration for {service} not found\n\n"]

        lines = [f"# Configuration for {service}\n"]
        for setting in db_config:
            if setting.startswith(f"{service}_"):
                lines.append(f"{setting}={db_config[setting]}\n")
        lines.append("\n")
        return lines

    with ThreadPoolExecutor() as executor:
        futures = executor.map(export_service, services)
        env_lines = list(chain.from_iterable(futures))

    if not env_lines:
        return handle_error("No services to export.", "services", True)

    env_output = BytesIO("".join(env_lines).encode("utf-8"))
    env_output.seek(0)

    return send_file(env_output, mimetype="text/plain", as_attachment=True, download_name="services_export.env")
