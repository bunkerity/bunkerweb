from collections import defaultdict
from datetime import datetime, timedelta
from operator import itemgetter
from psutil import virtual_memory
from os import sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-home",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-home")

from flask import Blueprint, render_template
from flask_login import login_required

from app.dependencies import BW_INSTANCES_UTILS, DB

home = Blueprint("home", __name__)


@home.route("/home", methods=["GET"])
@login_required
def home_page():
    logger.debug("home_page() called")
    
    # Get metrics data
    logger.debug("Retrieving request metrics from instances")
    requests = BW_INSTANCES_UTILS.get_metrics("requests").get("requests", [])
    logger.debug(f"Retrieved {len(requests)} total requests")

    # Get all blocked requests and filter unique ones
    seen_ids = set()
    blocked_requests = [request for request in requests if request.get("id") not in seen_ids and not seen_ids.add(request.get("id"))]
    logger.debug(f"Filtered to {len(blocked_requests)} unique requests")

    request_countries = {}
    request_ips = {}
    current_date = datetime.now().astimezone()
    time_buckets = {(current_date - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0): 0 for i in range(24)}

    logger.debug("Processing request data for analytics")
    processed_requests = 0
    blocked_count = 0
    
    for request in blocked_requests:
        timestamp = datetime.fromtimestamp(request["date"]).astimezone()
        bucket = timestamp.replace(minute=0, second=0, microsecond=0)
        if bucket < current_date - timedelta(hours=24):
            continue

        processed_requests += 1

        if request["country"] not in request_countries:
            request_countries[request["country"]] = {"request": 0, "blocked": 0}
        if request["ip"] not in request_ips:
            request_ips[request["ip"]] = {"request": 0, "blocked": 0}

        request_countries[request["country"]]["request"] = request_countries[request["country"]]["request"] + 1
        request_ips[request["ip"]]["request"] += 1
        
        if request["status"] in (403, 429, 444):
            blocked_count += 1
            request_countries[request["country"]]["blocked"] = request_countries[request["country"]]["blocked"] + 1
            request_ips[request["ip"]]["blocked"] += 1

            if bucket <= current_date:
                time_buckets[bucket] += 1

    logger.debug(f"Processed {processed_requests} requests from last 24h, {blocked_count} blocked")
    logger.debug(f"Found {len(request_countries)} unique countries, {len(request_ips)} unique IPs")

    # Get error metrics
    logger.debug("Retrieving error metrics from instances")
    errors = BW_INSTANCES_UTILS.get_metrics("errors")
    request_errors = defaultdict(int)
    for error, count in errors.items():
        request_errors[int(error.replace("counter_", ""))] = count
    
    logger.debug(f"Found {len(request_errors)} error types")

    # Get system memory information
    logger.debug("Retrieving system memory information")
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

    logger.debug(f"Memory status: {used_gb:.1f}GB/{total_gb:.1f}GB ({used_percent:.1f}%) - state: {memory_state}")

    # Get instances and services data
    logger.debug("Retrieving instances and services data")
    instances = BW_INSTANCES_UTILS.get_instances()
    services = DB.get_services(with_drafts=True)
    logger.debug(f"Found {len(instances)} instances and {len(services)} services")

    # Prepare sorted data for template
    sorted_countries = dict(sorted(request_countries.items(), key=lambda item: (-item[1]["blocked"], item[0])))
    sorted_ips = dict(sorted(request_ips.items(), key=lambda item: (-item[1]["blocked"], item[0])))
    sorted_errors = dict(sorted(request_errors.items(), key=itemgetter(0)))
    time_buckets_iso = {key.isoformat(): value for key, value in time_buckets.items()}

    logger.debug("Rendering home template with dashboard data")
    return render_template(
        "home.html",
        instances=instances,
        services=services,
        request_errors=sorted_errors,
        request_countries=sorted_countries,
        request_ips=sorted_ips,
        time_buckets=time_buckets_iso,
        memory_info=memory_info,
    )
