from collections import defaultdict
from contextlib import suppress
from datetime import datetime
from io import BytesIO, StringIO
from ipaddress import ip_address as validate_ip_address
from json import JSONDecodeError, loads
from math import floor
from time import time
from traceback import format_exc
from html import escape, unescape

from flask import Blueprint, Response, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from app.dependencies import BW_CONFIG, BW_INSTANCES_UTILS, DB
from app.utils import LOGGER, RESERVED_SERVICE_NAMES, csv_safe, csv_writer, flash

from app.routes.utils import (
    cors_required,
    get_default_ban_time,
    get_redis_client,
    get_remain,
    handle_error,
    parse_search_panes,
    parse_search_panes_dict,
)
from CrowdSec import CrowdSecClient, CrowdSecError  # type: ignore
from crowdsec_unban import apply as crowdsec_apply, preview as crowdsec_preview_data, revalidate as crowdsec_revalidate  # type: ignore
from redis_keys import ban_ip, unescape as redis_unescape  # type: ignore

bans = Blueprint("bans", __name__)

LEASE_KIND = "crowdsec_lease"


# Column order shared between the table and exports — must stay in sync with bans.js
_BAN_COLUMNS = (
    "date",  # 0
    "ip",  # 1
    "country",  # 2
    "reason",  # 3
    "scope",  # 4
    "service",  # 5
    "end_date",  # 6
    "time_left",  # 7
    "actions",  # 8
)


def _ban_identity(row):
    """Row identity: a lease and an explicit ban for the same IP and scope are two rows."""
    return (row.get("ip"), row.get("ban_scope"), row.get("service", "_"), row.get("kind", "ban"))


def _ban_id(ban):
    """IP+scope+service+kind as the unique ID of a ban."""
    service = ban.get("service")
    # Normalize service to "_" for global bans or when service is None
    if ban.get("ban_scope") == "global" or service is None:
        service = "_"
    return f"{ban.get('ip','')}|{ban.get('ban_scope','')}|{service}|{ban.get('kind', 'ban')}"  # noqa: E231


def _lease_source(ban):
    reason_data = ban.get("reason_data")
    return reason_data if ban.get("kind") == LEASE_KIND and isinstance(reason_data, dict) else {}


def format_ban(ban):
    """One ban as a DataTable row. Defensive: some bans may lack some fields."""
    source = _lease_source(ban)
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
        "kind": escape(str(ban.get("kind") or "ban")),
        "cs_node": escape(str(source.get("instance") or "")),
        "cs_connection": escape(str(source.get("connection") or "")),
        "actions": "",  # Actions column for buttons
    }


def _redis_scan(redis_client, patterns):
    """(key, data, ttl) for every key matching one of the patterns, in two pipelined round trips per pattern."""
    scan = []
    for pattern in patterns:
        keys = list(redis_client.scan_iter(pattern, count=1000))
        if not keys:
            continue
        pipe = redis_client.pipeline(transaction=False)
        for key in keys:
            pipe.get(key)
            pipe.ttl(key)
        results = pipe.execute()
        scan.extend((key, results[2 * idx], results[2 * idx + 1]) for idx, key in enumerate(keys))
    return scan


def _redis_lease_rows(scan):
    """Ban rows for the CrowdSec lease keys of a `_redis_scan`: `bans_cs_ip_<ip>` and `bans_cs_service_<svc>_ip_<ip>`."""
    rows = []
    for key, data, exp in scan:
        if not data:
            continue
        key_str = key.decode("utf-8", "replace") if isinstance(key, bytes) else key
        if key_str.startswith("bans_cs_service_"):
            service, ip = key_str[len("bans_cs_service_") :].rsplit("_ip_", 1)  # noqa: E203
            ban_scope, service, ip = "service", redis_unescape(service), ban_ip(ip)
        elif key_str.startswith("bans_cs_ip_"):
            ban_scope, ip = "global", ban_ip(key_str[len("bans_cs_ip_") :])  # noqa: E203
            service = None
        else:
            continue
        try:
            lease = loads(data.decode("utf-8", "replace") if isinstance(data, bytes) else data)
        except (JSONDecodeError, ValueError) as e:
            LOGGER.warning(f"Failed to decode CrowdSec ban data for {ip}, skipping it: {e}")
            continue
        if not isinstance(lease, dict):
            continue
        lease.update({"ip": ip, "exp": exp, "ban_scope": ban_scope, "kind": LEASE_KIND, "permanent": False})
        lease["service"] = service or lease.get("service") or "unknown"
        rows.append(lease)
    return rows


