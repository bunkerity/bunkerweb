from time import time
from typing import Dict, List, Optional, Set

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import API_CLIENT, BW_CONFIG, CONFIG_TASKS_EXECUTOR, DATA
from app.i18n import translated
from app.api_client import ApiClientError, ApiUnavailableError
from app.models.save_scope import control_keys, restore_unowned_settings
from app.models.secret_settings import is_secret_setting, redact_secrets, restore_secrets, secret_setting_names
from app.raw_drafts import (
    RAW_DRAFT_SETTINGS,
    RAW_PRESENT_SETTINGS,
    STRUCTURAL_SETTINGS,
    RawDraftSettingsError,
    draft_edits_discarded,
    draft_state_changes,
    drafted_settings,
    existing_draft_keys,
    freeze_draft_edits,
    locked_draft_change,
    metadata_raw_only,
    parse_raw_draft_settings,
)
from app.routes.services import postable_scope, postable_shelf_scope, resolve_plugin, resolve_save_mode, shelf_plugin_scope
from app.utils import LOGGER, flash, get_activation_map, get_blacklisted_settings, is_readonly_request, plugin_settings_body, plugin_settings_body_script

from app.routes.utils import extract_file_setting_names, handle_error, wait_applying

global_settings = Blueprint("global_settings", __name__)


