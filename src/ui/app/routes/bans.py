from collections import defaultdict
from datetime import datetime, timezone
from json import JSONDecodeError, dumps, loads
from math import floor
from time import time
from html import escape
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
    title="UI-bans",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-bans")

from flask import Blueprint, flash as flask_flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, BW_INSTANCES_UTILS, DB
from app.utils import flash

from app.routes.utils import cors_required, get_redis_client, get_remain, handle_error, verify_data_in_form

bans = Blueprint("bans", __name__)


@bans.route("/bans", methods=["GET"])
@login_required
def bans_page():
    logger.debug("bans_page() called")
    
    # Get list of services for the service dropdown in the UI
    services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"]
    if isinstance(services, str):
        services = services.split()

    logger.debug(f"Retrieved {len(services)} services for bans page")
    return render_template("bans.html", services=services)


@bans.route("/bans/fetch", methods=["POST"])
@login_required
@cors_required
def bans_fetch():
    logger.debug("bans_fetch() called")
    redis_client = get_redis_client()

    bans = []
    if redis_client:
        logger.debug("Retrieving bans from Redis")
        try:
            # Retrieve global bans from Redis (stored with prefix "bans_ip_")
            global_ban_count = 0
            for key in redis_client.scan_iter("bans_ip_*"):
                key_str = key.decode("utf-8", "replace")
                ip = key_str.replace("bans_ip_", "")
                data = redis_client.get(key)
                if not data:
                    continue
                exp = redis_client.ttl(key)
                try:
                    ban_data = loads(data.decode("utf-8", "replace"))
                    # Ensure consistent scope for frontend display
                    ban_data["ban_scope"] = "global"
                    ban_data["permanent"] = ban_data.get("permanent", False) or exp == 0

                    # Check if this is a permanent ban
                    if ban_data.get("permanent", False):
                        exp = 0  # Override TTL for permanent bans

                    bans.append({"ip": ip, "exp": exp, "permanent": ban_data.get("permanent", False)} | ban_data)
                    global_ban_count += 1
                except Exception as e:
                    logger.exception(f"Failed to decode ban data for {ip}")
                    logger.error(f"Failed to decode ban data for {ip}: {e}")

            # Retrieve service-specific bans from Redis (stored with prefix "bans_service_*_ip_*")
            service_ban_count = 0
            for key in redis_client.scan_iter("bans_service_*_ip_*"):
                key_str = key.decode("utf-8", "replace")
                service, ip = key_str.replace("bans_service_", "").split("_ip_")
                data = redis_client.get(key)
                if not data:
                    continue
                exp = redis_client.ttl(key)
                try:
                    ban_data = loads(data.decode("utf-8", "replace"))
                    # Ensure consistent scope for frontend display
                    ban_data["ban_scope"] = "service"
                    ban_data["service"] = service
                    ban_data["permanent"] = ban_data.get("permanent", False) or exp == 0

                    # Check if this is a permanent ban
                    if ban_data.get("permanent", False):
                        exp = 0  # Override TTL for permanent bans

                    bans.append({"ip": ip, "exp": exp, "permanent": ban_data.get("permanent", False)} | ban_data)
                    service_ban_count += 1
                except Exception as e:
                    logger.exception(f"Failed to decode ban data for {ip} on service {service}")
                    logger.error(f"Failed to decode ban data for {ip} on service {service}: {e}")
            
            logger.debug(f"Retrieved {global_ban_count} global bans and {service_ban_count} service bans from Redis")
            
        except BaseException as e:
            logger.exception("Couldn't get bans from redis")
            logger.error(f"Couldn't get bans from redis: {e}")
            flash("Failed to fetch bans from Redis, see logs for more information.", "error")
            bans = []

    # Also fetch bans from all connected BunkerWeb instances
    logger.debug("Retrieving bans from BunkerWeb instances")
    instance_bans = BW_INSTANCES_UTILS.get_bans()
    logger.debug(f"Retrieved {len(instance_bans)} bans from instances")

    # Current timestamp for calculating remaining times
    timestamp_now = time()

    # Process instance bans and avoid duplicates with Redis bans
    instance_ban_count = 0
    for ban in instance_bans:
        # Normalize ban scope to ensure consistent frontend display
        if "ban_scope" not in ban:
            if ban.get("service", "_") == "_":
                ban["ban_scope"] = "global"
            else:
                ban["ban_scope"] = "service"

        # Skip if this ban already exists in the list (checking IP, scope and service combination)
        if not any(b["ip"] == ban["ip"] and b["ban_scope"] == ban["ban_scope"] and (b.get("service", "_") == ban.get("service", "_")) for b in bans):
            bans.append(ban)
            instance_ban_count += 1

    logger.debug(f"Added {instance_ban_count} unique instance bans, total bans: {len(bans)}")

    # Format ban times for display
    permanent_count = 0
    for ban in bans:
        exp = ban.pop("exp", 0)

        # Handle permanent bans (exp = 0)
        if exp == 0 or ban.get("permanent", False):
            ban["remain"] = "permanent"
            ban["permanent"] = True
            ban["end_date"] = "permanent"
            permanent_count += 1
        else:
            # Calculate human-readable remaining time for non-permanent bans
            remain = ("unknown", "unknown") if exp <= 0 else get_remain(exp)
            ban["remain"] = remain[0]
            # Format timestamps for start and end dates
            ban["start_date"] = datetime.fromtimestamp(floor(ban["date"])).astimezone().isoformat()
            ban["end_date"] = datetime.fromtimestamp(floor(timestamp_now + exp)).astimezone().isoformat()

    logger.debug(f"Processed ban times: {permanent_count} permanent, {len(bans) - permanent_count} temporary")

    # DataTables parameters
    draw = int(request.form.get("draw", 1))
    start = int(request.form.get("start", 0))
    length = int(request.form.get("length", 10))
    search_value = request.form.get("search[value]", "").lower()
    order_column_index = int(request.form.get("order[0][column]", 0)) - 1
    order_direction = request.form.get("order[0][dir]", "desc")
    search_panes = defaultdict(list)
    for key, value in request.form.items():
        if key.startswith("searchPanes["):
            field = key.split("[")[1].split("]")[0]
            search_panes[field].append(value)

    logger.debug(f"DataTables params: draw={draw}, start={start}, length={length}, "
                f"search='{search_value}', order_col={order_column_index}, order_dir={order_direction}")
    logger.debug(f"SearchPanes filters: {dict(search_panes)}")

    # DataTable columns (must match frontend order)
    columns = [
        "date",  # 0
        "ip",  # 1
        "country",  # 2
        "reason",  # 3
        "scope",  # 4
        "service",  # 5
        "end_date",  # 6
        "time_left",  # 7
        "actions",  # 8
    ]

    # Helper: format a ban for DataTable row
    def format_ban(ban):
        # Defensive: some bans may lack some fields
        return {
            "date": datetime.fromtimestamp(floor(ban.get("date", 0))).isoformat() if ban.get("date") else "N/A",
            "ip": escape(str(ban.get("ip", "N/A"))),
            "country": escape(str(ban.get("country", "N/A"))),
            "reason": escape(str(ban.get("reason", "N/A"))),
            "scope": escape(str(ban.get("ban_scope", "global"))),
            "service": escape(str(ban.get("service") or "_")),
            "end_date": "permanent" if ban.get("permanent", False) else escape(str(ban.get("end_date", "N/A"))),
            "time_left": "permanent" if ban.get("permanent", False) else escape(str(ban.get("remain", "N/A"))),
            "permanent": bool(ban.get("permanent", False)),
            "actions": "",  # Actions column for buttons
        }

    # Apply searchPanes filters
    def filter_by_search_panes(bans):
        filtered = bans
        for field, selected_values in search_panes.items():
            if not selected_values:
                continue
            if field == "date":
                # Special handling for date searchpane
                now = time()

                def date_filter(ban):
                    ban_date = ban.get("date", 0)
                    for val in selected_values:
                        if val == "last_24h" and now - ban_date < 86400:
                            return True
                        if val == "last_7d" and now - ban_date < 604800:
                            return True
                        if val == "last_30d" and now - ban_date < 2592000:
                            return True
                        if val == "older_30d" and now - ban_date >= 2592000:
                            return True
                    return False

                filtered = list(filter(date_filter, filtered))
            elif field == "scope":
                # Special handling for scope searchpane
                def scope_filter(ban):
                    for val in selected_values:
                        if val == "global" == ban.get("ban_scope"):
                            return True
                        if val == "service" == ban.get("ban_scope"):
                            return True
                    return False

                filtered = list(filter(scope_filter, filtered))
            # Special handling for end_date searchpane
            if field == "end_date":
                # Special handling for end_date searchpane
                now = time()

                def end_date_filter(ban):
                    # Always include permanent bans in the "future_30d" category
                    if ban.get("permanent", False) and "future_30d" in selected_values:
                        return True

                    exp = ban.get("exp", 0)
                    if ban.get("permanent", False):
                        return "permanent" in selected_values

                    for val in selected_values:
                        if val == "permanent" and ban.get("permanent", False):
                            return True
                        if val == "next_24h" and exp < 86400:
                            return True
                        if val == "next_7d" and exp < 604800:
                            return True
                        if val == "next_30d" and exp < 2592000:
                            return True
                        if val == "future_30d" and exp >= 2592000:
                            return True
                    return False

                filtered = list(filter(end_date_filter, filtered))
            elif field == "service":
                # Special handling for service searchpane
                def service_filter(ban):
                    ban_service = ban.get("service")
                    # Normalize global bans to "_"
                    if ban.get("ban_scope") == "global" or ban_service in (None, ""):
                        ban_service = "_"
                    return str(ban_service) in selected_values

                filtered = list(filter(service_filter, filtered))
            else:
                filtered = [ban for ban in filtered if str(ban.get(field, "N/A")) in selected_values]
        return filtered

    # Global search filtering
    def global_search_filter(ban):
        # Special handling for permanent bans in search
        if search_value == "permanent" and ban.get("permanent", False):
            return True

        return any(search_value in str(ban.get(col, "")).lower() for col in columns)

    # Sort bans
    def sort_bans(bans):
        if 0 <= order_column_index < len(columns):
            sort_key = columns[order_column_index]
            # Special handling for end_date and time_left sorting for permanent bans
            if sort_key in ("end_date", "time_left"):
                # For these columns, permanent bans should sort either at the top or bottom
                # depending on sort order
                bans.sort(
                    key=lambda x: ("0" if order_direction == "desc" else "z") if x.get("permanent", False) else x.get(sort_key, ""),
                    reverse=(order_direction == "desc"),
                )
            else:
                bans.sort(key=lambda x: x.get(sort_key, ""), reverse=(order_direction == "desc"))

    # Apply filters and sort
    if search_value:
        filtered_bans = list(filter(global_search_filter, bans))
        logger.debug(f"After global search: {len(filtered_bans)} bans")
    else:
        filtered_bans = bans
    
    filtered_bans = filter_by_search_panes(filtered_bans)
    logger.debug(f"After search panes filter: {len(filtered_bans)} bans")
    
    sort_bans(filtered_bans)

    if length == -1:
        paginated_bans = filtered_bans
    else:
        paginated_bans = filtered_bans[start : start + length]
    
    logger.debug(f"Paginated to {len(paginated_bans)} bans")

    # Format for DataTable
    formatted_bans = [format_ban(ban) for ban in paginated_bans]

    # Calculate pane counts (for SearchPanes)
    pane_counts = defaultdict(lambda: defaultdict(lambda: {"total": 0, "count": 0}))

    # Use IP+scope+service as unique ID for bans
    def ban_id(ban):
        service = ban.get("service")
        # Normalize service to "_" for global bans or when service is None
        if ban.get("ban_scope") == "global" or service is None:
            service = "_"
        return f"{ban.get('ip','')}|{ban.get('ban_scope','')}|{service}"

    filtered_ids = {ban_id(ban) for ban in filtered_bans}
    for ban in bans:
        for field in columns[1:]:  # skip date
            value = ban.get(field, "N/A")
            # Special handling for service field to normalize global bans
            if field == "service":
                if ban.get("ban_scope") == "global" or value in (None, ""):
                    value = "_"
            if isinstance(value, (dict, list)):
                value = str(value)
            pane_counts[field][value]["total"] += 1
            if ban_id(ban) in filtered_ids:
                pane_counts[field][value]["count"] += 1

    # Prepare SearchPanes options (special formatting for date, country, scope, service, and end_date)
    base_flags_url = url_for("static", filename="img/flags")
    search_panes_options = {}

    # Special handling for date searchpane options
    search_panes_options["date"] = [
        {
            "label": '<span data-i18n="searchpane.last_24h">Last 24 hours</span>',
            "value": "last_24h",
            "total": sum(1 for ban in bans if time() - ban.get("date", 0) < 86400),
            "count": sum(1 for ban in filtered_bans if time() - ban.get("date", 0) < 86400),
        },
        {
            "label": '<span data-i18n="searchpane.last_7d">Last 7 days</span>',
            "value": "last_7d",
            "total": sum(1 for ban in bans if time() - ban.get("date", 0) < 604800),
            "count": sum(1 for ban in filtered_bans if time() - ban.get("date", 0) < 604800),
        },
        {
            "label": '<span data-i18n="searchpane.last_30d">Last 30 days</span>',
            "value": "last_30d",
            "total": sum(1 for ban in bans if time() - ban.get("date", 0) < 2592000),
            "count": sum(1 for ban in filtered_bans if time() - ban.get("date", 0) < 2592000),
        },
        {
            "label": '<span data-i18n="searchpane.older_30d">More than 30 days</span>',
            "value": "older_30d",
            "total": sum(1 for ban in bans if time() - ban.get("date", 0) >= 2592000),
            "count": sum(1 for ban in filtered_bans if time() - ban.get("date", 0) >= 2592000),
        },
    ]

    # Special handling for country searchpane options
    search_panes_options["country"] = []
    for code, counts in pane_counts["country"].items():
        country_code = str(code).lower()
        search_panes_options["country"].append(
            {
                "label": f'<img src="{base_flags_url}/{"zz" if code in ("unknown", "local", "n/a")  else country_code}.svg" class="border border-1 p-0 me-1" height="17" />&nbsp;－&nbsp;<span data-i18n="country.{"not_applicable" if code in ("unknown", "local") else str(code).upper()}">{"N/A" if code in ("unknown", "local") else code}</span>',
                "value": code,
                "total": counts["total"],
                "count": counts["count"],
            }
        )

    # Special handling for scope searchpane options
    search_panes_options["scope"] = [
        {
            "label": '<i class="bx bx-xs bx-globe"></i> <span data-i18n="scope.global">Global</span>',
            "value": "global",
            "total": sum(1 for ban in bans if ban.get("ban_scope") == "global"),
            "count": sum(1 for ban in filtered_bans if ban.get("ban_scope") == "global"),
        },
        {
            "label": '<i class="bx bx-xs bx-server"></i> <span data-i18n="scope.service_specific">Service</span>',
            "value": "service",
            "total": sum(1 for ban in bans if ban.get("ban_scope") == "service"),
            "count": sum(1 for ban in filtered_bans if ban.get("ban_scope") == "service"),
        },
    ]

    # Special handling for service searchpane options
    search_panes_options["service"] = []
    for name, counts in pane_counts["service"].items():
        display_name = "default server" if (not name or name == "_") else escape(str(name))
        search_panes_options["service"].append(
            {
                "label": display_name,
                "value": escape(str(name)),
                "total": counts["total"],
                "count": counts["count"],
            }
        )

    # Special handling for end_date searchpane options
    search_panes_options["end_date"] = [
        {
            "label": '<span data-i18n="searchpane.permanent">Permanent</span>',
            "value": "permanent",
            "total": sum(1 for ban in bans if ban.get("permanent", False) or ban.get("exp", 0) == 0),
            "count": sum(1 for ban in filtered_bans if ban.get("permanent", False) or ban.get("exp", 0) == 0),
        },
        {
            "label": '<span data-i18n="searchpane.next_24h">Next 24 hours</span>',
            "value": "next_24h",
            "total": sum(1 for ban in bans if not ban.get("permanent", False) and ban.get("exp", 0) < 86400),
            "count": sum(1 for ban in filtered_bans if not ban.get("permanent", False) and ban.get("exp", 0) < 86400),
        },
        {
            "label": '<span data-i18n="searchpane.next_7d">Next 7 days</span>',
            "value": "next_7d",
            "total": sum(1 for ban in bans if not ban.get("permanent", False) and ban.get("exp", 0) < 604800),
            "count": sum(1 for ban in filtered_bans if not ban.get("permanent", False) and ban.get("exp", 0) < 604800),
        },
        {
            "label": '<span data-i18n="searchpane.next_30d">Next 30 days</span>',
            "value": "next_30d",
            "total": sum(1 for ban in bans if not ban.get("permanent", False) and ban.get("exp", 0) < 2592000),
            "count": sum(1 for ban in filtered_bans if not ban.get("permanent", False) and ban.get("exp", 0) < 2592000),
        },
        {
            "label": '<span data-i18n="searchpane.future_30d">More than 30 days</span>',
            "value": "future_30d",
            "total": sum(1 for ban in bans if not ban.get("permanent", False) and ban.get("exp", 0) >= 2592000),
            "count": sum(1 for ban in filtered_bans if not ban.get("permanent", False) and ban.get("exp", 0) >= 2592000),
        },
    ]

    # Add any remaining fields from pane_counts
    for field, values in pane_counts.items():
        if field not in search_panes_options:
            search_panes_options[field] = [
                {
                    "label": escape(str(value)),
                    "value": escape(str(value)),
                    "total": counts["total"],
                    "count": counts["count"],
                }
                for value, counts in values.items()
            ]

    logger.debug(f"Returning DataTables response: {len(formatted_bans)} formatted bans")

    # Response
    return jsonify(
        {
            "draw": draw,
            "recordsTotal": len(bans),
            "recordsFiltered": len(filtered_bans),
            "data": formatted_bans,
            "searchPanes": {"options": search_panes_options},
        }
    )


