from collections import defaultdict
from operator import itemgetter
from psutil import virtual_memory
from flask import Blueprint, render_template
from flask_login import login_required

from app.dependencies import BW_INSTANCES_UTILS, DB

home = Blueprint("home", __name__)


@home.route("/home", methods=["GET"])
@login_required
def home_page():
    # Use streaming aggregation to avoid loading all requests into memory
    # This significantly reduces memory usage for large Redis datasets
    home_aggregates = BW_INSTANCES_UTILS.get_home_aggregates(hours=24)

    request_countries = home_aggregates.get("request_countries", {})
    request_ips = home_aggregates.get("request_ips", {})
    time_buckets = home_aggregates.get("time_buckets", {})

    errors = BW_INSTANCES_UTILS.get_metrics("errors")
    request_errors = defaultdict(int)
    for error, count in errors.items():
        request_errors[int(error.replace("counter_", ""))] = count

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
        request_errors=dict(sorted(request_errors.items(), key=itemgetter(0))),
        request_countries=dict(sorted(request_countries.items(), key=lambda item: (-item[1]["blocked"], item[0]))),
        request_ips=dict(sorted(request_ips.items(), key=lambda item: (-item[1]["blocked"], item[0]))),
        time_buckets=time_buckets,
        memory_info=memory_info,
    )
