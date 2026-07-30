import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from functools import lru_cache
from itertools import chain
from json import dumps, loads
from time import time
from typing import Any, Dict, List, Optional, Set, Tuple
from flask import Blueprint, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from regex import search, sub

from app.dependencies import API_CLIENT, BW_CONFIG, CONFIG_TASKS_EXECUTOR, CORE_PLUGINS_PATH, DATA
from app.api_client import ApiClientError, ApiUnavailableError
from app.models.save_scope import control_keys, restore_unowned_settings
from app.models.service_attachments import attached_ids, failed_families, get_service_attachments, resource_conflict_context

from app.routes.configs import EXPORT_FORMAT_VERSION, apply_imported_configs, flash_import_results, parse_configs_export
from app.routes.utils import CUSTOM_CONF_RX, extract_file_setting_names, handle_error, verify_data_in_form, wait_applying
from app.utils import (
    LOGGER,
    _SYNTHESIZED_ALWAYS_ON,
    flash,
    can_delete_service,
    get_activation_map,
    get_blacklisted_settings,
    is_editable_method,
    is_readonly_request,
    is_ui_api_method,
)

services = Blueprint("services", __name__)

ZIP_ALLOWED_MEMBERS = frozenset({"services_export.env", "configs_export.json"})
ZIP_MAX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024  # 20 MB aggregate cap guards against zip bombs.


def _configs_list_to_dict(configs_list):
    result = {}
    for c in configs_list:
        sid = c.get("service") or None
        sid = None if sid in ("global", "") else sid
        key = (f"{sid}_" if sid else "") + f"{c['type']}_{c['name']}"
        entry = dict(c)
        entry["service_id"] = sid
        entry.pop("service", None)
        if "data" in entry and isinstance(entry["data"], str):
            entry["data"] = entry["data"].encode("utf-8")
        result[key] = entry
    return result


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
    try:
        services_list = API_CLIENT.get_services(with_drafts=True)
    except (ApiClientError, ApiUnavailableError):
        flash("Could not fetch services from the API.", "error")
        services_list = []

    try:
        templates_data = API_CLIENT.get_templates()
    except (ApiClientError, ApiUnavailableError):
        flash("Could not fetch templates from the API.", "error")
        templates_data = {}

    services_with_configs: List[str] = []
    try:
        api_configs = API_CLIENT.get_configs(with_drafts=True, with_data=False)
    except (ApiClientError, ApiUnavailableError):
        flash("Could not fetch custom configurations from the API.", "error")
        api_configs = []

    seen_service_ids = set()
    for config in api_configs:
        service_id = config.get("service") or None
        if service_id in ("global", ""):
            service_id = None
        if not service_id:
            continue
        if config.get("template") or not is_editable_method(config.get("method")):
            continue
        seen_service_ids.add(service_id)
    services_with_configs = sorted(seen_service_ids)

    return render_template(
        "services.html",
        services=services_list,
        templates=templates_data,
        services_with_configs=services_with_configs,
    )


@services.route("/services/", methods=["GET"])
@login_required
def services_redirect():
    return redirect(url_for("services.services_page"))


@services.route("/services/convert", methods=["POST"])
@login_required
def services_convert():
    if API_CLIENT.readonly:
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

    services = [s for s in request.form["services"].split(",") if s.strip()]
    if not services:
        return handle_error("No services selected.", "services", True)

    convert_to = request.form["convert_to"]
    if convert_to not in ("online", "draft"):
        return handle_error("Invalid convert_to parameter.", "services", True)
    DATA.load_from_file()

    def convert_services(services: List[str], convert_to: str):
        wait_applying()

        db_services = API_CLIENT.get_services(with_drafts=True)
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

        db_config = BW_CONFIG.get_config(with_drafts=True, methods=False)
        for service in services_to_convert:
            db_config[f"{service}_IS_DRAFT"] = "yes" if convert_to == "draft" else "no"

        try:
            API_CLIENT.save_config(db_config, "ui", changed=True)
        except Exception as e:
            DATA["TO_FLASH"].append({"content": str(e), "type": "error"})
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
    if API_CLIENT.readonly:
        return handle_error("Database is in read-only mode", "services")

    verify_data_in_form(
        data={"services": None},
        err_message="Missing services parameter on /services/delete.",
        redirect_url="services",
        next=True,
    )
    services = [s for s in request.form["services"].split(",") if s.strip()]
    if not services:
        return handle_error("No services selected.", "services", True)
    DATA.load_from_file()

    def delete_services(services: List[str]):
        wait_applying()

        db_config = BW_CONFIG.get_config(methods=False, with_drafts=True)
        db_services = API_CLIENT.get_services(with_drafts=True)
        all_drafts = True
        services_to_delete = set()
        # Drafted autoconf services are hard-deleted via the API (DELETE /services/<id> routes them
        # to a method-agnostic delete); save_config(method="ui") would otherwise skip them.
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

        for service_id in autoconf_drafts_to_delete:
            try:
                API_CLIENT.delete_service(service_id)
            except (ApiClientError, ApiUnavailableError) as e:
                DATA["TO_FLASH"].append({"content": f"Failed to delete drafted autoconf service {service_id}: {e.message}", "type": "error"})
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


def build_service_attachments(service: str) -> dict:
    """Resources attached to ``service``, or empty entries for the "new" page.

    Kept as a named function rather than inlined so the route stays testable without
    a Flask request context.
    """
    return get_service_attachments(API_CLIENT, "" if service == "new" else service)


_DETACH_METHODS = {
    "upstream": "detach_upstream",
    "certificate": "detach_certificate",
    "redirect": "detach_redirect",
    "workflow": "detach_workflow",
}