def _merge_instance_bans(bans_list, instance_bans):
    """Add the instance rows whose identity Redis did not already provide. Redis wins: the cluster shares one Redis."""
    # Set membership rather than a scan of bans_list per instance ban: both sides usually hold the same bans and
    # the scan was quadratic (measured ~1.7 s at 10k bans, on every table draw).
    seen_bans = {_ban_identity(b) for b in bans_list}

    for ban in instance_bans:
        if "ban_scope" not in ban:
            ban["ban_scope"] = "global" if ban.get("service", "_") == "_" else "service"
        ban_key = _ban_identity(ban)
        if ban_key not in seen_bans:
            seen_bans.add(ban_key)
            bans_list.append(ban)
    return bans_list


def _collect_all_bans():
    """Pull every ban from Redis (global + service-scoped) and from each
    BunkerWeb instance, deduplicate them, and enrich with `remain`/`start_date`/
    `end_date` for display. Returns the raw (unfiltered) list."""
    redis_client = get_redis_client()

    bans_list = []
    if redis_client:
        try:
            # Collect keys first, then pipeline GET+TTL for all of them. This
            # turns 2 round-trips per ban (get + ttl) into ~2 round-trips total.
            # Results come back flat: [data0, ttl0, data1, ttl1, ...].
            global_keys = list(redis_client.scan_iter("bans_ip_*", count=1000))
            if global_keys:
                pipe = redis_client.pipeline(transaction=False)
                for key in global_keys:
                    pipe.get(key)
                    pipe.ttl(key)
                results = pipe.execute()
                for idx, key in enumerate(global_keys):
                    data = results[2 * idx]
                    exp = results[2 * idx + 1]
                    if not data:
                        continue
                    key_str = key.decode("utf-8", "replace")
                    ip = ban_ip(key_str.replace("bans_ip_", ""))
                    raw_value = data.decode("utf-8", "replace")
                    try:
                        ban_data = loads(raw_value)
                    except (JSONDecodeError, ValueError) as e:
                        LOGGER.warning(f"Failed to decode ban data for {ip}, using raw value as reason: {e}")
                        ban_data = {"reason": raw_value, "service": "unknown", "date": 0, "country": "unknown", "ban_scope": "global", "permanent": False}

                    ban_data["ban_scope"] = "global"
                    ban_data["permanent"] = ban_data.get("permanent", False) or exp == 0

                    if ban_data.get("permanent", False):
                        exp = 0

                    bans_list.append({"ip": ip, "exp": exp, "permanent": ban_data.get("permanent", False)} | ban_data)

            service_keys = list(redis_client.scan_iter("bans_service_*_ip_*", count=1000))
            if service_keys:
                pipe = redis_client.pipeline(transaction=False)
                for key in service_keys:
                    pipe.get(key)
                    pipe.ttl(key)
                results = pipe.execute()
                for idx, key in enumerate(service_keys):
                    data = results[2 * idx]
                    exp = results[2 * idx + 1]
                    if not data:
                        continue
                    key_str = key.decode("utf-8", "replace")
                    service, ip = key_str.replace("bans_service_", "").rsplit("_ip_", 1)
                    service, ip = redis_unescape(service), ban_ip(ip)
                    raw_value = data.decode("utf-8", "replace")
                    try:
                        ban_data = loads(raw_value)
                    except (JSONDecodeError, ValueError) as e:
                        LOGGER.warning(f"Failed to decode ban data for {ip} on service {service}, using raw value as reason: {e}")
                        ban_data = {"reason": raw_value, "service": service, "date": 0, "country": "unknown", "ban_scope": "service", "permanent": False}

                    ban_data["ban_scope"] = "service"
                    ban_data["service"] = service
                    ban_data["permanent"] = ban_data.get("permanent", False) or exp == 0

                    if ban_data.get("permanent", False):
                        exp = 0

                    bans_list.append({"ip": ip, "exp": exp, "permanent": ban_data.get("permanent", False)} | ban_data)

            bans_list.extend(_redis_lease_rows(_redis_scan(redis_client, ("bans_cs_ip_*", "bans_cs_service_*_ip_*"))))
        except BaseException as e:
            LOGGER.debug(format_exc())
            LOGGER.error(f"Couldn't get bans from redis: {e}")
            bans_list = []

    instance_bans = BW_INSTANCES_UTILS.get_bans()

    timestamp_now = time()

    _merge_instance_bans(bans_list, instance_bans)

    for ban in bans_list:
        exp = ban.pop("exp", 0)
        if exp == 0 or ban.get("permanent", False):
            ban["remain"] = "permanent"
            ban["permanent"] = True
            ban["end_date"] = "permanent"
        else:
            remain = ("unknown", "unknown") if exp <= 0 else get_remain(exp)
            ban["remain"] = remain[0]
            ban["start_date"] = datetime.fromtimestamp(floor(ban["date"])).astimezone().isoformat()
            ban["end_date"] = datetime.fromtimestamp(floor(timestamp_now + exp)).astimezone().isoformat()
        # Preserve `exp` for end_date pane filters that still need it
        ban["exp"] = exp

    return bans_list


