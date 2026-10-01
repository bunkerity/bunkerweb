from contextlib import suppress
from datetime import datetime
from hmac import compare_digest
from json import JSONDecodeError, dumps, loads
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from flask import Blueprint, Response, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from markupsafe import escape

from requests.exceptions import RequestException

from common_utils import normalize_check_value, normalize_list_value, split_templates, trim_scalar_value  # type: ignore
from default_server import is_reserved_default_server  # type: ignore
from template_package import PACKAGE_FORMAT, PACKAGE_MAX, TEMPLATE_ID_RX, parse_package, template_from_archive  # type: ignore
from unit_parser import normalize_unit  # type: ignore

from app.dependencies import API_CLIENT, BW_CONFIG, DATA
from app.api_client import ApiClientError, ApiUnavailableError
from app.i18n import plugin_text, setting_text, translated
from app.routes.configs import CONFIG_TYPES
from app.models.plugin_catalog import (
    SOURCES,
    build_catalog_view,
    catalog_enabled,
    fetch_archive,
    find_item,
    is_stale,
    item_compatible,
    read_cached,
    template_fingerprint,
    template_payload,
    template_state,
    update_token,
    verify_digest,
)
from app.routes.utils import cors_required
from app.utils import LOGGER, flash

templates = Blueprint("templates", __name__)

VIEW_MODES = {"easy", "raw"}

# Human-readable labels for custom-config types (config keys stored as "type/name.conf" --
# see db_methods/templates.py's get_templates()). Falls back to a titleized type when a
# CUSTOM_CONFIGS_TYPES_ENUM value isn't listed here (e.g. a future type).
_CONFIG_TYPE_LABELS: Dict[str, str] = {
    "http": "HTTP",
    "stream": "Stream",
    "server_http": "Server HTTP",
    "server_stream": "Server stream",
    "default_server_http": "Default server",
    "modsec": "ModSecurity",
    "modsec_crs": "CRS",
    "crs_plugins_before": "CRS plugins (before)",
    "crs_plugins_after": "CRS plugins (after)",
}

# Rank + Bootstrap styling for each badge type, mirroring the design kit's tplTagRank
# (plugin -> config -> feature) ordering -- see _template_tag_badges().
_BADGE_TYPE_META: Dict[str, Dict[str, Any]] = {
    "plugin": {"rank": 0, "variant": "primary", "icon": "bx-plug"},
    "config": {"rank": 1, "variant": "secondary", "icon": "bx-file-blank"},
    "feature": {"rank": 2, "variant": "success", "icon": "bx-package"},
}

# Kit tplCard cards show a small MIX of chip colors, not a monochrome flood of one type.
# Classify each owning plugin so a template's chips read as a mix: security plugins stay
# green ("plugin"), header/rule/CORS config surfaces go navy ("config"), and performance
# behaviors go amber ("feature"). Security plugins not listed here default to "plugin".
# Internal / always-on infra plugins are too generic to badge and are dropped entirely.
_PLUGIN_BADGE_TYPE: Dict[str, str] = {
    "gzip": "feature",
    "brotli": "feature",
    "clientcache": "feature",
    "limit": "feature",
    "headers": "config",
    "cors": "config",
    "modsecurity": "config",
    "inject": "config",
    "robotstxt": "config",
    "securitytxt": "config",
}
_BADGE_SKIP_PLUGINS = frozenset({"general", "errors", "misc", "pro", "sessions", "db", "jobs", "metrics", "redis", "ui", "templates", "backup", "realip"})


def _normalize_view_mode(raw: Optional[str]) -> str:
    if not isinstance(raw, str):
        return "easy"
    candidate = raw.strip().lower()
    return candidate if candidate in VIEW_MODES else "easy"


def _normalise_tags(raw: Any) -> List[str]:
    if isinstance(raw, (list, tuple, set)):
        return [str(item) for item in raw if isinstance(item, (str, int, float, bool))]
    if isinstance(raw, (str, int, float, bool)):
        return [str(raw)]
    return []


