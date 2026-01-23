from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from itertools import chain
from time import time
from typing import Dict, List, Tuple
from flask import Blueprint, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from regex import sub

from app.dependencies import BW_CONFIG, CONFIG_TASKS_EXECUTOR, DATA, DB

from app.routes.utils import CUSTOM_CONF_RX, handle_error, verify_data_in_form, wait_applying
from app.utils import LOGGER, get_blacklisted_settings, is_editable_method

services = Blueprint("services", __name__)


def parse_services_export(content: str) -> Tuple[Dict[str, Dict[str, str]], List[str]]:
    services_map: Dict[str, Dict[str, str]] = {}
    errors: List[str] = []

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            errors.append(f"Line {line_number} is not a valid key/value pair.")
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if "_" not in key:
            errors.append(f"Line {line_number} is missing a service prefix.")
            continue
        service_id, setting = key.split("_", 1)
        if not service_id or not setting:
            errors.append(f"Line {line_number} has an invalid key: {key}.")
            continue
        services_map.setdefault(service_id, {})[setting] = value

    return services_map, errors


@services.route("/services", methods=["GET"])
@login_required
def services_page():
    return render_template("services.html", services=DB.get_services(with_drafts=True), templates=DB.get_templates())


@services.route("/services/", methods=["GET"])
@login_required
def services_redirect():
    return redirect(url_for("services.services_page"))


