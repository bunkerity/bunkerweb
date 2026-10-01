from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from default_server import is_reserved_default_server  # type: ignore

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.i18n import translated
from app.utils import flash, is_readonly_request

upstreams = Blueprint("upstreams", __name__)

METHODS = ("round_robin", "least_conn", "ip_hash")
PROTOCOLS = ("http", "grpc", "stream")
MAX_SERVICES = 100
MAX_SERVERS = 64
# The API's name / server / fail_timeout rules (db_methods/upstreams.py), written so a browser accepts
# them as an HTML `pattern`: it compiles with the `v` flag, which rejects a bare `-` at the end of a
# class and then silently skips the check. tests/unit/ui/test_attachable_form_patterns.py keeps them in step.
NAME_PATTERN = r"[A-Za-z0-9_\-]+"
SERVER_PATTERN = r"(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9]([A-Za-z0-9._\-]*[A-Za-z0-9])?)(:[1-9][0-9]{0,4})?"
FAIL_TIMEOUT_PATTERN = r"[0-9]+(ms|s|m|h|d)?"


def _redirect(**params):
    # `retry="create"`/`retry="edit"` tells the page to reopen that modal with the operator's input.
    return redirect(url_for("upstreams.upstreams_page", **params))


def _readonly():
    if API_CLIENT.readonly:
        flash(translated("flash.database_read_only_mode") or "Database is in read-only mode", "error")
        return True
    if is_readonly_request(API_CLIENT.readonly):
        # Two causes, two messages: the database is fine here, the session's permission is not.
        flash(translated("flash.do_not_have_write_permission") or "You do not have the write permission", "error")
        return True
    return False


def _servers():
    """Read the pool members from the parallel form lists.

    Every field is a ``<select>`` or a text input that always submits, including the role, so
    the lists stay aligned row by row — an unchecked checkbox would submit nothing and shift
    every following server onto the wrong host.
    """
    hosts = [value.strip() for value in request.form.getlist("server_host")]
    weights = request.form.getlist("server_weight")
    max_fails = request.form.getlist("server_max_fails")
    fail_timeouts = request.form.getlist("server_fail_timeout")
    roles = request.form.getlist("server_role")

    servers = []
    for index, host in enumerate(hosts):
        if not host:
            continue  # a blank row is an unused slot in the editor, not an error
        role = roles[index] if index < len(roles) else "primary"
        try:
            server = {
                "host": host,
                "weight": int(weights[index]) if index < len(weights) and weights[index] else 1,
                "max_fails": int(max_fails[index]) if index < len(max_fails) and max_fails[index] else 1,
                "fail_timeout": (fail_timeouts[index].strip() if index < len(fail_timeouts) and fail_timeouts[index].strip() else "10s"),
                "backup": role == "backup",
                "down": role == "down",
            }
        except ValueError:
            raise ValueError(
                translated("upstreams.flash.weight_max_fails_whole_numbers", host=host) or f"The weight and max fails of {host} must be whole numbers"
            )
        servers.append(server)

    if not servers:
        raise ValueError(translated("upstreams.flash.at_least_one_server_required") or "At least one server is required")
    if len(servers) > MAX_SERVERS:
        raise ValueError(translated("upstreams.flash.too_many_servers", value=MAX_SERVERS) or f"An upstream cannot have more than {MAX_SERVERS} servers")
    return servers


def _attachments():
    service_ids = list(dict.fromkeys(value.strip() for value in request.form.getlist("service_ids") if value.strip()))
    if len(service_ids) > MAX_SERVICES:
        raise ValueError(
            translated("upstreams.flash.too_many_services", value=MAX_SERVICES) or f"An upstream cannot be attached to more than {MAX_SERVICES} services"
        )
    match_path = (request.form.get("match_path") or "/").strip() or "/"
    if not match_path.startswith("/"):
        raise ValueError(translated("upstreams.flash.match_path_must_start_with_slash") or "The reverse proxy path must start with /")
    return [{"service_id": service_id, "match_path": match_path} for service_id in service_ids]


