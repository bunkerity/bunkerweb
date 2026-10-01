from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from default_server import is_reserved_default_server  # type: ignore

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.i18n import translated
from app.utils import flash, is_readonly_request

redirects = Blueprint("redirects", __name__)

STATUS_CODES = ("301", "302", "303", "307", "308")
MAX_SERVICES = 100
# The redirect plugin's REDIRECT_FROM / REDIRECT_TO regexes, rewritten so a browser accepts them as an
# HTML `pattern` (compiled with the `v` flag, which rejects an unescaped `{`, `}` or `-` in a class and
# then silently skips the check). tests/unit/ui/test_attachable_form_patterns.py keeps them in step.
FROM_PATH_PATTERN = r"^(?!(?:~\*|~|\^~|=)$)(?:(?:~\*|~|\^~|=) )?[^\s;\{\}]+$"
TO_URL_PATTERN = r"^https?:\/\/[\-\w@:%.+~#=]+[\-\w\(\)!@:%+.~#?&\/=$]*$"
# The API names the redirect plugin setting that refused a value; the operator only knows the form field.
INVALID_FIELD_MESSAGES = {
    "REDIRECT_FROM": ("redirects.err.invalid_from_path", "The source path is not valid: it cannot contain spaces, semicolons or braces."),
    "REDIRECT_TO": ("redirects.err.invalid_to_url", "The target must be a full http:// or https:// URL."),
}


def _redirect(**params):
    # `retry="create"`/`retry="edit"` tells the page to reopen that modal with the operator's input.
    return redirect(url_for("redirects.redirects_page", **params))


def _flash_api_error(operation: str, message: str):
    setting = message.removeprefix("Invalid value for ").split(":", 1)[0] if message.startswith("Invalid value for ") else ""
    if setting in INVALID_FIELD_MESSAGES:
        key, text = INVALID_FIELD_MESSAGES[setting]
        flash(translated(key) or text, "error")
    else:
        # One whole sentence per operation: the verb is part of the translation, never interpolated.
        key = "redirects.flash.could_not_create" if operation == "create" else "redirects.flash.could_not_update"
        flash(translated(key, message=message) or f"Could not {operation} the redirect: {message}", "error")


def _readonly():
    if API_CLIENT.readonly:
        flash(translated("flash.database_read_only_mode") or "Database is in read-only mode", "error")
        return True
    if is_readonly_request(API_CLIENT.readonly):
        # Two causes, two messages: the database is fine here, the session's permission is not.
        flash(translated("flash.do_not_have_write_permission") or "You do not have the write permission", "error")
        return True
    return False


def _services():
    values = list(dict.fromkeys(value.strip() for value in request.form.getlist("service_ids") if value.strip()))
    if len(values) > MAX_SERVICES:
        raise ValueError(
            translated("redirects.flash.too_many_services", value=MAX_SERVICES) or f"A redirect cannot be attached to more than {MAX_SERVICES} services"
        )
    return values


def _rule(*, required=True):
    """Read the rule fields from the form.

    ``required=False`` returns only the submitted fields so an edit can leave the others
    untouched; the API's PATCH ignores what is not sent.
    """
    rule = {}
    name = (request.form.get("name") or "").strip()
    if name:
        rule["name"] = name
    elif required:
        raise ValueError(translated("redirects.flash.name_required") or "The redirect name is required")

    to_url = (request.form.get("to_url") or "").strip()
    if to_url:
        rule["to_url"] = to_url
    elif required:
        raise ValueError(translated("redirects.flash.target_required") or "The redirect target is required")

    from_path = (request.form.get("from_path") or "").strip()
    if from_path:
        rule["from_path"] = from_path
    elif required:
        rule["from_path"] = "/"

    status_code = (request.form.get("status_code") or "").strip()
    if status_code:
        if status_code not in STATUS_CODES:
            raise ValueError(
                translated("redirects.flash.status_code_must_be_one_of", value=", ".join(STATUS_CODES))
                or f"The status code must be one of {', '.join(STATUS_CODES)}"
            )
        rule["status_code"] = status_code
    elif required:
        rule["status_code"] = "301"

    # Keyed on presence, not truthiness: the edit modal always submits the textarea, so an
    # emptied description must reach the API as "" instead of being silently dropped.
    if "description" in request.form or required:
        description = (request.form.get("description") or "").strip()
        if len(description) > 4000:
            raise ValueError(translated("flash.description_too_long") or "The description cannot exceed 4000 characters")
        rule["description"] = description

    # An unchecked checkbox submits nothing, so its absence is a real "no" on both create and
    # edit — unlike the text fields, it is always sent.
    rule["append_request_uri"] = request.form.get("append_request_uri") in ("yes", "on", "true", "1")
    return rule


