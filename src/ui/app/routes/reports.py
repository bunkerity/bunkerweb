from collections import defaultdict
from datetime import datetime
from itertools import chain
from json import dumps, loads
from traceback import format_exc
from html import escape

from flask import Blueprint, flash, jsonify, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, BW_INSTANCES_UTILS
from app.utils import LOGGER

from app.routes.utils import cors_required, get_redis_client

reports = Blueprint("reports", __name__)


@reports.route("/reports", methods=["GET"])
@login_required
def reports_page():
    return render_template("reports.html")


@reports.route("/reports/fetch", methods=["POST"])
@login_required
@cors_required
def reports_fetch():
    redis_client = get_redis_client()

    # Load configuration to resolve Bad Behavior ban time per service
    try:
        db_config = BW_CONFIG.get_config(methods=False, with_drafts=True) if BW_CONFIG else {}
    except Exception:
        db_config = {}

    def get_default_ban_time(server_name: str) -> int:
        try:
            if not db_config:
                return 86400
            # Prefer service-specific value when available
            if server_name and server_name not in ("_", ""):
                service_key = f"{server_name}_BAD_BEHAVIOR_BAN_TIME"
                if service_key in db_config:
                    return int(db_config.get(service_key, 86400))
            # Fallback to global default from config, or plugin default (24h)
            return int(db_config.get("BAD_BEHAVIOR_BAN_TIME", 86400))
        except Exception:
            return 86400

    # Fetch reports
    def fetch_reports():
        if redis_client:
            try:
                redis_reports = redis_client.lrange("requests", 0, -1)
                redis_reports = (loads(report_raw.decode("utf-8", "replace")) for report_raw in redis_reports)
            except BaseException as e:
                LOGGER.debug(format_exc())
                LOGGER.error(f"Failed to fetch reports from Redis: {e}")
                flash("Failed to fetch reports from Redis, see logs for more information.", "error")
                redis_reports = []
        else:
            redis_reports = []
        instance_reports = BW_INSTANCES_UTILS.get_reports() if BW_INSTANCES_UTILS else []
        return chain(redis_reports, instance_reports)

    # Filter valid and unique reports
    seen_ids = set()
    all_reports = list(
        report
        for report in fetch_reports()
        if report.get("id") not in seen_ids
        and (400 <= report.get("status", 0) < 500 or report.get("security_mode") == "detect")
        and not seen_ids.add(report.get("id"))
    )

    # Extract DataTables parameters
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

    # Keep this in sync with the frontend DataTables columns
    columns = [
        "date",
        "id",
        "ip",
        "country",
        "method",
        "url",
        "status",
        "user_agent",
        "reason",
        "server_name",
        "data",
        "security_mode",
        "actions",  # actions column for row buttons
    ]

    # Apply searchPanes filters
    def filter_by_search_panes(reports):
        for field, selected_values in search_panes.items():
            # Compare as strings to handle numeric fields (e.g., status codes)
            selected_values_str = {str(v) for v in selected_values}
            reports = [report for report in reports if str(report.get(field, "N/A")) in selected_values_str]
        return reports

    # Global search filtering
    def global_search_filter(report):
        return any(search_value in str(report.get(col, "")).lower() for col in columns)

    # Sort reports
    def sort_reports(reports):
        if 0 <= order_column_index < len(columns):
            sort_key = columns[order_column_index]
            reports.sort(key=lambda x: x.get(sort_key, ""), reverse=(order_direction == "desc"))

    # Apply filters and sort
    filtered_reports = filter(global_search_filter, all_reports) if search_value else all_reports
    filtered_reports = list(filter_by_search_panes(filtered_reports))
    sort_reports(filtered_reports)

    paginated_reports = filtered_reports if length == -1 else filtered_reports[start : start + length]  # noqa: E203

    # Format reports for the response
    def format_report(report):
        try:
            # Handle the data field safely - ensure it's proper JSON or convert safely
            data_field = report.get("data", {})
            if isinstance(data_field, str):
                try:
                    # Try to parse if it's already a JSON string
                    data_json = loads(data_field)
                    data_output = dumps(data_json)
                except (ValueError, TypeError):
                    # If parsing fails, just dump it as a string
                    data_output = dumps(data_field)
            else:
                # If it's not a string, dump the object directly
                data_output = dumps(data_field)

            return {
                "date": datetime.fromtimestamp(report.get("date", 0)).isoformat() if report.get("date") else "N/A",
                "id": escape(str(report.get("id", "N/A"))),
                "ip": escape(str(report.get("ip", "N/A"))),
                "country": escape(str(report.get("country", "N/A"))),
                "method": escape(str(report.get("method", "N/A"))),
                "url": escape(str(report.get("url", "N/A"))),
                "status": escape(str(report.get("status", "N/A"))),
                "user_agent": escape(str(report.get("user_agent", "N/A"))),
                "reason": escape(str(report.get("reason", "N/A"))),
                "server_name": escape(str(report.get("server_name", "N/A"))),
                "data": data_output,
                "security_mode": escape(str(report.get("security_mode", "N/A"))),
                # default ban duration in seconds for quick-ban action
                "ban_default_exp": get_default_ban_time(str(report.get("server_name", "_"))),
                # Placeholder for UI actions column
                "actions": "",
            }
        except Exception as e:
            LOGGER.error(f"Error formatting report: {e}")
            # Return a safe fallback if formatting fails
            return {
                "date": "N/A",
                "id": "N/A",
                "ip": escape(str(report.get("ip", "N/A"))),
                "country": "N/A",
                "method": "N/A",
                "url": "N/A",
                "status": "N/A",
                "user_agent": "N/A",
                "reason": "Error parsing report data",
                "server_name": "N/A",
                "data": "{}",
                "security_mode": "N/A",
                "ban_default_exp": 86400,
                "actions": "",
            }

    formatted_reports = [format_report(report) for report in paginated_reports]

    # Calculate pane counts
    pane_counts = defaultdict(lambda: defaultdict(lambda: {"total": 0, "count": 0}))
    filtered_ids = {report["id"] for report in filtered_reports}

    for report in all_reports:
        for field in columns[2:]:  # Skip date and id fields for panes
            # Skip actions field from search panes aggregation
            if field == "actions":
                continue
            value = report.get(field, "N/A")

            # Ensure value is hashable (convert dicts or lists to strings if necessary)
            if isinstance(value, (dict, list)):
                value = str(value)

            pane_counts[field][value]["total"] += 1
            if report["id"] in filtered_ids:
                pane_counts[field][value]["count"] += 1

    # Prepare SearchPanes options
    base_flags_url = url_for("static", filename="img/flags")
    search_panes_options = {}
    for field, values in pane_counts.items():
        if field == "country":
            search_panes_options["country"] = []
            for code, counts in values.items():
                country_code = code.lower()
                country_name = "N/A"
                search_panes_options["country"].append(
                    {
                        "label": f"""<img src="{base_flags_url}/{'zz' if code == 'local' else country_code}.svg" class="border border-1 p-0 me-1" height="17" />&nbsp;－&nbsp;<span data-i18n="country.{'not_applicable' if code == 'local' else code.upper()}">{'N/A' if code == 'local' else country_name}</span>""",
                        "value": code,
                        "total": counts["total"],
                        "count": counts["count"],
                    }
                )
        elif field == "server_name":
            search_panes_options["server_name"] = []
            for name, counts in values.items():
                display_name = "default server" if name == "_" else name
                search_panes_options["server_name"].append(
                    {
                        "label": display_name,
                        "value": name,
                        "total": counts["total"],
                        "count": counts["count"],
                    }
                )
        else:
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
            "recordsTotal": len(all_reports),
            "recordsFiltered": len(filtered_reports),
            "data": formatted_reports,
            "searchPanes": {"options": search_panes_options},
        }
    )