def _pool(*, required=True):
    """Read the pool fields from the form.

    ``required=False`` returns only the submitted fields so an edit can leave the others
    untouched; the API's PATCH ignores what is not sent.
    """
    pool = {}
    name = (request.form.get("name") or "").strip()
    if name:
        pool["name"] = name
    elif required:
        raise ValueError(translated("upstreams.flash.name_required") or "The upstream name is required")

    protocol = (request.form.get("protocol") or "").strip()
    if protocol:
        if protocol not in PROTOCOLS:
            raise ValueError(
                translated("upstreams.flash.protocol_must_be_one_of", value=", ".join(PROTOCOLS)) or f"The protocol must be one of {', '.join(PROTOCOLS)}"
            )
        pool["protocol"] = protocol
    elif required:
        pool["protocol"] = "http"

    method = (request.form.get("method") or "").strip()
    if method:
        if method not in METHODS:
            raise ValueError(translated("upstreams.flash.method_must_be_one_of", value=", ".join(METHODS)) or f"The method must be one of {', '.join(METHODS)}")
        pool["method"] = method
    elif required:
        pool["method"] = "round_robin"

    # An unchecked switch submits nothing, so its absence is a real "no" on both create and
    # edit — unlike the text fields, it is always meaningful.
    pool["backend_ssl"] = request.form.get("backend_ssl") in ("yes", "on", "true", "1")

    # Always sent by both modals, so an emptied field means "no keepalive" and must reach the
    # API as an explicit null instead of being dropped.
    if "keepalive" in request.form or required:
        keepalive = (request.form.get("keepalive") or "").strip()
        if keepalive:
            if not keepalive.isdigit() or int(keepalive) < 1:
                raise ValueError(translated("upstreams.flash.keepalive_must_be_positive_whole_number") or "The keepalive count must be a positive whole number")
            pool["keepalive"] = int(keepalive)
        else:
            pool["keepalive"] = None

    # Keyed on presence, not truthiness: the edit modal always submits the textarea, so an
    # emptied description must reach the API as "" instead of being silently dropped.
    if "description" in request.form or required:
        description = (request.form.get("description") or "").strip()
        if len(description) > 4000:
            raise ValueError(translated("flash.description_too_long") or "The description cannot exceed 4000 characters")
        pool["description"] = description

    if request.form.getlist("server_host") or required:
        pool["servers"] = _servers()
    return pool


@upstreams.route("/upstreams", methods=["GET"])
@login_required
def upstreams_page():
    try:
        result = API_CLIENT.get_upstreams(limit=500)
        upstream_rows = result.get("upstreams", [])
        total = result.get("total", len(upstream_rows))
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(translated("upstreams.flash.could_not_fetch_upstreams", message=exc.message) or f"Could not fetch upstreams: {exc.message}", "error")
        upstream_rows, total = [], 0

    try:
        # The reserved default server has no `Host` to route an upstream pool to -- never offered
        # as an assignment target (DS-B4 handoff item 4 / criticos-DS-B optional 8).
        services = [service for service in API_CLIENT.get_services(with_drafts=True) if not is_reserved_default_server(service)]
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(
            translated("upstreams.flash.could_not_fetch_services_upstream_assignments", message=exc.message)
            or f"Could not fetch services for upstream assignments: {exc.message}",
            "error",
        )
        services = []

    return render_template(
        "upstreams.html",
        upstreams=upstream_rows,
        total=total,
        truncated=total > len(upstream_rows),
        services=services,
        methods=METHODS,
        protocols=PROTOCOLS,
        name_pattern=NAME_PATTERN,
        server_pattern=SERVER_PATTERN,
        fail_timeout_pattern=FAIL_TIMEOUT_PATTERN,
    )