@redirects.route("/redirects", methods=["GET"])
@login_required
def redirects_page():
    try:
        result = API_CLIENT.get_redirects(limit=500)
        redirect_rows = result.get("redirects", [])
        total = result.get("total", len(redirect_rows))
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(translated("redirects.flash.could_not_fetch_redirects", message=exc.message) or f"Could not fetch redirects: {exc.message}", "error")
        redirect_rows, total = [], 0

    try:
        # The reserved default server has nothing to redirect FROM -- never offered as an
        # assignment target (DS-B4 handoff item 4 / criticos-DS-B optional 8).
        services = [service for service in API_CLIENT.get_services(with_drafts=True) if not is_reserved_default_server(service)]
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(
            translated("redirects.flash.could_not_fetch_services_redirect_assignments", message=exc.message)
            or f"Could not fetch services for redirect assignments: {exc.message}",
            "error",
        )
        services = []

    return render_template(
        "redirects.html",
        redirects=redirect_rows,
        total=total,
        truncated=total > len(redirect_rows),
        services=services,
        status_codes=STATUS_CODES,
        from_path_pattern=FROM_PATH_PATTERN,
        to_url_pattern=TO_URL_PATTERN,
    )


@redirects.route("/redirects/create", methods=["POST"])
@login_required
def redirects_create():
    if _readonly():
        return _redirect()
    try:
        payload = _rule()
        payload["service_ids"] = _services()
        API_CLIENT.create_redirect(**payload)
        flash(translated("redirects.flash.redirect_created_successfully", value=payload["name"]) or f"Redirect {payload['name']} created successfully")
    except ValueError as exc:
        flash(str(exc), "error")
        return _redirect(retry="create")
    except (ApiClientError, ApiUnavailableError) as exc:
        _flash_api_error("create", exc.message)
        return _redirect(retry="create")
    return _redirect()


@redirects.route("/redirects/update", methods=["POST"])
@login_required
def redirects_update():
    if _readonly():
        return _redirect()
    redirect_id = (request.form.get("redirect_id") or "").strip()
    if not redirect_id:
        flash(translated("redirects.flash.redirect_required") or "The redirect is required", "error")
        return _redirect()
    try:
        API_CLIENT.update_redirect(redirect_id, **_rule(required=False))
        flash(translated("redirects.flash.redirect_updated_successfully") or "Redirect updated successfully")
    except ValueError as exc:
        flash(str(exc), "error")
        return _redirect(retry="edit")
    except (ApiClientError, ApiUnavailableError) as exc:
        _flash_api_error("update", exc.message)
        return _redirect(retry="edit")
    return _redirect()


@redirects.route("/redirects/delete", methods=["POST"])
@login_required
def redirects_delete():
    if _readonly():
        return _redirect()
    redirect_id = (request.form.get("redirect_id") or "").strip()
    if not redirect_id:
        flash(translated("redirects.flash.redirect_required") or "The redirect is required", "error")
        return _redirect()
    try:
        API_CLIENT.delete_redirect(redirect_id)
        flash(translated("redirects.flash.redirect_deleted_successfully") or "Redirect deleted successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        # A redirect still attached to a service is refused by the API on purpose: detaching
        # is the operator's decision, not a side effect of a delete.
        flash(translated("redirects.flash.could_not_delete_redirect", message=exc.message) or f"Could not delete the redirect: {exc.message}", "error")
    return _redirect()


@redirects.route("/redirects/attach", methods=["POST"])
@login_required
def redirects_attach():
    if _readonly():
        return _redirect()
    redirect_id = (request.form.get("redirect_id") or "").strip()
    try:
        if not redirect_id:
            raise ValueError(translated("redirects.flash.redirect_required") or "The redirect is required")
        service_ids = _services()
        if not service_ids:
            raise ValueError(translated("redirects.flash.at_least_one_service_required") or "At least one service is required")
        for service_id in service_ids:
            API_CLIENT.attach_redirect(redirect_id, service_id)
        flash(translated("redirects.flash.redirect_attached_service", len=len(service_ids)) or f"Redirect attached. Services: {len(service_ids)}")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(translated("redirects.flash.could_not_attach_redirect", message=exc.message) or f"Could not attach the redirect: {exc.message}", "error")
    return _redirect()


@redirects.route("/redirects/detach", methods=["POST"])
@login_required
def redirects_detach():
    if _readonly():
        return _redirect()
    redirect_id = (request.form.get("redirect_id") or "").strip()
    service_id = (request.form.get("service_id") or "").strip()
    if not redirect_id or not service_id:
        flash(translated("redirects.flash.redirect_service_are_required") or "The redirect and the service are required", "error")
        return _redirect()
    try:
        API_CLIENT.detach_redirect(redirect_id, service_id)
        flash(translated("redirects.flash.redirect_detached_successfully") or "Redirect detached successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(translated("redirects.flash.could_not_detach_redirect", message=exc.message) or f"Could not detach the redirect: {exc.message}", "error")
    return _redirect()