def _build_multisite_settings_catalog() -> List[Dict[str, Any]]:
    catalog: List[Dict[str, Any]] = []
    seen_keys: Set[str] = set()

    def append_entry(
        key: str,
        meta: Dict[str, Any],
        plugin_info: Dict[str, Any],
        plugin_order: int,
        setting_order: int,
    ) -> None:
        if not key or key in seen_keys or not isinstance(meta, dict):
            return
        if meta.get("context") != "multisite":
            return

        entry: Dict[str, Any] = {
            "key": key,
            "label": setting_text(key, "label", meta.get("label") or key),
            "type": meta.get("type") or "",
            "plugin": {
                "id": plugin_info.get("id", ""),
                "name": plugin_text(plugin_info.get("id"), "meta.name", plugin_info.get("name") or plugin_info.get("id", "")),
                "type": plugin_info.get("type", "core"),
            },
            "plugin_order": plugin_order,
            "setting_order": setting_order,
        }

        plugin_category = plugin_info.get("category")
        if plugin_category:
            entry["plugin"]["category"] = plugin_category

        # Translated here, before serialisation: the editor reads this catalog as JSON, never through `_()`.
        description = setting_text(key, "help", meta.get("help") or meta.get("description"))
        if description:
            entry["description"] = description

        if "default" in meta:
            entry["default"] = meta.get("default")

        if meta.get("multiple"):
            entry["multiple"] = meta.get("multiple")

        regex = meta.get("regex")
        if regex:
            entry["regex"] = regex

        category = meta.get("category")
        if category and category != plugin_category:
            entry["category"] = category

        docs = meta.get("docs") or meta.get("doc") or plugin_info.get("docs")
        if docs:
            entry["docs"] = docs

        tags = meta.get("tags") or meta.get("keywords")
        tag_list = _normalise_tags(tags)
        if tag_list:
            entry["tags"] = tag_list

        entry["advanced"] = bool(meta.get("advanced")) if "advanced" in meta else False

        if isinstance(meta.get("select"), list):
            options_list = [option for option in meta["select"] if isinstance(option, (str, int, float, bool, dict))]
            if options_list:
                entry["options"] = options_list

        if isinstance(meta.get("multiselect"), list):
            entry["multiselect"] = [option for option in meta["multiselect"] if isinstance(option, dict) and option.get("id")]

        if isinstance(meta.get("separator"), str):
            entry["separator"] = meta["separator"]

        if isinstance(meta.get("accept"), str):
            entry["accept"] = meta["accept"]

        seen_keys.add(key)
        catalog.append(entry)

    try:
        base_settings = BW_CONFIG.get_settings()
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("Unable to load base settings catalog: %s", exc)
        base_settings = {}

    general_info = {
        "id": "general",
        "name": "General",
        "type": "core",
        "category": "core",
    }

    for setting_index, (key, meta) in enumerate(base_settings.items()):
        if isinstance(meta, dict):
            append_entry(key, meta, general_info, -1, setting_index)

    try:
        raw_plugin_records = API_CLIENT.get_plugins(type="all", with_data=True)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("Unable to load plugin order from database: %s", exc)
        raw_plugin_records = []

    plugin_order_map = {record.get("id"): index for index, record in enumerate(raw_plugin_records, start=1)}

    try:
        plugins = BW_CONFIG.get_plugins(with_data=True)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("Unable to load plugin settings catalog: %s", exc)
        plugins = {}

    if isinstance(plugins, dict):
        plugin_items = list(plugins.items())
    else:
        plugin_items = [(plugin.get("id"), plugin) for plugin in plugins or []]

    plugin_items.sort(key=lambda item: plugin_order_map.get(item[0], len(plugin_order_map) + 1000))

    for plugin_id, plugin_data in plugin_items:
        if not isinstance(plugin_data, dict):
            continue
        plugin_settings = plugin_data.get("settings")
        if not isinstance(plugin_settings, dict):
            continue

        plugin_order = plugin_order_map.get(plugin_id, len(plugin_order_map) + 1000)

        plugin_info = {
            "id": plugin_id,
            "name": plugin_data.get("name") or plugin_id,
            "type": plugin_data.get("type", "core"),
            "category": plugin_data.get("category"),
            "docs": plugin_data.get("docs") or plugin_data.get("doc"),
        }

        for setting_index, (key, meta) in enumerate(plugin_settings.items()):
            append_entry(key, meta, plugin_info, plugin_order, setting_index)

    catalog.sort(
        key=lambda item: (
            item.get("plugin_order", len(plugin_order_map) + 1000),
            item.get("setting_order", 10**6),
        )
    )
    return catalog


