import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from itertools import chain
from json import dumps
from time import time
from typing import Dict, List, Optional, Tuple
from flask import Blueprint, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from regex import sub

from app.dependencies import BW_CONFIG, CONFIG_TASKS_EXECUTOR, DATA, DB

from app.routes.configs import EXPORT_FORMAT_VERSION, apply_imported_configs, flash_import_results, parse_configs_export
from app.routes.utils import CUSTOM_CONF_RX, extract_file_setting_names, handle_error, verify_data_in_form, wait_applying
from app.utils import LOGGER, can_delete_service, get_blacklisted_settings, is_editable_method, is_ui_api_method

services = Blueprint("services", __name__)

ZIP_ALLOWED_MEMBERS = frozenset({"services_export.env", "configs_export.json"})
ZIP_MAX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024  # 20 MB aggregate cap guards against zip bombs.


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
    services_with_configs = sorted(
        {
            config["service_id"]
            for config in DB.get_custom_configs(with_drafts=True, with_data=False)
            if config.get("service_id") and not config.get("template") and is_editable_method(config.get("method"))
        }
    )
    return render_template(
        "services.html",
        services=DB.get_services(with_drafts=True),
        templates=DB.get_templates(),
        services_with_configs=services_with_configs,
    )


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
        non_editable_services = set()
        non_convertible_services = set()

        for db_service in db_services:
            if db_service["id"] in services:
                if not is_ui_api_method(db_service["method"]):
                    non_editable_services.add(db_service["id"])
                    continue
                if db_service["is_draft"] == (convert_to == "draft"):
                    non_convertible_services.add(db_service["id"])
                    continue
                services_to_convert.add(db_service["id"])

        for non_editable_service in non_editable_services:
            DATA["TO_FLASH"].append({"content": f"Service {non_editable_service} is not a UI/API service and will not be converted.", "type": "error"})

        for non_convertible_service in non_convertible_services:
            DATA["TO_FLASH"].append(
                {"content": f"Service {non_convertible_service} is already a {convert_to} service and will not be converted.", "type": "error"}
            )

        if not services_to_convert:
            DATA["TO_FLASH"].append({"content": "All selected services could not be found, are not UI/API services or are already converted.", "type": "error"})
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
        # Drafted autoconf services are deleted directly against the DB — save_config(method="ui")
        # would otherwise ignore them (method mismatch) and leave the rows untouched.
        autoconf_drafts_to_delete = set()
        non_deletable_services = set()

        non_deletable_reasons: Dict[str, str] = {}
        for db_service in db_services:
            if db_service["id"] in services:
                if not can_delete_service(db_service):
                    non_deletable_services.add(db_service["id"])
                    if db_service["method"] == "autoconf":
                        non_deletable_reasons[db_service["id"]] = "online autoconf service (convert it to draft first)"
                    else:
                        non_deletable_reasons[db_service["id"]] = "not a UI/API service"
                    continue
                if not db_service["is_draft"]:
                    all_drafts = False
                services_to_delete.add(db_service["id"])
                if db_service["method"] == "autoconf" and db_service["is_draft"]:
                    autoconf_drafts_to_delete.add(db_service["id"])

        for non_deletable_service in non_deletable_services:
            reason = non_deletable_reasons.get(non_deletable_service, "not a UI/API service")
            DATA["TO_FLASH"].append({"content": f"Service {non_deletable_service} is {reason} and will not be deleted.", "type": "error"})

        if not services_to_delete:
            DATA["TO_FLASH"].append({"content": "All selected services could not be found or are not UI/API services.", "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            return

        if autoconf_drafts_to_delete:
            err = DB.delete_services(list(autoconf_drafts_to_delete))
            if err:
                DATA["TO_FLASH"].append({"content": f"Failed to delete drafted autoconf services: {err}", "type": "error"})
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
        file_setting_names = extract_file_setting_names(variables)

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

        def update_service(service: str, variables: Dict[str, str], is_draft: bool, mode: str, clone: str, file_setting_names: Dict[str, str]):
            wait_applying()

            if clone and service == "new":
                cloned_service_config = {k: v for k, v in DB.get_config(methods=False, with_drafts=True, service=clone).items()}
                clone_prefix = f"{clone}_"

                for key, value in cloned_service_config.items():
                    # Strip the clone service prefix from keys so they are recognized as valid setting names
                    stripped_key = key.removeprefix(clone_prefix)
                    if stripped_key in variables or stripped_key in ("SERVER_NAME", "OLD_SERVER_NAME", "IS_DRAFT", "USE_UI"):
                        continue

                    variables[stripped_key] = value

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

            for db_custom_config, data in all_custom_configs.items():
                if data.get("method") == "default" and data.get("template"):
                    removed_custom_configs.add(db_custom_config)

            # Defense-in-depth: in advanced/raw modes the form may omit keys (multi-value
            # rebuild dropping a suffix, conditional Jinja branch, plugin tab not in DOM,
            # JS race). Without this restoration the cleanup pass in Database.save_config
            # would delete the corresponding DB rows. Only restore values whose method is
            # NOT editable from the UI — legitimate user clears of a ui-method setting
            # still go through (the form rebuild posts an empty value, not absence).
            # Skip transient/form-managed keys plus the existing blacklist.
            restore_skip = get_blacklisted_settings() | {"SERVER_NAME", "OLD_SERVER_NAME", "USE_TEMPLATE", "USE_UI"}
            if service != "new" and mode != "easy":
                old_template = db_config.get("USE_TEMPLATE", {}).get("value", "")
                new_template = variables.get("USE_TEMPLATE", "")
                template_unchanged = old_template == new_template
                for setting, value in db_config.items():
                    if setting in variables or setting in restore_skip:
                        continue
                    setting_method = value.get("method")
                    if not is_editable_method(setting_method, allow_default=False):
                        # Don't carry old-template defaults forward when switching templates.
                        if setting_method == "default" and value.get("template") and not template_unchanged:
                            continue
                        variables[setting] = value["value"]

            variables_to_check = variables.copy()
            has_file_name_changes = False

            for variable, value in variables.items():
                if value == db_config.get(variable, {"value": None})["value"]:
                    del variables_to_check[variable]

            for setting_name, file_name in file_setting_names.items():
                current_file_name = str(db_config.get(setting_name, {}).get("file_name", "") or "").strip()
                if file_name != current_file_name:
                    has_file_name_changes = True
                    break

            variables = BW_CONFIG.check_variables(variables, db_config, variables_to_check, new=service == "new", threaded=True)

            no_removed_settings = True
            blacklist = get_blacklisted_settings()
            for setting in db_config:
                if setting not in blacklist and setting not in variables:
                    no_removed_settings = False
                    break

            if (
                no_removed_settings
                and service != "new"
                and was_draft == is_draft
                and not variables_to_check
                and not configs_changed
                and not has_file_name_changes
            ):
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
                operation, error = BW_CONFIG.new_service(variables, is_draft=is_draft, override_method=override_method, file_name_map=file_setting_names)
            else:
                operation, error = BW_CONFIG.edit_service(
                    old_server_name,
                    variables,
                    check_changes=(was_draft != is_draft or not is_draft),
                    is_draft=is_draft,
                    override_method=override_method,
                    file_name_map=file_setting_names,
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
        CONFIG_TASKS_EXECUTOR.submit(update_service, service, variables.copy(), is_draft, mode, clone, file_setting_names)

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

    include_configs = request.args.get("include_configs", "").lower() in ("1", "yes", "true", "on")

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

    env_bytes = "".join(env_lines).encode("utf-8")

    if not include_configs:
        return send_file(BytesIO(env_bytes), mimetype="text/plain", as_attachment=True, download_name="services_export.env")

    selected_services = {service for service in services if service}
    db_configs = DB.get_custom_configs(with_drafts=True, with_data=True)
    configs_payload: List[Dict] = []
    for db_config_row in db_configs:
        if db_config_row.get("template"):
            continue
        service_id = db_config_row.get("service_id") or None
        if service_id not in selected_services:
            continue
        raw_data = db_config_row.get("data", b"") or b""
        if isinstance(raw_data, bytes):
            try:
                data_str = raw_data.decode("utf-8")
            except UnicodeDecodeError:
                data_str = raw_data.decode("utf-8", errors="replace")
        else:
            data_str = str(raw_data)
        configs_payload.append(
            {
                "service_id": service_id,
                "type": db_config_row["type"],
                "name": db_config_row["name"],
                "data": data_str,
                "is_draft": bool(db_config_row.get("is_draft", False)),
            }
        )

    configs_doc = {
        "version": EXPORT_FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "configs": configs_payload,
    }

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("services_export.env", env_bytes)
        zip_file.writestr("configs_export.json", dumps(configs_doc, indent=2, ensure_ascii=False))
    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype="application/zip", as_attachment=True, download_name="services_export.zip")


@services.route("/services/import", methods=["POST"])
@login_required
def services_service_import():
    if DB.readonly:
        return handle_error("Database is in read-only mode", "services")

    services_file = request.files.get("services_file")
    if not services_file or not services_file.filename:
        return handle_error("No services file uploaded.", "services", True)

    raw_bytes = services_file.read()
    is_zip = raw_bytes.startswith(b"PK\x03\x04") or (services_file.filename or "").lower().endswith(".zip")

    env_content: Optional[str] = None
    parsed_configs: List[Dict] = []
    configs_parse_errors: List[str] = []

    if is_zip:
        try:
            zip_buffer = BytesIO(raw_bytes)
            with zipfile.ZipFile(zip_buffer, "r") as zip_file:
                entries = {zinfo.filename: zinfo for zinfo in zip_file.infolist() if zinfo.filename in ZIP_ALLOWED_MEMBERS}
                if not entries:
                    return handle_error(
                        "The uploaded archive must contain services_export.env and/or configs_export.json.",
                        "services",
                        True,
                    )
                total_uncompressed = sum(zinfo.file_size for zinfo in entries.values())
                if total_uncompressed > ZIP_MAX_UNCOMPRESSED_BYTES or any(zinfo.file_size > ZIP_MAX_UNCOMPRESSED_BYTES for zinfo in entries.values()):
                    return handle_error("Refusing to extract the archive: uncompressed size exceeds the safety limit.", "services", True)
                env_zinfo = entries.get("services_export.env")
                if env_zinfo is not None:
                    try:
                        env_content = zip_file.read(env_zinfo).decode("utf-8")
                    except UnicodeDecodeError:
                        return handle_error("Invalid encoding for services_export.env inside the archive.", "services", True)
                json_zinfo = entries.get("configs_export.json")
                if json_zinfo is not None:
                    try:
                        configs_raw = zip_file.read(json_zinfo).decode("utf-8")
                    except UnicodeDecodeError:
                        return handle_error("Invalid encoding for configs_export.json inside the archive.", "services", True)
                    parsed_configs, configs_parse_errors = parse_configs_export(configs_raw)
        except zipfile.BadZipFile:
            return handle_error("Uploaded file is not a valid zip archive.", "services", True)
    else:
        try:
            env_content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return handle_error("Invalid file encoding. Please upload a UTF-8 file.", "services", True)

    services_map: Dict[str, Dict[str, str]] = {}
    parse_errors: List[str] = []
    if env_content:
        services_map, parse_errors = parse_services_export(env_content)

    if not services_map and not parsed_configs and not configs_parse_errors:
        return handle_error("No services or custom configurations found in the import file.", "services", True)

    overwrite_configs = request.form.get("overwrite_configs", "no") == "yes"

    DATA.load_from_file()

    def import_services(
        services_map: Dict[str, Dict[str, str]],
        parse_errors: List[str],
        parsed_configs: List[Dict],
        configs_parse_errors: List[str],
        overwrite_configs: bool,
    ):
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

        configs_results = None
        if parsed_configs or configs_parse_errors:
            # Let the scheduler observe the new services before we reference them by service_id.
            wait_applying()
            configs_results = apply_imported_configs(parsed_configs, overwrite_configs, configs_parse_errors)
            flash_import_results(configs_results)

        config_changed = bool(created) or bool(configs_results and (configs_results["created"] or configs_results["overwritten"]))
        DATA.update({"RELOADING": False, "CONFIG_CHANGED": config_changed})

    DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
    CONFIG_TASKS_EXECUTOR.submit(
        import_services,
        services_map,
        parse_errors,
        parsed_configs,
        configs_parse_errors,
        overwrite_configs,
    )

    message = "Importing services and custom configurations" if parsed_configs or configs_parse_errors else "Importing services"
    return redirect(
        url_for(
            "loading",
            next=url_for("services.services_page"),
            message=message,
        )
    )
