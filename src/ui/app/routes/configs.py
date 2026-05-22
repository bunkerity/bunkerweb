from datetime import datetime, timezone
from io import BytesIO
from json import JSONDecodeError, dumps, loads
from re import match
from time import time
from typing import Dict, List, Literal, Optional, Tuple

from flask import Blueprint, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from werkzeug.utils import secure_filename

from common_utils import bytes_hash  # type: ignore

from app.dependencies import BW_CONFIG, CONFIG_TASKS_EXECUTOR, DATA, DB
from app.utils import flash, is_editable_method

from app.routes.utils import handle_error, verify_data_in_form, wait_applying

configs = Blueprint("configs", __name__)

CONFIG_NAME_RX = r"^[\w_-]{1,255}$"
EXPORT_FORMAT_VERSION = 1

CONFIG_TYPES = {
    "HTTP": {"context": "global", "description": "Configurations at the HTTP level of NGINX."},
    "SERVER_HTTP": {"context": "multisite", "description": "Configurations at the HTTP/Server level of NGINX."},
    "DEFAULT_SERVER_HTTP": {
        "context": "global",
        "description": 'Configurations at the Server level of NGINX, specifically for the "default server" when the supplied client name doesn\'t match any server name in SERVER_NAME.',
    },
    "MODSEC_CRS": {"context": "multisite", "description": "Configurations applied before the OWASP Core Rule Set is loaded."},
    "MODSEC": {
        "context": "multisite",
        "description": "Configurations applied after the OWASP Core Rule Set is loaded, or used when the Core Rule Set is not loaded.",
    },
    "STREAM": {"context": "global", "description": "Configurations at the Stream level of NGINX."},
    "SERVER_STREAM": {"context": "multisite", "description": "Configurations at the Stream/Server level of NGINX."},
    "CRS_PLUGINS_BEFORE": {"context": "multisite", "description": "Configurations applied before the OWASP Core Rule Set plugins are loaded."},
    "CRS_PLUGINS_AFTER": {"context": "multisite", "description": "Configurations applied after the OWASP Core Rule Set plugins are loaded."},
}


def parse_configs_export(content: str) -> Tuple[List[Dict], List[str]]:
    """Parse a custom-configs export payload.

    Returns (valid_configs, errors). Invalid entries are skipped with a recorded
    error; callers may still import the valid ones."""
    errors: List[str] = []
    try:
        payload = loads(content)
    except JSONDecodeError as exc:
        return [], [f"File is not valid JSON: {exc.msg}"]

    if not isinstance(payload, dict):
        return [], ["Export payload must be a JSON object with a 'configs' array."]

    configs_raw = payload.get("configs")
    if not isinstance(configs_raw, list):
        return [], ["Export payload is missing a 'configs' array."]

    valid: List[Dict] = []
    allowed_types_lower = {key.lower() for key in CONFIG_TYPES}

    for index, entry in enumerate(configs_raw, start=1):
        label = f"entry #{index}"
        if not isinstance(entry, dict):
            errors.append(f"{label} is not a JSON object.")
            continue

        entry_name = entry.get("name")
        entry_type = entry.get("type")
        entry_service = entry.get("service_id")
        entry_data = entry.get("data", "")
        entry_draft = entry.get("is_draft", False)

        if not isinstance(entry_name, str) or not match(CONFIG_NAME_RX, entry_name):
            errors.append(f"{label} has an invalid name.")
            continue
        if not isinstance(entry_type, str):
            errors.append(f"{label} ({entry_name}) has a missing or invalid type.")
            continue
        normalized_type = entry_type.strip().replace("-", "_").lower()
        if normalized_type not in allowed_types_lower:
            errors.append(f"{label} ({entry_name}) has an unknown type '{entry_type}'.")
            continue
        if entry_service is not None and not isinstance(entry_service, str):
            errors.append(f"{label} ({entry_name}) has an invalid service_id.")
            continue
        if not isinstance(entry_data, str):
            errors.append(f"{label} ({entry_name}) has non-string data.")
            continue
        if not isinstance(entry_draft, bool):
            errors.append(f"{label} ({entry_name}) has a non-boolean is_draft value.")
            continue

        service_id: Optional[str]
        if entry_service in (None, "", "global"):
            service_id = None
        else:
            service_id = entry_service

        valid.append(
            {
                "service_id": service_id,
                "type": normalized_type,
                "name": entry_name,
                "data": entry_data,
                "is_draft": entry_draft,
            }
        )

    return valid, errors


