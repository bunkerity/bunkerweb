from contextlib import suppress
from operator import itemgetter

from flask import Blueprint, render_template
from flask_login import login_required

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.utils import flash

timings = Blueprint("timings", __name__)

# Phases that do not run once per request: three worker-lifecycle hooks, the background timer,
# and the internal API. Their share of a request is undefined, so the page shows "—" rather
# than a percentage that would read as latency the visitor paid for.
NON_REQUEST_PHASES = frozenset(("init", "init_worker", "init_workers", "timer", "api"))

# metrics:log() records whole-request duration under its own plugin id, unconditionally and
# independently of METRICS_COLLECT_TIMINGS. It is the denominator, not a row.
REQUEST_PLUGIN, REQUEST_PHASE = "metrics", "request"


def duration(seconds):
    """Render a duration at a scale an operator can read.

    Plugin calls land in microseconds and whole requests in milliseconds, so a single fixed
    unit makes one of the two unreadable — either a wall of zeroes or a wall of digits.
    """
    if seconds is None:
        return "—"
    if seconds >= 1:
        return f"{seconds:.2f} s"
    if seconds >= 0.001:
        return f"{seconds * 1000:.2f} ms"
    return f"{seconds * 1000000:.0f} µs"


def _rows(payload):
    """Flatten {plugin: {phase: aggregate}} into rows an operator can sort by cost.

    Returns ``(rows, request_total)``. ``request_total`` is the whole-request aggregate, pulled
    out of the table because it is what every other row is measured against.
    """
    request_total = None
    rows = []
    for plugin_id, phases in (payload or {}).items():
        if not isinstance(phases, dict):
            continue
        for phase, stats in phases.items():
            if not isinstance(stats, dict):
                continue
            entry = {
                "plugin": plugin_id,
                "phase": phase,
                "count": int(stats.get("count") or 0),
                "mean": float(stats.get("mean") or 0.0),
                "max": float(stats.get("max") or 0.0),
                "total": float(stats.get("sum") or 0.0),
            }
            if plugin_id == REQUEST_PLUGIN and phase == REQUEST_PHASE:
                request_total = entry
                continue
            rows.append(entry)

    denominator = request_total["total"] if request_total else 0.0
    for row in rows:
        # A share is only meaningful against a request the plugin actually ran inside.
        row["share"] = (row["total"] / denominator * 100) if denominator and row["phase"] not in NON_REQUEST_PHASES else None

    rows.sort(key=itemgetter("total"), reverse=True)
    return rows, request_total


@timings.route("/timings", methods=["GET"])
@login_required
def timings_page():
    payload, unreachable = {}, False
    try:
        payload = API_CLIENT.get_metrics_timings()
    except ApiUnavailableError:
        # The API answers 503 when no instance reported, and the client collapses every 5xx to
        # this one error, so "nobody is reporting" and "the API is down" arrive identically.
        # The instance fetch below tells them apart without a second guess.
        unreachable = True
    except ApiClientError as e:
        flash(f"Error fetching plugin timings: {e.message}", "error")

    try:
        instances = API_CLIENT.get_instances()
    except (ApiClientError, ApiUnavailableError):
        flash("Error fetching instances", "error")
        instances = []

    rows, request_total = _rows(payload.get("timings"))

    # An operator staring at an empty table deserves to know whether the feature is off rather
    # than assume the fleet is idle. Only asked for when there is nothing to show.
    collecting = True
    if not rows:
        with suppress(ApiClientError, ApiUnavailableError):
            settings = API_CLIENT.get_global_settings(filtered_settings=["METRICS_COLLECT_TIMINGS"])
            collecting = str(settings.get("METRICS_COLLECT_TIMINGS", "yes")) != "no"

    reporting = payload.get("instances") or {}
    return render_template(
        "timings.html",
        rows=rows,
        request_total=request_total,
        duration=duration,
        collecting=collecting,
        unreachable=unreachable,
        reporting_count=len(reporting),
        total_instances=len(instances),
        partial=payload.get("status") == "partial",
    )
