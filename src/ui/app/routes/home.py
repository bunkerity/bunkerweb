from re import match
from operator import itemgetter
from psutil import virtual_memory
from flask import Blueprint, render_template
from flask_login import login_required

from app.dependencies import BW_INSTANCES_UTILS, DB

home = Blueprint("home", __name__)


@home.route("/home", methods=["GET"])
@login_required
def home_page():
    home_stats_days = 7
    # Use streaming aggregation to avoid loading all requests into memory
    # This significantly reduces memory usage for large Redis datasets
    home_aggregates = BW_INSTANCES_UTILS.get_home_aggregates(hours=24 * home_stats_days)

    request_countries = home_aggregates.get("request_countries", {})
    top_blocked_ips = home_aggregates.get("top_blocked_ips", {})
    blocked_unique_ips = home_aggregates.get("blocked_unique_ips", 0)
    time_buckets = home_aggregates.get("time_buckets", {})

    # Use errors metrics for status distribution (includes 2xx/3xx/4xx/5xx),
    # fallback to request-window statuses when errors metrics are unavailable.
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

    if not request_statuses:
        request_statuses = home_aggregates.get("request_statuses", {})

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

    return render_template(
        "home.html",
        instances=BW_INSTANCES_UTILS.get_instances(),
        services=DB.get_services(with_drafts=True),
        request_errors=dict(sorted(request_statuses.items(), key=itemgetter(0))),
        request_countries=dict(sorted(request_countries.items(), key=lambda item: (-item[1]["blocked"], item[0]))),
        request_ips=top_blocked_ips,
        blocked_unique_ips=blocked_unique_ips,
        time_buckets=time_buckets,
        memory_info=memory_info,
        home_stats_days=home_stats_days,
    )