def apply_imported_configs(parsed_configs: List[Dict], overwrite: bool, parse_errors: Optional[List[str]] = None) -> Dict[str, List[str]]:
    """Apply parsed custom configs to the database.

    Returns a dict with keys 'created', 'overwritten', 'skipped', 'failed', 'parse_errors'.
    Callers are responsible for flashing results and updating RELOADING/CONFIG_CHANGED."""
    results: Dict[str, List[str]] = {
        "created": [],
        "overwritten": [],
        "skipped": [],
        "failed": [],
        "parse_errors": list(parse_errors or []),
    }

    services_value = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",)).get("SERVER_NAME", "")
    existing_services = set(services_value.split()) if services_value else set()

    # Key on the normalized (underscore) type: template-provided configs carry the hyphenated form.
    existing_configs = {
        (db_config.get("service_id") or None, db_config["type"].strip().replace("-", "_").lower(), db_config["name"]): db_config
        for db_config in DB.get_custom_configs(with_drafts=True, with_data=False)
    }

    for entry in parsed_configs:
        service_id = entry["service_id"]
        config_type = entry["type"]
        config_name = entry["name"]
        label = f"{config_type}/{config_name}{f' for service {service_id}' if service_id else ''}"

        if service_id and service_id not in existing_services:
            results["failed"].append(f"{label} (service '{service_id}' does not exist)")
            continue

        existing = existing_configs.get((service_id, config_type, config_name))
        is_new = existing is None

        if existing is not None:
            if existing.get("template"):
                # The target serves this config from a template. Honor the change-detection rule:
                # only materialize a real UI override when the imported data differs from the
                # template default; identical data stays template-managed (no shadowing row).
                if bytes_hash(entry["data"], algorithm="sha256") == existing.get("checksum"):
                    results["skipped"].append(f"{label} (unchanged from template)")
                    continue
                is_new = True
            elif not is_editable_method(existing.get("method")):
                results["skipped"].append(f"{label} (non-editable method: {existing.get('method')})")
                continue
            elif not overwrite:
                results["skipped"].append(f"{label} (already exists; enable 'Overwrite existing' to replace)")
                continue

        method = existing["method"] if existing and is_editable_method(existing.get("method")) else "ui"
        error = DB.upsert_custom_config(
            config_type,
            config_name,
            {
                "service_id": service_id,
                "type": config_type,
                "name": config_name,
                "data": entry["data"],
                "method": method,
                "is_draft": entry["is_draft"],
            },
            service_id=service_id,
            new=is_new,
        )
        if error:
            results["failed"].append(f"{label} ({error})")
            continue

        (results["created"] if is_new else results["overwritten"]).append(label)

    return results


def flash_import_results(results: Dict[str, List[str]]) -> None:
    """Append flash entries summarizing an apply_imported_configs run."""
    for error in results.get("parse_errors", []):
        DATA["TO_FLASH"].append({"content": f"Import warning: {error}", "type": "error"})
    created = results.get("created", [])
    overwritten = results.get("overwritten", [])
    skipped = results.get("skipped", [])
    failed = results.get("failed", [])
    if created:
        DATA["TO_FLASH"].append({"content": f"Imported custom configuration{'s' if len(created) > 1 else ''}: {', '.join(created)}", "type": "success"})
    if overwritten:
        DATA["TO_FLASH"].append(
            {"content": f"Overwrote custom configuration{'s' if len(overwritten) > 1 else ''}: {', '.join(overwritten)}", "type": "success"}
        )
    if skipped:
        DATA["TO_FLASH"].append({"content": f"Skipped custom configuration{'s' if len(skipped) > 1 else ''}: {', '.join(skipped)}", "type": "warning"})
    if failed:
        DATA["TO_FLASH"].append({"content": f"Failed to import custom configuration{'s' if len(failed) > 1 else ''}: {', '.join(failed)}", "type": "error"})