def _to_float(value, default=0.0):
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if value is None:
            return float(default)
        return float(str(value))
    except Exception:
        return float(default)


def _filter_and_sort_bans(all_bans, search_value, search_panes, order_column_index, order_direction):
    """Apply the same filtering + sorting logic as `/bans/fetch`, returning the
    full filtered list (no pagination)."""

    def filter_by_search_panes(items):
        filtered = items
        for field, selected_values in search_panes.items():
            if not selected_values:
                continue
            if field == "date":
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

                def scope_filter(ban):
                    return ban.get("ban_scope") in selected_values

                filtered = list(filter(scope_filter, filtered))
            elif field == "end_date":

                def end_date_filter(ban):
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

                def service_filter(ban):
                    ban_service = ban.get("service")
                    if ban.get("ban_scope") == "global" or ban_service in (None, ""):
                        ban_service = "_"
                    return str(ban_service) in selected_values

                filtered = list(filter(service_filter, filtered))
            else:
                filtered = [b for b in filtered if str(b.get(field, "N/A")) in selected_values]
        return filtered

    def global_search_filter(ban):
        if search_value == "permanent" and ban.get("permanent", False):
            return True
        return any(search_value in str(ban.get(col, "")).lower() for col in _BAN_COLUMNS)

    filtered_bans = list(filter(global_search_filter, all_bans)) if search_value else list(all_bans)
    filtered_bans = list(filter_by_search_panes(filtered_bans))

    if 0 <= order_column_index < len(_BAN_COLUMNS):
        sort_key = _BAN_COLUMNS[order_column_index]
        if sort_key in ("end_date", "time_left"):
            filtered_bans.sort(
                key=lambda x: ("0" if order_direction == "desc" else "z") if x.get("permanent", False) else x.get(sort_key, ""),
                reverse=(order_direction == "desc"),
            )
        elif sort_key == "date":
            filtered_bans.sort(key=lambda x: _to_float(x.get("date", 0.0), 0.0), reverse=(order_direction == "desc"))
        else:
            filtered_bans.sort(key=lambda x: x.get(sort_key, ""), reverse=(order_direction == "desc"))

    return filtered_bans


def _get_filtered_bans(source):
    return _filter_and_sort_bans(
        _collect_all_bans(),
        source.get("search", "").lower(),
        parse_search_panes_dict(source),
        0,
        "desc",
    )


