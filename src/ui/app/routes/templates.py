from datetime import datetime
from json import JSONDecodeError, loads
from typing import Any, Dict, List, Optional, Set

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.dependencies import API_CLIENT, BW_CONFIG
from app.api_client import ApiClientError, ApiUnavailableError
from app.routes.configs import CONFIG_TYPES
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
            "label": meta.get("label") or key,
            "type": meta.get("type") or "",
            "plugin": {
                "id": plugin_info.get("id", ""),
                "name": plugin_info.get("name") or plugin_info.get("id", ""),
                "type": plugin_info.get("type", "core"),
            },
            "plugin_order": plugin_order,
            "setting_order": setting_order,
        }

        plugin_category = plugin_info.get("category")
        if plugin_category:
            entry["plugin"]["category"] = plugin_category

        description = meta.get("help") or meta.get("description")
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
    usage: Dict[str, int] = {template_id: 0 for template_id in templates_index}
    try:
        services = API_CLIENT.get_services(with_drafts=True)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("Unable to load services for template usage counts: %s", exc)
        return usage

    for service in services or []:
        template_id = (service or {}).get("template") or ""
        if template_id in usage:
            usage[template_id] += 1
    return usage


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

    steps: List[Dict[str, Any]] = [
        {
            "title": step.get("title", ""),
            "subtitle": step.get("subtitle"),
            "settings": step.get("settings", []),
            "configs": step.get("configs", []),
        }
        for step in details.get("steps", []) or []
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
        return {"status": "error", "code": 409, "message": "Database is in read-only mode"}
    if _user_readonly():
        return {"status": "error", "code": 403, "message": "User is read-only"}
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
    can_edit = not database_readonly and not user_readonly and (mode == "create" or method == "ui")

    edit_restrictions: List[str] = []
    if database_readonly:
        edit_restrictions.append("database")
    if user_readonly:
        edit_restrictions.append("user")
    if mode == "edit" and method != "ui":
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


@templates.route("/templates", methods=["GET"])
@login_required
def templates_page():
    db_templates = API_CLIENT.get_templates()
    template_usage = _compute_template_usage(db_templates)
    catalog = _build_multisite_settings_catalog()
    template_badges = {template_id: _split_badges(_template_tag_badges(template_data, catalog)) for template_id, template_data in db_templates.items()}
    return render_template("templates.html", templates=db_templates, template_usage=template_usage, template_badges=template_badges)


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
            flash(f"Template {clone_id} not found.", "error")

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
        flash("Template not found.", "error")
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

    flash(f"Template {template_id} created successfully.", "success")
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

    flash(f"Template {template_id} updated successfully.", "success")
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
        flash("No templates selected for deletion.", "warning")
        return redirect(url_for("templates.templates_page"))

    template_ids = [tid.strip() for tid in template_ids_str.split(",") if tid.strip()]

    errors = []
    success_count = 0
    for template_id in template_ids:
        try:
            API_CLIENT.delete_template(template_id)
            success_count += 1
        except (ApiClientError, ApiUnavailableError) as e:
            errors.append(f"Error deleting template {template_id}: {e.message}")

    if success_count > 0:
        flash(f"Successfully deleted {success_count} template(s).", "success")
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

    flash(f"Template {template_id} deleted successfully.", "success")
    return jsonify({"status": "success"})