def _use_modsecurity_global_crs() -> bool:
    value = BW_CONFIG.get_config(
        global_only=True,
        methods=False,
        with_drafts=True,
        filtered_settings=("USE_MODSECURITY_GLOBAL_CRS",),
    ).get("USE_MODSECURITY_GLOBAL_CRS", "no")
    return str(value).lower() == "yes"


@configs.route("/configs", methods=["GET"])
@login_required
def configs_page():
    service = request.args.get("service", "")
    config_type = request.args.get("type", "")
    return render_template(
        "configs.html",
        configs=DB.get_custom_configs(with_drafts=True, with_data=False),
        services=BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"],
        db_templates=" ".join([template for template in DB.get_templates() if template != "ui"]),
        config_service=service,
        config_type=config_type,
    )


@configs.route("/configs/convert", methods=["POST"])
@login_required
def configs_convert():
    if DB.readonly:
        return handle_error("Database is in read-only mode", "configs")

    verify_data_in_form(
        data={"configs": None},
        err_message="Missing configs parameter on /configs/convert.",
        redirect_url="configs",
        next=True,
    )
    verify_data_in_form(
        data={"convert_to": None},
        err_message="Missing convert_to parameter on /configs/convert.",
        redirect_url="configs",
        next=True,
    )

    raw_configs = request.form["configs"]
    if not raw_configs:
        return handle_error("No configs selected.", "configs", True)
    try:
        configs = loads(raw_configs)
    except JSONDecodeError:
        return handle_error("Invalid configs parameter on /configs/convert.", "configs", True)

    convert_to = request.form["convert_to"]
    if convert_to not in ("online", "draft"):
        return handle_error("Invalid convert_to parameter.", "configs", True)
    DATA.load_from_file()

    def convert_configs(configs: List[Dict[str, str]], convert_to: str):
        wait_applying()

        db_configs = DB.get_custom_configs(with_drafts=True)
        db_config_map = {(config.get("service_id"), config["type"], config["name"]): config for config in db_configs}

        configs_to_convert = set()
        non_editable_configs = set()
        non_convertible_configs = set()
        missing_configs = set()

        for config in configs:
            service_id = config.get("service") or None
            service_id = None if service_id in ("global", "") else service_id
            config_type = config.get("type", "").strip().replace("-", "_").lower()
            name = config.get("name")
            key = (service_id, config_type, name)
            db_config = db_config_map.get(key)
            config_label = f"{config_type}/{name}{f' for service {service_id}' if service_id else ''}"
            if not db_config:
                missing_configs.add(config_label)
                continue
            if db_config.get("template") or not is_editable_method(db_config.get("method")):
                non_editable_configs.add(config_label)
                continue
            if db_config.get("is_draft", False) == (convert_to == "draft"):
                non_convertible_configs.add(config_label)
                continue
            configs_to_convert.add(key)

        for non_editable_config in non_editable_configs:
            DATA["TO_FLASH"].append(
                {"content": f"Custom config {non_editable_config} is not a UI/API custom config and will not be converted.", "type": "error"}
            )

        for non_convertible_config in non_convertible_configs:
            DATA["TO_FLASH"].append(
                {"content": f"Custom config {non_convertible_config} is already a {convert_to} config and will not be converted.", "type": "error"}
            )

        for missing_config in missing_configs:
            DATA["TO_FLASH"].append({"content": f"Custom config {missing_config} could not be found.", "type": "error"})

        if not configs_to_convert:
            DATA["TO_FLASH"].append(
                {"content": "All selected custom configs could not be found, are not UI/API custom configs or are already converted.", "type": "error"}
            )
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            return

        for key in configs_to_convert:
            db_config = db_config_map[key]
            error = DB.upsert_custom_config(
                db_config["type"],
                db_config["name"],
                {
                    "service_id": db_config.get("service_id"),
                    "type": db_config["type"],
                    "name": db_config["name"],
                    "data": db_config["data"],
                    "method": db_config["method"],
                    "is_draft": convert_to == "draft",
                },
                service_id=db_config.get("service_id"),
            )
            if error:
                DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {error}", "type": "error"})
                DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                return

        converted_labels = [f"{config[1]}/{config[2]}{f' for service {config[0]}' if config[0] else ''}" for config in configs_to_convert]
        DATA["TO_FLASH"].append({"content": f"Converted to \"{convert_to.title()}\" configs: {', '.join(converted_labels)}", "type": "success"})
        DATA["RELOADING"] = False

    DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
    CONFIG_TASKS_EXECUTOR.submit(convert_configs, configs, convert_to)

    return redirect(
        url_for(
            "loading",
            next=url_for("configs.configs_page"),
            message=f"Converting config{'s' if len(configs) > 1 else ''} to {convert_to}",
        )
    )