def detach_service_resource(service: str, family: str, resource_id: str, match_path: str = ""):
    """Detach one resource from one service.

    ``family`` is validated against the known map rather than interpolated into a
    method name, so a crafted form field cannot reach an arbitrary client method.
    """
    if family not in _DETACH_METHODS:
        raise ValueError(f"Unknown resource family {family!r}")
    if API_CLIENT.readonly:
        raise PermissionError("The API is in read-only mode")

    method = getattr(API_CLIENT, _DETACH_METHODS[family])
    if family == "upstream":
        return method(resource_id, service, match_path=match_path)
    return method(resource_id, service)


@services.route("/services/<string:service>/resources/detach", methods=["POST"])
@login_required
def services_resource_detach(service: str):
    family = request.form.get("family", "")
    resource_id = request.form.get("resource_id", "")
    match_path = request.form.get("match_path", "")

    try:
        detach_service_resource(service, family, resource_id, match_path)
        flash(f"Detached the {family} from {service}.", "success")
    except PermissionError:
        flash("The API is in read-only mode, cannot detach.", "error")
    except ValueError:
        flash("Unknown resource type.", "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not detach: {exc.message}", "error")

    return redirect(url_for("services.services_service_page", service=service))


_ATTACH_METHODS = {
    "upstream": "attach_upstream",
    "certificate": "attach_certificate",
    "redirect": "attach_redirect",
    "workflow": "attach_workflow",
}


def attach_service_resource(service: str, family: str, resource_id: str, *, match_path: str = "/", primary: bool = False):
    """Attach one resource to one service.

    The API owns the conflict rules -- overlapping upstream match_path, colliding
    redirect paths, and demoting a previous primary certificate -- so this helper does
    not duplicate them; it surfaces the API's error instead.
    """
    if family not in _ATTACH_METHODS:
        raise ValueError(f"Unknown resource family {family!r}")
    if API_CLIENT.readonly:
        raise PermissionError("The API is in read-only mode")

    method = getattr(API_CLIENT, _ATTACH_METHODS[family])
    if family == "upstream":
        return method(resource_id, service, match_path=match_path or "/")
    if family == "certificate":
        return method(resource_id, service, primary=primary)
    return method(resource_id, service)


@services.route("/services/<string:service>/resources/attach", methods=["POST"])
@login_required
def services_resource_attach(service: str):
    family = request.form.get("family", "")
    resource_id = request.form.get("resource_id", "")
    match_path = request.form.get("match_path", "/")
    primary = request.form.get("primary", "no") == "yes"

    try:
        attach_service_resource(service, family, resource_id, match_path=match_path, primary=primary)
        flash(f"Attached the {family} to {service}.", "success")
    except PermissionError:
        flash("The API is in read-only mode, cannot attach.", "error")
    except ValueError:
        flash("Unknown resource type.", "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not attach: {exc.message}", "error")

    return redirect(url_for("services.services_service_page", service=service))


def resolve_plugin(plugin: str, plugins_data: Dict[str, dict]) -> Optional[dict]:
    """Look up a plugin id by membership in the real, installed plugin set.

    Strictly tighter than any regex: PLUGIN_NAME_RX's 4-64 character range rejected the real
    core plugin ids "db", "ui", "php", "pro" and "ssl" outright. A dict lookup accepts exactly
    the ids that exist and nothing else -- no traversal payload or malformed id is ever a
    member of `plugins_data`, and there is no length limit to get wrong.
    """
    return plugins_data.get(plugin)


def resolve_template(template: str, templates_data: Dict[str, dict]) -> Optional[dict]:
    """Look up a template id by membership in the real, installed template set.

    Same rule and the same reason as resolve_plugin: `template` is a raw URL path segment, and
    flash.html/sidebar-notifications.html render flashes with |safe, so it must never be
    regex-validated and then interpolated into one. A dict lookup accepts exactly the ids that
    exist; the caller logs the raw value and flashes a constant instead.
    """
    return templates_data.get(template)


def _base_setting_name(key: str) -> str:
    """Strip a trailing numeric multiple-suffix: "PROXY_HOST_2" -> "PROXY_HOST".

    Same rule as app/models/save_scope.py's `_in_scope`, which needs it to match a `multiple`
    setting's suffixed db_config key back to its plugin.json base name -- kept in sync by hand
    since the two live in different modules.
    """
    return key.rsplit("_", 1)[0] if search(r"_\d+$", key) else key


SAVE_MODES: Tuple[str, ...] = ("easy", "advanced", "raw", "compose")


def resolve_save_mode(mode: Optional[str], default: str) -> str:
    """Normalise the client-supplied `mode` down to what the SAVE path understands.

    `mode` is an ordinary query argument, not a route segment -- the pills are client-side tabs
    and `handleModeChange` (static/js/plugins-settings.js:565-595) syncs the URL with
    `history.pushState`. A bookmark, a stale tab or a Back navigation can therefore hand this
    route any string at all, so the fallback must be the branch that cannot destroy an
    unexpected payload: `Database.save_config` deletes any in-scope key the form did not post
    (db_methods/config_save.py:592), so the cost of guessing wrong is measured in deleted rows.

    THE FALLBACK IS NOT THE PAGE'S DEFAULT PANE, AND SINCE T7 IT IS DELIBERATELY NOT. Compose is
    what both pages now render by default, but the compose pane is a real `<form>` whose action
    carries `?mode=compose` literally (models/compose_pane.html), so a compose payload always
    says so and never needs the fallback. What still arrives with no mode at all is anything the
    monolith submits with `?mode=` stripped, and resolving THAT to `compose` would hand a partial
    payload the shelf's full scope. `easy` (service) and `advanced` (global) both stay preserving
    -- easy re-injects every stored value indiscriminately (:836-839), advanced declares no scope
    at all -- so falling through to them destroys nothing whatever posted.

    T8 removes the easy branch with the pane; the service fallback then becomes whichever branch
    is still the preserving one, never the compose scope.

    routes/templates.py's own VIEW_MODES is a different feature that happens to share the
    chrome; it is not routed through here.
    """
    return mode if mode in SAVE_MODES else default


