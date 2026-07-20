from datetime import datetime, timezone
from json import JSONDecodeError, dumps, loads
from re import fullmatch

from flask import Blueprint, Response, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.routes.utils import cors_required
from app.utils import flash

resource_groups = Blueprint("resource_groups", __name__)

RESOURCE_KINDS = ("ip", "country", "asn", "rdns", "user_agent", "uri")
EDITABLE_METHODS = ("ui", "api", "wizard")
MAX_ENTRIES = 5000
MAX_VALUE_LENGTH = 8192
MAX_COMMENT_LENGTH = 1000
RESERVED_ALIASES = frozenset({"ASEAN", "BENELUX", "DACH", "EEA", "EU", "FIVE_EYES", "G7", "GCC", "LATAM", "NORDICS", "SCHENGEN", "USMCA"})


def _redirect():
    return redirect(url_for("resource_groups.resource_groups_page"))


def _alias(value):
    value = (value or "").strip().removeprefix("@")
    if not fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("The alias must contain 1 to 64 letters, digits, underscores, or dashes")
    if value.upper() in RESERVED_ALIASES:
        raise ValueError("This alias is reserved by BunkerWeb")
    return value


def _entries(value):
    try:
        entries = loads(value or "[]")
    except JSONDecodeError as exc:
        raise ValueError("The resource entries are not valid JSON") from exc
    if not isinstance(entries, list):
        raise ValueError("The resource entries must be a list")
    if len(entries) > MAX_ENTRIES:
        raise ValueError(f"A resource group cannot contain more than {MAX_ENTRIES} entries")

    parsed = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Entry {index} is invalid")
        kind = str(entry.get("kind", "")).strip().lower()
        value = str(entry.get("value", "")).strip()
        comment = str(entry.get("comment") or "").strip()
        if kind not in RESOURCE_KINDS:
            raise ValueError(f"Entry {index} has an invalid kind")
        if not value or len(value) > MAX_VALUE_LENGTH:
            raise ValueError(f"Entry {index} has an invalid value")
        if len(comment) > MAX_COMMENT_LENGTH:
            raise ValueError(f"Entry {index} has a comment that is too long")
        parsed.append({"kind": kind, "value": value, "comment": comment, "order": index})
    return parsed


@resource_groups.route("/groups", methods=["GET"])
@login_required
def resource_groups_page():
    try:
        groups = API_CLIENT.get_resource_groups(include_usage=True)
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not fetch resource groups: {exc.message}", "error")
        groups = {}

    rows = [{"id": group_id, **details} for group_id, details in groups.items()]
    rows.sort(key=lambda group: str(group.get("name", "")).casefold())
    return render_template(
        "groups.html",
        resource_groups=rows,
        resource_kinds=RESOURCE_KINDS,
        editable_methods=EDITABLE_METHODS,
    )


@resource_groups.route("/groups/save", methods=["POST"])
@login_required
def resource_groups_save():
    if API_CLIENT.readonly:
        flash("Database is in read-only mode", "error")
        return _redirect()

    try:
        entries = _entries(request.form.get("entries"))
        description = (request.form.get("description") or "").strip()
        if len(description) > 4000:
            raise ValueError("The description cannot exceed 4000 characters")

        group_id = (request.form.get("group_id") or "").strip()
        if group_id:
            API_CLIENT.update_resource_group(group_id, description=description, entries=entries)
            flash("Resource group updated successfully")
        else:
            alias = _alias(request.form.get("alias"))
            API_CLIENT.create_resource_group(alias, alias, description=description, entries=entries)
            flash(f"Resource group @{alias} created successfully")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not save the resource group: {exc.message}", "error")
    return _redirect()


@resource_groups.route("/groups/clone", methods=["POST"])
@login_required
def resource_groups_clone():
    if API_CLIENT.readonly:
        flash("Database is in read-only mode", "error")
        return _redirect()
    try:
        source_id = (request.form.get("source_id") or "").strip()
        if not source_id:
            raise ValueError("The source resource group is required")
        alias = _alias(request.form.get("alias"))
        API_CLIENT.clone_resource_group(source_id, alias, alias)
        flash(f"Resource group cloned as @{alias}")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not clone the resource group: {exc.message}", "error")
    return _redirect()


@resource_groups.route("/groups/delete", methods=["POST"])
@login_required
def resource_groups_delete():
    if API_CLIENT.readonly:
        flash("Database is in read-only mode", "error")
        return _redirect()
    group_id = (request.form.get("group_id") or "").strip()
    if not group_id:
        flash("The resource group is required", "error")
        return _redirect()
    try:
        API_CLIENT.delete_resource_group(group_id)
        flash("Resource group deleted successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not delete the resource group: {exc.message}", "error")
    return _redirect()


@resource_groups.route("/groups/<group_id>/references", methods=["GET"])
@login_required
@cors_required
def resource_groups_references(group_id):
    try:
        return jsonify(status="success", references=API_CLIENT.get_resource_group_references(group_id))
    except (ApiClientError, ApiUnavailableError) as exc:
        return jsonify(status="error", message=exc.message), getattr(exc, "status_code", None) or 502


@resource_groups.route("/groups/export", methods=["GET"])
@login_required
def resource_groups_export():
    try:
        groups = API_CLIENT.get_resource_groups()
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not export resource groups: {exc.message}", "error")
        return _redirect()

    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "groups": [{"id": group_id, **details} for group_id, details in groups.items()],
    }
    return Response(
        dumps(payload, indent=2, sort_keys=True),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=bunkerweb-resource-groups.json"},
    )