@bans.route("/bans/ban", methods=["POST"])
@login_required
def bans_ban():
    logger.debug("bans_ban() called")
    
    # Check database state
    if DB.readonly:
        logger.debug("Database is in read-only mode, blocking ban operation")
        return handle_error("Database is in read-only mode", "bans")

    # Validate input parameters
    verify_data_in_form(
        data={"bans": None},
        err_message="Missing bans parameter on /bans/ban.",
        redirect_url="bans",
        next=True,
    )
    bans_param = request.form["bans"]
    if not bans_param:
        logger.debug("No bans provided in request")
        return handle_error("No bans.", "bans", True)
    
    try:
        bans_list = loads(bans_param)
        logger.debug(f"Processing {len(bans_list)} ban requests")
    except JSONDecodeError:
        logger.exception("Invalid JSON in bans parameter")
        return handle_error("Invalid bans parameter on /bans/ban.", "bans", True)

    redis_client = get_redis_client()
    successful_bans = 0
    
    for i, ban in enumerate(bans_list):
        logger.debug(f"Processing ban {i+1}/{len(bans_list)}: {ban}")
        
        # Validate ban structure
        if not isinstance(ban, dict) or "ip" not in ban:
            logger.debug(f"Invalid ban structure: {ban}")
            flask_flash(f"Invalid ban: {ban}, skipping it ...", "error")
            continue

        # Extract and normalize ban parameters
        ip = ban.get("ip", "")
        reason = ban.get("reason", "ui")
        ban_scope = ban.get("ban_scope", "global")
        service = ban.get("service", "")

        logger.debug(f"Ban details: IP={ip}, reason={reason}, scope={ban_scope}, service={service}")

        # Check for permanent ban
        is_permanent = False
        if ban.get("end_date") == "0" or ban.get("exp") == 0:
            is_permanent = True
            ban_end = 0  # Set to 0 for permanent bans
            logger.debug(f"Permanent ban detected for IP {ip}")
        else:
            try:
                # Parse and normalize the ban end date from ISO format
                ban_end_str = ban["end_date"]
                if "." in ban_end_str and "Z" in ban_end_str:
                    ban_end_str = ban_end_str.split(".")[0] + "Z"

                ban_end = datetime.fromisoformat(ban_end_str.replace("Z", "+00:00"))
                # Ensure timezone awareness
                if ban_end.tzinfo is None:
                    ban_end = ban_end.replace(tzinfo=timezone.utc)

                # Calculate seconds from now until ban end
                current_time = datetime.now().astimezone()
                ban_end = (ban_end - current_time).total_seconds()

                # Ensure ban duration is positive
                if ban_end <= 0:
                    logger.debug(f"Invalid ban duration for IP {ip}: {ban_end}")
                    flask_flash(f"Invalid ban duration for IP {ip}, must be in the future", "error")
                    continue

                logger.debug(f"Temporary ban for IP {ip}: {ban_end} seconds")

            except ValueError as e:
                logger.exception(f"Invalid ban date format for IP {ip}")
                flask_flash(f"Invalid ban date format: {ban['end_date']}, error: {e}", "error")
                continue

        # Validate service name for service-specific bans
        if ban_scope == "service":
            services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"]
            if isinstance(services, str):
                services = services.split()

            # Force global ban if service is invalid
            if not service or service == "Web UI" or service not in services:
                logger.debug(f"Invalid service '{service}' for IP {ip}, defaulting to global ban")
                flask_flash(f"Invalid service '{service}' for IP {ip}, defaulting to global ban", "warning")
                ban_scope = "global"
                service = "Web UI"

        if redis_client:
            try:
                # Generate the appropriate Redis key based on ban scope
                if ban_scope == "service" and service != "Web UI":
                    ban_key = f"bans_service_{service}_ip_{ip}"
                else:
                    ban_key = f"bans_ip_{ip}"
                    ban_scope = "global"

                logger.debug(f"Storing ban in Redis with key: {ban_key}")

                # Store ban data in Redis with proper expiration
                ban_data = {"reason": reason, "date": time(), "service": service, "ban_scope": ban_scope, "permanent": is_permanent}

                ok = redis_client.set(ban_key, dumps(ban_data))
                if not ok:
                    logger.debug(f"Failed to store ban for {ip} in Redis")
                    flash(f"Couldn't ban {ip} on redis", "error")

                # Only set expiration for non-permanent bans
                if not is_permanent and ban_end > 0:
                    redis_client.expire(ban_key, int(ban_end))
                    logger.debug(f"Set expiration for {ip}: {int(ban_end)} seconds")
                
            except BaseException as e:
                logger.exception(f"Couldn't ban {ip} on redis: {e}")
                flash(f"Failed to ban {ip} on redis, see logs for more information.", "error")

        # Propagate ban to all connected BunkerWeb instances
        logger.debug(f"Propagating ban for {ip} to BunkerWeb instances")
        resp = BW_INSTANCES_UTILS.ban(ip, ban_end, reason, service, ban_scope)
        if resp:
            logger.debug(f"Failed to ban {ip} on some instances: {resp}")
            flash(f"Couldn't ban {ip} on the following instances: {', '.join(resp)}", "error")
        else:
            successful_bans += 1
            if ban_scope == "service":
                if is_permanent:
                    logger.info(f"Successfully banned {ip} permanently for service {service}")
                    flash(f"Successfully banned {ip} permanently for service {service}")
                else:
                    logger.info(f"Successfully banned {ip} for service {service}")
                    flash(f"Successfully banned {ip} for service {service}")
            else:
                if is_permanent:
                    logger.info(f"Successfully banned {ip} permanently globally")
                    flash(f"Successfully banned {ip} permanently globally")
                else:
                    logger.info(f"Successfully banned {ip} globally")
                    flash(f"Successfully banned {ip} globally")

    logger.info(f"Ban operation completed: {successful_bans}/{len(bans_list)} successful")
    return redirect(url_for("loading", next=url_for("bans.bans_page"), message=f"Banning {len(bans_list)} IP{'s' if len(bans_list) > 1 else ''}"))


