from collections import defaultdict
from datetime import datetime, timedelta
from operator import itemgetter
from psutil import virtual_memory
from flask import Blueprint, render_template
from flask_login import login_required

from app.dependencies import BW_INSTANCES_UTILS, DB

home = Blueprint("home", __name__)


@home.route("/home", methods=["GET"])
@login_required
def home_page():
    requests = BW_INSTANCES_UTILS.get_metrics("requests").get("requests", [])

    request_countries = {}
    request_ips = {}
    current_date = datetime.now().astimezone()
    time_buckets = {(current_date - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0): 0 for i in range(24)}

    for request in requests:
        timestamp = datetime.fromtimestamp(request["date"]).astimezone()
        bucket = timestamp.replace(minute=0, second=0, microsecond=0)
        if bucket < current_date - timedelta(hours=24):
            continue

        if request["country"] not in request_countries:
            request_countries[request["country"]] = {"request": 0, "blocked": 0}
        if request["ip"] not in request_ips:
            request_ips[request["ip"]] = {"request": 0, "blocked": 0}

        request_countries[request["country"]]["request"] = request_countries[request["country"]]["request"] + 1
        request_ips[request["ip"]]["request"] += 1
        if request["status"] in (403, 429, 444):
            request_countries[request["country"]]["blocked"] = request_countries[request["country"]]["blocked"] + 1
            request_ips[request["ip"]]["blocked"] += 1

            if bucket <= current_date:
                time_buckets[bucket] += 1

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
        time_buckets={key.isoformat(): value for key, value in time_buckets.items()},
        memory_info=memory_info,
    )