def shelf_plugin_scope(
    plugin_id: str,
    plugin_data: dict,
    db_config: Dict[str, Dict[str, Any]],
    *,
    global_page: bool,
    is_pro_version: bool,
    blacklisted: Set[str],
    is_stream: bool = False,
    activation_map: Optional[Dict[str, Any]] = None,
) -> Set[str]:
    """The activation keys ONE compose-shelf row renders as an enabled, postable control.

    THIS IS THE CONTRACT THE SHELF MARKUP HAS TO HONOUR, and it is deliberately expressed as
    "what does the row post", never as "what does the activation map declare". A disabled input
    posts nothing, an unchecked checkbox posts nothing, and an in-scope key that is not posted
    has its row DELETED (db_methods/config_save.py:592) -- so over-claiming destroys data while
    under-claiming merely preserves it.

    All-or-nothing per plugin, because a shelf row carries ONE control for the whole plugin:
    either it renders enabled and posts every key returned here (ON with the new value, OFF with
    the declared inactive value, siblings with their currently resolved value -- see the
    USE_LIMIT_REQ/USE_LIMIT_CONN case below), or it renders no postable control and this returns
    an empty set. There is no half state to drift into.

    Empty -- no control, nothing owned -- when any of these holds:

    * ``extensions.activation: "always"``, or the synthesized always-on ``general``: the row says
      "Always on" and has no switch.
    * A declared activation key of `global` context on a service page. That also covers "the
      settings-driven loop renders no row for this plugin at all" (models/plugins_settings.html:137):
      a plugin with zero multisite settings cannot have a multisite activation key, so the per-key
      filter below is the same test as a `get_filtered_settings` emptiness check -- mutation-checked
      as equivalent, and `.get("context")` here does not raise on the malformed manifest that
      `get_filtered_settings`' `data["context"]` would. `backup` and `redis` are the live cases, and
      `models/config.py:61` would silently drop such a key from a service payload anyway.
    * A PRO plugin without an active licence, or a `stream: no` plugin on a stream service
      (`plugin_data["stream"]` has THREE values: yes / no / partial -- only the literal "no" is
      excluded).
    * A declared activation key that is blacklisted, or absent from the plugin's own settings, or
      whose stored method is not UI-editable and is not a global the service may override (the
      same formula as `postable_scope._passes`).
    * A declared activation key that is `multiple` or `multiselect`. Locked with the PO: those
      rows get a count and a chevron, never a switch, so they post nothing. Two live cases, both
      of which would be silent data loss if claimed: `country`'s BLACKLIST_COUNTRY /
      WHITELIST_COUNTRY are `multiselect`, and `redirect`'s REDIRECT_TO is `"multiple":
      "redirect"` -- and `_in_scope` base-matches (save_scope.py:39-40), so claiming REDIRECT_TO
      would drag every stored REDIRECT_TO_<n> into scope for a row that posts none of them.
      Excluding the key at source is why the compose save needs no `preserve_suffixed`.
    * A declared activation key of type `text`. The shelf gives these an OPENER, not a control --
      there is no switch that can author an HTML block or a PHP socket path -- so the row posts
      nothing and must own nothing. `inject`'s INJECT_BODY / INJECT_HEAD and `php`'s REMOTE_PHP /
      LOCAL_PHP are the four live cases. Round-tripping their stored value through a hidden input
      to keep them in scope is NOT a safe alternative: `Config.check_variables` normalises CRLF
      and `edit_service` runs `trim_scalar_value` (common_utils.py:163; `text` is not in
      `NO_TRIM_TYPES`), so a multi-line or trailing-newline global -- the normal shape for an HTML
      block -- comes back changed, `_is_default_value` no longer matches the global, and
      config_save materialises a real `ui` row that permanently decouples the service from it.
      Claiming them deletes; round-tripping them corrupts; excluding them does neither.

    Multi-key: `limit` declares {USE_LIMIT_REQ: "no", USE_LIMIT_CONN: "no"}, both `check`,
    both defaulting to "yes". "ON writes the first key" is only safe when the siblings are OUT of
    scope, and OFF needs them IN -- so both are returned, and the row must post BOTH on every
    save. Posting USE_LIMIT_REQ alone would leave USE_LIMIT_CONN in scope and unposted, delete its
    row, fall back to its "yes" default and silently turn the connection limiter ON.
    """
    declaration = (get_activation_map() if activation_map is None else activation_map).get(plugin_id)

    # No switch at all -- nothing rendered, nothing posted, nothing owned.
    if plugin_id in _SYNTHESIZED_ALWAYS_ON or declaration == "always":
        return set()

    settings = plugin_data.get("settings") or {}
    if plugin_data.get("type") == "pro" and not is_pro_version:
        return set()
    if not global_page and is_stream and plugin_data.get("stream") == "no":
        return set()

    if isinstance(declaration, dict):
        keys = set(declaration)
    else:
        # Tier 3, the naming convention every plugin that declares no manifest relies on. Same
        # USE_<ID>-then-USE_<NAME> order as is_plugin_active (app/utils.py:372), but resolved
        # against the plugin's DECLARED settings rather than the stored config: the shelf needs a
        # setting to render a control from, and a key with no declaration has no type, no legal
        # values and no inactive value.
        plugin_name_formatted = str(plugin_data.get("name", "")).replace(" ", "_").upper()
        candidate = next((key for key in (f"USE_{plugin_id.upper()}", f"USE_{plugin_name_formatted}") if key in settings), None)
        if candidate is None:
            return set()
        keys = {candidate}

    for key in keys:
        setting_data = settings.get(key)
        if setting_data is None or key in blacklisted:
            return set()
        if not global_page and setting_data.get("context") != "multisite":
            return set()
        if setting_data.get("multiple") or setting_data.get("type") in ("multiselect", "multivalue", "text"):
            return set()
        entry = db_config.get(key) or {}
        if not is_editable_method(entry.get("method", "default"), allow_default=True) and (global_page or not entry.get("global")):
            return set()

    return keys