def _compute_template_usage(templates_index: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    """Count, per template id, how many services (including drafts) have USE_TEMPLATE set to it.

    Real usage data for the gallery's "N svc" chip -- never fabricated. Falls back to all-zero
    counts (chip omitted) if the services list can't be fetched, rather than failing the page."""
    return {template_id: len(services) for template_id, services in _template_services(templates_index).items()}


def _template_services(templates_index: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """Per template id, the ids of the services (drafts included) whose USE_TEMPLATE lists it.

    The catalogue update preview names them (C4): a replaced template changes every one of them
    at the next generation, for each setting the service did not set itself. A service listing
    one template twice is one service. Empty lists if the services can't be fetched."""
    usage: Dict[str, List[str]] = {template_id: [] for template_id in templates_index}
    try:
        services = API_CLIENT.get_services(with_drafts=True)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("Unable to load services for template usage counts: %s", exc)
        return usage

    for service in services or []:
        # The reserved default server is not a service an operator manages or picks a template
        # for -- excluded from the count for the same reason it is never offered as an attachment
        # target elsewhere (DS-B4 handoff item 4 / criticos-DS-B optional 8).
        if is_reserved_default_server(service):
            continue
        # USE_TEMPLATE is an ORDERED LIST, so `template` may name several layers. Counting the
        # raw value would match no template at all and report 0 uses for every multi-template
        # service -- a wrong number, which is worse than no chip.
        for template_id in dict.fromkeys(split_templates((service or {}).get("template"))):
            if template_id in usage:
                usage[template_id].append(str((service or {}).get("id") or ""))
    return usage


def _setting_canon(settings_catalog: List[Dict[str, Any]]) -> Callable[[str, str], str]:
    """``canon(key, value)``: a template setting value in the form the DB stores it.

    The catalogue ships values as written (jellyfin's ``MAX_CLIENT_SIZE`` is ``20M``) and the DB
    stores them canonical (``20m``), so the listing compares both through this or every such
    template reads as changed forever. ``settings_catalog`` is the page's own
    ``_build_multisite_settings_catalog()``. An unknown key keeps its value.
    """
    # ponytail: mirrors BW_CONFIG.check_variables' canonicalisation minus select casefolding (the
    # catalog does not carry `case_insensitive`); a missed case shows as a changed value in the
    # preview, never as a wrong write -- the DB canonicalises what is stored.
    by_key = {entry["key"]: entry for entry in settings_catalog if isinstance(entry, dict) and entry.get("key")}

    def canon(key: str, value: str) -> str:
        entry = by_key.get(key) or by_key.get(key.rsplit("_", 1)[0]) or {}
        setting_type = entry.get("type")
        value = trim_scalar_value(setting_type, value)
        if setting_type == "check":
            return normalize_check_value(value)
        if setting_type in ("size", "duration"):
            return normalize_unit(setting_type, value) or value
        if setting_type in ("multiselect", "multivalue"):
            return normalize_list_value(value, entry.get("separator") or " ")
        return value

    return canon


def _template_tag_badges(template_data: Dict[str, Any], catalog: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Derive typed feature badges for a template gallery card from the settings/custom-configs
    it actually bundles -- no fake tag list, no catalog shipped to the client.

    Mirrors the design kit's tplTagRank ordering (plugin -> config -> feature) but is data-driven,
    typed via ``_PLUGIN_BADGE_TYPE`` so a card reads as a MIX of chip colors rather than a flood
    of one type:
      - "plugin"  security plugin the template touches (green) -- antibot, blacklist, country...
      - "config"  header/rule/CORS config surface (navy) -- headers, cors, modsecurity plus every
                  distinct custom-config type (http/modsec_crs/...) the template bundles.
      - "feature" performance behavior (amber) -- gzip, brotli, client cache, limit.
    Internal / always-on infra plugins (``_BADGE_SKIP_PLUGINS``) are too generic to badge.
    """
    catalog_by_key = {entry["key"]: entry for entry in catalog}

    typed_names: Dict[str, Dict[str, str]] = {"plugin": {}, "config": {}, "feature": {}}
    for key in template_data.get("settings") or {}:
        entry = catalog_by_key.get(key)
        if not entry:
            continue
        plugin = entry.get("plugin") or {}
        plugin_id = plugin.get("id", "")
        if not plugin_id or plugin_id in _BADGE_SKIP_PLUGINS:
            continue
        badge_type = _PLUGIN_BADGE_TYPE.get(plugin_id, "plugin")
        typed_names[badge_type][plugin_id] = plugin.get("name") or plugin_id

    for config_key in template_data.get("configs") or {}:
        config_type = config_key.split("/", 1)[0] if "/" in config_key else config_key
        typed_names["config"][f"config:{config_type}"] = _CONFIG_TYPE_LABELS.get(config_type, config_type.replace("_", " ").title())

    badges: List[Dict[str, str]] = []
    for badge_type in ("plugin", "config", "feature"):
        meta = _BADGE_TYPE_META[badge_type]
        for name in sorted(typed_names[badge_type].values()):
            badges.append({"text": name, "type": badge_type, "variant": meta["variant"], "icon": meta["icon"]})
    return badges


def _split_badges(badges: List[Dict[str, str]], limit: int = 3) -> Dict[str, List[Dict[str, str]]]:
    """Split a ranked badge list into a capped ``visible`` head + an ``overflow`` tail for the
    card. Prefers one chip per type first so the visible set reads as a MIX (kit tplCard shows
    1-3 mixed-color chips), then backfills spare slots by rank; overflow becomes the "+N" chip."""
    visible: List[Dict[str, str]] = []
    overflow: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for badge in badges:
        if badge["type"] not in seen and len(visible) < limit:
            seen.add(badge["type"])
            visible.append(badge)
        else:
            overflow.append(badge)
    while len(visible) < limit and overflow:
        visible.append(overflow.pop(0))
    visible.sort(key=lambda badge: _BADGE_TYPE_META[badge["type"]]["rank"])
    return {"visible": visible, "overflow": overflow}


def _convert_template_details(details: Dict[str, Any]) -> Dict[str, Any]:
    raw_settings = details.get("settings", {})
    if isinstance(raw_settings, dict):
        settings = {str(key): value for key, value in raw_settings.items()}
    else:
        settings = {}
        for item in raw_settings or []:
            key = item.get("key")
            if key:
                settings[key] = item.get("default", "")

    # Step titles/subtitles are authored in English in the owning plugin's `templates/<id>.json`
    # (`src/common/core/templates/templates/*.json` for the 4 built-ins, or a plugin's own
    # `templates/` for a plugin-provided one) and merged into the i18n catalog under
    # `<plugin_id>.templates.<template_id>.steps.<index>.title` (`_merge_plugin_catalog`,
    # `PLUGIN_METADATA_SUBTREES`). Resolved here, server-side, with the raw stored value as the
    # fallback: the browser catalog strips this subtree (server-only, like every other
    # `PLUGIN_METADATA_SUBTREES` entry), so `template_edit.js` cannot look it up itself. A
    # UI-created template has no `plugin_id`; `plugin_text` returns the fallback unchanged for it.
    owning_plugin = details.get("plugin_id")
    template_id = details.get("id", "")
    steps: List[Dict[str, Any]] = [
        {
            "title": plugin_text(owning_plugin, f"templates.{template_id}.steps.{index}.title", step.get("title", "")),
            "subtitle": plugin_text(owning_plugin, f"templates.{template_id}.steps.{index}.subtitle", step.get("subtitle")),
            "settings": step.get("settings", []),
            "configs": step.get("configs", []),
        }
        for index, step in enumerate(details.get("steps", []) or [])
    ]

    configs: List[Dict[str, Any]] = [
        {
            "type": cfg.get("type", ""),
            "name": cfg.get("name", ""),
            "data": cfg.get("data", ""),
            "order": cfg.get("order"),
        }
        for cfg in details.get("configs", []) or []
    ]

    return {
        "id": details.get("id", ""),
        "name": details.get("name", details.get("id", "")),
        "settings": settings,
        "steps": steps,
        "configs": configs,
    }


def _user_readonly() -> bool:
    return "write" not in getattr(current_user, "list_permissions", [])


def _check_permissions() -> Dict[str, Any]:
    if API_CLIENT.readonly:
        return {"status": "error", "code": 409, "message": translated("flash.database_read_only_mode") or "Database is in read-only mode"}
    if _user_readonly():
        return {"status": "error", "code": 403, "message": translated("templates.flash.user_is_read_only") or "User is read-only"}
    return {}


def _load_template_from_request() -> Dict[str, Any]:
    payload = request.form.get("template", "").strip()
    if not payload:
        return {"error": "Missing template payload"}
    try:
        data = loads(payload)
    except JSONDecodeError as exc:
        return {"error": f"Invalid JSON payload: {exc}"}
    if not isinstance(data, dict):
        return {"error": "Template payload must be a JSON object"}
    return {"data": data}


def _serialize_template_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    serialized: Dict[str, Any] = {}
    for key, value in meta.items():
        if isinstance(value, datetime):
            serialized[key] = value.astimezone().isoformat()
        else:
            serialized[key] = value
    return serialized


def _build_editor_context(
    *,
    mode: str,
    template_id: Optional[str],
    template_data: Dict[str, Any],
    templates_index: Optional[Dict[str, Dict[str, Any]]] = None,
    template_meta: Optional[Dict[str, Any]] = None,
    clone_meta: Optional[Dict[str, str]] = None,
    view_mode: str = "easy",
) -> Dict[str, Any]:
    templates_index = templates_index or API_CLIENT.get_templates()
    template_meta = template_meta or {}

    user_readonly = _user_readonly()
    database_readonly = API_CLIENT.readonly
    method = template_meta.get("method", "ui")
    # A plugin-owned template is refused by the API whatever its method (`template_owner`): a
    # UI-uploaded plugin's templates carry method "ui" too.
    managed = method != "ui" or bool(template_meta.get("plugin_id"))
    can_edit = not database_readonly and not user_readonly and (mode == "create" or not managed)

    edit_restrictions: List[str] = []
    if database_readonly:
        edit_restrictions.append("database")
    if user_readonly:
        edit_restrictions.append("user")
    if mode == "edit" and managed:
        edit_restrictions.append("method")

    routes = {
        "list": url_for("templates.templates_page"),
        "create": url_for("templates.templates_create"),
    }
    if template_id:
        routes["update"] = url_for("templates.templates_update", template_id=template_id)

    multisite_config_types = [
        {
            "id": config_type,
            "value": config_type.lower(),
            "label": config_type,
            "description": details.get("description", ""),
        }
        for config_type, details in CONFIG_TYPES.items()
        if details.get("context") == "multisite"
    ]

    multisite_settings_catalog = _build_multisite_settings_catalog()
    normalized_view_mode = _normalize_view_mode(view_mode)

    return {
        "view_mode": normalized_view_mode,
        "mode": normalized_view_mode,
        "editor_mode": mode,
        "template_id": template_id,
        "template_data": template_data,
        "template_meta": template_meta,
        "template_meta_serialized": _serialize_template_meta(template_meta),
        "clone_meta": clone_meta,
        "can_edit_template": can_edit,
        "edit_restrictions": edit_restrictions,
        "routes": routes,
        "multisite_config_types": multisite_config_types,
        "multisite_settings_catalog": multisite_settings_catalog,
    }


def _catalog_context(installed: Dict[str, Dict[str, Any]], canon: Callable[[str, str], str]) -> Dict[str, Any]:
    """Same shape as the plugins page's; each card carries its C4 state and diff preview.

    ``installed`` is the page's own ``get_templates()`` (id -> row). Best-effort I/O: a catalogue
    section never fails the page. The install and update routes re-read everything and refuse
    when it is unavailable.
    """
    bw_version = "unknown"
    with suppress(Exception):
        bw_version = API_CLIENT.get_metadata().get("version", "unknown")
    return build_catalog_view("templates", DATA.get("PLUGIN_CATALOG"), installed, bw_version, canon)


@templates.route("/templates", methods=["GET"])
@login_required
def templates_page():
    db_templates = API_CLIENT.get_templates()
    template_users = _template_services(db_templates)
    catalog = _build_multisite_settings_catalog()
    template_badges = {template_id: _split_badges(_template_tag_badges(template_data, catalog)) for template_id, template_data in db_templates.items()}
    return render_template(
        "templates.html",
        templates=db_templates,
        template_usage={template_id: len(services) for template_id, services in template_users.items()},
        template_users=template_users,
        template_badges=template_badges,
        **_catalog_context(db_templates, _setting_canon(catalog)),
    )


@templates.route("/templates/new", methods=["GET"])
@login_required
def template_create_page():
    clone_id = request.args.get("clone", "").strip()
    templates_index = API_CLIENT.get_templates()
    view_mode = _normalize_view_mode(request.args.get("view", request.args.get("mode")))
    template_payload = {
        "id": "",
        "name": "",
        "settings": {},
        "steps": [],
        "configs": [],
    }
    clone_meta: Optional[Dict[str, str]] = None
    if clone_id:
        details = API_CLIENT.get_template(clone_id)
        if details:
            converted = _convert_template_details({**details, "id": clone_id})
            converted["id"] = ""
            template_payload = converted
            clone_meta = {
                "source_id": clone_id,
                "source_name": details.get("name", clone_id),
            }
        else:
            flash(translated("templates.flash.template_not_found", clone_id=clone_id) or f"Template {clone_id} not found.", "error")

    context = _build_editor_context(
        mode="create",
        template_id=None,
        template_data=template_payload,
        templates_index=templates_index,
        clone_meta=clone_meta,
        view_mode=view_mode,
    )
    return render_template("template_edit.html", **context)


@templates.route("/templates/<template_id>", methods=["GET"])
@login_required
def template_edit_page(template_id: str):
    details = API_CLIENT.get_template(template_id)
    if not details:
        flash(translated("templates.flash.template_not_found_2") or "Template not found.", "error")
        return redirect(url_for("templates.templates_page"))

    templates_index = API_CLIENT.get_templates()
    template_meta = templates_index.get(template_id, {})
    view_mode = _normalize_view_mode(request.args.get("view", request.args.get("mode")))
    context = _build_editor_context(
        mode="edit",
        template_id=template_id,
        template_data=_convert_template_details({**details, "id": template_id}),
        templates_index=templates_index,
        template_meta=template_meta,
        view_mode=view_mode,
    )
    return render_template("template_edit.html", **context)


@templates.route("/templates/<template_id>/json", methods=["GET"])
@login_required
@cors_required
def templates_detail(template_id: str):
    details = API_CLIENT.get_template(template_id)
    if not details:
        return jsonify({"status": "error", "message": "Template not found"}), 404
    return jsonify({"status": "success", "template": _convert_template_details({**details, "id": template_id})})


@templates.route("/templates/<template_id>/export", methods=["GET"])
@login_required
def templates_export(template_id: str):
    """Download one template as a ``bunkerweb-template/1`` package, built by the API.

    A read: any user, any template, plugin-owned ones included -- exporting a core template and
    importing the copy under a new id is how one gets edited.
    """
    try:
        package = API_CLIENT.export_template(template_id)
    except (ApiClientError, ApiUnavailableError) as e:
        flash(
            translated("templates.flash.export_failed", template=template_id, error=e.message) or f"Couldn't export template {template_id}: {e.message}",
            "error",
        )
        return redirect(url_for("templates.templates_page"))
    filename = template_id if TEMPLATE_ID_RX.match(template_id) else "template"
    return Response(
        dumps(package, indent=2, ensure_ascii=False),
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.bwtemplate.json"'},
    )


@templates.route("/templates/import", methods=["POST"])
@login_required
@cors_required
def templates_import():
    """Import one template from a file: a ``bunkerweb-template/1`` package (``.json``) or a
    folder archive (``.zip`` / ``.tar.*`` holding ``<id>/template.json`` + ``configs/``).

    **Admin, not `write`**, for the reason `templates_catalog_install` gives: the config blobs
    become NGINX configuration that nothing downstream inspects, and the API only ever sees the
    UI's own credential, so this route is the only place a user's role is checked.

    The file is read up to one byte past the cap and parsed here by the shared parser, so a
    refusal names its reason (bad id, a path outside the one template folder, too large, ...).
    The API parses the package again and owns the collision and ownership rules: an existing id
    is a 409 unless ``replace=yes`` was ticked, and a template the UI does not own is never
    replaced.
    """
    permission = _check_permissions()
    if permission:
        return jsonify({"status": "error", "message": permission["message"]}), permission["code"]
    if not current_user.admin:
        return jsonify({"status": "error", "message": translated("templates.import.admin_only") or "Importing templates is restricted to administrators"}), 403

    upload = request.files.get("template_file")
    if not upload or not upload.filename:
        return jsonify({"status": "error", "message": translated("templates.import.no_file") or "Choose a file to import."}), 400

    blob = upload.stream.read(PACKAGE_MAX + 1)
    if len(blob) > PACKAGE_MAX:
        return (
            jsonify({"status": "error", "message": translated("templates.import.too_large") or "The template was not imported: the file is larger than 1 MiB"}),
            413,
        )
    data, problem = parse_package(blob) if blob.lstrip()[:1] == b"{" else template_from_archive(blob)
    status = 400
    if problem:
        return (
            jsonify({"status": "error", "message": translated("templates.import.refused", reason=problem) or f"The template was not imported: {problem}"}),
            status,
        )
    if data is None:
        return (
            jsonify({"status": "error", "message": translated("templates.import.unreadable") or "The template was not imported: the file could not be read"}),
            status,
        )

    try:
        result = API_CLIENT.import_template({"format": PACKAGE_FORMAT, **data}, replace=request.form.get("replace") == "yes")
    except ApiClientError as e:
        return jsonify({"status": "error", "message": e.message}), e.status_code or 400
    except ApiUnavailableError as e:
        return jsonify({"status": "error", "message": e.message}), 503

    key, fallback = ("templates.flash.replaced", "Template {} replaced.") if result.get("replaced") else ("templates.flash.imported", "Template {} imported.")
    flash(translated(key, template=data["id"]) or fallback.format(data["id"]), "success")
    return jsonify({"status": "success", "id": data["id"]})


@templates.route("/templates/create", methods=["POST"])
@login_required
@cors_required
def templates_create():
    permission = _check_permissions()
    if permission:
        return jsonify({"status": "error", "message": permission["message"]}), permission["code"]

    template_payload = _load_template_from_request()
    if "error" in template_payload:
        return jsonify({"status": "error", "message": template_payload["error"]}), 400

    template_data = template_payload["data"]
    template_id = template_data.get("id", "").strip()
    if not template_id:
        return jsonify({"status": "error", "message": "Template id is required"}), 400

    create_kwargs = dict(
        name=template_data.get("name", template_id),
        settings=template_data.get("settings", {}),
        steps=template_data.get("steps", []),
        configs=template_data.get("configs", []),
    )
    try:
        API_CLIENT.create_template(template_id, **create_kwargs)
    except (ApiClientError, ApiUnavailableError) as e:
        return jsonify({"status": "error", "message": e.message}), getattr(e, "status_code", None) or 400

    flash(translated("templates.flash.template_created_successfully", template_id=template_id) or f"Template {template_id} created successfully.", "success")
    return jsonify({"status": "success"})


class _Refusal(Exception):
    """A catalogue route's refusal: a JSON error with its status."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.message, self.status = message, status

    def response(self) -> Tuple[Response, int]:
        return jsonify({"status": "error", "message": self.message}), self.status


def _checked_catalog_template() -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """The gates a catalogue install and update share, in order. ``(id, item, section)`` or `_Refusal`.

    The request contributes the id only; the repository, pinned tag, digest and compatibility
    all come from the server-side cached listing (`find_item`).
    """
    if not catalog_enabled():
        raise _Refusal("The community catalogue is disabled", 403)
    permission = _check_permissions()
    if permission:
        raise _Refusal(permission["message"], permission["code"])
    if not current_user.admin:
        raise _Refusal("Installing or updating catalogue templates is restricted to administrators", 403)

    template_id = (request.form.get("id") or "").strip()
    if not template_id:
        raise _Refusal("Template id is required", 400)

    cached = DATA.get("PLUGIN_CATALOG")
    item, section = find_item(cached, "templates", template_id)
    if not item or not section:
        raise _Refusal(f"No catalogue entry named {template_id}", 404)

    _, fetched_at = read_cached(cached)
    if is_stale(fetched_at):
        raise _Refusal("The catalogue is out of date and cannot be installed from", 409)

    if not section.get("tag") or not section.get("sha256"):
        raise _Refusal(f"The cached catalogue entry for {template_id} is incomplete", 409)

    # Fails CLOSED, and symmetric with the plugin half by design rather than by coincidence. The
    # API is already required a few lines below (`get_templates`), so asking it for the version
    # adds no failure mode that was not already there -- what it buys is that the flag in
    # `SOURCES` really is the only thing to change, on the server as well as in the template.
    try:
        bw_version = API_CLIENT.get_metadata().get("version", "unknown")
    except (ApiClientError, ApiUnavailableError) as e:
        raise _Refusal(f"Couldn't determine the BunkerWeb version: {e.message}", 503)

    if not item_compatible("templates", bw_version, item):
        supported = ", ".join(item.get("supported") or []) or "no BunkerWeb version"
        raise _Refusal(f"Template {template_id} declares support for {supported}; this is {bw_version}", 422)
    return template_id, item, section


def _verified_catalog_template(template_id: str, section: Dict[str, Any]) -> Dict[str, Any]:
    """Download the listed release at its pinned tag, prove it is the listed bytes, assemble one template."""
    tag, digest = section["tag"], section["sha256"]
    # At the pinned tag, never at "latest".
    try:
        archive = fetch_archive(SOURCES["templates"]["repo"], tag)
    except ValueError as e:
        raise _Refusal(f"Refused to download {template_id}: {e}", 502)
    except RequestException as e:
        raise _Refusal(f"Couldn't download {template_id}: {e}", 502)

    # Before anything is read out of the archive. A git tag can be force-moved; this is what makes
    # "the bytes listed" and "the bytes installed" the same claim.
    if not verify_digest(archive, digest):
        LOGGER.error(f"Archive digest mismatch installing template {template_id} from {tag}: expected {digest}")
        raise _Refusal(f"The {tag} archive no longer matches what the catalogue listed. Nothing was installed.", 502)

    # Assembles the template from its folder: `template.json` plus the config blobs its `configs`
    # references name, materialised from these same verified bytes. Re-checks the declared id.
    data, problem = template_payload(archive, template_id)
    if problem or data is None:
        raise _Refusal(f"Refused to install {template_id}: {problem}", 502)
    return data


@templates.route("/templates/catalog/install", methods=["POST"])
@login_required
@cors_required
def templates_catalog_install():
    """Install one curated service template from the community catalogue.

    Same chain as the plugin half (`/plugins/catalog/install`): the request contributes only an
    `id`, everything else comes from the server-side cached listing, and the recorded-digest gate
    runs on the downloaded archive before anything is read out of it.

    Three things differ, and all three are deliberate.

    **Admin, not `write`.** `/templates/create` needs only `write`, but a catalogue template
    carries config blobs fetched from the internet, and `_prepare_template_entities` validates
    settings hard while storing config data with *no* content validation at all -- it is
    stringified, encoded, hashed and written. That text becomes NGINX configuration on the
    instances. This gate lives in the route by necessity: the API authenticates the UI's single
    service credential and has no per-user role to check, so anything reaching the API directly
    with that credential bypasses it.

    **The version gate is CALLED here even though it currently passes everything.** The templates
    repository has no version field and no compatibility file, so `item_compatible` returns True
    for this half (`SOURCES["templates"]["version_gate"]` is False) and a bound invented here
    would assert a compatibility its publisher never stated. The call is made anyway, and that is
    the point: an earlier revision documented "flip the flag and nothing else changes" while this
    route never consulted the gate at all, so flipping it would have hidden the button
    (`templates.html` renders on `item.compatible`) and left this endpoint -- reachable directly,
    it is `@cors_required` JSON, not a form post -- installing regardless. A gate the server does
    not call is not a gate; the promise is now true because the code makes it true.

    **The payload is re-validated by the DB layer, and that is the real compatibility check.** It
    is handed to `create_template`, so every setting id is checked against the live Settings
    table: a template naming a setting this BunkerWeb does not have is refused with
    `Unknown settings: ...`. That is a structural check against this exact build, and it is
    strictly more informative than a declared version range.
    """
    try:
        template_id, _, section = _checked_catalog_template()
        try:
            if template_id in API_CLIENT.get_templates():
                return jsonify({"status": "error", "message": f"Template {template_id} already exists"}), 409
        except (ApiClientError, ApiUnavailableError) as e:
            return jsonify({"status": "error", "message": f"Couldn't list templates: {e.message}"}), 503
        data = _verified_catalog_template(template_id, section)
    except _Refusal as refusal:
        return refusal.response()

    try:
        API_CLIENT.create_template(
            template_id,
            name=data["name"],
            settings=data["settings"],
            steps=data["steps"],
            configs=data["configs"],
        )
    except (ApiClientError, ApiUnavailableError) as e:
        return jsonify({"status": "error", "message": e.message}), getattr(e, "status_code", None) or 400

    flash(
        translated("templates.flash.template_installed_catalogue", template_id=template_id) or f"Template {template_id} installed from the catalogue.",
        "success",
    )
    return jsonify({"status": "success"})


@templates.route("/templates/catalog/update", methods=["POST"])
@login_required
@cors_required
def templates_catalog_update():
    """Replace an installed catalogue template with the listed one, after its diff was confirmed (C4).

    The install chain runs unchanged (kill switch, admin, freshness, pinned tag, version gate,
    digest), and three things are added:

    * only the UI's own template is replaced -- one a plugin owns or another method wrote is
      refused here before any download, and again by the API (`template_owner`, 409);
    * the form carries ``confirm``, the `update_token` of the pair of templates the page showed a
      diff for. Both fingerprints are rebuilt now, from the verified bytes and the live row, so a
      listing that moved or a template edited since the preview is refused, never replaced unseen;
    * the write goes through the template import API with ``replace``, which re-validates the
      whole package against this build (an unknown setting refuses all of it).

    Services keep their ``USE_TEMPLATE`` list; each one picks up the new layer at its next
    generation, for every setting it did not set itself. The preview names them.
    """
    try:
        template_id, _, section = _checked_catalog_template()
        try:
            row = API_CLIENT.get_templates().get(template_id)
        except (ApiClientError, ApiUnavailableError) as e:
            return jsonify({"status": "error", "message": f"Couldn't list templates: {e.message}"}), 503
        if row is None:
            message = translated("templates.catalog.update_not_installed", template=escape(template_id))
            return jsonify({"status": "error", "message": message or f"Template {escape(template_id)} is not installed: install it instead"}), 409
        # The listing's own ownership rule, so the card and the route cannot disagree.
        owner = template_state({}, row)
        if owner["state"] == "managed":
            message = translated("templates.catalog.update_managed", template=escape(template_id), owner=escape(owner["managed_by"]))
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": message or f"Template {escape(template_id)} is managed by {escape(owner['managed_by'])}: the catalogue does not change it",
                    }
                ),
                409,
            )
        data = _verified_catalog_template(template_id, section)
    except _Refusal as refusal:
        return refusal.response()

    listed, installed = template_fingerprint(data), template_fingerprint(row)
    if listed == installed:
        message = translated("templates.catalog.update_up_to_date", template=escape(template_id))
        return jsonify({"status": "error", "message": message or f"Template {escape(template_id)} already matches the catalogue"}), 409
    if not compare_digest(str(request.form.get("confirm") or ""), update_token(listed, installed)):
        message = translated("templates.catalog.update_changed", template=escape(template_id))
        return (
            jsonify(
                {
                    "status": "error",
                    "message": message or f"Template {escape(template_id)} or the catalogue changed since the preview; reload the page and review it again",
                }
            ),
            409,
        )

    try:
        API_CLIENT.import_template({"format": PACKAGE_FORMAT, **data}, replace=True)
    except ApiClientError as e:
        return jsonify({"status": "error", "message": e.message}), e.status_code or 400
    except ApiUnavailableError as e:
        return jsonify({"status": "error", "message": e.message}), 503

    flash(translated("templates.flash.catalog_updated", template=template_id) or f"Template {template_id} updated from the catalogue.", "success")
    return jsonify({"status": "success"})