def _get_filtered_report_bans(source):
    if not BW_INSTANCES_UTILS:
        return []

    try:
        config = BW_CONFIG.get_config(methods=False, with_drafts=True) if BW_CONFIG else {}
    except Exception:
        config = {}

    result = BW_INSTANCES_UTILS.get_reports_query(
        start=0,
        length=-1,
        search=source.get("search", "").lower(),
        order_column="date",
        order_dir="desc",
        search_panes=parse_search_panes(source),
        count_only=False,
        include_pane_counts=False,
    )

    targets = []
    seen = set()
    for report in result.get("data", []):
        ip = report.get("ip")
        server_name = str(report.get("server_name") or "_")
        ban_scope = "global" if server_name == "_" else "service"
        service = "" if ban_scope == "global" else server_name
        key = (ip, ban_scope, service)
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            {
                "ip": ip,
                "reason": report.get("reason") or "ui",
                "ban_scope": ban_scope,
                "service": service,
                "exp": get_default_ban_time(config, server_name),
            }
        )

    return targets


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
    try:
        bans = _collect_all_bans()
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Couldn't get bans from redis: {e}")
        flash("Failed to fetch bans from Redis, see logs for more information.", "error")
        bans = []

    # DataTables parameters
    draw = int(request.form.get("draw", 1))
    start = max(0, int(request.form.get("start", 0)))
    length = max(1, min(int(request.form.get("length", 10)), 1000))
    search_value = request.form.get("search[value]", "").lower()
    # DataTables includes two leading non-data columns (details-control and select)
    # Adjust incoming index to align with backend data columns
    try:
        order_column_index_dt = int(request.form.get("order[0][column]", 0))
    except Exception:
        order_column_index_dt = 0
    order_column_index = max(order_column_index_dt - 2, 0)
    order_direction = request.form.get("order[0][dir]", "desc")
    search_panes = parse_search_panes_dict(request.form)

    # Local alias kept for the formatter / pane-counts code below
    columns = list(_BAN_COLUMNS)

    filtered_bans = _filter_and_sort_bans(bans, search_value, search_panes, order_column_index, order_direction)

    paginated_bans = filtered_bans if length == -1 else filtered_bans[start : start + length]  # noqa: E203

    # Format for DataTable
    formatted_bans = [format_ban(ban) for ban in paginated_bans]

    # Calculate pane counts (for SearchPanes)
    pane_counts = defaultdict(lambda: defaultdict(lambda: {"total": 0, "count": 0}))

    filtered_ids = {_ban_id(ban) for ban in filtered_bans}
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
            if _ban_id(ban) in filtered_ids:
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


def _bans_export_rows():
    """Collect, filter, and sort bans using the request's search/searchPanes/order
    parameters and return them as plain dict rows ready to be written to CSV/XLSX."""
    bans = _collect_all_bans()

    search_value = request.args.get("search", "").lower()
    order_column = request.args.get("order_column", "date").strip().lower()
    order_dir = request.args.get("order_dir", "desc").strip().lower()
    if order_dir not in ("asc", "desc"):
        order_dir = "desc"
    try:
        order_column_index = _BAN_COLUMNS.index(order_column)
    except ValueError:
        order_column_index = 0

    search_panes = parse_search_panes_dict(request.args)
    filtered_bans = _filter_and_sort_bans(bans, search_value, search_panes, order_column_index, order_dir)

    rows = []
    for ban in filtered_bans:
        date_value = "N/A"
        ban_date = ban.get("date")
        if ban_date:
            with suppress(Exception):
                date_value = datetime.fromtimestamp(floor(ban_date)).astimezone().isoformat()

        ban_scope = ban.get("ban_scope") or "global"
        service = ban.get("service") or "_"
        if ban_scope == "global" or service in (None, ""):
            service = "_"

        if ban.get("permanent", False):
            end_date = "permanent"
            time_left = "permanent"
        else:
            end_date = unescape(str(ban.get("end_date", "N/A")))
            time_left = unescape(str(ban.get("remain", "N/A")))

        rows.append(
            {
                "date": date_value,
                "ip": str(ban.get("ip", "N/A")),
                "country": str(ban.get("country", "N/A")),
                "reason": str(ban.get("reason", "N/A")),
                "scope": ban_scope,
                "service": service,
                "end_date": end_date,
                "time_left": time_left,
            }
        )
    return rows


