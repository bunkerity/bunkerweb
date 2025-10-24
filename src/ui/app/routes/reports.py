from collections import defaultdict
from datetime import datetime
from json import dumps, loads
from traceback import format_exc
from html import escape

from flask import Blueprint, jsonify, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, BW_INSTANCES_UTILS
from app.utils import LOGGER

from app.routes.utils import cors_required

reports = Blueprint("reports", __name__)


@reports.route("/reports", methods=["GET"])
@login_required
def reports_page():
    return render_template("reports.html")


@reports.route("/reports/fetch", methods=["POST"])
@login_required
@cors_required
def reports_fetch():
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
                    return int(db_config[service_key])
            # Fallback to global default from config, or plugin default (24h)
            return int(db_config.get("BAD_BEHAVIOR_BAN_TIME", 86400))
        except Exception:
            return 86400

    # Extract DataTables parameters
    draw = int(request.form.get("draw", 1))
    start = int(request.form.get("start", 0))
    length = int(request.form.get("length", 10))
    search_value = request.form.get("search[value]", "").lower()

    # DataTables includes two leading non-data columns (details-control and select)
    # Adjust the incoming order column index to match our data columns mapping
    try:
        order_column_index_dt = int(request.form.get("order[0][column]", 0))
    except Exception:
        order_column_index_dt = 0
    # Subtract 2 to align with backend columns (starting at "date")
    order_column_index = max(order_column_index_dt - 2, 0)
    order_direction = request.form.get("order[0][dir]", "desc")

    # Parse search panes
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

    # Build search panes string for backend (format: field1:value1,value2;field2:value3)
    search_panes_str = ";".join(f"{field}:{','.join(values)}" for field, values in search_panes.items()) if search_panes else ""

    # Determine order column name
    order_column_name = columns[order_column_index] if 0 <= order_column_index < len(columns) else "date"

    # Use optimized query endpoint from InstancesUtils
    if BW_INSTANCES_UTILS:
        try:
            result = BW_INSTANCES_UTILS.get_reports_query(
                start=start,
                length=length,
                search=search_value,
                order_column=order_column_name,
                order_dir=order_direction,
                search_panes=search_panes_str,
                count_only=False,
            )

            total_count = result.get("total", 0)
            filtered_count = result.get("filtered", 0)
            paginated_reports = result.get("data", [])
            pane_counts_backend = result.get("pane_counts", {})

        except Exception as e:
            LOGGER.error(f"Error using optimized reports query: {e}")
            LOGGER.debug(format_exc())
            # Fallback to old method
            result = {"total": 0, "filtered": 0, "data": [], "pane_counts": {}}
            total_count = 0
            filtered_count = 0
            paginated_reports = []
            pane_counts_backend = {}
    else:
        # Fallback when BW_INSTANCES_UTILS is not available
        result = {"total": 0, "filtered": 0, "data": [], "pane_counts": {}}
        total_count = 0
        filtered_count = 0
        paginated_reports = []
        pane_counts_backend = {}

    # Format reports for the response
    def format_report(report):
        try:
            # Handle the data field safely - ensure it's proper JSON or convert safely
            data_field = report.get("data", {})
            if isinstance(data_field, str):
                try:
                    # Try to parse it as JSON
                    data_output = dumps(loads(data_field))
                except (ValueError, TypeError):
                    # If it fails, wrap it as a JSON string
                    data_output = dumps({"raw": data_field})
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

    # Prepare SearchPanes options from backend counts
    base_flags_url = url_for("static", filename="img/flags")
    search_panes_options = {}

    for field, values in pane_counts_backend.items():
        if field == "country":
            search_panes_options["country"] = []
            for code, counts in values.items():
                str_code = str(code)
                country_code = str_code.lower()
                is_unknown = str_code in ("unknown", "local", "n/a")
                fallback_label = "N/A" if is_unknown else str_code
                i18n_key = "not_applicable" if str_code in ("unknown", "local") else str_code.upper()
                flag_code = "zz" if is_unknown else country_code
                search_panes_options["country"].append(
                    {
                        "label": f'<img src="{base_flags_url}/{flag_code}.svg" class="border border-1 p-0 me-1" height="17" />&nbsp;－&nbsp;<span data-i18n="country.{i18n_key}">{fallback_label}</span>',
                        "value": str_code,
                        "total": counts["total"],
                        "count": counts["count"],
                    }
                )
        elif field == "server_name":
            search_panes_options["server_name"] = []
            for name, counts in values.items():
                search_panes_options["server_name"].append(
                    {
                        "label": f'<code class="language-dns">{escape("default server" if name == "_" else name)}</code>',
                        "value": escape(name),
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
            "recordsTotal": total_count,
            "recordsFiltered": filtered_count,
            "data": formatted_reports,
            "searchPanes": {"options": search_panes_options},
        }
    )