@templates.route("/templates/<template_id>/update", methods=["POST"])
@login_required
@cors_required
def templates_update(template_id: str):
    permission = _check_permissions()
    if permission:
        return jsonify({"status": "error", "message": permission["message"]}), permission["code"]

    details = API_CLIENT.get_template(template_id)
    if not details:
        return jsonify({"status": "error", "message": "Template not found"}), 404

    current = _convert_template_details({**details, "id": template_id})

    template_payload = _load_template_from_request()
    if "error" in template_payload:
        return jsonify({"status": "error", "message": template_payload["error"]}), 400

    template_data = template_payload["data"]

    settings = template_data.get("settings")
    steps = template_data.get("steps")
    configs = template_data.get("configs")

    update_kwargs = dict(
        name=template_data.get("name", current.get("name", template_id)),
        settings=settings if settings is not None else current.get("settings", {}),
        steps=steps if steps is not None else current.get("steps", []),
        configs=configs if configs is not None else current.get("configs", []),
    )
    try:
        API_CLIENT.update_template(template_id, **update_kwargs)
    except (ApiClientError, ApiUnavailableError) as e:
        return jsonify({"status": "error", "message": e.message}), getattr(e, "status_code", None) or 400

    flash(translated("templates.flash.template_updated_successfully", template_id=template_id) or f"Template {template_id} updated successfully.", "success")
    return jsonify({"status": "success"})