def update_global_config(
    variables: Dict[str, str],
    override_non_global_services: bool,
    file_setting_names: Dict[str, str],
    *,
    scope: Optional[Set[str]] = None,
    draft_settings: Optional[Dict[str, Optional[bool]]] = None,
):
    """Save the global settings page. ``draft_settings`` is the RAW editor's setting-draft map
    (app/raw_drafts.py) and None for every other pane."""
    wait_applying()

    # Edit check fields and remove already existing ones
    config = BW_CONFIG.get_config(methods=True, with_drafts=True)
    # The same snapshot with the RAW-editor setting drafts in it: `config` above holds only the
    # effective values those drafts leave in place.
    draft_config = BW_CONFIG.get_config(global_only=True, methods=True, with_drafts=True, with_setting_drafts=True)
    drafted = drafted_settings(draft_config)

    services = config["SERVER_NAME"]["value"].split()

    # The pages render a stored secret as a placeholder (models/secret_settings.py): one that comes
    # back untouched means "keep it", so put the stored value back before anything compares.
    # The RAW page renders a draft's retained value, so a placeholder there restores from the draft.
    variables = restore_secrets(variables, config, secret_setting_names(BW_CONFIG.get_plugins_settings()), drafted if draft_settings is not None else {})

    # Global settings have never had a restore pass: the page posts every key, so
    # absence meant deletion and that was fine. A per-plugin page posts only its own
    # keys, so without this it would delete every other global setting -- the same
    # data-loss bug fixed for services in S3.1, at global scope.
    #
    # `config` is NOT global_only (the propagation loop below needs the service rows), and a
    # service that merely INHERITS a multisite global shares that global's dict object
    # (db_methods/config_read.py:202 does `config.setdefault(f"{service}_{key}", value)`), so
    # `<svc>_<KEY>` carries `global: True` too. Keeping those here would put a key no global form
    # ever posts into the "was something removed?" loop below, which can then never conclude
    # "nothing changed" -- every no-op save would report success and trigger a reload. Same
    # `startswith(f"{service}_")` rule the rest of the codebase splits the two namespaces with
    # (models/config.py:132-137, db_methods/config_read.py:266). Dropping them from the payload
    # is safe: gen_conf re-materialises every service setting from get_services()
    # (models/config.py:52-64), which is already how a service's OWN row -- `global: False`, so
    # never restored even before this -- survives a global save.
    service_prefixes = tuple(f"{service}_" for service in services)
    global_config_entries = {key: value for key, value in config.items() if value.get("global", True) and not key.startswith(service_prefixes)}
    variables = restore_unowned_settings(
        variables,
        global_config_entries,
        scope=scope,
        # Same one-definition rule as the service page, and the two lists are NOT the same: the
        # global blacklist adds SERVER_NAME/USE_TEMPLATE, and `control_keys(True)` is empty
        # because this page must not post SERVER_NAME (it is the service list) and has no draft
        # state. A shared control-key list would be wrong on both pages.
        restore_skip=get_blacklisted_settings(True) | set(control_keys(True)),
        template_unchanged=True,
    )

    discarded_draft_edits = set()
    if draft_settings is None:
        discarded_draft_edits = freeze_draft_edits(variables, drafted, config)
    elif error := locked_draft_change(draft_settings, draft_config):
        DATA["TO_FLASH"].append({"content": error, "type": "error"})
        DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
        return
    draft_state_changed = any(draft_state_changes(desired, draft_config.get(key)) for key, desired in (draft_settings or {}).items())

    variables_to_check = variables.copy()
    has_file_name_changes = False

    for variable, value in variables.items():
        # The RAW editor posts a draft's retained value, so that is what "unchanged" means for it.
        setting = (drafted.get(variable) if draft_settings is not None else None) or config.get(variable, {"value": None, "global": True})
        if setting.get("global", True) and value == setting["value"]:
            del variables_to_check[variable]

    for setting_name, file_name in file_setting_names.items():
        current_file_name = str(config.get(setting_name, {}).get("file_name", "") or "").strip()
        if file_name != current_file_name:
            has_file_name_changes = True
            break

    # Same shape as services.py's `update_service`: a fresh, caller-owned list so a refusal
    # (reverted or dropped, either shape) decides the final flash instead of an unconditional
    # success -- see models/config.py:check_variables's own docstring for why this can't be a
    # before/after diff of DATA["TO_FLASH"] (its own load_from_file() reload hazard).
    refused: List[str] = []
    variables = BW_CONFIG.check_variables(variables, config, variables_to_check, global_config=True, threaded=True, refused=refused)
    refused_count = len(refused)
    # `variables_to_check` says "the user posted something for this key", not "the global value
    # changed". check_variables restores a rejected value to the stored one instead of dropping it
    # (models/config.py:reject_value), and it also canonicalizes values, so a key can come back out
    # of it holding exactly what is already stored. Propagating that is destructive, not a no-op:
    # the loop below would write the unchanged global onto every service and, with
    # override_non_global_services, onto services holding their OWN override -- which
    # config_save.py:1097 then deletes as redundant. Compare against the stored value so only a
    # real change propagates.
    changed_variables = {key: value for key, value in variables.items() if key in variables_to_check and value != config.get(key, {}).get("value")}
    # A drafted value is never applied, so it must not be copied onto the services either -- and a
    # draft activated by this save must, exactly like any other changed global value.
    drafts = draft_settings or {}
    changed_variables = {key: value for key, value in changed_variables.items() if drafts.get(key) is not True}
    changed_variables.update({key: variables[key] for key, desired in drafts.items() if desired is False and key in drafted and key in variables})

    no_removed_settings = True
    blacklist = get_blacklisted_settings(True)
    for setting in global_config_entries:
        if setting not in blacklist and setting not in variables:
            no_removed_settings = False
            break

    if no_removed_settings and not variables_to_check and not draft_state_changed and not has_file_name_changes:
        content = translated("global_settings.flash.not_edited_no_values_changed") or "The global settings were not edited because no values were changed."
        if discarded_draft_edits:
            content += f" {draft_edits_discarded()}"
        DATA["TO_FLASH"].append({"content": content, "type": "warning"})
        DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
        return

    # Posted, then refused -- and nothing else changed. The check above looks at what was POSTED,
    # so it let this through, and the save ended on "Global settings saved, but 1 value(s) were
    # refused." plus "The Scheduler will attempt to apply the changes." for a save that stored
    # nothing (QA-UI M15). `check_variables` has already said which value was refused and why.
    if refused_count and not changed_variables and no_removed_settings and not has_file_name_changes:
        DATA["TO_FLASH"].append(
            {
                "content": translated("global_settings.flash.global_settings_not_saved_every_changed")
                or "The global settings were not saved: every changed value was refused.",
                "type": "error",
            }
        )
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

    # Only a NEW key is checked: an emptied field removes the key, there is nothing to check (L21).
    if variables.get("PRO_LICENSE_KEY") and variables["PRO_LICENSE_KEY"] != config.get("PRO_LICENSE_KEY", {}).get("value"):
        DATA["TO_FLASH"].append(
            {
                "content": translated("global_settings.flash.checking_license_key_upgrade") or "Checking license key to upgrade.",
                "type": "success",
                "save": False,
            }
        )

    operation, error = BW_CONFIG.edit_global_conf(variables, check_changes=True, file_name_map=file_setting_names, draft_settings=draft_settings)

    if error:
        if operation:
            DATA["TO_FLASH"].append({"content": operation, "type": "error"})
    else:
        if refused_count:
            DATA["TO_FLASH"].append(
                {
                    "content": translated("global_settings.flash.saved_but_values_refused", refused_count=refused_count)
                    or f"Global settings saved, but {refused_count} values were refused.",
                    "type": "warning",
                }
            )
        else:
            DATA["TO_FLASH"].append(
                {"content": translated("global_settings.flash.saved_successfully") or "Global settings successfully saved.", "type": "success"}
            )
        if discarded_draft_edits:
            DATA["TO_FLASH"].append({"content": draft_edits_discarded(), "type": "warning"})
        DATA["TO_FLASH"].append(
            {
                "content": translated("flash.scheduler_will_attempt_apply_changes") or "The Scheduler will attempt to apply the changes.",
                "type": "success",
                "save": False,
            }
        )

    DATA["RELOADING"] = False


