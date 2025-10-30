from datetime import datetime
from json import JSONDecodeError, loads
from typing import Any, Dict, List, Optional, Set

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.dependencies import BW_CONFIG, DB
from app.routes.configs import CONFIG_TYPES
from app.routes.utils import cors_required
from app.utils import LOGGER, flash


templates = Blueprint("templates", __name__)

VIEW_MODES = {"easy", "raw"}


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
        raw_plugin_records = DB.get_plugins(_type="all", with_data=True)
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
    if DB.readonly:
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
    templates_index = templates_index or DB.get_templates()
    template_meta = template_meta or {}

    user_readonly = _user_readonly()
    database_readonly = DB.readonly
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
    db_templates = DB.get_templates()
    return render_template("templates.html", templates=db_templates)


@templates.route("/templates/new", methods=["GET"])
@login_required
def template_create_page():
    clone_id = request.args.get("clone", "").strip()
    templates_index = DB.get_templates()
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
        details = DB.get_template_details(clone_id)
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
    details = DB.get_template_details(template_id)
    if not details:
        flash("Template not found.", "error")
        return redirect(url_for("templates.templates_page"))

    templates_index = DB.get_templates()
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
    details = DB.get_template_details(template_id)
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
    err = DB.create_template(template_id, **create_kwargs)
    if err:
        return jsonify({"status": "error", "message": err}), 400

    flash(f"Template {template_id} created successfully.", "success")
    return jsonify({"status": "success"})


@templates.route("/templates/<template_id>/update", methods=["POST"])
@login_required
@cors_required
def templates_update(template_id: str):
    permission = _check_permissions()
    if permission:
        return jsonify({"status": "error", "message": permission["message"]}), permission["code"]

    details = DB.get_template_details(template_id)
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
    err = DB.update_template(template_id, **update_kwargs)
    if err:
        return jsonify({"status": "error", "message": err}), 400

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
        err = DB.delete_template(template_id)
        if err:
            errors.append(f"Error deleting template {template_id}: {err}")
        else:
            success_count += 1

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

    err = DB.delete_template(template_id)
    if err:
        status = 409 if "currently used" in err.lower() else 400
        return jsonify({"status": "error", "message": err}), status

    flash(f"Template {template_id} deleted successfully.", "success")
    return jsonify({"status": "success"})
