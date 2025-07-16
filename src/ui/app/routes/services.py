from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from itertools import chain
from os import sep
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

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-services",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-services")

from flask import Blueprint, redirect, render_template, request, send_file, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DATA, DB

from app.routes.utils import CUSTOM_CONF_RX, handle_error, verify_data_in_form, wait_applying
from app.utils import get_blacklisted_settings

services = Blueprint("services", __name__)


@services.route("/services", methods=["GET"])
@login_required
def services_page():
    return render_template("services.html", services=DB.get_services(with_drafts=True))


@services.route("/services/", methods=["GET"])
@login_required
def services_redirect():
    return redirect(url_for("services.services_page"))


@services.route("/services/convert", methods=["POST"])
@login_required
def services_convert():
    logger.debug("Services convert endpoint called")
    if DB.readonly:
        logger.debug("Database is in read-only mode, returning error")
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
    logger.debug(f"Converting services: {services}")
    if not services:
        return handle_error("No services selected.", "services", True)

    convert_to = request.form["convert_to"]
    logger.debug(f"Converting to: {convert_to}")
    if convert_to not in ("online", "draft"):
        return handle_error("Invalid convert_to parameter.", "services", True)
    DATA.load_from_file()

    def convert_services(services: List[str], convert_to: str):
        logger.debug(f"Starting conversion of {len(services)} services to {convert_to}")
        wait_applying()

        db_services = DB.get_services(with_drafts=True)
        logger.debug(f"Found {len(db_services)} services in database")
        services_to_convert = set()
        non_ui_services = set()
        non_convertible_services = set()

        for db_service in db_services:
            if db_service["id"] in services:
                logger.debug(f"Processing service {db_service['id']}: method={db_service['method']}, is_draft={db_service.get('is_draft', False)}")
                if db_service["method"] != "ui":
                    non_ui_services.add(db_service["id"])
                    continue
                if db_service["is_draft"] == (convert_to == "draft"):
                    non_convertible_services.add(db_service["id"])
                    continue
                services_to_convert.add(db_service["id"])

        logger.debug(f"Services to convert: {services_to_convert}")
        logger.debug(f"Non-UI services: {non_ui_services}")
        logger.debug(f"Non-convertible services: {non_convertible_services}")

        for non_ui_service in non_ui_services:
            DATA["TO_FLASH"].append({"content": f"Service {non_ui_service} is not a UI service and will not be converted.", "type": "error"})

        for non_convertible_service in non_convertible_services:
            DATA["TO_FLASH"].append(
                {"content": f"Service {non_convertible_service} is already a {convert_to} service and will not be converted.", "type": "error"}
            )

        if not services_to_convert:
            logger.debug("No services to convert, returning early")
            DATA["TO_FLASH"].append({"content": "All selected services could not be found, are not UI services or are already converted.", "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            return

        db_config = DB.get_config(with_drafts=True)
        for service in services_to_convert:
            db_config[f"{service}_IS_DRAFT"] = "yes" if convert_to == "draft" else "no"
            logger.debug(f"Set {service}_IS_DRAFT to {'yes' if convert_to == 'draft' else 'no'}")

        logger.debug("Saving configuration changes")
        ret = DB.save_config(db_config, "ui", changed=True)
        if isinstance(ret, str):
            logger.error(f"Failed to save config: {ret}")
            DATA["TO_FLASH"].append({"content": ret, "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            return
        logger.debug("Configuration saved successfully")
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


@services.route("/services/delete", methods=["POST"])
@login_required
def services_delete():
    logger.debug("Services delete endpoint called")
    if DB.readonly:
        logger.debug("Database is in read-only mode, returning error")
        return handle_error("Database is in read-only mode", "services")

    verify_data_in_form(
        data={"services": None},
        err_message="Missing services parameter on /services/delete.",
        redirect_url="services",
        next=True,
    )
    services = request.form["services"].split(",")
    logger.debug(f"Deleting services: {services}")
    if not services:
        return handle_error("No services selected.", "services", True)
    DATA.load_from_file()

    def delete_services(services: List[str]):
        logger.debug(f"Starting deletion of {len(services)} services")
        wait_applying()

        db_config = BW_CONFIG.get_config(methods=False, with_drafts=True)
        db_services = DB.get_services(with_drafts=True)
        logger.debug(f"Found {len(db_services)} services in database")
        all_drafts = True
        services_to_delete = set()
        non_ui_services = set()

        for db_service in db_services:
            if db_service["id"] in services:
                logger.debug(f"Processing service {db_service['id']}: method={db_service['method']}, is_draft={db_service.get('is_draft', False)}")
                if db_service["method"] != "ui":
                    non_ui_services.add(db_service["id"])
                    continue
                if not db_service["is_draft"]:
                    all_drafts = False
                services_to_delete.add(db_service["id"])

        logger.debug(f"Services to delete: {services_to_delete}")
        logger.debug(f"Non-UI services: {non_ui_services}")
        logger.debug(f"All drafts: {all_drafts}")

        for non_ui_service in non_ui_services:
            DATA["TO_FLASH"].append({"content": f"Service {non_ui_service} is not a UI service and will not be deleted.", "type": "error"})

        if not services_to_delete:
            logger.debug("No services to delete, returning early")
            DATA["TO_FLASH"].append({"content": "All selected services could not be found or are not UI services.", "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            return

        logger.debug("Updating SERVER_NAME configuration")
        db_config["SERVER_NAME"] = " ".join([service["id"] for service in db_services if service["id"] not in services_to_delete])
        new_env = db_config.copy()

        settings_removed = 0
        for setting in db_config:
            for service in services_to_delete:
                if setting.startswith(f"{service}_"):
                    del new_env[setting]
                    settings_removed += 1
        
        logger.debug(f"Removed {settings_removed} service-specific settings")

        logger.debug(f"Generating configuration with check_changes={not all_drafts}")
        ret = BW_CONFIG.gen_conf(new_env, [], check_changes=not all_drafts)
        if isinstance(ret, str):
            logger.error(f"Failed to generate config: {ret}")
            DATA["TO_FLASH"].append({"content": ret, "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            return
        logger.debug("Configuration generated successfully")
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


@services.route("/services/<string:service>", methods=["GET", "POST"])
@login_required
def services_service_page(service: str):
    logger.debug(f"Service page accessed for service: {service}")
    services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(" ")
    service_exists = service in services
    logger.debug(f"Service exists: {service_exists}, available services: {len(services)}")

    if service != "new" and not service_exists:
        logger.debug(f"Service {service} not found, redirecting to services page")
        return redirect(url_for("services.services_page"))

    if request.method == "POST":
        logger.debug(f"POST request for service {service}")
        if DB.readonly:
            logger.debug("Database is in read-only mode, returning error")
            return handle_error("Database is in read-only mode", "services")

        DATA.load_from_file()

        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]
        logger.debug(f"Processing {len(variables)} form variables")

        mode = request.args.get("mode", "easy")
        logger.debug(f"Service mode: {mode}")

        if mode == "raw":
            logger.debug("Processing raw mode variables")
            server_name = variables.get("SERVER_NAME", variables.get("OLD_SERVER_NAME", "")).split(" ")[0]
            for variable, value in variables.copy().items():
                if variable.endswith("_SERVER_NAME") and variable != "OLD_SERVER_NAME":
                    server_name = value.split(" ")[0]
            for variable in variables.copy():
                if variable.startswith(f"{server_name}_"):
                    variables[variable.replace(f"{server_name}_", "", 1)] = variables.pop(variable)

        is_draft = variables.pop("IS_DRAFT", "no") == "yes"
        logger.debug(f"Service is_draft: {is_draft}")

        def update_service(service: str, variables: Dict[str, str], is_draft: bool, mode: str):
            logger.debug(f"Starting service update for {service} with {len(variables)} variables")
            wait_applying()

            # Edit check fields and remove already existing ones
            if service != "new":
                db_config = DB.get_config(methods=True, with_drafts=True, service=service)
                logger.debug(f"Loaded existing config for service {service} with {len(db_config)} settings")
            else:
                db_config = DB.get_config(global_only=True, methods=True)
                logger.debug(f"Loaded global config for new service with {len(db_config)} settings")

            was_draft = db_config.get("IS_DRAFT", {"value": "no"})["value"] == "yes"
            logger.debug(f"Service was_draft: {was_draft}")

            old_server_name = variables.pop("OLD_SERVER_NAME", "")
            db_custom_configs = {}
            new_configs = set()
            configs_changed = False

            if mode == "easy":
                logger.debug("Processing easy mode with custom configs")
                db_templates = DB.get_templates()
                db_custom_configs = DB.get_custom_configs(with_drafts=True, as_dict=True)
                logger.debug(f"Loaded {len(db_templates)} templates and {len(db_custom_configs)} custom configs")

                for variable, value in variables.copy().items():
                    conf_match = CUSTOM_CONF_RX.match(variable)
                    if conf_match:
                        del variables[variable]
                        key = f"{conf_match['type'].lower()}_{conf_match['name']}"
                        logger.debug(f"Processing custom config: {key}")
                        if value == db_templates.get(f"{key}.conf"):
                            if db_custom_configs.pop(f"{service}_{key}", None):
                                configs_changed = True
                                logger.debug(f"Removed custom config {key}")
                            continue
                        value = value.replace("\r\n", "\n").strip().encode("utf-8")

                        new_configs.add(key)
                        db_custom_config = db_custom_configs.get(f"{service}_{key}", {"data": None, "method": "ui"})

                        if db_custom_config["method"] != "ui" and db_custom_config["template"] != variables.get("USE_TEMPLATE", ""):
                            logger.debug(f"Skipping non-UI custom config {key}")
                            DATA["TO_FLASH"].append(
                                {"content": f"The template Custom config {key} cannot be edited because it has not been created with the UI.", "type": "error"}
                            )
                            continue
                        elif value == db_custom_config["data"].strip():
                            logger.debug(f"Custom config {key} unchanged")
                            continue

                        configs_changed = True
                        logger.debug(f"Custom config {key} changed")
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
                        logger.debug(f"Removing obsolete custom config {db_custom_config}")
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

            logger.debug(f"Variables to check: {len(variables_to_check)}")
            variables = BW_CONFIG.check_variables(variables, db_config, variables_to_check, new=service == "new", threaded=True)
            logger.debug(f"Variables after check: {len(variables)}")

            no_removed_settings = True
            blacklist = get_blacklisted_settings()
            for setting in db_config:
                if setting not in blacklist and setting not in variables:
                    no_removed_settings = False
                    break

            logger.debug(f"No removed settings: {no_removed_settings}, configs changed: {configs_changed}")

            if no_removed_settings and service != "new" and was_draft == is_draft and not variables_to_check and not configs_changed:
                logger.debug("No changes detected, returning early")
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
                    logger.debug("New service missing SERVER_NAME")
                    DATA["TO_FLASH"].append({"content": "The service was not created because the server name was not provided.", "type": "error"})
                    DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                    return
                variables["SERVER_NAME"] = old_server_name

            operation = None
            error = None

            if new_configs or configs_changed:
                logger.debug(f"Saving {len(db_custom_configs)} custom configs")
                error = DB.save_custom_configs(db_custom_configs.values(), "ui", changed=service != "new" and (was_draft != is_draft or not is_draft))
                if error:
                    logger.error(f"Failed to save custom configs: {error}")
                    DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {error}", "type": "error"})

            if service == "new":
                logger.debug("Creating new service")
                old_server_name = variables["SERVER_NAME"]
                operation, error = BW_CONFIG.new_service(variables, is_draft=is_draft)
            else:
                logger.debug("Editing existing service")
                operation, error = BW_CONFIG.edit_service(old_server_name, variables, check_changes=(was_draft != is_draft or not is_draft), is_draft=is_draft)

            logger.debug(f"Service operation result: operation='{operation}', error={error}")

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
            logger.debug("Service update completed")

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


@services.route("/services/export", methods=["GET"])
@login_required
def services_service_export():
    logger.debug("Services export endpoint called")
    services = request.args.get("services", "").split(",")
    logger.debug(f"Exporting services: {services}")
    if not services:
        return handle_error("No services selected.", "services", True)

    db_config = BW_CONFIG.get_config(methods=False, with_drafts=True)
    logger.debug(f"Loaded configuration with {len(db_config)} settings")

    def export_service(service: str) -> List[str]:
        logger.debug(f"Exporting service: {service}")
        if service not in db_config["SERVER_NAME"].split(" "):
            logger.debug(f"Service {service} not found in configuration")
            return [f"# Configuration for {service} not found\n\n"]

        lines = [f"# Configuration for {service}\n"]
        service_settings = 0
        for setting in db_config:
            if setting.startswith(f"{service}_"):
                lines.append(f"{setting}={db_config[setting]}\n")
                service_settings += 1
        lines.append("\n")
        logger.debug(f"Exported {service_settings} settings for service {service}")
        return lines

    logger.debug("Starting parallel export of services")
    with ThreadPoolExecutor() as executor:
        futures = executor.map(export_service, services)
        env_lines = list(chain.from_iterable(futures))

    logger.debug(f"Generated {len(env_lines)} total lines for export")
    if not env_lines:
        return handle_error("No services to export.", "services", True)

    env_output = BytesIO("".join(env_lines).encode("utf-8"))
    env_output.seek(0)
    logger.debug("Export file generated successfully")

    return send_file(env_output, mimetype="text/plain", as_attachment=True, download_name="services_export.env")