@global_settings.route("/global-config", methods=["GET", "POST"])
@global_settings.route("/global-settings", methods=["GET", "POST"])
@login_required
def global_settings_page():
    try:
        global_config = API_CLIENT.get_global_settings(full=True, methods=True)
    except (ApiClientError, ApiUnavailableError):
        flash(translated("flash.could_not_fetch_global_settings_api") or "Could not fetch global settings from the API.", "error")
        global_config = {}

    if request.method == "POST":
        if API_CLIENT.readonly:
            return handle_error(translated("flash.database_read_only_mode") or "Database is in read-only mode", "global_settings")
        # Not covered by the `is_readonly` the shelf scope carries below: that branch only runs in
        # `compose` mode, and this page SAVES as `advanced` by default (resolve_save_mode), where
        # `scope` stays None -- the historical "this payload is the complete desired state" save.
        # A session without `write` reaching here therefore writes every key it posted.
        if is_readonly_request(API_CLIENT.readonly):
            return handle_error(translated("flash.do_not_have_write_permission") or "You do not have the write permission", "global_settings")
        DATA.load_from_file()

        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]
        file_setting_names = extract_file_setting_names(variables)

        # Setting drafts travel as two JSON lists the RAW editor posts beside its values; any
        # other pane posting them is refused rather than silently drafting keys it never showed.
        # A RAW post without them changes no draft state, like every other pane.
        raw_draft_value = variables.pop(RAW_DRAFT_SETTINGS, None)
        raw_present_value = variables.pop(RAW_PRESENT_SETTINGS, None)
        draft_settings = None
        if resolve_save_mode(request.args.get("mode"), "advanced") != "raw":
            if raw_draft_value is not None or raw_present_value is not None:
                return handle_error(metadata_raw_only(), "global_settings")
        elif raw_draft_value is not None or raw_present_value is not None:
            try:
                saved_drafts = API_CLIENT.get_global_settings(full=True, methods=True, with_setting_drafts=True)
                draft_settings = parse_raw_draft_settings(
                    raw_draft_value,
                    posted_keys=set(variables),
                    present_value=raw_present_value,
                    existing_draft_keys=existing_draft_keys(saved_drafts),
                    settings=BW_CONFIG.get_plugins_settings(),
                    global_config=True,
                )
            except (ApiClientError, ApiUnavailableError):
                return handle_error(
                    translated("flash.could_not_fetch_global_settings_api") or "Could not fetch global settings from the API.", "global_settings"
                )
            except RawDraftSettingsError as error:
                return handle_error(str(error), "global_settings")

        override_non_global_services = variables.pop("OVERRIDE_NON_GLOBAL_SERVICES", variables.pop("OVERRIDE_TEMPLATE_SERVICES", "no")) == "yes"

        # Same contract as the service page: only the compose shelf posts a known subset and may
        # therefore declare a scope. `advanced` (this page's default, and where an unrecognised
        # mode from a bookmarked URL lands) and `raw` both post every rendered key, so they keep
        # the historical `scope=None`. See resolve_save_mode.
        scope = None
        if resolve_save_mode(request.args.get("mode"), "advanced") == "compose":
            try:
                metadata = API_CLIENT.get_metadata()
            except (ApiClientError, ApiUnavailableError):
                metadata = {}
            scope = postable_shelf_scope(
                BW_CONFIG.get_plugins(),
                global_config,
                global_page=True,
                is_pro_version=metadata.get("is_pro", False),
                blacklisted=get_blacklisted_settings(True),
                is_readonly=is_readonly_request(API_CLIENT.readonly),
            )

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        CONFIG_TASKS_EXECUTOR.submit(
            update_global_config, variables, override_non_global_services, file_setting_names, scope=scope, draft_settings=draft_settings
        )

        arguments = {}
        # Compared against this page's GET default (compose), not against the SAVE fallback
        # (advanced): this decides which pane to land back on, and omitting the argument lands on
        # the default one. See resolve_save_mode for why the two differ.
        if request.args.get("mode", "compose") != "compose":
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

    secrets = secret_setting_names(BW_CONFIG.get_plugins_settings())
    if request.args.get("as_json", "false").lower() == "true":
        # Read by template-settings-page.js to copy global values into a template: a secret is left
        # out, not masked, so a placeholder can never be copied into a template and saved there.
        return {key: value for key, value in global_config.items() if not is_secret_setting(key, secrets)}

    # Compose is this page's default pane since S3.4's chrome slice. The SAVE default stays
    # `advanced` on purpose -- see resolve_save_mode.
    mode = request.args.get("mode", "compose")
    search_type = request.args.get("type", "all")
    # The RAW pane shows setting drafts with their retained value; the compose pane keeps the
    # effective one. None falls back to `config` in the template.
    # Fail closed: falling back to the effective values would hand the RAW editor a draft-less
    # view, and saving it would activate, overwrite or delete a retained draft.
    try:
        raw_draft_config = API_CLIENT.get_global_settings(full=True, methods=True, with_setting_drafts=True)
    except (ApiClientError, ApiUnavailableError):
        return handle_error(translated("flash.could_not_fetch_global_settings_api") or "Could not fetch global settings from the API.", "home")
    return render_template(
        "global_settings.html",
        raw_draft_config=redact_secrets(raw_draft_config, secrets) if raw_draft_config else raw_draft_config,
        raw_draft_control_keys=sorted(STRUCTURAL_SETTINGS),
        mode=mode,
        type=search_type,
        # `full=True`, unlike the `config` main.py injects into every template
        # (main.py:1297, which omits it). The shelf reads activation off this map and
        # `is_plugin_active` defaults an ABSENT key to its INACTIVE value, so the injected map
        # would render every on-by-default plugin as off -- and the POST scope is computed from
        # THIS one (postable_shelf_scope above), so the two must be the same map or the shelf's
        # markup and its declared scope disagree, which is how in-scope keys go unposted and get
        # deleted (db_methods/config_save.py:592).
        # Secrets masked here and only here: the scope above is computed from the real map, and
        # masking changes values, never which keys exist.
        config=redact_secrets(global_config, secrets),
        # The shelf's required context; see models/compose_shelf.html for why none of it is
        # defaulted, and app/models/save_scope.py for why `control_keys(True)` is empty.
        shelf_plugin_scope=shelf_plugin_scope,
        activation_map=get_activation_map(),
        control_keys=control_keys,
        global_page=True,
        # NOT derived from `service_id`, which is also "" on /services/new -- this page has no
        # service at all, and the flag is what stops the shelf emitting SERVER_NAME (the service
        # LIST at global scope) as a control key.
        service_id="",
    )