_BAN_EXPORT_HEADERS = (
    "Date",
    "IP Address",
    "Country",
    "Reason",
    "Scope",
    "Service",
    "End Date",
    "Time Left",
)
_BAN_EXPORT_FIELDS = ("date", "ip", "country", "reason", "scope", "service", "end_date", "time_left")


@bans.route("/bans/export/csv", methods=["GET"])
@login_required
def bans_export_csv():
    """Export the current filtered+sorted ban list as CSV (all columns, all rows)."""
    try:
        rows = _bans_export_rows()
    except Exception as e:
        LOGGER.error(f"Error collecting bans for CSV export: {e}")
        LOGGER.debug(format_exc())
        return jsonify({"error": "Failed to export bans"}), 500

    output = StringIO()
    writer = csv_writer(output)
    writer.writerow(_BAN_EXPORT_HEADERS)
    for row in rows:
        writer.writerow([row[field] for field in _BAN_EXPORT_FIELDS])

    output.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=bunkerweb_bans_{timestamp}.csv"},
    )


@bans.route("/bans/export/excel", methods=["GET"])
@login_required
def bans_export_excel():
    """Export the current filtered+sorted ban list as XLSX (all columns, all rows)."""
    try:
        rows = _bans_export_rows()
    except Exception as e:
        LOGGER.error(f"Error collecting bans for Excel export: {e}")
        LOGGER.debug(format_exc())
        return jsonify({"error": "Failed to export bans"}), 500

    wb = Workbook()
    ws = wb.active
    ws.title = "Bans"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

    ws.append(list(_BAN_EXPORT_HEADERS))
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill

    for row in rows:
        ws.append([csv_safe(row[field]) for field in _BAN_EXPORT_FIELDS])

    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            with suppress(Exception):
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[column_letter].width = min(max_length + 2, 50)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"bunkerweb_bans_{timestamp}.xlsx",
    )


@bans.route("/bans/ban", methods=["POST"])
@login_required
def bans_ban():
    # Check database state
    if DB.readonly:
        return handle_error("Database is in read-only mode", "bans")

    selection_mode = request.form.get("selection_mode", "explicit")
    if selection_mode == "filtered":
        if request.form.get("source") != "reports":
            return handle_error("Invalid filtered ban source.", "bans", True)
        bans = _get_filtered_report_bans(request.form)
    elif selection_mode == "explicit":
        raw_bans = request.form.get("bans", "")
        if not raw_bans:
            return handle_error("No bans.", "bans", True)
        try:
            bans = loads(raw_bans)
        except JSONDecodeError:
            return handle_error("Invalid bans parameter on /bans/ban.", "bans", True)
    else:
        return handle_error("Invalid ban selection mode.", "bans", True)

    if not bans:
        return handle_error("No matching reports.", "bans", True)

    for ban in bans:
        # Validate ban structure
        if not isinstance(ban, dict) or "ip" not in ban:
            continue

        # Extract and normalize ban parameters
        ip = ban.get("ip", "")
        reason = ban.get("reason", "ui")
        ban_scope = ban.get("ban_scope", "global")
        if ban_scope not in ("global", "service"):  # only two valid scopes; clamp anything else
            ban_scope = "global"
        service = ban.get("service", "")

        # Validate IP address
        try:
            validate_ip_address(ip)
        except ValueError:
            flash(f"Invalid IP address: {ip}", "error")
            continue

        # Check for permanent ban
        if ban.get("end_date") == "0" or ban.get("exp") == 0:
            ban_end = 0
        else:
            ban_end = ban.get("exp", 0)

        # Validate service name for service-specific bans
        if ban_scope == "service":
            if not service or service in RESERVED_SERVICE_NAMES:
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


