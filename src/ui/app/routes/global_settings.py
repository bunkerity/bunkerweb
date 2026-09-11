from contextlib import suppress
from time import time
from typing import Dict, Optional

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, CONFIG_TASKS_EXECUTOR, DATA, DB
from app.raw_drafts import (
    RAW_DRAFT_SETTINGS,
    RAW_PRESENT_SETTINGS,
    STRUCTURAL_SETTINGS,
    RawDraftSettingsError,
    existing_draft_keys,
    parse_raw_draft_settings,
)
from app.utils import get_blacklisted_settings, is_editable_method

from app.routes.utils import extract_file_setting_names, handle_error, wait_applying

global_settings = Blueprint("global_settings", __name__)


def _settings_catalog() -> Dict:
    settings = BW_CONFIG.get_plugins_settings()
    return settings if isinstance(settings, dict) else {}


@global_settings.route("/global-config", methods=["GET", "POST"])
@global_settings.route("/global-settings", methods=["GET", "POST"])
@login_required
def global_settings_page():
    global_config = DB.get_config(global_only=True, methods=True)

    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "global_settings")
        DATA.load_from_file()

        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]
        file_setting_names = extract_file_setting_names(variables)
        mode = request.args.get("mode", "advanced")
        raw_draft_value = variables.pop(RAW_DRAFT_SETTINGS, None)
        raw_present_value = variables.pop(RAW_PRESENT_SETTINGS, None)
        if mode != "raw" and (raw_draft_value is not None or raw_present_value is not None):
            return handle_error("Setting draft metadata is only accepted in raw mode.", "global_settings", True)

        draft_settings = None
        if mode == "raw":
            if raw_present_value is None:
                return handle_error("Missing RAW_PRESENT_SETTINGS metadata.", "global_settings", True)
            saved_draft_config = DB.get_config(global_only=True, methods=True, with_drafts=True, with_setting_drafts=True)
            try:
                draft_settings = parse_raw_draft_settings(
                    raw_draft_value,
                    posted_keys=set(variables),
                    present_value=raw_present_value,
                    existing_draft_keys=existing_draft_keys(saved_draft_config if isinstance(saved_draft_config, dict) else {}),
                    settings=_settings_catalog(),
                    global_config=True,
                )
            except RawDraftSettingsError as error:
                return handle_error(str(error), "global_settings", True)

        override_non_global_services = variables.pop("OVERRIDE_NON_GLOBAL_SERVICES", variables.pop("OVERRIDE_TEMPLATE_SERVICES", "no")) == "yes"

        def update_global_config(
            variables: Dict[str, str],
            override_non_global_services: bool,
            file_setting_names: Dict[str, str],
            draft_settings: Optional[Dict[str, Optional[bool]]],
            mode: str,
        ):
            wait_applying()

            # Edit check fields and remove already existing ones
            config = DB.get_config(methods=True, with_drafts=True)
            draft_config = DB.get_config(methods=True, with_drafts=True, with_setting_drafts=True)
            services = config["SERVER_NAME"]["value"].split()
            preserved_draft_edits = set()

            def _entry_value(settings: dict, key: str):
                value = settings.get(key, {"value": None})
                return value.get("value") if isinstance(value, dict) else value

            def _is_draft(settings: dict, key: str) -> bool:
                value = settings.get(key, {})
                return isinstance(value, dict) and bool(value.get("is_draft"))

            if mode == "raw":
                for setting, metadata in draft_config.items():
                    if not isinstance(metadata, dict) or not metadata.get("is_draft") or setting in STRUCTURAL_SETTINGS:
                        continue
                    retained_file_name = str(metadata.get("file_name", "") or "").strip()
                    if retained_file_name:
                        file_setting_names.setdefault(setting, retained_file_name)

            if mode != "raw":
                for setting, metadata in draft_config.items():
                    if not isinstance(metadata, dict) or not metadata.get("is_draft") or setting in STRUCTURAL_SETTINGS:
                        continue
                    if setting in variables and variables[setting] != _entry_value(config, setting):
                        preserved_draft_edits.add(setting)
                    variables[setting] = metadata.get("value", "")
                    if setting in file_setting_names:
                        effective_file_name = str(config.get(setting, {}).get("file_name", "") or "").strip()
                        if file_setting_names[setting] != effective_file_name:
                            preserved_draft_edits.add(setting)
                        # Keep the retained filename when the effective
                        # fallback filename was posted by Simple/Advanced.
                        file_setting_names[setting] = str(metadata.get("file_name", "") or "").strip()
            variables_to_check = variables.copy()
            has_file_name_changes = False

            for variable, value in variables.items():
                setting = config.get(variable, {"value": None, "global": True})
                # Simple/Advanced values come from the effective config. Saved
                # drafts are restored above and must not be treated as a fresh
                # change merely because their retained value differs from the
                # effective fallback.
                if mode != "raw" and _is_draft(draft_config, variable):
                    del variables_to_check[variable]
                    continue
                comparison_config = draft_config if mode == "raw" and _is_draft(draft_config, variable) else config
                if setting.get("global", True) and value == _entry_value(comparison_config, variable):
                    del variables_to_check[variable]

            for setting_name, file_name in file_setting_names.items():
                if mode != "raw" and _is_draft(draft_config, setting_name):
                    continue
                file_config = draft_config if _is_draft(draft_config, setting_name) else config
                current_file_name = str(file_config.get(setting_name, {}).get("file_name", "") or "").strip()
                if file_name != current_file_name:
                    has_file_name_changes = True
                    break

            validation_variables = variables_to_check.copy()
            draft_value_keys = set()
            if mode == "raw":
                for key, desired in (draft_settings or {}).items():
                    current_is_draft = _is_draft(draft_config, key)
                    state_changed = (desired is None and current_is_draft) or (desired is not None and bool(desired) != current_is_draft)
                    metadata = draft_config.get(key, {})
                    if state_changed and isinstance(metadata, dict) and not is_editable_method(metadata.get("method"), allow_default=True):
                        DATA["TO_FLASH"].append(
                            {
                                "content": f"Setting {key} cannot change draft state because it is managed by the {metadata.get('method')} method.",
                                "type": "error",
                            }
                        )
                        DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                        return

                    value_changed = key in variables and variables[key] != _entry_value(draft_config, key)
                    needs_value_validation = (desired is True and (state_changed or value_changed)) or (desired is False and current_is_draft)
                    if needs_value_validation:
                        draft_value_keys.add(key)
                        if key in variables:
                            validation_variables.setdefault(key, variables[key])

            variables = BW_CONFIG.check_variables(variables, config, validation_variables, global_config=True, threaded=True)
            invalid_draft_values = [key for key in draft_value_keys if key not in variables]
            if invalid_draft_values:
                DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                return

            draft_state_changed = any(
                (desired is None and _is_draft(draft_config, key)) or (desired is not None and bool(desired) != _is_draft(draft_config, key))
                for key, desired in (draft_settings or {}).items()
            )
            changed_variables = {key: value for key, value in variables.items() if key in variables_to_check and not ((draft_settings or {}).get(key) is True)}
            changed_variables.update(
                {
                    key: variables[key]
                    for key, desired in (draft_settings or {}).items()
                    if desired is False and _is_draft(draft_config, key) and key in variables
                }
            )

            no_removed_settings = True
            blacklist = get_blacklisted_settings(True)
            for setting in global_config:
                if setting not in blacklist and setting not in variables:
                    no_removed_settings = False
                    break

            if no_removed_settings and not variables_to_check and not draft_state_changed and not has_file_name_changes:
                content = "The global settings were not edited because no values were changed."
                if preserved_draft_edits:
                    content += " Draft settings remain unchanged; activate or edit them in Raw mode."
                DATA["TO_FLASH"].append({"content": content, "type": "warning"})
                DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                return

            if "PRO_LICENSE_KEY" in variables:
                DATA["PRO_LOADING"] = True

            for variable, value in changed_variables.items():
                for service in services:
                    setting = config.get(f"{service}_{variable}", None)
                    if (
                        setting
                        and (setting["global"] or override_non_global_services)
                        and (setting["value"] != value or setting["value"] == config.get(variable, {"value": None})["value"])
                    ):
                        variables[f"{service}_{variable}"] = value

            with suppress(BaseException):
                if config["PRO_LICENSE_KEY"]["value"] != variables["PRO_LICENSE_KEY"]:
                    DATA["TO_FLASH"].append({"content": "Checking license key to upgrade.", "type": "success", "save": False})

            operation, error = BW_CONFIG.edit_global_conf(
                variables,
                check_changes=True,
                file_name_map=file_setting_names,
                draft_settings=draft_settings,
            )

            if not error:
                operation = "Global settings successfully saved."

            if operation:
                if operation.startswith(("Can't", "The database is read-only")):
                    DATA["TO_FLASH"].append({"content": operation, "type": "error"})
                else:
                    DATA["TO_FLASH"].append({"content": operation, "type": "success"})
                    if preserved_draft_edits:
                        DATA["TO_FLASH"].append({"content": "Draft settings remain unchanged; activate or edit them in Raw mode.", "type": "warning"})
                    DATA["TO_FLASH"].append({"content": "The Scheduler will be in charge of applying the changes.", "type": "success", "save": False})

            DATA["RELOADING"] = False

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        CONFIG_TASKS_EXECUTOR.submit(update_global_config, variables, override_non_global_services, file_setting_names, draft_settings, mode)

        arguments = {}
        if request.args.get("mode", "advanced") != "advanced":
            arguments["mode"] = request.args["mode"]
        if request.args.get("type", "all") != "all":
            arguments["type"] = request.args["type"]

        return redirect(
            url_for(
                "loading",
                next=url_for("global_settings.global_settings_page") + f"?{'&'.join([f'{k}={v}' for k, v in arguments.items()])}",
                message="Saving global settings",
            )
        )
    elif request.args.get("as_json", "false").lower() == "true":
        return global_config

    mode = request.args.get("mode", "advanced")
    search_type = request.args.get("type", "all")
    raw_draft_config = DB.get_config(methods=True, with_drafts=True, with_setting_drafts=True, global_only=True)
    return render_template("global_settings.html", mode=mode, type=search_type, raw_draft_config=raw_draft_config)