@bans.route("/bans/unban", methods=["POST"])
@login_required
def bans_unban():
    logger.debug("bans_unban() called")
    
    # Check database state
    if DB.readonly:
        logger.debug("Database is in read-only mode, blocking unban operation")
        return handle_error("Database is in read-only mode", "bans")

    # Validate input parameters
    verify_data_in_form(
        data={"ips": None},
        err_message="Missing bans parameter on /bans/unban.",
        redirect_url="bans",
        next=True,
    )
    unbans_param = request.form["ips"]
    if not unbans_param:
        logger.debug("No unbans provided in request")
        return handle_error("No bans.", "ips", True)
    
    try:
        unbans = loads(unbans_param)
        logger.debug(f"Processing {len(unbans)} unban requests")
    except JSONDecodeError:
        logger.exception("Invalid JSON in ips parameter")
        return handle_error("Invalid ips parameter on /bans/unban.", "bans", True)

    redis_client = get_redis_client()
    successful_unbans = 0
    
    for i, unban in enumerate(unbans):
        logger.debug(f"Processing unban {i+1}/{len(unbans)}: {unban}")
        
        # Validate unban structure
        if "ip" not in unban:
            logger.debug(f"Invalid unban structure: {unban}")
            flask_flash(f"Invalid unban: {unban}, skipping it ...", "error")
            continue

        # Extract and normalize unban parameters
        ip = unban.get("ip")
        ban_scope = unban.get("ban_scope", "global")
        service = unban.get("service")

        logger.debug(f"Unban details: IP={ip}, scope={ban_scope}, service={service}")

        # Normalize Web UI and default services to global scope
        if service in ("default server", "Web UI", "unknown"):
            if ban_scope == "service":
                logger.debug(f"Invalid service for IP {ip}, defaulting to global unban")
                flask_flash(f"Invalid service for IP {ip}, defaulting to global unban", "warning")
            service = None
            ban_scope = "global"

        if redis_client:
            try:
                # For service-specific unbans, only remove that service's ban
                # For global unbans, remove both global and all service-specific bans
                if service and ban_scope == "service":
                    key_deleted = redis_client.delete(f"bans_service_{service}_ip_{ip}")
                    logger.debug(f"Deleted service-specific ban for {ip} on {service}: {key_deleted} key(s)")
                else:
                    # Remove global ban
                    global_deleted = redis_client.delete(f"bans_ip_{ip}")
                    logger.debug(f"Deleted global ban for {ip}: {global_deleted} key(s)")
                    
                    # Also remove all service-specific bans for this IP
                    service_keys_deleted = 0
                    for key in redis_client.scan_iter(f"bans_service_*_ip_{ip}"):
                        redis_client.delete(key)
                        service_keys_deleted += 1
                    logger.debug(f"Deleted {service_keys_deleted} service-specific bans for {ip}")
                    
            except BaseException as e:
                logger.exception(f"Couldn't unban {ip} on redis: {e}")
                flash(f"Failed to unban {ip} on redis, see logs for more information.", "error")

        # Propagate unban to all connected BunkerWeb instances
        logger.debug(f"Propagating unban for {ip} to BunkerWeb instances")
        resp = BW_INSTANCES_UTILS.unban(ip, service)
        if resp:
            service_text = f" for service {service}" if service else ""
            logger.debug(f"Failed to unban {ip}{service_text} on some instances: {resp}")
            flash(f"Couldn't unban {ip}{service_text} on the following instances: {', '.join(resp)}", "error")
        else:
            successful_unbans += 1
            service_text = f" for service {service}" if service else ""
            logger.info(f"Successfully unbanned {ip}{service_text}")
            flash(f"Successfully unbanned {ip}{service_text}")

    logger.info(f"Unban operation completed: {successful_unbans}/{len(unbans)} successful")
    return redirect(url_for("loading", next=url_for("bans.bans_page"), message=f"Unbanning {len(unbans)} IP{'s' if len(unbans) > 1 else ''}"))