def postable_shelf_scope(
    plugins_data: Dict[str, dict],
    db_config: Dict[str, Dict[str, Any]],
    *,
    global_page: bool,
    is_pro_version: bool,
    blacklisted: Set[str],
    is_readonly: bool = False,
    activation_map: Optional[Dict[str, Any]] = None,
) -> Set[str]:
    """Every key the compose shelf posts on this page: the union of `shelf_plugin_scope`.

    `is_readonly` disables every control at once, so the whole page posts nothing and owns
    nothing -- checked here rather than per plugin, exactly as `postable_scope` does.
    """
    if is_readonly:
        return set()

    # models/config.py:61 keys a service's server type off SERVER_TYPE; a stream service renders
    # no usable control for an http-only plugin. Global scope has no single server type.
    is_stream = not global_page and (db_config.get("SERVER_TYPE") or {}).get("value", "http") == "stream"
    if activation_map is None:
        activation_map = get_activation_map()

    scope: Set[str] = set()
    for plugin_id, plugin_data in plugins_data.items():
        scope |= shelf_plugin_scope(
            plugin_id,
            plugin_data,
            db_config,
            global_page=global_page,
            is_pro_version=is_pro_version,
            blacklisted=blacklisted,
            is_stream=is_stream,
            activation_map=activation_map,
        )
    return scope


def postable_scope(
    plugin_data: dict,
    db_config: Dict[str, Dict[str, Any]],
    *,
    global_page: bool,
    is_pro_version: bool,
    blacklisted: Set[str],
    is_readonly: bool = False,
) -> Set[str]:
    """The keys this page's form can actually submit, and is therefore authoritative for.

    Mirrors the `disabled` computation in models/plugin_settings_body.html. A disabled input posts
    nothing, and an in-scope key that is not posted has its row deleted
    (db_methods/config_save.py:592) -- so claiming authority over a key the form cannot send is a
    silent data-destroying bug, not a harmless over-claim.

    `is_readonly` mirrors the template's own top-of-body `is_readonly` branch, which disables
    every field regardless of method or PRO status -- so it is checked first, right beside the
    PRO short-circuit. A `multiple` setting is evaluated on each suffixed row's own stored entry
    (method/global), never the base/suffix-0 row, because that is what the template does in its
    multiples loop -- a plugin.json only names the base, but "PROXY_HOST_2" can be disabled while
    "PROXY_HOST" (suffix 0) is not, or vice versa.

    Deliberately conservative: when in doubt a key is left OUT of scope, which preserves it.
    """
    if is_readonly:
        return set()
    if plugin_data.get("type") == "pro" and not is_pro_version:
        return set()

    settings = plugin_data.get("settings") or {}

    def _passes(base_key: str, data: dict, entry: Dict[str, Any]) -> bool:
        if base_key in blacklisted:
            return False
        if not global_page and data.get("context") != "multisite":
            return False
        method = entry.get("method", "default")
        disabled = not is_editable_method(method, allow_default=True) and (global_page or not entry.get("global"))
        return not disabled

    scope: Set[str] = set()
    seen_bases: Set[str] = set()
    for key, entry in db_config.items():
        base = _base_setting_name(key)
        data = settings.get(base)
        if data is None:
            continue
        seen_bases.add(base)
        if _passes(base, data, entry):
            scope.add(key)

    # A declared setting with no stored row at all (suffixed or not) has no method to be
    # disabled by -- default it to "default" (editable) and keep it, same conservative-when-in-
    # doubt contract as before: a key that was never written cannot be deleted.
    for key, data in settings.items():
        if key in seen_bases:
            continue
        if _passes(key, data, {}):
            scope.add(key)

    return scope


def postable_template_scope(
    template_data: dict,
    db_config: Dict[str, Dict[str, Any]],
    *,
    blacklisted: Set[str],
    is_readonly: bool = False,
    template_editable: bool = True,
) -> Set[str]:
    """The keys this page's form can actually submit, and is therefore authoritative for.

    Mirrors the `disabled` computation in the stepper markup (models/plugins_settings_easy.html,
    extracted into models/template_steps_body.html). A disabled input posts nothing, and an
    in-scope key that is not posted has its row deleted (db_methods/config_save.py:592) -- so
    claiming authority over a key the form cannot send is silent data destruction, not a
    harmless over-claim. Deliberately conservative: when in doubt a key is left OUT, which
    preserves it.

    `is_readonly` and `template_editable` mirror the two branches that suppress every field at
    once: the template's own `{% if is_readonly %}{% set disabled = true %}`, and the
    "template in use" notice that renders *instead of* the stepper when the service already
    uses another template it may not edit.

    Candidates are exactly the keys named by a step -- not `template_data["settings"]`, not a
    plugin manifest, and NOT a stored key merely sharing a base name with one. The stepper is a
    flat `{% for setting in step["settings"] %}` emitting one `name="{{ setting }}"` input per
    step-named key (models/template_steps_body.html:115); unlike the per-plugin body
    (models/plugin_settings_body.html:122) it has no `get_multiples` loop, so a stored
    REVERSE_PROXY_HOST_1 is never rendered and never posted even when a step names the base.
    Claiming it here would delete it. A step's list may name a suffixed key directly
    (db_methods/templates.py:82 builds those) -- then and only then is that row in scope, and it
    is judged on its own stored entry.

    That is not sufficient on its own: save_scope.py:39-40 base-matches, so declaring the base
    pulls every stored suffix back into scope whatever this function returns. update_service
    re-injects those rows for `mode == "template"`; the two must stay together.

    There is deliberately no `multisite` context filter and no PRO check -- the stepper has
    neither, and adding one would drop a key the form does post.

    CUSTOM_CONF_* keys are never in scope: update_service strips them from `variables` before
    restore_unowned_settings runs, and they have no db_config rows.
    """
    if is_readonly or not template_editable:
        return set()

    scope: Set[str] = set()
    for step in template_data.get("steps") or []:
        for setting in step.get("settings") or []:
            if setting in blacklisted:
                continue
            # A step-named key with no stored row at all has no method to be disabled by --
            # "default" is editable under allow_default, and a key that was never written
            # cannot be deleted anyway.
            entry = db_config.get(setting) or {}
            method = entry.get("method", "default")
            if is_editable_method(method, allow_default=True) or entry.get("global"):
                scope.add(setting)

    return scope


