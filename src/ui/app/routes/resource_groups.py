from datetime import datetime, timezone
from json import JSONDecodeError, dumps, loads
from re import fullmatch

from flask import Blueprint, Response, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.i18n import translated
from app.form_retry import keep_form, take_form_retry
from app.routes.utils import cors_required
from app.utils import flash, is_readonly_request

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
        raise ValueError(translated("resource_groups.flash.alias_invalid_chars") or "The alias must contain 1 to 64 letters, digits, underscores, or dashes")
    if value.upper() in RESERVED_ALIASES:
        raise ValueError(translated("resource_groups.flash.alias_reserved") or "This alias is reserved by BunkerWeb")
    return value


def _entries(value):
    try:
        entries = loads(value or "[]")
    except JSONDecodeError as exc:
        raise ValueError(translated("resource_groups.flash.entries_not_valid_json") or "The resource entries are not valid JSON") from exc
    if not isinstance(entries, list):
        raise ValueError(translated("resource_groups.flash.entries_not_a_list") or "The resource entries must be a list")
    if len(entries) > MAX_ENTRIES:
        raise ValueError(
            translated("resource_groups.flash.too_many_entries", value=MAX_ENTRIES) or f"A resource group cannot contain more than {MAX_ENTRIES} entries"
        )

    parsed = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(translated("resource_groups.flash.entry_invalid", index=index) or f"Entry {index} is invalid")
        kind = str(entry.get("kind", "")).strip().lower()
        value = str(entry.get("value", "")).strip()
        comment = str(entry.get("comment") or "").strip()
        if kind not in RESOURCE_KINDS:
            raise ValueError(translated("resource_groups.flash.entry_invalid_kind", index=index) or f"Entry {index} has an invalid kind")
        if not value or len(value) > MAX_VALUE_LENGTH:
            raise ValueError(translated("resource_groups.flash.entry_invalid_value", index=index) or f"Entry {index} has an invalid value")
        if len(comment) > MAX_COMMENT_LENGTH:
            raise ValueError(translated("resource_groups.flash.entry_comment_too_long", index=index) or f"Entry {index} has a comment that is too long")
        parsed.append({"kind": kind, "value": value, "comment": comment, "order": index})
    return parsed


@resource_groups.route("/groups", methods=["GET"])
@login_required
def resource_groups_page():
    try:
        groups = API_CLIENT.get_resource_groups(include_usage=True)
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(translated("flash.could_not_fetch_resource_groups", message=exc.message) or f"Could not fetch resource groups: {exc.message}", "error")
        groups = {}

    rows = [{"id": group_id, **details} for group_id, details in groups.items()]
    rows.sort(key=lambda group: str(group.get("name", "")).casefold())
    return render_template(
        "groups.html",
        resource_groups=rows,
        resource_kinds=RESOURCE_KINDS,
        editable_methods=EDITABLE_METHODS,
        form_retry=take_form_retry(),
    )


@resource_groups.route("/groups/save", methods=["POST"])
@login_required
def resource_groups_save():
    if API_CLIENT.readonly:
        flash(translated("flash.database_read_only_mode") or "Database is in read-only mode", "error")
        return _redirect()
    if is_readonly_request(API_CLIENT.readonly):
        flash(translated("flash.do_not_have_write_permission") or "You do not have the write permission", "error")
        return _redirect()

    try:
        entries = _entries(request.form.get("entries"))
        description = (request.form.get("description") or "").strip()
        if len(description) > 4000:
            raise ValueError(translated("flash.description_too_long") or "The description cannot exceed 4000 characters")

        group_id = (request.form.get("group_id") or "").strip()
        if group_id:
            API_CLIENT.update_resource_group(group_id, description=description, entries=entries)
            flash(translated("resource_groups.flash.resource_group_updated_successfully") or "Resource group updated successfully")
        else:
            alias = _alias(request.form.get("alias"))
            API_CLIENT.create_resource_group(alias, alias, description=description, entries=entries)
            flash(translated("resource_groups.flash.resource_group_created_successfully", alias=alias) or f"Resource group @{alias} created successfully")
    # A refusal keeps the editor's input for the page to reopen it with (QA-UI M28): the modal used
    # to come back closed, its alias, description and every entry gone.
    except ValueError as exc:
        flash(str(exc), "error")
        keep_form("resource-group", str(exc))
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(
            translated("resource_groups.flash.could_not_save_resource_group", message=exc.message) or f"Could not save the resource group: {exc.message}",
            "error",
        )
        keep_form("resource-group", f"Could not save the resource group: {exc.message}")
    return _redirect()


@resource_groups.route("/groups/clone", methods=["POST"])
@login_required
def resource_groups_clone():
    if API_CLIENT.readonly:
        flash(translated("flash.database_read_only_mode") or "Database is in read-only mode", "error")
        return _redirect()
    if is_readonly_request(API_CLIENT.readonly):
        flash(translated("flash.do_not_have_write_permission") or "You do not have the write permission", "error")
        return _redirect()
    try:
        source_id = (request.form.get("source_id") or "").strip()
        if not source_id:
            raise ValueError(translated("resource_groups.flash.source_required") or "The source resource group is required")
        alias = _alias(request.form.get("alias"))
        API_CLIENT.clone_resource_group(source_id, alias, alias)
        flash(translated("resource_groups.flash.resource_group_cloned", alias=alias) or f"Resource group cloned as @{alias}")
    except ValueError as exc:
        flash(str(exc), "error")
        keep_form("resource-group-clone", str(exc))
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(
            translated("resource_groups.flash.could_not_clone_resource_group", message=exc.message) or f"Could not clone the resource group: {exc.message}",
            "error",
        )
        keep_form("resource-group-clone", f"Could not clone the resource group: {exc.message}")
    return _redirect()


@resource_groups.route("/groups/delete", methods=["POST"])
@login_required
def resource_groups_delete():
    if API_CLIENT.readonly:
        flash(translated("flash.database_read_only_mode") or "Database is in read-only mode", "error")
        return _redirect()
    if is_readonly_request(API_CLIENT.readonly):
        flash(translated("flash.do_not_have_write_permission") or "You do not have the write permission", "error")
        return _redirect()
    group_id = (request.form.get("group_id") or "").strip()
    if not group_id:
        flash(translated("resource_groups.flash.resource_group_required") or "The resource group is required", "error")
        return _redirect()
    try:
        API_CLIENT.delete_resource_group(group_id)
        flash(translated("resource_groups.flash.resource_group_deleted_successfully") or "Resource group deleted successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(
            translated("resource_groups.flash.could_not_delete_resource_group", message=exc.message) or f"Could not delete the resource group: {exc.message}",
            "error",
        )
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
        flash(
            translated("resource_groups.flash.could_not_export_resource_groups", message=exc.message) or f"Could not export resource groups: {exc.message}",
            "error",
        )
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