def _normalize_target(ip, ban_scope, service):
    """(ip, ban_scope, service) of a CrowdSec ban as the instances store it. Raises ValueError on a malformed target."""
    if not isinstance(ip, str):
        raise ValueError("Invalid IP address")
    validate_ip_address(ip)
    if service is not None and not isinstance(service, str):
        raise ValueError("Invalid service")
    if ban_scope not in ("global", "service"):
        ban_scope = "global"
    # Same downgrade as the explicit Unban and the instance API: reserved names are the global scope
    if service in RESERVED_SERVICE_NAMES:
        ban_scope, service = "global", None
    elif ban_scope == "service" and service is None:
        raise ValueError("A service ban needs a service")
    return ip, ban_scope, service if ban_scope == "service" else None


def _selection_key(ip, ban_scope, service):
    return f"{ip}|{ban_scope}|{service or '_'}"


def _parse_selection(raw):
    """`crowdsec_selection` form field, `{"<ip>|<ban_scope>|<service>": ["<key>", ...]}`, keyed by the normalized target."""
    if not raw:
        return {}
    data = loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Invalid selection")
    selection = {}
    for key, values in data.items():
        parts = key.split("|", 2)
        if len(parts) != 3 or not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise ValueError("Invalid selection")
        selection[_selection_key(*_normalize_target(*parts))] = values
    return selection


def _partial_message(ip, result):
    details = [f"decision {item.get('key') or item.get('connection_id')}: {item.get('error')}" for item in result.get("failed", [])]
    details += [f"lease on {item.get('instance')}: {item.get('error')}" for item in result.get("lease_failed", [])]
    if result.get("unavailable"):
        details.append("could not check " + ", ".join(map(str, result["unavailable"])))
    if result.get("down"):
        details.append("instances down: " + ", ".join(map(str, result["down"])))
    tail = (
        "The ban stays on the instances that failed or were down, repeat the Unban."
        if result.get("lease_removed")
        else "The ban stays until the Unban is repeated or it expires."
    )
    return f"The CrowdSec Unban of {ip} is incomplete ({'; '.join(details)}). {tail}"


def _is_crowdsec_admin():
    return bool(current_user.admin and "write" in current_user.list_permissions)


@bans.route("/bans/crowdsec_preview", methods=["POST"])
@login_required
def bans_crowdsec_preview():
    actor = current_user.get_id()
    if not _is_crowdsec_admin():
        LOGGER.warning("CrowdSec Unban preview actor=%r outcome=denied", actor)
        return jsonify({"error": "CrowdSec decision removal is restricted to administrators"}), 403
    if DB.readonly:
        return jsonify({"error": "Database is in read-only mode"}), 423

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Invalid CrowdSec ban target"}), 400
    try:
        ip, ban_scope, service = _normalize_target(body.get("ip"), body.get("ban_scope", "global"), body.get("service"))
    except ValueError:
        return jsonify({"error": "Invalid CrowdSec ban target"}), 400

    try:
        return jsonify(crowdsec_preview_data(CrowdSecClient(DB), ip, ban_scope, service))
    except CrowdSecError as exc:
        LOGGER.warning("CrowdSec Unban preview actor=%r ip=%s outcome=error status=%s", actor, ip, exc.status)
        return jsonify({"error": str(exc)}), exc.status
    except Exception:
        LOGGER.exception("CrowdSec Unban preview actor=%r ip=%s outcome=error", actor, ip)
        return jsonify({"error": "Unable to complete the CrowdSec request"}), 500