def update_service(
    service: str,
    variables: Dict[str, str],
    is_draft: bool,
    mode: str,
    clone: str,
    file_setting_names: Dict[str, str],
    *,
    scope: Optional[Set[str]] = None,
):
    wait_applying()

    if clone and service == "new":
        cloned_service_config = {k: v for k, v in API_CLIENT.get_service(clone, full=True, methods=False, with_drafts=True).items()}
        clone_prefix = f"{clone}_"

        for key, value in cloned_service_config.items():
            # Strip the clone service prefix from keys so they are recognized as valid setting names
            stripped_key = key.removeprefix(clone_prefix)
            if stripped_key in variables or stripped_key in ("SERVER_NAME", "OLD_SERVER_NAME", "IS_DRAFT", "USE_UI"):
                continue

            variables[stripped_key] = value

    # Edit check fields and remove already existing ones
    if service != "new":
        db_config = API_CLIENT.get_service(service, full=True, methods=True, with_drafts=True)
    else:
        db_config = API_CLIENT.get_global_settings(full=True, methods=True)

    service_method = db_config.get("SERVER_NAME", {}).get("method", "ui") if service != "new" else "ui"
    override_method = service_method if is_editable_method(service_method) else "ui"

    was_draft = db_config.get("IS_DRAFT", {"value": "no"})["value"] == "yes"

    old_server_name = variables.pop("OLD_SERVER_NAME", "")
    db_custom_configs = {}
    all_custom_configs = _configs_list_to_dict(API_CLIENT.get_configs(with_drafts=True, with_data=True))
    removed_custom_configs: set[str] = set()
    new_configs = set()
    configs_changed = False

    if mode in ("easy", "template"):
        db_templates = API_CLIENT.get_templates()
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
                # `data` is None on the default dict above, which is reached whenever the lookup
                # misses. Two ways for it to miss, both live:
                #  * the config belongs to a template the service does not use -- the overlay is
                #    materialised only for the service's own USE_TEMPLATE
                #    (db_methods/custom_configs.py:218-221), and the per-template page can be
                #    opened for any template, so this is the common one;
                #  * the type carries an underscore -- custom_configs.py:222 keys the overlay
                #    hyphenated ({svc}_modsec-crs_api) while the key built above is underscored,
                #    and the shipped `api` template ships modsec-crs/api.conf.
                # Either way this line raises AttributeError today, inside a worker thread where
                # it would strand DATA["RELOADING"]. The key-format mismatch is out of scope here.
                elif value == (db_custom_config["data"] or b"").strip():
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

        # Easy mode's second restore layer, deliberately NOT extended to the template page:
        # restore_unowned_settings (below) covers it with a declared scope instead. Do not
        # unify the two -- this one re-injects indiscriminately, which also stops a legitimate
        # clear of a ui-method setting from going through.
        if mode == "easy" and service != "new":
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

    # Which stored settings must survive this save -- see app/models/save_scope.py.
    # `scope=None` keeps the historical method-based behaviour; the per-plugin and
    # per-template pages (S3.2, S3.3) pass the key set they own instead.
    # `restore_skip` is the blacklist plus exactly the keys this page must post itself -- one
    # definition, so a control key added to the shelf cannot be left out of the skip set (or
    # vice versa) and quietly start being restored instead of posted.
    restore_skip = get_blacklisted_settings() | set(control_keys())
    if service != "new" and mode != "easy":
        old_template = db_config.get("USE_TEMPLATE", {}).get("value", "")
        new_template = variables.get("USE_TEMPLATE", "")
        variables = restore_unowned_settings(
            variables,
            db_config,
            scope=scope,
            restore_skip=restore_skip,
            template_unchanged=old_template == new_template,
            # The stepper has no multiples cloner -- one input per step-named key
            # (models/template_steps_body.html:115 vs models/plugin_settings_body.html:122) -- so
            # a stored REVERSE_PROXY_HOST_1 is never posted, while save_scope.py:39-40
            # base-matches it into the scope declared for REVERSE_PROXY_HOST and would DELETE it.
            # The compose shelf needs no such flag: shelf_plugin_scope drops `multiple`
            # activation keys at source, so no suffix is ever base-matched into its scope.
            preserve_suffixed=mode == "template",
        )

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

    if no_removed_settings and service != "new" and was_draft == is_draft and not variables_to_check and not configs_changed and not has_file_name_changes:
        DATA["TO_FLASH"].append(
            {
                "content": f"The service {service} was not edited because no values{' or custom configs' if mode in ('easy', 'template') else ''} were changed.",
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
            # Use per-config create/update to avoid bulk delete when renaming services
            for custom_config in final_custom_configs.values():
                conf_data = custom_config.get("data")
                if isinstance(conf_data, bytes):
                    conf_data = conf_data.decode("utf-8", errors="replace")
                try:
                    API_CLIENT.create_config(
                        service=custom_config.get("service_id"),
                        type=custom_config.get("type"),
                        name=custom_config.get("name"),
                        data=conf_data or "",
                        is_draft=custom_config.get("is_draft", False),
                    )
                except Exception as create_err:
                    if "already exists" in str(create_err):
                        try:
                            API_CLIENT.update_config(
                                custom_config.get("service_id"),
                                custom_config.get("type"),
                                custom_config.get("name"),
                                data=conf_data or "",
                                is_draft=custom_config.get("is_draft", False),
                            )
                        except Exception as update_err:
                            DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {update_err}", "type": "error"})
                            break
                    else:
                        DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {create_err}", "type": "error"})
                        break
        else:
            serializable_configs = []
            for cfg in final_custom_configs.values():
                cfg_copy = cfg.copy()
                if isinstance(cfg_copy.get("data"), bytes):
                    cfg_copy["data"] = cfg_copy["data"].decode("utf-8", errors="replace")
                serializable_configs.append(cfg_copy)
            try:
                API_CLIENT.bulk_save_configs(
                    serializable_configs,
                    override_method,
                    changed=service != "new" and (was_draft != is_draft or not is_draft),
                )
            except Exception as e:
                DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {e}", "type": "error"})

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


def inject_template_dom_ids(templates_data: Dict[str, dict]) -> Dict[str, dict]:
    """Give every template a DOM-safe, unique `dom_id` -- the API payload carries none.

    Mutates in place and returns the same dict. Shared by the service page and the per-template
    page: the stepper's ids (`navs-steps-<dom_id>-<n>`) and the JS that keys off them come from
    here, so a route that skips this renders a stepper whose navigation silently no-ops. Run it
    over the *whole* templates map before narrowing to one entry, or the dedupe suffix can
    differ between the two pages.
    """
    used_dom_ids = set()

    for template_id, template_data in templates_data.items():
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

    return templates_data


@lru_cache(maxsize=1)
def core_plugin_order() -> Dict[str, List[str]]:
    """`core/order.json`, the `{phase: [plugin ids]}` map the request-path strip fills pass 2 from.

    Cached: it is a shipped file that only changes with the image, and the strip reads it on every
    service page render. Missing or unreadable is not an error -- the partial documents `{}` as a
    supported value (a service whose `PLUGINS_ORDER_<PHASE>` was overridden with a partial list then
    shows the remainder in the unordered group instead of in the middle; nothing is ever dropped).
    """
    try:
        order = loads((CORE_PLUGINS_PATH / "order.json").read_text(encoding="utf-8"))
    except BaseException as e:  # noqa: B036 -- a strip that cannot be ordered must not 500 the page
        LOGGER.debug(f"Could not read the core plugin order: {e}")
        return {}
    return order if isinstance(order, dict) else {}


@services.route("/services/<string:service>", methods=["GET", "POST"])
@login_required
def services_service_page(service: str):
    try:
        services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split()
    except Exception:
        flash("Could not fetch services configuration.", "error")
        services = []
    service_exists = service in services

    if service != "new" and not service_exists:
        return redirect(url_for("services.services_page"))

    if request.method == "POST":
        if API_CLIENT.readonly:
            return handle_error("Database is in read-only mode", "services")

        DATA.load_from_file()

        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]
        file_setting_names = extract_file_setting_names(variables)

        # Resolved centrally against this page's own GET default, so an unrecognised `mode` saves
        # the way the pane it renders posts. See resolve_save_mode.
        mode = resolve_save_mode(request.args.get("mode"), "easy")
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

        # Only the compose shelf declares a scope, because only it renders a form that posts a
        # KNOWN subset. `easy`, `advanced` and `raw` keep the historical `scope=None` -- the
        # method-based restore for the first two, "this payload is the complete desired state"
        # for raw. Declaring a scope for a pane that does not render the shelf pairs a partial
        # payload with authority to delete what it never posted. A new service has no stored rows
        # to protect either (update_service skips the restore for it entirely, and db_config
        # would be the GLOBAL config there).
        scope = None
        if mode == "compose" and service != "new":
            try:
                scope_config = API_CLIENT.get_service(service, full=True, methods=True, with_drafts=True)
            except (ApiClientError, ApiUnavailableError):
                return handle_error("Could not fetch service from the API.", "services")
            try:
                metadata = API_CLIENT.get_metadata()
            except (ApiClientError, ApiUnavailableError):
                metadata = {}
            scope = postable_shelf_scope(
                BW_CONFIG.get_plugins(),
                scope_config,
                global_page=False,
                is_pro_version=metadata.get("is_pro", False),
                blacklisted=get_blacklisted_settings(),
                is_readonly=is_readonly_request(API_CLIENT.readonly),
            )

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        CONFIG_TASKS_EXECUTOR.submit(update_service, service, variables.copy(), is_draft, mode, clone, file_setting_names, scope=scope)

        new_service = False
        if service == "new":
            if "SERVER_NAME" not in variables:
                return redirect(url_for("loading", next=url_for("services.services_page")))
            new_service = True
            service = variables["SERVER_NAME"].split(" ")[0]

        arguments = {}
        # Which PANE to come back to, which is not the same question as which save path ran: the
        # user is still looking at whichever tab they submitted from. Keyed off the raw argument
        # so this stays a display decision, and compared against `compose` because that is this
        # page's GET default -- omitting the argument lands back on it.
        requested_mode = request.args.get("mode", "compose")
        if requested_mode != "compose":
            arguments["mode"] = requested_mode
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

    # Compose is this page's default pane since S3.4's chrome slice. The SAVE default stays
    # `easy` on purpose -- see resolve_save_mode.
    mode = request.args.get("mode", "compose")
    search_type = request.args.get("type", "all")
    template = request.args.get("template", "low")

    try:
        db_templates = API_CLIENT.get_templates()
    except (ApiClientError, ApiUnavailableError):
        flash("Could not fetch templates from the API.", "error")
        db_templates = {}

    inject_template_dom_ids(db_templates)

    try:
        db_custom_configs = _configs_list_to_dict(API_CLIENT.get_configs(with_drafts=True, with_data=True))
    except (ApiClientError, ApiUnavailableError):
        flash("Could not fetch custom configs from the API.", "error")
        db_custom_configs = {}

    clone = None
    if service == "new":
        clone = request.args.get("clone", "")
        try:
            db_config = API_CLIENT.get_global_settings(full=True, methods=True)
        except (ApiClientError, ApiUnavailableError):
            flash("Could not fetch global settings from the API.", "error")
            db_config = {}

        if clone:
            try:
                clone_service_data = API_CLIENT.get_service(clone, full=True, methods=True, with_drafts=True)
            except (ApiClientError, ApiUnavailableError):
                flash(f"Could not fetch service {clone} for cloning.", "error")
                clone_service_data = {}

            for key, setting in clone_service_data.items():
                original_value = db_config.get(key, {}).get("value")
                db_config[key] = setting | {"clone": original_value != setting.get("value")}
            if "SERVER_NAME" in db_config:
                db_config["SERVER_NAME"].update({"value": "", "clone": False})
            if "USE_UI" in db_config:
                db_config["USE_UI"].update({"value": "no", "clone": False})
            for key, value in list(db_custom_configs.items()):
                if key.startswith(f"{clone}_"):
                    db_custom_configs[key.replace(f"{clone}_", f"{service}_", 1)] = value
    else:
        try:
            db_config = API_CLIENT.get_service(service, full=True, methods=True, with_drafts=True)
        except (ApiClientError, ApiUnavailableError):
            flash(f"Could not fetch service {service} from the API.", "error")
            db_config = {}

    attachments = build_service_attachments(service)

    # The band only knows what is already attached; the attach picker needs the
    # unattached candidates too, per family, so it fans out to the same four getters.
    attach_candidates: dict = {}
    if service != "new":
        for family, (getter, rows_key) in (
            ("upstream", ("get_upstreams", "upstreams")),
            ("certificate", ("get_certificates", "certificates")),
            ("redirect", ("get_redirects", "redirects")),
            ("workflow", ("get_workflows", "workflows")),
        ):
            try:
                payload = getattr(API_CLIENT, getter)(limit=500)
            except (ApiClientError, ApiUnavailableError):
                attach_candidates[family] = []
                continue
            rows = payload.get(rows_key, [])
            if family == "upstream":
                # An upstream pool can be attached to the same service at more than one
                # path, so an already-attached pool must stay a candidate -- unlike the
                # other families, which only ever attach once.
                attach_candidates[family] = rows
            else:
                already = attached_ids(attachments, family)
                attach_candidates[family] = [row for row in rows if row.get("id") not in already]

    for family in failed_families(attachments):
        flash(f"Could not fetch attached {family}s for this service.", "error")

    service_id = "" if service == "new" else service
    return render_template(
        "service_settings.html",
        config=db_config,
        templates=db_templates,
        configs=db_custom_configs,
        clone=clone,
        mode=mode,
        type=search_type,
        current_template=template,
        attachments=attachments,
        attach_candidates=attach_candidates,
        service_id=service_id,
        # The compose shelf's required context (models/compose_shelf.html documents why none of
        # it is defaulted): the scope function ITSELF, so the row's markup and the save path can
        # never derive it differently, and the activation map read once here rather than per row
        # -- `is_plugin_active` re-reads it internally and returns {} on a scan failure, which
        # would silently drop every plugin to the USE_<ID> convention.
        shelf_plugin_scope=shelf_plugin_scope,
        activation_map=get_activation_map(),
        control_keys=control_keys,
        global_page=False,
        # What the attach dialog needs to refuse a conflict before the API does; `db_config` adds
        # the inline half of the location namespace (app/models/service_attachments.py).
        resource_conflicts=resource_conflict_context(attachments, service_id, db_config),
        plugin_order=core_plugin_order(),
    )


@services.route("/services/<string:service>/plugins/<string:plugin>", methods=["GET", "POST"])
@login_required
def services_plugin_page(service: str, plugin: str):
    """One plugin's settings for one service.

    Renders the plugin's own declared settings only -- it loads no plugin code, which is what
    keeps this out of the threat model that governs plugin-supplied pages (S4).
    """
    # `plugin` is a raw URL path segment -- resolve it by membership in the real plugin set
    # before doing anything else, and never interpolate it into a flash message:
    # flash.html/sidebar-notifications.html render flashes with |safe, so an unvalidated value
    # here is a reflected injection on the trusted UI origin. Membership is strictly tighter
    # than a regex (see resolve_plugin) and the warning below carries the raw value instead.
    plugin_data = resolve_plugin(plugin, BW_CONFIG.get_plugins())
    if not plugin_data:
        LOGGER.warning(f"Plugin not found on the service plugin page: {plugin!r}")
        return handle_error("Plugin not found", "services")

    try:
        db_config = API_CLIENT.get_service(service, full=True, methods=True, with_drafts=True)
    except (ApiClientError, ApiUnavailableError):
        LOGGER.warning(f"Could not fetch service from the API on the service plugin page: {service!r}")
        return handle_error("Could not fetch service from the API.", "services")
    if not db_config:
        LOGGER.warning(f"Service not found on the service plugin page: {service!r}")
        return handle_error("Service not found", "services")

    if request.method == "POST":
        if API_CLIENT.readonly:
            return handle_error("Database is in read-only mode", "services")

        DATA.load_from_file()
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]
        file_setting_names = extract_file_setting_names(variables)
        is_draft = variables.pop("IS_DRAFT", "no") == "yes"

        try:
            metadata = API_CLIENT.get_metadata()
        except (ApiClientError, ApiUnavailableError):
            metadata = {}

        # One helper, four call sites -- see app/utils.py:is_readonly_request. The API's own
        # readonly state is already ruled out by the early return above, so in practice this is
        # the transient-user-permission-load-error case.
        is_readonly = is_readonly_request(API_CLIENT.readonly)

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        CONFIG_TASKS_EXECUTOR.submit(
            update_service,
            service,
            variables.copy(),
            is_draft,
            "compose",
            "",
            file_setting_names,
            scope=postable_scope(
                plugin_data,
                db_config,
                global_page=False,
                is_pro_version=metadata.get("is_pro", False),
                blacklisted=get_blacklisted_settings(),
                is_readonly=is_readonly,
            ),
        )

        return redirect(
            url_for(
                "loading",
                # A rename makes this page's own URL dead (the path param still names the
                # pre-rename service, so the GET would flash "Service not found" next to the
                # success message). Same post-rename destination as the legacy page, :952-960.
                next=(
                    url_for("services.services_plugin_page", service=service, plugin=plugin)
                    if variables.get("SERVER_NAME", service).split(" ")[0] == service
                    else url_for("services.services_page")
                ),
                message=f"Saving {plugin_data['name']} settings for service {service}",
            )
        )

    return render_template(
        "plugin_settings_page.html",
        plugin=plugin,
        plugin_data=plugin_data | {"id": plugin},
        config=db_config,
        service_id=service,
        clone=None,
    )