@services.route("/services/convert", methods=["POST"])
@login_required
def services_convert():
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
    CONFIG_TASKS_EXECUTOR.submit(convert_services, services, convert_to)

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
    CONFIG_TASKS_EXECUTOR.submit(delete_services, services)

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
    services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split()
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
        clone = request.args.get("clone", "")

        if mode == "raw":
            server_name = variables.get("SERVER_NAME", variables.get("OLD_SERVER_NAME", "")).split(" ")[0]
            for variable, value in variables.copy().items():
                if variable.endswith("_SERVER_NAME") and variable != "OLD_SERVER_NAME":
                    server_name = value.split(" ")[0]
            for variable in variables.copy():
                if variable.startswith(f"{server_name}_"):
                    variables[variable.replace(f"{server_name}_", "", 1)] = variables.pop(variable)

        is_draft = variables.pop("IS_DRAFT", "no") == "yes"

        def update_service(service: str, variables: Dict[str, str], is_draft: bool, mode: str, clone: str):
            wait_applying()

            if clone and service == "new":
                cloned_service_config = {k: v for k, v in DB.get_config(methods=False, with_drafts=True, service=clone).items()}

                for key, value in cloned_service_config.items():
                    if key in variables or key in ("SERVER_NAME", "OLD_SERVER_NAME", "IS_DRAFT", "USE_UI"):
                        continue

                    variables[key] = value

            # Edit check fields and remove already existing ones
            if service != "new":
                db_config = DB.get_config(methods=True, with_drafts=True, service=service)
            else:
                db_config = DB.get_config(global_only=True, methods=True)

            service_method = db_config.get("SERVER_NAME", {}).get("method", "ui") if service != "new" else "ui"
            override_method = service_method if is_editable_method(service_method) else "ui"

            was_draft = db_config.get("IS_DRAFT", {"value": "no"})["value"] == "yes"

            old_server_name = variables.pop("OLD_SERVER_NAME", "")
            db_custom_configs = {}
            all_custom_configs = DB.get_custom_configs(with_drafts=True, as_dict=True)
            removed_custom_configs: set[str] = set()
            new_configs = set()
            configs_changed = False

            if mode == "easy":
                db_templates = DB.get_templates()
                db_custom_configs = all_custom_configs.copy()

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
                        db_custom_config = db_custom_configs.get(f"{service}_{key}", {"data": None, "method": override_method, "is_draft": False})

                        if not is_editable_method(db_custom_config["method"]) and db_custom_config["template"] != variables.get("USE_TEMPLATE", ""):
                            DATA["TO_FLASH"].append(
                                {
                                    "content": (
                                        f"The template Custom config {key} cannot be edited because it has been created via the {db_custom_config['method']} method."
                                    ),
                                    "type": "error",
                                }
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
                            "method": override_method,
                            "is_draft": db_custom_config.get("is_draft", False),
                        }

                if service != "new":
                    for setting, value in db_config.items():
                        if setting not in variables:
                            variables[setting] = value["value"]

                for db_custom_config, data in db_custom_configs.copy().items():
                    if data["method"] == "default" and data["template"]:
                        LOGGER.debug(f"Removing default custom config {db_custom_config} because it is not used anymore.")
                        removed_custom_configs.add(db_custom_config)
                        del db_custom_configs[db_custom_config]
                        continue

                    if db_custom_config.startswith(f"{service}_") and db_custom_config.replace(f"{service}_", "", 1) not in new_configs and data["template"]:
                        LOGGER.debug(f"Removing custom config {db_custom_config} because it is not used anymore.")
                        configs_changed = True
                        removed_custom_configs.add(db_custom_config)
                        del db_custom_configs[db_custom_config]
                        continue

                    db_custom_configs[db_custom_config] = {
                        "service_id": data["service_id"],
                        "type": data["type"],
                        "name": data["name"],
                        "data": data["data"],
                        "method": data["method"],
                        "is_draft": data.get("is_draft", False),
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

            # Build the final custom config map taking into account removals and additions
            new_server_name = variables.get("SERVER_NAME", "").split(" ")[0]
            old_server_name_splitted = old_server_name.split()
            old_server_id = old_server_name_splitted[0] if old_server_name_splitted and old_server_name_splitted[0] else service
            renamed_service = service != "new" and new_server_name and new_server_name != old_server_id

            final_custom_configs: dict[str, dict] = {}
            for key, data in all_custom_configs.items():
                if key in removed_custom_configs:
                    continue

                # If this config belongs to the service being renamed, rewrite it
                if renamed_service and key.startswith(f"{old_server_id}_"):
                    new_key = key.replace(f"{old_server_id}_", f"{new_server_name}_", 1)
                    final_custom_configs[new_key] = data | {"service_id": new_server_name}
                    configs_changed = True
                    continue

                final_custom_configs[key] = data

            # Apply changes from the current edit session (db_custom_configs overrides base)
            for key, data in db_custom_configs.items():
                target_key = key
                target_data = data
                if renamed_service and key.startswith(f"{service}_"):
                    target_key = key.replace(f"{service}_", f"{new_server_name}_", 1)
                    target_data = data | {"service_id": new_server_name}
                    configs_changed = True
                final_custom_configs[target_key] = target_data

            if service == "new":
                old_server_name = variables["SERVER_NAME"]
                operation, error = BW_CONFIG.new_service(variables, is_draft=is_draft, override_method=override_method)
            else:
                operation, error = BW_CONFIG.edit_service(
                    old_server_name,
                    variables,
                    check_changes=(was_draft != is_draft or not is_draft),
                    is_draft=is_draft,
                    override_method=override_method,
                )

            # Save custom configs after the service edit so the new service id exists
            if new_configs or configs_changed:
                if renamed_service:
                    # Use per-config upsert to avoid bulk delete when renaming services
                    for custom_config in final_custom_configs.values():
                        custom_conf_data = {
                            "service_id": custom_config.get("service_id"),
                            "type": custom_config.get("type"),
                            "name": custom_config.get("name"),
                            "data": custom_config.get("data"),
                            "checksum": custom_config.get("checksum"),
                            "method": custom_config.get("method"),
                        }
                        error = DB.upsert_custom_config(
                            custom_conf_data["type"],
                            custom_conf_data["name"],
                            custom_conf_data,
                            service_id=custom_conf_data["service_id"],
                        )
                        if error:
                            DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {error}", "type": "error"})
                            break
                else:
                    error = DB.save_custom_configs(
                        final_custom_configs.values(),
                        override_method,
                        changed=service != "new" and (was_draft != is_draft or not is_draft),
                    )
                    if error:
                        DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {error}", "type": "error"})

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
        CONFIG_TASKS_EXECUTOR.submit(update_service, service, variables.copy(), is_draft, mode, clone)

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
    used_dom_ids = set()

    for template_id, template_data in db_templates.items():
        dom_id = sub(r"[^0-9A-Za-z_-]+", "-", template_id).strip("-")
        if not dom_id:
            dom_id = "template"

        base_dom_id = dom_id
        suffix = 2
        while dom_id in used_dom_ids:
            dom_id = f"{base_dom_id}-{suffix}"
            suffix += 1

        used_dom_ids.add(dom_id)
        template_data["dom_id"] = dom_id

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
            db_config["USE_UI"].update({"value": "no", "clone": False})
            for key, value in DB.get_custom_configs(with_drafts=True, as_dict=True).items():
                if key.startswith(f"{clone}_"):
                    db_custom_configs[key.replace(f"{clone}_", f"{service}_", 1)] = value
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
    services = request.args.get("services", "").split(",")
    if not services:
        return handle_error("No services selected.", "services", True)

    db_config = BW_CONFIG.get_config(methods=False, with_drafts=True)

    def export_service(service: str) -> List[str]:
        if service not in db_config["SERVER_NAME"].split():
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


@services.route("/services/import", methods=["POST"])
@login_required
def services_service_import():
    if DB.readonly:
        return handle_error("Database is in read-only mode", "services")

    services_file = request.files.get("services_file")
    if not services_file or not services_file.filename:
        return handle_error("No services file uploaded.", "services", True)

    try:
        content = services_file.read().decode("utf-8")
    except UnicodeDecodeError:
        return handle_error("Invalid file encoding. Please upload a UTF-8 file.", "services", True)

    services_map, parse_errors = parse_services_export(content)
    if not services_map:
        return handle_error("No services found in the import file.", "services", True)

    DATA.load_from_file()

    def import_services(services_map: Dict[str, Dict[str, str]], parse_errors: List[str]):
        wait_applying()

        for error in parse_errors:
            DATA["TO_FLASH"].append({"content": f"Import warning: {error}", "type": "error"})

        existing_services = {service["id"] for service in DB.get_services(with_drafts=True)}
        base_config = DB.get_config(global_only=True, methods=True)
        created = []
        skipped = []
        failed = []

        for service_id, variables in services_map.items():
            service_variables = variables.copy()
            is_draft = service_variables.pop("IS_DRAFT", "no") == "yes"

            if service_id in existing_services:
                skipped.append(service_id)
                continue

            server_name = service_variables.get("SERVER_NAME", "").strip()
            if not server_name:
                failed.append(f"{service_id} (missing SERVER_NAME)")
                continue

            service_variables = BW_CONFIG.check_variables(service_variables, base_config, service_variables.copy(), new=True, threaded=True)
            server_name = service_variables.get("SERVER_NAME", "").strip()
            if not server_name:
                failed.append(f"{service_id} (invalid SERVER_NAME)")
                continue

            operation, error = BW_CONFIG.new_service(service_variables, is_draft=is_draft, override_method="ui", check_changes=not is_draft)
            if error:
                failed.append(service_id)
                DATA["TO_FLASH"].append({"content": operation, "type": "error"})
                continue

            created.append(server_name.split(" ")[0])

        if created:
            DATA["TO_FLASH"].append({"content": f"Imported service{'s' if len(created) > 1 else ''}: {', '.join(created)}", "type": "success"})
        if skipped:
            DATA["TO_FLASH"].append({"content": f"Skipped existing service{'s' if len(skipped) > 1 else ''}: {', '.join(skipped)}", "type": "warning"})
        if failed:
            DATA["TO_FLASH"].append({"content": f"Failed to import service{'s' if len(failed) > 1 else ''}: {', '.join(failed)}", "type": "error"})

        DATA.update({"RELOADING": False, "CONFIG_CHANGED": bool(created)})

    DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
    CONFIG_TASKS_EXECUTOR.submit(import_services, services_map, parse_errors)

    return redirect(
        url_for(
            "loading",
            next=url_for("services.services_page"),
            message="Importing services",
        )
    )