@bans.route("/bans/update_duration", methods=["POST"])
@login_required
def bans_update_duration():
    logger.debug("bans_update_duration() called")
    
    # Check database state
    if DB.readonly:
        logger.debug("Database is in read-only mode, blocking duration update")
        return handle_error("Database is in read-only mode", "bans")

    # Validate input parameters
    verify_data_in_form(
        data={"updates": None},
        err_message="Missing updates parameter on /bans/update_duration.",
        redirect_url="bans",
        next=True,
    )
    updates_param = request.form["updates"]
    if not updates_param:
        logger.debug("No updates provided in request")
        return handle_error("No updates.", "bans", True)
    
    try:
        updates = loads(updates_param)
        logger.debug(f"Processing {len(updates)} duration update requests")
    except JSONDecodeError:
        logger.exception("Invalid JSON in updates parameter")
        return handle_error("Invalid updates parameter on /bans/update_duration.", "bans", True)

    redis_client = get_redis_client()

    # Fetch existing bans from instances to get original reasons
    logger.debug("Fetching existing bans from instances for reason preservation")
    instance_bans = BW_INSTANCES_UTILS.get_bans()
    instance_bans_dict = {}
    for ban in instance_bans:
        # Normalize ban scope if missing
        if "ban_scope" not in ban:
            if ban.get("service", "_") == "_":
                ban["ban_scope"] = "global"
            else:
                ban["ban_scope"] = "service"

        ban_key = f"{ban.get('ip')}|{ban.get('ban_scope', 'global')}|{ban.get('service', '_') if ban['ban_scope'] == 'service' else '_'}"
        instance_bans_dict[ban_key] = ban

    logger.debug(f"Built instance bans dictionary with {len(instance_bans_dict)} entries")
    successful_updates = 0

    for i, update in enumerate(updates):
        logger.debug(f"Processing duration update {i+1}/{len(updates)}: {update}")
        
        # Validate update structure
        if not isinstance(update, dict) or "ip" not in update or "duration" not in update:
            logger.debug(f"Invalid update structure: {update}")
            flask_flash("Invalid update structure for one of the bans, skipping", "error")
            continue

        # Extract and normalize update parameters
        ip = update.get("ip", "")
        duration = update.get("duration", "")
        ban_scope = update.get("ban_scope", "global")
        service = update.get("service", "")

        logger.debug(f"Update details: IP={ip}, duration={duration}, scope={ban_scope}, service={service}")

        # Calculate new expiration time based on duration
        if duration == "permanent":
            is_permanent = True
            new_exp = 0
            logger.debug(f"Setting permanent ban for {ip}")
        elif duration == "1h":
            is_permanent = False
            new_exp = 3600  # 1 hour in seconds
            logger.debug(f"Setting 1 hour ban for {ip}")
        elif duration == "24h":
            is_permanent = False
            new_exp = 86400  # 24 hours in seconds
            logger.debug(f"Setting 24 hour ban for {ip}")
        elif duration == "1w":
            is_permanent = False
            new_exp = 604800  # 1 week in seconds
            logger.debug(f"Setting 1 week ban for {ip}")
        elif duration == "custom":
            # Handle custom duration from end_date
            custom_end_date = update.get("end_date")
            logger.debug(f"Processing custom end date for {ip}: {custom_end_date}")

            if custom_end_date:
                try:
                    # Parse and normalize the custom end date from ISO format
                    end_date_str = custom_end_date
                    if "." in end_date_str and "Z" in end_date_str:
                        end_date_str = end_date_str.split(".")[0] + "Z"

                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    # Ensure timezone awareness
                    if end_date.tzinfo is None:
                        end_date = end_date.replace(tzinfo=timezone.utc)

                    # Calculate seconds from now until ban end
                    current_datetime = datetime.now().astimezone()
                    new_exp = (end_date - current_datetime).total_seconds()

                    # Ensure ban duration is positive
                    if new_exp <= 0:
                        logger.debug(f"Invalid custom ban duration for IP {ip}: {new_exp}")
                        flask_flash(f"Invalid custom ban duration for IP {ip}, must be in the future", "error")
                        continue

                    is_permanent = False
                    logger.debug(f"Custom duration for {ip}: {new_exp} seconds")
                except ValueError as e:
                    logger.exception(f"Invalid custom end date format for IP {ip}")
                    flask_flash(f"Invalid custom end date format for IP {ip}: {e}", "error")
                    continue
            else:
                logger.debug(f"Custom duration selected but no end date provided for IP {ip}")
                flask_flash(f"Custom duration selected but no end date provided for IP {ip}, skipping", "error")
                continue
        else:
            logger.debug(f"Invalid duration '{duration}' for IP {ip}")
            flask_flash(f"Invalid duration '{duration}' for IP {ip}, skipping", "error")
            continue

        # Validate service name for service-specific bans
        if ban_scope == "service":
            services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"]
            if isinstance(services, str):
                services = services.split()

            # Force global ban if service is invalid
            if not service or service == "Web UI" or service not in services:
                logger.debug(f"Invalid service '{service}' for IP {ip}, defaulting to global ban")
                flask_flash(f"Invalid service '{service}' for IP {ip}, defaulting to global ban", "warning")
                ban_scope = "global"
                service = "Web UI"

        # Generate the appropriate Redis key based on ban scope
        if ban_scope == "service" and service != "Web UI":
            ban_key = f"bans_service_{service}_ip_{ip}"
        else:
            ban_key = f"bans_ip_{ip}"
            ban_scope = "global"

        # Fetch existing ban data first to preserve original reason
        original_reason = "ui"  # Default fallback

        # Try to get original reason from Redis first
        redis_ban_found = False
        if redis_client:
            try:
                existing_data = redis_client.get(ban_key)
                if existing_data:
                    redis_ban_found = True
                    # Parse existing ban data to get original reason
                    try:
                        existing_ban_data = loads(existing_data.decode("utf-8", "replace"))
                        original_reason = existing_ban_data.get("reason", "ui")
                        logger.debug(f"Found existing ban in Redis for {ip}, reason: {original_reason}")
                    except Exception:
                        logger.exception(f"Could not parse existing ban data for {ip}, using default reason")
            except Exception as e:
                logger.exception(f"Error fetching ban from Redis for {ip}: {e}")

        # If not found in Redis, try to get from instances
        if not redis_ban_found:
            # Create lookup key for instances dict
            instance_lookup_key = f"{ip}|{ban_scope}|{service or '_'}"
            if instance_lookup_key in instance_bans_dict:
                original_reason = instance_bans_dict[instance_lookup_key].get("reason", "ui")
                logger.debug(f"Found existing ban in instances for {ip}, reason: {original_reason}")
            else:
                # Try alternative lookup for global bans
                if ban_scope == "global":
                    alt_lookup_key = f"{ip}|global|_"
                    if alt_lookup_key in instance_bans_dict:
                        original_reason = instance_bans_dict[alt_lookup_key].get("reason", "ui")
                        logger.debug(f"Found alternative global ban for {ip}, reason: {original_reason}")
                    else:
                        logger.debug(f"Ban for IP {ip} not found in Redis or instances")
                        flask_flash(f"Ban for IP {ip} not found in Redis or instances, skipping", "warning")
                        continue
                else:
                    logger.debug(f"Service-specific ban for IP {ip} not found")
                    flask_flash(f"Ban for IP {ip} not found in Redis or instances, skipping", "warning")
                    continue

        # Update Redis ban if it exists there
        if redis_client and redis_ban_found:
            try:
                ban_data = existing_ban_data.copy()  # Preserve all original data
                ban_data["permanent"] = is_permanent
                # Keep original reason and date intact

                ok = redis_client.set(ban_key, dumps(ban_data))
                if not ok:
                    logger.debug(f"Failed to update ban duration for {ip} in Redis")
                    flash(f"Couldn't update ban duration for {ip} on redis", "error")
                    continue

                # Set expiration for non-permanent bans or remove expiration for permanent bans
                if is_permanent:
                    redis_client.persist(ban_key)  # Remove expiration
                    logger.debug(f"Removed expiration for permanent ban: {ip}")
                else:
                    redis_client.expire(ban_key, int(new_exp))
                    logger.debug(f"Set new expiration for {ip}: {int(new_exp)} seconds")
                    
            except BaseException as e:
                logger.exception(f"Couldn't update ban duration for {ip} on redis: {e}")
                flash(f"Failed to update ban duration for {ip} on redis, see logs for more information.", "error")
                continue

        # Update ban on BunkerWeb instances using original reason
        logger.debug(f"Updating ban on instances for {ip} with reason: {original_reason}")
        ban_resp = BW_INSTANCES_UTILS.ban(ip, new_exp, original_reason, service, ban_scope)
        if ban_resp:
            logger.debug(f"Failed to update ban duration for {ip} on some instances: {ban_resp}")
            flask_flash(f"Couldn't update ban duration for {ip} on the following instances: {', '.join(ban_resp)}", "error")
        else:
            successful_updates += 1
            duration_text = "permanently" if is_permanent else f"for {duration}"
            service_text = f" for service {service}" if ban_scope == "service" else ""
            logger.info(f"Successfully updated ban duration for {ip}{service_text} to {duration_text}")
            flash(f"Successfully updated ban duration for {ip}{service_text} to {duration_text}")

    logger.info(f"Duration update operation completed: {successful_updates}/{len(updates)} successful")
    return redirect(url_for("loading", next=url_for("bans.bans_page"), message=f"Updating duration for {len(updates)} ban{'s' if len(updates) > 1 else ''}"))
