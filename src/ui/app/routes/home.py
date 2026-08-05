from datetime import datetime
from re import match
from operator import itemgetter
from psutil import virtual_memory
from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.dependencies import API_CLIENT, BW_INSTANCES_UTILS
from app.api_client import ApiClientError, ApiUnavailableError
from app.utils import LOGGER, flash
from app.routes.utils import cors_required

home = Blueprint("home", __name__)

# Number of "Top reasons for blocks" rows shown on the dashboard card.
HOME_TOP_REASONS_LIMIT = 5


@home.route("/home", methods=["GET"])
@login_required
def home_page():
    home_stats_days = 7

    # Status distribution comes from the lightweight per-status "errors" counter (a small
    # set of Redis counter keys, NOT the heavy 7-day request stream) so the status band and
    # status donut render on the initial page load. The heavy aggregation -- world map,
    # blocked-IP donut, blocking timeline, top reasons, unique-IP count -- is deferred to
    # the async GET /home/metrics endpoint below (fetched by home.js after first paint).
    request_statuses = {}
    errors_metrics = BW_INSTANCES_UTILS.get_metrics("errors")
    if isinstance(errors_metrics, dict):
        for metric_key, count in errors_metrics.items():
            try:
                metric_key_str = str(metric_key).strip()
                if metric_key_str.startswith("counter_"):
                    metric_key_str = metric_key_str.replace("counter_", "", 1)

                status_match = match(r"^(\d{3})", metric_key_str)
                if not status_match:
                    continue
                status_code = int(status_match.group(1))

                metric_value = count
                if isinstance(metric_value, dict):
                    metric_value = metric_value.get("value", 0)
                metric_count = int(float(metric_value))
                if metric_count <= 0:
                    continue
                request_statuses[status_code] = request_statuses.get(status_code, 0) + metric_count
            except Exception:
                continue

    # Get system memory information
    memory = virtual_memory()
    total_gb = memory.total / (1024**3)
    used_gb = memory.used / (1024**3)
    available_gb = memory.available / (1024**3)

    # Calculate percentage consistently based on used/total
    used_percent = (used_gb / total_gb) * 100 if total_gb > 0 else 0

    # Determine memory state based on total RAM and usage
    if used_percent >= 90:
        memory_state = "danger"  # Critical usage regardless of total RAM
    elif total_gb < 8:
        memory_state = "low"
    elif total_gb < 16:
        memory_state = "medium"
    else:
        memory_state = "high"

    memory_info = {
        "total_gb": round(total_gb, 1),
        "used_gb": round(used_gb, 1),
        "used_percent": round(used_percent, 1),
        "available_gb": round(available_gb, 1),
        "memory_state": memory_state,
    }

    try:
        services = API_CLIENT.get_services(with_drafts=True)
    except (ApiClientError, ApiUnavailableError) as e:
        flash(f"Error fetching services: {e.message}", "error")
        services = []

    # Onboarding / "Getting started" signal -- richest untapped source is the metadata
    # endpoint (is_initialized / first_config_saved), each field defaulting safely to
    # False on any failure so the checklist just shows more pending items rather than
    # erroring the whole page out.
    try:
        metadata = API_CLIENT.get_metadata()
    except (ApiClientError, ApiUnavailableError):
        metadata = {}

    mfa_enabled = bool(getattr(current_user, "totp_secret", None))

    # Honest label: BunkerWeb has no live job-queue signal (no Celery queue depth exposed
    # to the UI), so this is a plain scheduled-jobs count, not "jobs queued".
    try:
        jobs = API_CLIENT.get_jobs()
    except (ApiClientError, ApiUnavailableError):
        jobs = {}

    # "Bans active" mini-tile -- a light per-instance count (BW_INSTANCES_UTILS.get_bans(),
    # already deduplicated), not the heavier Redis-backed aggregation the bans dashboard
    # itself uses (that stays in routes/bans.py).
    try:
        bans_active = len(BW_INSTANCES_UTILS.get_bans())
    except Exception:
        bans_active = 0

    # Certificates KPI tile -- reuse the same endpoint the certificates page calls and
    # bucket by the API's own computed status (expiring_soon = within 30 days, expired =
    # past valid_to). "total" is the pre-pagination count, accurate even if the returned
    # list is capped at the 500-cert page limit; per-status tallies cover the fetched page.
    try:
        certs_resp = API_CLIENT.get_certificates(limit=500)
    except (ApiClientError, ApiUnavailableError):
        certs_resp = {}
    certificates = certs_resp.get("certificates", []) if isinstance(certs_resp, dict) else []
    certificates_total = certs_resp.get("total", len(certificates)) if isinstance(certs_resp, dict) else 0
    certs_expired = sum(1 for cert in certificates if cert.get("status") == "expired")
    certs_expiring = sum(1 for cert in certificates if cert.get("status") == "expiring_soon")

    try:
        upstreams_resp = API_CLIENT.get_upstreams(limit=1)
    except (ApiClientError, ApiUnavailableError):
        upstreams_resp = {}
    upstreams_total = upstreams_resp.get("total", len(upstreams_resp.get("upstreams", []))) if isinstance(upstreams_resp, dict) else 0

    return render_template(
        "home.html",
        instances=BW_INSTANCES_UTILS.get_instances(),
        services=services,
        request_errors=dict(sorted(request_statuses.items(), key=itemgetter(0))),
        memory_info=memory_info,
        home_stats_days=home_stats_days,
        is_initialized=bool(metadata.get("is_initialized", False)),
        first_config_saved=bool(metadata.get("first_config_saved", False)),
        mfa_enabled=mfa_enabled,
        jobs_count=len(jobs),
        bans_active=bans_active,
        certificates_total=certificates_total,
        certs_expired=certs_expired,
        certs_expiring=certs_expiring,
        upstreams_total=upstreams_total,
        # Deferred to the async GET /home/metrics fetch (home.js) -- shipped empty so the
        # chart containers + their hidden -data divs exist for the client to populate.
        # `top_reasons` is deliberately NOT here: unlike these, its card renders no server-side
        # rows at all (home.html:217-223 is an empty `#home-top-reasons-body` that home.js
        # fills with DOM APIs, because reason strings are untrusted). Passing an empty list
        # read as "the server still computes this", which is how its tests came to assert a
        # context key the template never used.
        request_countries={},
        request_ips={},
        blocked_unique_ips=0,
        time_buckets={},
        countries_count=0,
    )


