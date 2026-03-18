from collections import defaultdict
from datetime import datetime
from json import JSONDecodeError, loads
from math import floor
from time import time
from traceback import format_exc
from html import escape

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, BW_INSTANCES_UTILS, DB
from app.utils import LOGGER, flash

from app.routes.utils import cors_required, get_redis_client, get_remain, handle_error, verify_data_in_form

bans = Blueprint("bans", __name__)


@bans.route("/bans", methods=["GET"])
@login_required
def bans_page():
    # Get list of services for the service dropdown in the UI
    services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"]
    if isinstance(services, str):
        services = services.split()

    return render_template("bans.html", services=services)


@bans.route("/bans/fetch", methods=["POST"])
@login_required
@cors_required
def bans_fetch():
    redis_client = get_redis_client()

    bans = []
    if redis_client:
        try:
            # Retrieve global bans from Redis (stored with prefix "bans_ip_")
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
                except Exception as e:
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Failed to decode ban data for {ip}: {e}")

            # Retrieve service-specific bans from Redis (stored with prefix "bans_service_*_ip_*")
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
                except Exception as e:
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Failed to decode ban data for {ip} on service {service}: {e}")
        except BaseException as e:
            LOGGER.debug(format_exc())
            LOGGER.error(f"Couldn't get bans from redis: {e}")
            flash("Failed to fetch bans from Redis, see logs for more information.", "error")
            bans = []

    # Also fetch bans from all connected BunkerWeb instances
    instance_bans = BW_INSTANCES_UTILS.get_bans()

    # Current timestamp for calculating remaining times
    timestamp_now = time()

    # Process instance bans and avoid duplicates with Redis bans
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

    # Format ban times for display
    for ban in bans:
        exp = ban.pop("exp", 0)

        # Handle permanent bans (exp = 0)
        if exp == 0 or ban.get("permanent", False):
            ban["remain"] = "permanent"
            ban["permanent"] = True
            ban["end_date"] = "permanent"
        else:
            # Calculate human-readable remaining time for non-permanent bans
            remain = ("unknown", "unknown") if exp <= 0 else get_remain(exp)
            ban["remain"] = remain[0]
            # Format timestamps for start and end dates
            ban["start_date"] = datetime.fromtimestamp(floor(ban["date"])).astimezone().isoformat()
            ban["end_date"] = datetime.fromtimestamp(floor(timestamp_now + exp)).astimezone().isoformat()

    # DataTables parameters
    draw = int(request.form.get("draw", 1))
    start = int(request.form.get("start", 0))
    length = int(request.form.get("length", 10))
    search_value = request.form.get("search[value]", "").lower()
    # DataTables includes two leading non-data columns (details-control and select)
    # Adjust incoming index to align with backend data columns
    try:
        order_column_index_dt = int(request.form.get("order[0][column]", 0))
    except Exception:
        order_column_index_dt = 0
    order_column_index = max(order_column_index_dt - 2, 0)
    order_direction = request.form.get("order[0][dir]", "desc")
    search_panes = defaultdict(list)
    for key, value in request.form.items():
        if key.startswith("searchPanes["):
            field = key.split("[")[1].split("]")[0]
            search_panes[field].append(value)

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
    def _to_float(value, default=0.0):
        try:
            if isinstance(value, (int, float)):
                return float(value)
            if value is None:
                return float(default)
            return float(str(value))
        except Exception:
            return float(default)

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
            elif sort_key == "date":
                bans.sort(key=lambda x: _to_float(x.get("date", 0.0), 0.0), reverse=(order_direction == "desc"))
            else:
                bans.sort(key=lambda x: x.get(sort_key, ""), reverse=(order_direction == "desc"))

    # Apply filters and sort
    filtered_bans = filter(global_search_filter, bans) if search_value else bans
    filtered_bans = list(filter_by_search_panes(filtered_bans))
    sort_bans(filtered_bans)

    paginated_bans = filtered_bans if length == -1 else filtered_bans[start : start + length]  # noqa: E203

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
        str_code = str(code)
        country_code = str_code.lower()
        is_unknown = str_code in ("unknown", "local", "n/a")
        flag_code = "zz" if is_unknown else country_code
        # Show both the alpha-2 code and the translated country name so users can search by either
        code_text = "N/A" if is_unknown else str_code.upper()
        i18n_key = "not_applicable" if str_code in ("unknown", "local") else str_code.upper()
        fallback_name = "N/A" if is_unknown else str_code
        search_panes_options["country"].append(
            {
                "label": f'<img src="{base_flags_url}/{flag_code}.svg" class="border border-1 p-0 me-1" height="17" />&nbsp;－&nbsp;<span class="me-1"><code>{code_text}</code></span><span data-i18n="country.{i18n_key}">{fallback_name}</span>',
                "value": str_code,
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
    # Check database state
    if DB.readonly:
        return handle_error("Database is in read-only mode", "bans")

    # Validate input parameters
    verify_data_in_form(
        data={"bans": None},
        err_message="Missing bans parameter on /bans/ban.",
        redirect_url="bans",
        next=True,
    )
    bans = request.form["bans"]
    if not bans:
        return handle_error("No bans.", "bans", True)
    try:
        bans = loads(bans)
    except JSONDecodeError:
        return handle_error("Invalid bans parameter on /bans/ban.", "bans", True)

    for ban in bans:
        # Validate ban structure
        if not isinstance(ban, dict) or "ip" not in ban:
            continue

        # Extract and normalize ban parameters
        ip = ban.get("ip", "")
        reason = ban.get("reason", "ui")
        ban_scope = ban.get("ban_scope", "global")
        service = ban.get("service", "")

        # Check for permanent ban
        if ban.get("end_date") == "0" or ban.get("exp") == 0:
            ban_end = 0
        else:
            ban_end = ban.get("exp", 0)

        # Validate service name for service-specific bans
        if ban_scope == "service":
            if not service or service in ("Web UI", "unknown", "bwcli", ""):
                ban_scope = "global"
                service = "unknown"

        # Propagate ban to all connected BunkerWeb instances
        resp = BW_INSTANCES_UTILS.ban(ip, ban_end, reason, service, ban_scope)
        if resp:
            LOGGER.error(f"Failed to ban {ip} on instances: {resp}")
            flash(f"Failed to ban {ip} on some instances: {resp}", "error")
        else:
            LOGGER.info(f"Banned {ip} on all instances")
            flash(f"Banned {ip} successfully.", "success")

    return redirect(url_for("loading", next=url_for("bans.bans_page"), message=f"Banning {len(bans)} IP{'s' if len(bans) > 1 else ''}"))


@bans.route("/bans/unban", methods=["POST"])
@login_required
def bans_unban():
    # Check database state
    if DB.readonly:
        return handle_error("Database is in read-only mode", "bans")

    # Validate input parameters
    verify_data_in_form(
        data={"ips": None},
        err_message="Missing bans parameter on /bans/unban.",
        redirect_url="bans",
        next=True,
    )
    unbans = request.form["ips"]
    if not unbans:
        return handle_error("No bans.", "ips", True)
    try:
        unbans = loads(unbans)
    except JSONDecodeError:
        return handle_error("Invalid ips parameter on /bans/unban.", "bans", True)

    for unban in unbans:
        # Validate unban structure
        if "ip" not in unban:
            continue

        # Extract and normalize unban parameters
        ip = unban.get("ip")
        ban_scope = unban.get("ban_scope", "global")
        service = unban.get("service")

        # Normalize Web UI and default services to global scope
        if service in ("default server", "Web UI", "unknown"):
            ban_scope = "global"
            service = None

        # Propagate unban to all connected BunkerWeb instances, now passing ban_scope
        resp = BW_INSTANCES_UTILS.unban(ip, service, ban_scope)
        if resp:
            LOGGER.error(f"Failed to unban {ip} on instances: {resp}")
            flash(f"Failed to unban {ip} on some instances: {resp}", "error")
        else:
            LOGGER.info(f"Unbanned {ip} on all instances")
            flash(f"Unbanned {ip} successfully.", "success")

    return redirect(url_for("loading", next=url_for("bans.bans_page"), message=f"Unbanning {len(unbans)} IP{'s' if len(unbans) > 1 else ''}"))


@bans.route("/bans/update_duration", methods=["POST"])
@login_required
def bans_update_duration():
    # Check database state
    if DB.readonly:
        return handle_error("Database is in read-only mode", "bans")

    # Validate input parameters
    verify_data_in_form(
        data={"updates": None},
        err_message="Missing updates parameter on /bans/update_duration.",
        redirect_url="bans",
        next=True,
    )
    updates = request.form["updates"]
    if not updates:
        return handle_error("No updates.", "bans", True)
    try:
        updates = loads(updates)
    except JSONDecodeError:
        return handle_error("Invalid updates parameter on /bans/update_duration.", "bans", True)

    # Fetch existing bans from instances to get original reasons
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

    for update in updates:
        # Validate update structure
        if not isinstance(update, dict) or "ip" not in update or "duration" not in update:
            continue

        # Extract and normalize update parameters
        ip = update.get("ip", "")
        duration = update.get("duration", "")
        ban_scope = update.get("ban_scope", "global")
        service = update.get("service", "")

        # Calculate new expiration time based on duration
        if duration == "permanent":
            new_exp = 0
        elif duration == "1h":
            new_exp = 3600
        elif duration == "24h":
            new_exp = 86400
        elif duration == "1w":
            new_exp = 604800
        elif duration == "custom":
            custom_exp = update.get("custom_exp", None)
            if custom_exp is not None:
                try:
                    new_exp = max(0, int(custom_exp))
                except (TypeError, ValueError):
                    new_exp = 0
            else:
                custom_end_date = update.get("end_date")
                if custom_end_date:
                    try:
                        end_dt = datetime.fromisoformat(custom_end_date)
                        if end_dt.tzinfo is None:
                            end_dt = end_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                        new_exp = max(0, int(end_dt.timestamp() - time()))
                    except (TypeError, ValueError):
                        new_exp = 0
                else:
                    new_exp = 0
        else:
            new_exp = 0

        # Validate service name for service-specific bans
        if ban_scope == "service":
            if not service or service in ("Web UI", "unknown", "bwcli", ""):
                ban_scope = "global"
                service = "unknown"

        # Fetch existing ban data first to preserve original reason
        original_reason = "ui"  # Default fallback
        ban_key = f"{ip}|{ban_scope}|{service if ban_scope == 'service' else '_'}"
        if ban_key in instance_bans_dict:
            original_reason = instance_bans_dict[ban_key].get("reason", "ui")

        # Update ban on BunkerWeb instances using original reason
        ban_resp = BW_INSTANCES_UTILS.ban(ip, new_exp, original_reason, service, ban_scope)
        if ban_resp:
            LOGGER.error(f"Failed to update ban duration for {ip} on instances: {ban_resp}")
            flash(f"Failed to update ban duration for {ip} on some instances: {ban_resp}", "error")
        else:
            LOGGER.info(f"Updated ban duration for {ip} on all instances")
            flash(f"Updated ban duration for {ip} successfully.", "success")

    return redirect(url_for("loading", next=url_for("bans.bans_page"), message=f"Updating duration for {len(updates)} ban{'s' if len(updates) > 1 else ''}"))