@bans.route("/bans/unban", methods=["POST"])
@login_required
def bans_unban():
    # Check database state
    if DB.readonly:
        return handle_error("Database is in read-only mode", "bans")

    selection_mode = request.form.get("selection_mode", "explicit")
    if selection_mode == "filtered":
        if request.form.get("source") != "bans":
            return handle_error("Invalid filtered unban source.", "bans", True)
        unbans = [
            {
                "ip": ban.get("ip"),
                "ban_scope": ban.get("ban_scope", "global"),
                "service": ban.get("service"),
                "kind": ban.get("kind", "ban"),
            }
            for ban in _get_filtered_bans(request.form)
        ]
        # A CrowdSec Unban needs a preview and a confirmation per ban, which a filtered selection cannot give
        if any(unban["kind"] == LEASE_KIND for unban in unbans):
            unbans = [unban for unban in unbans if unban["kind"] != LEASE_KIND]
            flash("CrowdSec bans were skipped, unban them from their own row.", "warning")
    elif selection_mode == "explicit":
        raw_unbans = request.form.get("ips", "")
        if not raw_unbans:
            return handle_error("No bans.", "bans", True)
        try:
            unbans = loads(raw_unbans)
        except JSONDecodeError:
            return handle_error("Invalid ips parameter on /bans/unban.", "bans", True)
    else:
        return handle_error("Invalid unban selection mode.", "bans", True)

    if not unbans:
        return handle_error("No matching bans.", "bans", True)

    unbans = [unban for unban in unbans if isinstance(unban, dict) and "ip" in unban]
    lease_unbans = [unban for unban in unbans if unban.get("kind") == LEASE_KIND]
    unbans = [unban for unban in unbans if unban.get("kind") != LEASE_KIND]

    # Lease items: every one is checked before anything is removed, so a changed or failing item leaves all bans as they were
    prepared = []
    if lease_unbans:
        actor = current_user.get_id()
        if not _is_crowdsec_admin():
            LOGGER.warning("CrowdSec Unban actor=%r outcome=denied", actor)
            return handle_error("CrowdSec decision removal is restricted to administrators", "bans", True)
        if request.form.get("crowdsec_confirmed") != "yes":
            return handle_error("Removing a CrowdSec ban needs an explicit confirmation", "bans", True)
        try:
            selection = _parse_selection(request.form.get("crowdsec_selection", ""))
            targets = {}
            for lease_unban in lease_unbans:
                target = _normalize_target(lease_unban.get("ip"), lease_unban.get("ban_scope", "global"), lease_unban.get("service"))
                targets[_selection_key(*target)] = target
        except ValueError:
            return handle_error("Invalid CrowdSec ban selection on /bans/unban.", "bans", True)

        client = CrowdSecClient(DB)
        for key, (ip, ban_scope, service) in targets.items():
            try:
                checked = crowdsec_revalidate(client, ip, ban_scope, service, selection.get(key, []))
            except CrowdSecError as exc:
                LOGGER.warning("CrowdSec Unban actor=%r ip=%s scope=%s service=%r outcome=error status=%s", actor, ip, ban_scope, service, exc.status)
                return handle_error(f"CrowdSec Unban of {ip} refused: {exc}", "bans", True)
            except Exception:
                LOGGER.exception("CrowdSec Unban actor=%r ip=%s scope=%s service=%r outcome=error", actor, ip, ban_scope, service)
                return handle_error(f"Unable to check the CrowdSec ban of {ip}, see logs for more information.", "bans", True)
            if checked["status"] != "ready":
                LOGGER.info("CrowdSec Unban actor=%r ip=%s scope=%s service=%r outcome=changed", actor, ip, ban_scope, service)
                return handle_error("The CrowdSec decisions changed, review the Unban again", "bans", True)
            prepared.append((ip, ban_scope, service, checked["preview"]))

    for unban in unbans:
        # Extract and normalize unban parameters
        ip = unban.get("ip")
        ban_scope = unban.get("ban_scope", "global")
        service = unban.get("service")

        # Validate IP address
        try:
            validate_ip_address(ip)
        except ValueError:
            flash(f"Invalid IP address: {ip}", "error")
            continue

        # Normalize Web UI and default services to global scope
        if service in RESERVED_SERVICE_NAMES:
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

    for ip, ban_scope, service, current in prepared:
        try:
            result = crowdsec_apply(client, ip, ban_scope, service, current)
        except Exception:
            LOGGER.exception("CrowdSec Unban actor=%r ip=%s scope=%s service=%r outcome=error", actor, ip, ban_scope, service)
            flash(f"The CrowdSec Unban of {ip} failed unexpectedly. The ban stays until the Unban is repeated or it expires.", "error")
            continue
        LOGGER.info("CrowdSec Unban actor=%r ip=%s scope=%s service=%r outcome=%s", actor, ip, ban_scope, service, result["status"])
        if result["status"] == "success":
            flash(f"Removed the CrowdSec ban on {ip}.", "success")
        else:
            flash(_partial_message(ip, result), "error")

    total = len(unbans) + len(prepared)
    return redirect(url_for("loading", next=url_for("bans.bans_page"), message=f"Unbanning {total} IP{'s' if total > 1 else ''}"))