@services.route("/services/<string:service>/templates/<string:template>", methods=["GET", "POST"])
@login_required
def services_template_page(service: str, template: str):
    """One template's guided steps for one service.

    Renders the template's own declared steps only, and declares the key set they can post
    (postable_template_scope) so a save cannot reach a setting this page never showed.
    """
    try:
        db_templates = API_CLIENT.get_templates()
    except (ApiClientError, ApiUnavailableError):
        LOGGER.warning("Could not fetch templates from the API on the service template page.")
        return handle_error("Could not fetch templates from the API.", "services")

    # `template` is a raw URL path segment -- resolve it by membership before anything else and
    # never interpolate it into a flash message (flashes render with |safe). See resolve_template.
    template_data = resolve_template(template, db_templates)
    if not template_data:
        LOGGER.warning(f"Template not found on the service template page: {template!r}")
        return handle_error("Template not found", "services")

    try:
        db_config = API_CLIENT.get_service(service, full=True, methods=True, with_drafts=True)
    except (ApiClientError, ApiUnavailableError):
        LOGGER.warning(f"Could not fetch service from the API on the service template page: {service!r}")
        return handle_error("Could not fetch service from the API.", "services")
    if not db_config:
        LOGGER.warning(f"Service not found on the service template page: {service!r}")
        return handle_error("Service not found", "services")

    template_method = db_config.get("USE_TEMPLATE", {}).get("method", "ui")
    selected_template = db_config.get("USE_TEMPLATE", {}).get("value", "")
    # models/template_steps_body.html:48 -- a service locked to another template renders the
    # "template in use" notice instead of any field, so the form posts nothing at all.
    template_editable = is_editable_method(template_method) or not selected_template or template == selected_template

    if request.method == "POST":
        if API_CLIENT.readonly:
            return handle_error("Database is in read-only mode", "services")

        DATA.load_from_file()
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]
        file_setting_names = extract_file_setting_names(variables)
        is_draft = variables.pop("IS_DRAFT", "no") == "yes"

        # One helper, four call sites -- see app/utils.py:is_readonly_request. The API's own
        # readonly state is already ruled out by the early return above, so in practice this is
        # the transient-user-permission-load-error case.
        is_readonly = is_readonly_request(API_CLIENT.readonly)

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        CONFIG_TASKS_EXECUTOR.submit(
            update_service,
            service,
            variables.copy(),
            is_draft,
            "template",
            "",
            file_setting_names,
            scope=postable_template_scope(
                template_data,
                db_config,
                blacklisted=get_blacklisted_settings(),
                is_readonly=is_readonly,
                template_editable=template_editable,
            ),
        )

        return redirect(
            url_for(
                "loading",
                # `low` step 1 renders SERVER_NAME as an editable, required field, so a rename
                # is a supported save here and it makes this page's own URL dead. Same
                # post-rename destination as the legacy page, :952-960.
                next=(
                    url_for("services.services_template_page", service=service, template=template)
                    if variables.get("SERVER_NAME", service).split(" ")[0] == service
                    else url_for("services.services_page")
                ),
                message=f"Saving template settings for service {service}",
            )
        )

    # dom_ids are derived across the whole map, then the page keeps the single pane it renders.
    inject_template_dom_ids(db_templates)

    try:
        db_custom_configs = _configs_list_to_dict(API_CLIENT.get_configs(with_drafts=True, with_data=True))
    except (ApiClientError, ApiUnavailableError):
        flash("Could not fetch custom configs from the API.", "error")
        db_custom_configs = {}

    # service_settings.html:5-8 sets these four with {% set %}; this page does not go through it.
    return render_template(
        "template_settings_page.html",
        config=db_config,
        templates={template: template_data},
        configs=db_custom_configs,
        service_id=service,
        clone=None,
        is_draft=db_config.get("IS_DRAFT", {}).get("value", "no"),
        service_method=db_config.get("SERVER_NAME", {}).get("method", "ui"),
        template_method=template_method,
        selected_template=selected_template,
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
    try:
        db_configs = API_CLIENT.get_configs(with_drafts=True, with_data=True)
    except (ApiClientError, ApiUnavailableError):
        return handle_error("Could not fetch custom configurations from the API.", "services", True)
    configs_payload: List[Dict] = []
    for db_config_row in db_configs:
        service_id = db_config_row.get("service") or None
        if service_id in ("global", ""):
            service_id = None
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
                "type": db_config_row["type"].strip().replace("-", "_").lower(),
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
    if API_CLIENT.readonly:
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

        existing_services = {service["id"] for service in API_CLIENT.get_services(with_drafts=True)}
        base_config = API_CLIENT.get_global_settings(full=True, methods=True)
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