@templates.route("/templates/delete", methods=["POST"])
@login_required
def templates_delete_multiple():
    permission = _check_permissions()
    if permission:
        flash(permission["message"], "error")
        return redirect(url_for("templates.templates_page"))

    template_ids_str = request.form.get("templates", "")
    if not template_ids_str:
        flash(translated("templates.flash.no_templates_selected_deletion") or "No templates selected for deletion.", "warning")
        return redirect(url_for("templates.templates_page"))

    template_ids = [tid.strip() for tid in template_ids_str.split(",") if tid.strip()]

    errors = []
    success_count = 0
    for template_id in template_ids:
        try:
            API_CLIENT.delete_template(template_id)
            success_count += 1
        except (ApiClientError, ApiUnavailableError) as e:
            errors.append(
                translated("templates.flash.error_deleting_template", template_id=template_id, message=e.message)
                or f"Error deleting template {template_id}: {e.message}"
            )

    if success_count > 0:
        flash(
            translated("templates.flash.successfully_deleted_template", success_count=success_count) or f"Templates deleted: {success_count}.",
            "success",
        )
    if errors:
        flash(" ".join(errors), "error")

    return redirect(url_for("templates.templates_page"))


@templates.route("/templates/<template_id>/delete", methods=["POST"])
@login_required
@cors_required
def templates_delete(template_id: str):
    permission = _check_permissions()
    if permission:
        return jsonify({"status": "error", "message": permission["message"]}), permission["code"]

    try:
        API_CLIENT.delete_template(template_id)
    except (ApiClientError, ApiUnavailableError) as e:
        status = 409 if "currently used" in e.message.lower() else (getattr(e, "status_code", None) or 400)
        return jsonify({"status": "error", "message": e.message}), status

    flash(translated("templates.flash.template_deleted_successfully", template_id=template_id) or f"Template {template_id} deleted successfully.", "success")
    return jsonify({"status": "success"})