@upstreams.route("/upstreams/create", methods=["POST"])
@login_required
def upstreams_create():
    if _readonly():
        return _redirect()
    try:
        payload = _pool()
        payload["services"] = _attachments()
        API_CLIENT.create_upstream(**payload)
        flash(translated("upstreams.flash.upstream_created_successfully", value=payload["name"]) or f"Upstream {payload['name']} created successfully")
    except ValueError as exc:
        flash(str(exc), "error")
        return _redirect(retry="create")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(translated("upstreams.flash.could_not_create_upstream", message=exc.message) or f"Could not create the upstream: {exc.message}", "error")
        return _redirect(retry="create")
    return _redirect()


@upstreams.route("/upstreams/update", methods=["POST"])
@login_required
def upstreams_update():
    if _readonly():
        return _redirect()
    upstream_id = (request.form.get("upstream_id") or "").strip()
    if not upstream_id:
        flash(translated("upstreams.flash.upstream_required") or "The upstream is required", "error")
        return _redirect()
    try:
        API_CLIENT.update_upstream(upstream_id, **_pool(required=False))
        flash(translated("upstreams.flash.upstream_updated_successfully") or "Upstream updated successfully")
    except ValueError as exc:
        flash(str(exc), "error")
        return _redirect(retry="edit")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(translated("upstreams.flash.could_not_update_upstream", message=exc.message) or f"Could not update the upstream: {exc.message}", "error")
        return _redirect(retry="edit")
    return _redirect()


@upstreams.route("/upstreams/delete", methods=["POST"])
@login_required
def upstreams_delete():
    if _readonly():
        return _redirect()
    upstream_id = (request.form.get("upstream_id") or "").strip()
    if not upstream_id:
        flash(translated("upstreams.flash.upstream_required") or "The upstream is required", "error")
        return _redirect()
    try:
        API_CLIENT.delete_upstream(upstream_id)
        flash(translated("upstreams.flash.upstream_deleted_successfully") or "Upstream deleted successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        # An upstream still attached to a service is refused by the API on purpose: detaching
        # is the operator's decision, not a side effect of a delete.
        flash(translated("upstreams.flash.could_not_delete_upstream", message=exc.message) or f"Could not delete the upstream: {exc.message}", "error")
    return _redirect()


@upstreams.route("/upstreams/attach", methods=["POST"])
@login_required
def upstreams_attach():
    if _readonly():
        return _redirect()
    upstream_id = (request.form.get("upstream_id") or "").strip()
    try:
        if not upstream_id:
            raise ValueError(translated("upstreams.flash.upstream_required") or "The upstream is required")
        attachments = _attachments()
        if not attachments:
            raise ValueError(translated("upstreams.flash.at_least_one_service_required") or "At least one service is required")
        for attachment in attachments:
            API_CLIENT.attach_upstream(upstream_id, attachment["service_id"], match_path=attachment["match_path"])
        flash(translated("upstreams.flash.upstream_attached_service", len=len(attachments)) or f"Upstream attached. Services: {len(attachments)}")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(translated("upstreams.flash.could_not_attach_upstream", message=exc.message) or f"Could not attach the upstream: {exc.message}", "error")
    return _redirect()


@upstreams.route("/upstreams/detach", methods=["POST"])
@login_required
def upstreams_detach():
    if _readonly():
        return _redirect()
    upstream_id = (request.form.get("upstream_id") or "").strip()
    service_id = (request.form.get("service_id") or "").strip()
    match_path = (request.form.get("match_path") or "").strip()
    if not upstream_id or not service_id:
        flash(translated("upstreams.flash.upstream_service_are_required") or "The upstream and the service are required", "error")
        return _redirect()
    try:
        API_CLIENT.detach_upstream(upstream_id, service_id, match_path=match_path)
        flash(translated("upstreams.flash.upstream_detached_successfully") or "Upstream detached successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(translated("upstreams.flash.could_not_detach_upstream", message=exc.message) or f"Could not detach the upstream: {exc.message}", "error")
    return _redirect()