@bans.route("/bans/update_duration", methods=["POST"])
@login_required
def bans_update_duration():
    # Check database state
    if DB.readonly:
        return handle_error("Database is in read-only mode", "bans")

    selection_mode = request.form.get("selection_mode", "explicit")
    if selection_mode == "filtered":
        if request.form.get("source") != "bans":
            return handle_error("Invalid filtered duration source.", "bans", True)
        duration = request.form.get("duration", "")
        updates = [
            {
                "ip": ban.get("ip"),
                "duration": duration,
                "ban_scope": ban.get("ban_scope", "global"),
                "service": ban.get("service"),
                "kind": ban.get("kind", "ban"),
                "custom_exp": request.form.get("custom_exp"),
                "end_date": request.form.get("end_date"),
            }
            for ban in _get_filtered_bans(request.form)
        ]
        # CrowdSec bans are not editable; a filtered selection skips them instead of failing the whole request
        if any(update["kind"] == LEASE_KIND for update in updates):
            updates = [update for update in updates if update["kind"] != LEASE_KIND]
            flash("CrowdSec bans were skipped, they follow their CrowdSec decision.", "warning")
    elif selection_mode == "explicit":
        raw_updates = request.form.get("updates", "")
        if not raw_updates:
            return handle_error("No updates.", "bans", True)
        try:
            updates = loads(raw_updates)
        except JSONDecodeError:
            return handle_error("Invalid updates parameter on /bans/update_duration.", "bans", True)
    else:
        return handle_error("Invalid duration selection mode.", "bans", True)

    if not updates:
        return handle_error("No matching bans.", "bans", True)

    if any(isinstance(update, dict) and update.get("kind") == LEASE_KIND for update in updates):
        return handle_error("CrowdSec bans follow their CrowdSec decision and cannot be edited", "bans")

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
        ban_key = _selection_key(ban.get("ip"), ban.get("ban_scope", "global"), ban.get("service", "_") if ban["ban_scope"] == "service" else None)
        instance_bans_dict[f"{ban_key}|{ban.get('kind', 'ban')}"] = ban

    for update in updates:
        # Validate update structure
        if not isinstance(update, dict) or "ip" not in update or "duration" not in update:
            continue

        # Extract and normalize update parameters
        ip = update.get("ip", "")
        duration = update.get("duration", "")
        ban_scope = update.get("ban_scope", "global")
        service = update.get("service", "")

        if duration not in ("permanent", "1h", "24h", "1w", "custom"):
            flash(f"Invalid ban duration: {duration}", "error")
            continue

        # Validate IP address
        try:
            validate_ip_address(ip)
        except ValueError:
            flash(f"Invalid IP address: {ip}", "error")
            continue

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
                    flash(f"Invalid custom ban duration for {ip}", "error")
                    continue
            else:
                custom_end_date = update.get("end_date")
                if custom_end_date:
                    try:
                        end_dt = datetime.fromisoformat(custom_end_date)
                        if end_dt.tzinfo is None:
                            end_dt = end_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                        new_exp = max(0, int(end_dt.timestamp() - time()))
                    except (TypeError, ValueError):
                        flash(f"Invalid custom ban end date for {ip}", "error")
                        continue
                else:
                    flash(f"Missing custom ban end date for {ip}", "error")
                    continue

        # Validate service name for service-specific bans
        if ban_scope == "service":
            if not service or service in RESERVED_SERVICE_NAMES:
                ban_scope = "global"
                service = "unknown"

        # Fetch existing ban data first to preserve original reason
        original_reason = "ui"  # Default fallback
        ban_key = f"{_selection_key(ip, ban_scope, service if ban_scope == 'service' else None)}|ban"
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
