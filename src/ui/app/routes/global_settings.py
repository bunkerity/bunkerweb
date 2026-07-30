from contextlib import suppress
from time import time
from typing import Dict, Optional, Set

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import API_CLIENT, BW_CONFIG, CONFIG_TASKS_EXECUTOR, DATA
from app.api_client import ApiClientError, ApiUnavailableError
from app.models.save_scope import control_keys, restore_unowned_settings
from app.routes.services import postable_scope, postable_shelf_scope, resolve_plugin, resolve_save_mode, shelf_plugin_scope
from app.utils import LOGGER, flash, get_activation_map, get_blacklisted_settings, is_readonly_request

from app.routes.utils import extract_file_setting_names, handle_error, wait_applying

global_settings = Blueprint("global_settings", __name__)


def update_global_config(
    variables: Dict[str, str],
    override_non_global_services: bool,
    file_setting_names: Dict[str, str],
    *,
    scope: Optional[Set[str]] = None,
):
    wait_applying()

    # Edit check fields and remove already existing ones
    config = BW_CONFIG.get_config(methods=True, with_drafts=True)

    services = config["SERVER_NAME"]["value"].split()

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

    variables_to_check = variables.copy()
    has_file_name_changes = False

    for variable, value in variables.items():
        setting = config.get(variable, {"value": None, "global": True})
        if setting["global"] and value == setting["value"]:
            del variables_to_check[variable]

    for setting_name, file_name in file_setting_names.items():
        current_file_name = str(config.get(setting_name, {}).get("file_name", "") or "").strip()
        if file_name != current_file_name:
            has_file_name_changes = True
            break

    variables = BW_CONFIG.check_variables(variables, config, variables_to_check, global_config=True, threaded=True)
    # `variables_to_check` says "the user posted something for this key", not "the global value
    # changed". check_variables restores a rejected value to the stored one instead of dropping it
    # (models/config.py:reject_value), and it also canonicalizes values, so a key can come back out
    # of it holding exactly what is already stored. Propagating that is destructive, not a no-op:
    # the loop below would write the unchanged global onto every service and, with
    # override_non_global_services, onto services holding their OWN override -- which
    # config_save.py:1097 then deletes as redundant. Compare against the stored value so only a
    # real change propagates.
    changed_variables = {key: value for key, value in variables.items() if key in variables_to_check and value != config.get(key, {}).get("value")}

    no_removed_settings = True
    blacklist = get_blacklisted_settings(True)
    for setting in global_config_entries:
        if setting not in blacklist and setting not in variables:
            no_removed_settings = False
            break

    if no_removed_settings and not variables_to_check and not has_file_name_changes:
        content = "The global settings were not edited because no values were changed."
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

    operation, error = BW_CONFIG.edit_global_conf(variables, check_changes=True, file_name_map=file_setting_names)

    if not error:
        operation = "Global settings successfully saved."

    if operation:
        if operation.startswith(("Can't", "The database is read-only")):
            DATA["TO_FLASH"].append({"content": operation, "type": "error"})
        else:
            DATA["TO_FLASH"].append({"content": operation, "type": "success"})
            DATA["TO_FLASH"].append({"content": "The Scheduler will be in charge of applying the changes.", "type": "success", "save": False})

    DATA["RELOADING"] = False


@global_settings.route("/global-config", methods=["GET", "POST"])
@global_settings.route("/global-settings", methods=["GET", "POST"])
@login_required
def global_settings_page():
    try:
        global_config = API_CLIENT.get_global_settings(full=True, methods=True)
    except (ApiClientError, ApiUnavailableError):
        flash("Could not fetch global settings from the API.", "error")
        global_config = {}

    if request.method == "POST":
        if API_CLIENT.readonly:
            return handle_error("Database is in read-only mode", "global_settings")
        DATA.load_from_file()

        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]
        file_setting_names = extract_file_setting_names(variables)
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
        CONFIG_TASKS_EXECUTOR.submit(update_global_config, variables, override_non_global_services, file_setting_names, scope=scope)

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
    elif request.args.get("as_json", "false").lower() == "true":
        return global_config

    # Compose is this page's default pane since S3.4's chrome slice. The SAVE default stays
    # `advanced` on purpose -- see resolve_save_mode.
    mode = request.args.get("mode", "compose")
    search_type = request.args.get("type", "all")
    return render_template(
        "global_settings.html",
        mode=mode,
        type=search_type,
        # `full=True`, unlike the `config` main.py injects into every template
        # (main.py:1297, which omits it). The shelf reads activation off this map and
        # `is_plugin_active` defaults an ABSENT key to its INACTIVE value, so the injected map
        # would render every on-by-default plugin as off -- and the POST scope is computed from
        # THIS one (postable_shelf_scope above), so the two must be the same map or the shelf's
        # markup and its declared scope disagree, which is how in-scope keys go unposted and get
        # deleted (db_methods/config_save.py:592).
        config=global_config,
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
        return handle_error("Plugin not found", "global_settings")

    try:
        global_config = API_CLIENT.get_global_settings(full=True, methods=True)
    except (ApiClientError, ApiUnavailableError):
        return handle_error("Could not fetch global settings from the API.", "global_settings")

    if request.method == "POST":
        if API_CLIENT.readonly:
            return handle_error("Database is in read-only mode", "global_settings")

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
        config=global_config,
        service_id="",
        clone=None,
    )