@home.route("/home/metrics", methods=["GET"])
@login_required
@cors_required
def home_metrics():
    """Heavy request-metric aggregation for the home dashboard, fetched asynchronously by
    home.js after first paint. Returns the world-map / blocked-IP donut / blocking-timeline
    series plus the derived unique-IP count, top-blocked reasons and country count that the
    map, mini-tile and reasons card display. Kept off the initial /home render so the shell
    paints instantly even when the 7-day Redis aggregation is slow. Any failure degrades to
    an empty payload (HTTP 200) rather than erroring the dashboard."""
    home_stats_days = 7
    # Streaming aggregation over the request window -- the single heaviest call on the page.
    try:
        home_aggregates = BW_INSTANCES_UTILS.get_home_aggregates(hours=24 * home_stats_days)
    except Exception as e:
        LOGGER.warning(f"Home metrics aggregation failed ({e}); returning empty state")
        home_aggregates = {}

    request_countries = home_aggregates.get("request_countries", {})
    top_blocked_ips = home_aggregates.get("top_blocked_ips", {})
    blocked_unique_ips = home_aggregates.get("blocked_unique_ips", 0)
    time_buckets = home_aggregates.get("time_buckets", {})

    # "Top reasons for blocks" -- reuse the reports facet endpoint (count_only, so no row
    # data is transferred) rather than a new DB/API method.
    try:
        reason_facets = API_CLIENT.get_metrics_requests(count_only=True, include_pane_counts=True).get("pane_counts", {}).get("reason", {})
    except (ApiClientError, ApiUnavailableError):
        reason_facets = {}

    reason_totals = [(str(reason), int(counts.get("total", 0))) for reason, counts in reason_facets.items()] if isinstance(reason_facets, dict) else []
    reason_grand_total = sum(count for _, count in reason_totals)
    top_reasons = [
        {"reason": reason, "count": count, "pct": round(count / reason_grand_total * 100, 1) if reason_grand_total else 0}
        for reason, count in sorted(reason_totals, key=lambda item: -item[1])[:HOME_TOP_REASONS_LIMIT]
    ]

    return jsonify(
        {
            "status": "success",
            "request_countries": dict(sorted(request_countries.items(), key=lambda item: (-item[1]["blocked"], item[0]))),
            "request_ips": top_blocked_ips,
            "blocked_unique_ips": blocked_unique_ips,
            "time_buckets": time_buckets,
            "top_reasons": top_reasons,
            "countries_count": len(request_countries),
        }
    )


@home.route("/home/dashboard", methods=["POST"])
@login_required
@cors_required
def home_dashboard():
    """Picker-driven data for the home dashboard's mini-tile trend + area chart.

    Mirrors ``reports_dashboard`` (routes/reports.py) -- same start/end/bucket parsing
    and the same 400 (bad range) / 503 (metrics API down) error mapping -- but only
    returns the timeseries + offenders the home page actually renders (no rules table).
    """
    try:
        end = int(request.form.get("end") or datetime.now().timestamp())
        start = int(request.form.get("start") or (end - 86400))
        bucket = request.form.get("bucket", "hour")
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid start/end"}), 400

    try:
        timeseries = API_CLIENT.get_metrics_timeseries(start=start, end=end, bucket=bucket)
        offenders = API_CLIENT.get_metrics_top_offenders(start=start, end=end, limit=10)
    except ApiClientError as e:
        if e.status_code == 400:
            LOGGER.warning(f"Metrics API rejected the request ({e})")
            return jsonify({"status": "error", "message": str(e) or "Invalid range"}), 400
        LOGGER.warning(f"Metrics API unavailable ({e}); home dashboard will show empty state")
        return jsonify({"status": "error", "message": "Metrics service unavailable"}), 503
    except ApiUnavailableError as e:
        LOGGER.warning(f"Metrics API unavailable ({e}); home dashboard will show empty state")
        return jsonify({"status": "error", "message": "Metrics service unavailable"}), 503

    return jsonify({"status": "success", "timeseries": timeseries, "offenders": offenders.get("offenders", [])})
