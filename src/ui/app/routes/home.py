from collections import defaultdict
from datetime import datetime, timedelta
from operator import itemgetter
from psutil import virtual_memory
from os import getenv, sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for home module")

from flask import Blueprint, render_template
from flask_login import login_required

from app.dependencies import BW_INSTANCES_UTILS, DB

home = Blueprint("home", __name__)


# Display comprehensive BunkerWeb dashboard with real-time security metrics and system analytics.
# Aggregates security events from multiple instances, processes request analytics by country and IP,
# analyzes blocked traffic patterns with hourly time bucket visualization, monitors system memory
# usage with intelligent state classification, and presents unified view of deployment health status.
@home.route("/home", methods=["GET"])
@login_required
def home_page():
    if DEBUG_MODE:
        logger.debug("home_page() called - initiating comprehensive dashboard data collection")
    
    # Retrieve security metrics from all BunkerWeb instances for analysis
    requests = BW_INSTANCES_UTILS.get_metrics("requests").get("requests", [])
    if DEBUG_MODE:
        logger.debug(f"Retrieved {len(requests)} request metrics from instances")

    # Filter unique security events by ID to prevent duplicate counting in analytics
    # Uses set-based deduplication to ensure accurate metrics representation
    seen_ids = set()
    blocked_requests = [request for request in requests if request.get("id") not in seen_ids and not seen_ids.add(request.get("id"))]
    if DEBUG_MODE:
        logger.debug(f"Filtered to {len(blocked_requests)} unique blocked requests")

    # Initialize analytics data structures for geographic and network analysis
    # Track requests and blocks by country and IP address for security insights
    request_countries = {}
    request_ips = {}
    current_date = datetime.now().astimezone()
    
    # Create 24-hour time buckets for temporal analysis of blocked requests
    # Each bucket represents one hour for trend visualization and pattern detection
    time_buckets = {(current_date - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0): 0 for i in range(24)}
    if DEBUG_MODE:
        logger.debug(f"Initialized analytics for time window: {current_date - timedelta(hours=23)} to {current_date}")

    # Process each unique request for geographic, network, and temporal analysis
    for request in blocked_requests:
        # Convert timestamp to timezone-aware datetime for accurate time bucket assignment
        timestamp = datetime.fromtimestamp(request["date"]).astimezone()
        bucket = timestamp.replace(minute=0, second=0, microsecond=0)
        
        # Skip requests older than 24 hours to maintain rolling window analysis
        if bucket < current_date - timedelta(hours=24):
            continue

        # Initialize country tracking if first occurrence for geographic analytics
        if request["country"] not in request_countries:
            request_countries[request["country"]] = {"request": 0, "blocked": 0}
        
        # Initialize IP tracking if first occurrence for network security analysis
        if request["ip"] not in request_ips:
            request_ips[request["ip"]] = {"request": 0, "blocked": 0}

        # Increment request counters for both geographic and network analytics
        request_countries[request["country"]]["request"] = request_countries[request["country"]]["request"] + 1
        request_ips[request["ip"]]["request"] += 1
        
        # Process blocked requests (403 Forbidden, 429 Rate Limited, 444 Connection Closed)
        # These status codes indicate security policy enforcement and threat mitigation
        if request["status"] in (403, 429, 444):
            request_countries[request["country"]]["blocked"] = request_countries[request["country"]]["blocked"] + 1
            request_ips[request["ip"]]["blocked"] += 1

            # Add to hourly time bucket for temporal analysis if within current timeframe
            if bucket <= current_date:
                time_buckets[bucket] += 1

    if DEBUG_MODE:
        logger.debug(f"Processed requests - Countries: {len(request_countries)}, IPs: {len(request_ips)}")

    # Retrieve error metrics from instances for comprehensive monitoring dashboard
    errors = BW_INSTANCES_UTILS.get_metrics("errors")
    if DEBUG_MODE:
        logger.debug(f"Retrieved {len(errors)} error metrics")
    
    # Process error counters and normalize format for dashboard display
    # Convert counter names to numeric status codes for proper sorting and visualization
    request_errors = defaultdict(int)
    for error, count in errors.items():
        request_errors[int(error.replace("counter_", ""))] = count

    # Collect system memory information for performance monitoring and capacity planning
    memory = virtual_memory()
    total_gb = memory.total / (1024**3)
    used_gb = memory.used / (1024**3)
    available_gb = memory.available / (1024**3)

    # Calculate memory utilization percentage for threshold-based alerting
    used_percent = (used_gb / total_gb) * 100 if total_gb > 0 else 0

    if DEBUG_MODE:
        logger.debug(f"Memory: {round(total_gb, 1)}GB total, {round(used_gb, 1)}GB used ({round(used_percent, 1)}%)")

    # Classify memory state based on usage percentage and total available memory
    # Provides intelligent alerting thresholds adapted to system capacity
    if used_percent >= 90:
        memory_state = "danger"  # Critical usage regardless of total RAM
    elif total_gb < 8:
        memory_state = "low"
    elif total_gb < 16:
        memory_state = "medium"
    else:
        memory_state = "high"

    if DEBUG_MODE:
        logger.debug(f"Memory state: {memory_state}")

    # Prepare memory information structure for dashboard rendering with rounded values
    memory_info = {
        "total_gb": round(total_gb, 1),
        "used_gb": round(used_gb, 1),
        "used_percent": round(used_percent, 1),
        "available_gb": round(available_gb, 1),
        "memory_state": memory_state,
    }

    if DEBUG_MODE:
        instances_count = len(BW_INSTANCES_UTILS.get_instances())
        services_count = len(DB.get_services(with_drafts=True))
        logger.debug(f"Dashboard data - Instances: {instances_count}, Services: {services_count}")

    # Render dashboard template with comprehensive analytics data and sorted visualizations
    # Sort countries and IPs by blocked request count (descending) for threat prioritization
    # Sort errors by status code (ascending) for logical HTTP status progression
    # Convert time buckets to ISO format for JavaScript datetime compatibility
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