@configs.route("/configs/delete", methods=["POST"])
@login_required
def configs_delete():
    if DB.readonly:
        return handle_error("Database is in read-only mode", "configs")

    verify_data_in_form(
        data={"configs": None},
        err_message="Missing configs parameter on /configs/delete.",
        redirect_url="configs",
        next=True,
    )
    configs = request.form["configs"]
    if not configs:
        return handle_error("No configs selected.", "configs", True)
    try:
        configs = loads(configs)
    except JSONDecodeError:
        return handle_error("Invalid configs parameter on /configs/delete.", "configs", True)
    DATA.load_from_file()

    def delete_configs(configs: Dict[str, str]):
        wait_applying()

        db_configs = DB.get_custom_configs(with_drafts=True)
        configs_to_delete = set()
        non_editable_configs = set()
        remaining_configs_by_method: Dict[str, List[Dict[str, str]]] = {"ui": [], "api": []}

        for db_config in db_configs:
            key = f"{(db_config['service_id'] + '/') if db_config['service_id'] else ''}{db_config['type']}/{db_config['name']}"
            keep = True
            for config in configs:
                # Normalize service comparison: treat "global" string as None
                config_service = config["service"] if config["service"] != "global" else None
                if db_config["name"] == config["name"] and db_config["service_id"] == config_service and db_config["type"] == config["type"]:
                    config_method = db_config.get("method")
                    if config_method not in remaining_configs_by_method:
                        non_editable_configs.add(key)
                        continue
                    configs_to_delete.add(key)
                    keep = False
                    break
            if db_config.get("template") or not keep:
                continue
            config_without_template = {k: v for k, v in db_config.items() if k != "template"}
            config_method = config_without_template.get("method")
            if config_method in remaining_configs_by_method:
                remaining_configs_by_method[config_method].append(config_without_template)

        for non_editable_config in non_editable_configs:
            DATA["TO_FLASH"].append(
                {
                    "content": f"Custom config {non_editable_config} is not a UI/API custom config and will not be deleted.",
                    "type": "error",
                }
            )

        if not configs_to_delete:
            DATA["TO_FLASH"].append({"content": "All selected custom configs could not be found or are not UI/API custom configs.", "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            return

        for method, configs_for_method in remaining_configs_by_method.items():
            error = DB.save_custom_configs(configs_for_method, method)
            if error:
                DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {error}", "type": "error"})
                DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                return
        DATA["TO_FLASH"].append({"content": f"Deleted config{'s' if len(configs_to_delete) > 1 else ''}: {', '.join(configs_to_delete)}", "type": "success"})
        DATA["RELOADING"] = False

    DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
    CONFIG_TASKS_EXECUTOR.submit(delete_configs, configs)

    return redirect(
        url_for(
            "loading",
            next=url_for("configs.configs_page"),
            message=f"Deleting selected config{'s' if len(configs) > 1 else ''}",
        )
    )


@configs.route("/configs/new", methods=["GET", "POST"])
@login_required
def configs_new():
    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "configs")

        verify_data_in_form(
            data={"service": None},
            err_message="Missing service parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        service = request.form["service"]
        services = BW_CONFIG.get_config(global_only=True, with_drafts=True, methods=False, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split()
        if service != "global" and service not in services:
            return handle_error(f"Service {service} does not exist.", "configs.configs_new", True)

        verify_data_in_form(
            data={"type": None},
            err_message="Missing type parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        config_type = request.form["type"]
        if config_type not in CONFIG_TYPES:
            return handle_error("Invalid type parameter on /configs/new.", "configs.configs_new", True)

        verify_data_in_form(
            data={"name": None},
            err_message="Missing name parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        config_name = request.form["name"]
        if not match(r"^[\w_-]{1,255}$", config_name):
            return handle_error("Invalid name parameter on /configs/new.", "configs.configs_new", True)

        verify_data_in_form(
            data={"value": None},
            err_message="Missing value parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        config_value = request.form["value"].replace("\r\n", "\n").strip()
        is_draft = request.form.get("is_draft", "no") == "yes"
        DATA.load_from_file()

        def create_config(
            service: Optional[str],
            config_type: Literal[
                "HTTP",
                "SERVER_HTTP",
                "DEFAULT_SERVER_HTTP",
                "MODSEC_CRS",
                "MODSEC",
                "STREAM",
                "SERVER_STREAM",
                "CRS_PLUGINS_BEFORE",
                "CRS_PLUGINS_AFTER",
            ],
            config_name: str,
            config_value: str,
            is_draft: bool,
        ):
            wait_applying()
            config_type = config_type.lower()

            new_config = {
                "type": config_type,
                "name": config_name,
                "data": config_value,
                "method": "ui",
                "is_draft": is_draft,
            }
            if service != "global":
                new_config["service_id"] = service

            error = DB.upsert_custom_config(config_type, config_name, new_config, service_id=new_config.get("service_id"), new=True)
            if error:
                if error == "The custom config already exists":
                    DATA["TO_FLASH"].append(
                        {
                            "content": f"Config {config_type}/{config_name}{' for service ' + service if service else ''} already exists",
                            "type": "error",
                        }
                    )
                    DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                    return
                DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {error}", "type": "error"})
                return
            DATA["TO_FLASH"].append(
                {
                    "content": f"Created custom configuration {config_type}/{config_name}{' for service ' + service if service else ''}",
                    "type": "success",
                }
            )
            DATA["RELOADING"] = False

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        CONFIG_TASKS_EXECUTOR.submit(create_config, service if service != "global" else None, config_type, config_name, config_value, is_draft)

        return redirect(
            url_for(
                "loading",
                next=url_for("configs.configs_edit", service="global" if service == "global" else service, config_type=config_type.lower(), name=config_name),
                message=f"Creating custom configuration {config_type}/{config_name}{' for service' + service if service != 'global' else ''}",
            )
        )

    clone = request.args.get("clone", "")
    config_service = ""
    config_type = ""
    config_name = ""
    is_draft = "no"

    if clone:
        config_service, config_type, config_name = clone.split("/")
        db_custom_config = DB.get_custom_config(config_type, config_name, service_id=config_service if config_service != "global" else None, with_data=True)
        clone = db_custom_config.get("data", b"").decode("utf-8")
        is_draft = "yes" if db_custom_config.get("is_draft") else "no"

    return render_template(
        "config_edit.html",
        config_types=CONFIG_TYPES,
        config_value=clone,
        config_service=config_service,
        type=config_type.upper(),
        name=config_name,
        is_draft=is_draft,
        use_modsecurity_global_crs=_use_modsecurity_global_crs(),
        global_crs_service_scoped_modsec_crs_error=DB.GLOBAL_CRS_SERVICE_SCOPED_MODSEC_CRS_ERROR,
        services=BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(),
    )


@configs.route("/configs/<string:service>/<string:config_type>/<string:name>", methods=["GET", "POST"])
@login_required
def configs_edit(service: str, config_type: str, name: str):
    if service == "global":
        service = None
    name = secure_filename(name)

    db_config = DB.get_custom_config(config_type, name, service_id=service, with_data=True)
    if not db_config:
        return handle_error(f"Config {config_type}/{name}{' for service ' + service if service else ''} does not exist.", "configs", True)
    is_draft = "yes" if db_config.get("is_draft") else "no"

    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "configs")

        if not db_config["template"] and not is_editable_method(db_config["method"]):
            return handle_error(
                f"Config {config_type}/{name}{' for service ' + service if service else ''} is not a UI/API custom config and cannot be edited.",
                "configs",
                True,
            )

        verify_data_in_form(
            data={"service": None},
            err_message="Missing service parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        new_service = request.form["service"]
        services = BW_CONFIG.get_config(global_only=True, with_drafts=True, methods=False, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split()
        if new_service != "global" and new_service not in services:
            return handle_error(f"Service {new_service} does not exist.", "configs.configs_new", True)

        if new_service == "global":
            new_service = None

        verify_data_in_form(
            data={"type": None},
            err_message="Missing type parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        new_type = request.form["type"]
        if new_type not in CONFIG_TYPES:
            return handle_error("Invalid type parameter on /configs/new.", "configs.configs_new", True)
        new_type = new_type.lower()

        verify_data_in_form(
            data={"name": None},
            err_message="Missing name parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        new_name = secure_filename(request.form["name"])
        if not match(r"^[\w_-]{1,255}$", new_name):
            return handle_error("Invalid name parameter on /configs/new.", "configs.configs_new", True)

        # Forbid renaming template-based configs (content can still be edited)
        if db_config.get("template") and new_name != name:
            return handle_error(
                "Renaming a template-based custom config is not allowed.",
                "configs",
                True,
            )

        verify_data_in_form(
            data={"value": None},
            err_message="Missing value parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        config_value = request.form["value"].replace("\r\n", "\n").strip()
        new_is_draft = request.form.get("is_draft", "no") == "yes"
        DATA.load_from_file()

        no_changes = (
            db_config["type"] == new_type
            and db_config["name"] == new_name
            and db_config["service_id"] == new_service
            and db_config["data"].decode("utf-8") == config_value
            and db_config.get("is_draft", False) == new_is_draft
        )
        if no_changes:
            return handle_error("No values were changed.", "configs", True)

        method = db_config["method"] if is_editable_method(db_config.get("method")) else "ui"
        error = DB.upsert_custom_config(
            config_type,
            name,
            {
                "service_id": new_service,
                "type": new_type,
                "name": new_name,
                "data": config_value,
                "method": method,
                "is_draft": new_is_draft,
            },
            service_id=service,
        )
        if error:
            flash(f"An error occurred while saving the custom configs: {error}", "error")
        else:
            flash(f"Saved custom configuration {new_type}/{new_name}{' for service ' + new_service if new_service else ''}")

        return redirect(
            url_for(
                "configs.configs_edit",
                service=new_service or "global",
                config_type=new_type,
                name=new_name,
            )
        )

    return render_template(
        "config_edit.html",
        config_types=CONFIG_TYPES,
        config_value=db_config["data"].decode("utf-8"),
        config_service=db_config.get("service_id"),
        type=db_config["type"].upper(),
        name=db_config["name"],
        config_method=db_config["method"],
        config_template=db_config.get("template"),
        is_draft=is_draft,
        use_modsecurity_global_crs=_use_modsecurity_global_crs(),
        global_crs_service_scoped_modsec_crs_error=DB.GLOBAL_CRS_SERVICE_SCOPED_MODSEC_CRS_ERROR,
        services=BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(),
    )


@configs.route("/configs/export", methods=["GET"])
@login_required
def configs_export():
    selection_raw = request.args.get("configs", "").strip()
    selection: Optional[List[Tuple[Optional[str], str, str]]] = None

    if selection_raw:
        try:
            decoded = loads(selection_raw)
        except JSONDecodeError:
            return handle_error("Invalid configs parameter on /configs/export.", "configs", True)
        if not isinstance(decoded, list) or not decoded:
            return handle_error("Invalid configs parameter on /configs/export.", "configs", True)
        selection = []
        for entry in decoded:
            if not isinstance(entry, dict):
                return handle_error("Invalid configs parameter on /configs/export.", "configs", True)
            entry_service = entry.get("service")
            entry_type = entry.get("type")
            entry_name = entry.get("name")
            if not isinstance(entry_type, str) or not isinstance(entry_name, str):
                return handle_error("Invalid configs parameter on /configs/export.", "configs", True)
            normalized_service: Optional[str]
            if entry_service in (None, "", "global"):
                normalized_service = None
            elif isinstance(entry_service, str):
                normalized_service = entry_service
            else:
                return handle_error("Invalid configs parameter on /configs/export.", "configs", True)
            selection.append((normalized_service, entry_type.strip().replace("-", "_").lower(), entry_name))

    db_configs = DB.get_custom_configs(with_drafts=True, with_data=True)
    exported: List[Dict] = []
    selection_set = set(selection) if selection else None

    for db_config in db_configs:
        service_id = db_config.get("service_id") or None
        # Normalize: template-provided configs carry hyphenated types (see get_custom_configs), real rows use the underscore enum form.
        config_type = db_config["type"].strip().replace("-", "_").lower()
        config_name = db_config["name"]
        if selection_set is not None and (service_id, config_type, config_name) not in selection_set:
            continue
        raw_data = db_config.get("data", b"") or b""
        if isinstance(raw_data, bytes):
            try:
                data_str = raw_data.decode("utf-8")
            except UnicodeDecodeError:
                data_str = raw_data.decode("utf-8", errors="replace")
        else:
            data_str = str(raw_data)
        exported.append(
            {
                "service_id": service_id,
                "type": config_type,
                "name": config_name,
                "data": data_str,
                "is_draft": bool(db_config.get("is_draft", False)),
            }
        )

    if not exported:
        return handle_error("No custom configurations to export.", "configs", True)

    payload = {
        "version": EXPORT_FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "configs": exported,
    }

    buffer = BytesIO(dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"))
    buffer.seek(0)
    return send_file(buffer, mimetype="application/json", as_attachment=True, download_name="configs_export.json")


@configs.route("/configs/import", methods=["POST"])
@login_required
def configs_import():
    if DB.readonly:
        return handle_error("Database is in read-only mode", "configs")

    configs_file = request.files.get("configs_file")
    if not configs_file or not configs_file.filename:
        return handle_error("No custom configurations file uploaded.", "configs", True)

    try:
        content = configs_file.read().decode("utf-8")
    except UnicodeDecodeError:
        return handle_error("Invalid file encoding. Please upload a UTF-8 JSON file.", "configs", True)

    parsed_configs, parse_errors = parse_configs_export(content)
    if not parsed_configs and parse_errors:
        for error in parse_errors:
            flash(f"Import error: {error}", "error")
        return redirect(url_for("configs.configs_page"))
    if not parsed_configs:
        return handle_error("No custom configurations found in the import file.", "configs", True)

    overwrite = request.form.get("overwrite", "no") == "yes"
    DATA.load_from_file()

    def import_configs(parsed_configs: List[Dict], parse_errors: List[str], overwrite: bool):
        wait_applying()
        results = apply_imported_configs(parsed_configs, overwrite, parse_errors)
        flash_import_results(results)
        DATA.update({"RELOADING": False, "CONFIG_CHANGED": bool(results["created"] or results["overwritten"])})

    DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
    CONFIG_TASKS_EXECUTOR.submit(import_configs, parsed_configs, parse_errors, overwrite)

    return redirect(
        url_for(
            "loading",
            next=url_for("configs.configs_page"),
            message="Importing custom configurations",
        )
    )