@global_settings.route("/global-settings/plugins/<string:plugin>", methods=["GET", "POST"])
@login_required
def global_settings_plugin_page(plugin: str):
    """One plugin's settings at global scope. Renders declared settings only, no plugin code."""
    # `plugin` is a raw URL path segment -- resolve it by membership in the real plugin set
    # before doing anything else, and never interpolate it into a flash message:
    # flash.html/sidebar-notifications.html render flashes with |safe, so an unvalidated value
    # here is a reflected injection on the trusted UI origin. Mirrors the same guard on
    # services_plugin_page in routes/services.py.
    plugin_data = resolve_plugin(plugin, BW_CONFIG.get_plugins())
    if not plugin_data:
        LOGGER.warning(f"Plugin not found on the global plugin page: {plugin!r}")
        return handle_error(translated("flash.plugin_not_found") or "Plugin not found", "global_settings")

    try:
        global_config = API_CLIENT.get_global_settings(full=True, methods=True)
    except (ApiClientError, ApiUnavailableError):
        return handle_error(translated("flash.could_not_fetch_global_settings_api") or "Could not fetch global settings from the API.", "global_settings")

    if request.method == "POST":
        if API_CLIENT.readonly:
            return handle_error(translated("flash.database_read_only_mode") or "Database is in read-only mode", "global_settings")
        # The empty scope computed below is NOT a refusal: `restore_unowned_settings`
        # (models/save_scope.py:155) opens with `variables = dict(payload)` and from there only
        # ADDS stored keys back -- it never drops a posted one. The scope suppresses DELETIONS,
        # nothing else, so without this gate every value a forged POST carried was written. At
        # global scope that is a whole plugin's configuration.
        if is_readonly_request(API_CLIENT.readonly):
            return handle_error(translated("flash.do_not_have_write_permission") or "You do not have the write permission", "global_settings")

        DATA.load_from_file()
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]
        file_setting_names = extract_file_setting_names(variables)

        try:
            metadata = API_CLIENT.get_metadata()
        except (ApiClientError, ApiUnavailableError):
            metadata = {}

        # Same helper as the service pages, and it matters more here. When the page rendered
        # read-only every control is disabled, so the form posts nothing -- but csrf_token still
        # renders, so the POST is valid. Without this the scope would still claim the plugin's whole
        # global key set, and "in scope but not posted" means DELETE (db_methods/config_save.py:592):
        # a read-only user would wipe a plugin's entire global configuration, one plugin per POST.
        # On a service page the same POST is a harmless no-op; at global scope it is not.
        is_readonly = is_readonly_request(API_CLIENT.readonly)

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        CONFIG_TASKS_EXECUTOR.submit(
            update_global_config,
            variables,
            False,
            file_setting_names,
            scope=postable_scope(
                plugin_data,
                global_config,
                global_page=True,
                is_pro_version=metadata.get("is_pro", False),
                blacklisted=get_blacklisted_settings(True),
                is_readonly=is_readonly,
            ),
        )

        return redirect(
            url_for(
                "loading",
                next=url_for("global_settings.global_settings_plugin_page", plugin=plugin),
                message=f"Saving {plugin_data['name']} global settings",
            )
        )

    return render_template(
        "plugin_settings_page.html",
        plugin=plugin,
        plugin_data=plugin_data | {"id": plugin},
        config=redact_secrets(global_config, secret_setting_names(BW_CONFIG.get_plugins_settings())),
        service_id="",
        clone=None,
        # Same override body as the per-service page, same reasoning -- see services.py. Both
        # scopes get a plugin's custom form from one template; nothing here changes the writer.
        settings_body=plugin_settings_body(plugin),
        settings_body_script=plugin_settings_body_script(plugin),
    )
