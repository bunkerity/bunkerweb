from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.utils import flash

redirects = Blueprint("redirects", __name__)

STATUS_CODES = ("301", "302", "303", "307", "308")
MAX_SERVICES = 100


def _redirect():
    return redirect(url_for("redirects.redirects_page"))


def _readonly():
    if not API_CLIENT.readonly:
        return False
    flash("Database is in read-only mode", "error")
    return True


def _services():
    values = list(dict.fromkeys(value.strip() for value in request.form.getlist("service_ids") if value.strip()))
    if len(values) > MAX_SERVICES:
        raise ValueError(f"A redirect cannot be attached to more than {MAX_SERVICES} services")
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
        raise ValueError("The redirect name is required")

    to_url = (request.form.get("to_url") or "").strip()
    if to_url:
        rule["to_url"] = to_url
    elif required:
        raise ValueError("The redirect target is required")

    from_path = (request.form.get("from_path") or "").strip()
    if from_path:
        rule["from_path"] = from_path
    elif required:
        rule["from_path"] = "/"

    status_code = (request.form.get("status_code") or "").strip()
    if status_code:
        if status_code not in STATUS_CODES:
            raise ValueError(f"The status code must be one of {', '.join(STATUS_CODES)}")
        rule["status_code"] = status_code
    elif required:
        rule["status_code"] = "301"

    # Keyed on presence, not truthiness: the edit modal always submits the textarea, so an
    # emptied description must reach the API as "" instead of being silently dropped.
    if "description" in request.form or required:
        description = (request.form.get("description") or "").strip()
        if len(description) > 4000:
            raise ValueError("The description cannot exceed 4000 characters")
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
        flash(f"Could not fetch redirects: {exc.message}", "error")
        redirect_rows, total = [], 0

    try:
        services = API_CLIENT.get_services(with_drafts=True)
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not fetch services for redirect assignments: {exc.message}", "error")
        services = []

    return render_template(
        "redirects.html",
        redirects=redirect_rows,
        total=total,
        truncated=total > len(redirect_rows),
        services=services,
        status_codes=STATUS_CODES,
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
        flash(f"Redirect {payload['name']} created successfully")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not create the redirect: {exc.message}", "error")
    return _redirect()


@redirects.route("/redirects/update", methods=["POST"])
@login_required
def redirects_update():
    if _readonly():
        return _redirect()
    redirect_id = (request.form.get("redirect_id") or "").strip()
    if not redirect_id:
        flash("The redirect is required", "error")
        return _redirect()
    try:
        API_CLIENT.update_redirect(redirect_id, **_rule(required=False))
        flash("Redirect updated successfully")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not update the redirect: {exc.message}", "error")
    return _redirect()


@redirects.route("/redirects/delete", methods=["POST"])
@login_required
def redirects_delete():
    if _readonly():
        return _redirect()
    redirect_id = (request.form.get("redirect_id") or "").strip()
    if not redirect_id:
        flash("The redirect is required", "error")
        return _redirect()
    try:
        API_CLIENT.delete_redirect(redirect_id)
        flash("Redirect deleted successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        # A redirect still attached to a service is refused by the API on purpose: detaching
        # is the operator's decision, not a side effect of a delete.
        flash(f"Could not delete the redirect: {exc.message}", "error")
    return _redirect()


@redirects.route("/redirects/attach", methods=["POST"])
@login_required
def redirects_attach():
    if _readonly():
        return _redirect()
    redirect_id = (request.form.get("redirect_id") or "").strip()
    try:
        if not redirect_id:
            raise ValueError("The redirect is required")
        service_ids = _services()
        if not service_ids:
            raise ValueError("At least one service is required")
        for service_id in service_ids:
            API_CLIENT.attach_redirect(redirect_id, service_id)
        flash(f"Redirect attached to {len(service_ids)} service(s)")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not attach the redirect: {exc.message}", "error")
    return _redirect()


@redirects.route("/redirects/detach", methods=["POST"])
@login_required
def redirects_detach():
    if _readonly():
        return _redirect()
    redirect_id = (request.form.get("redirect_id") or "").strip()
    service_id = (request.form.get("service_id") or "").strip()
    if not redirect_id or not service_id:
        flash("The redirect and the service are required", "error")
        return _redirect()
    try:
        API_CLIENT.detach_redirect(redirect_id, service_id)
        flash("Redirect detached successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not detach the redirect: {exc.message}", "error")
    return _redirect()
