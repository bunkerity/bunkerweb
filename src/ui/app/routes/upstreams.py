from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.utils import flash

upstreams = Blueprint("upstreams", __name__)

METHODS = ("round_robin", "least_conn", "ip_hash")
PROTOCOLS = ("http", "grpc", "stream")
MAX_SERVICES = 100
MAX_SERVERS = 64


def _redirect():
    return redirect(url_for("upstreams.upstreams_page"))


def _readonly():
    if not API_CLIENT.readonly:
        return False
    flash("Database is in read-only mode", "error")
    return True


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
            raise ValueError(f"The weight and max fails of {host} must be whole numbers")
        servers.append(server)

    if not servers:
        raise ValueError("At least one server is required")
    if len(servers) > MAX_SERVERS:
        raise ValueError(f"An upstream cannot have more than {MAX_SERVERS} servers")
    return servers


def _attachments():
    service_ids = list(dict.fromkeys(value.strip() for value in request.form.getlist("service_ids") if value.strip()))
    if len(service_ids) > MAX_SERVICES:
        raise ValueError(f"An upstream cannot be attached to more than {MAX_SERVICES} services")
    match_path = (request.form.get("match_path") or "/").strip() or "/"
    if not match_path.startswith("/"):
        raise ValueError("The reverse proxy path must start with /")
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
        raise ValueError("The upstream name is required")

    protocol = (request.form.get("protocol") or "").strip()
    if protocol:
        if protocol not in PROTOCOLS:
            raise ValueError(f"The protocol must be one of {', '.join(PROTOCOLS)}")
        pool["protocol"] = protocol
    elif required:
        pool["protocol"] = "http"

    method = (request.form.get("method") or "").strip()
    if method:
        if method not in METHODS:
            raise ValueError(f"The method must be one of {', '.join(METHODS)}")
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
                raise ValueError("The keepalive count must be a positive whole number")
            pool["keepalive"] = int(keepalive)
        else:
            pool["keepalive"] = None

    # Keyed on presence, not truthiness: the edit modal always submits the textarea, so an
    # emptied description must reach the API as "" instead of being silently dropped.
    if "description" in request.form or required:
        description = (request.form.get("description") or "").strip()
        if len(description) > 4000:
            raise ValueError("The description cannot exceed 4000 characters")
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
        flash(f"Could not fetch upstreams: {exc.message}", "error")
        upstream_rows, total = [], 0

    try:
        services = API_CLIENT.get_services(with_drafts=True)
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not fetch services for upstream assignments: {exc.message}", "error")
        services = []

    return render_template(
        "upstreams.html",
        upstreams=upstream_rows,
        total=total,
        truncated=total > len(upstream_rows),
        services=services,
        methods=METHODS,
        protocols=PROTOCOLS,
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
        flash(f"Upstream {payload['name']} created successfully")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not create the upstream: {exc.message}", "error")
    return _redirect()


@upstreams.route("/upstreams/update", methods=["POST"])
@login_required
def upstreams_update():
    if _readonly():
        return _redirect()
    upstream_id = (request.form.get("upstream_id") or "").strip()
    if not upstream_id:
        flash("The upstream is required", "error")
        return _redirect()
    try:
        API_CLIENT.update_upstream(upstream_id, **_pool(required=False))
        flash("Upstream updated successfully")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not update the upstream: {exc.message}", "error")
    return _redirect()


@upstreams.route("/upstreams/delete", methods=["POST"])
@login_required
def upstreams_delete():
    if _readonly():
        return _redirect()
    upstream_id = (request.form.get("upstream_id") or "").strip()
    if not upstream_id:
        flash("The upstream is required", "error")
        return _redirect()
    try:
        API_CLIENT.delete_upstream(upstream_id)
        flash("Upstream deleted successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        # An upstream still attached to a service is refused by the API on purpose: detaching
        # is the operator's decision, not a side effect of a delete.
        flash(f"Could not delete the upstream: {exc.message}", "error")
    return _redirect()


@upstreams.route("/upstreams/attach", methods=["POST"])
@login_required
def upstreams_attach():
    if _readonly():
        return _redirect()
    upstream_id = (request.form.get("upstream_id") or "").strip()
    try:
        if not upstream_id:
            raise ValueError("The upstream is required")
        attachments = _attachments()
        if not attachments:
            raise ValueError("At least one service is required")
        for attachment in attachments:
            API_CLIENT.attach_upstream(upstream_id, attachment["service_id"], match_path=attachment["match_path"])
        flash(f"Upstream attached to {len(attachments)} service(s)")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not attach the upstream: {exc.message}", "error")
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
        flash("The upstream and the service are required", "error")
        return _redirect()
    try:
        API_CLIENT.detach_upstream(upstream_id, service_id, match_path=match_path)
        flash("Upstream detached successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not detach the upstream: {exc.message}", "error")
    return _redirect()
