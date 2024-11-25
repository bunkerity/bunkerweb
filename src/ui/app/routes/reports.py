from datetime import datetime
from itertools import chain
from json import loads

from flask import Blueprint, render_template
from flask_login import login_required

from app.dependencies import BW_INSTANCES_UTILS

from app.routes.utils import get_redis_client

reports = Blueprint("reports", __name__)


@reports.route("/reports", methods=["GET"])
@login_required
def reports_page():
    redis_client = get_redis_client()

    # Generator for Redis reports
    redis_reports = (loads(report) for report in redis_client.lrange("requests", 0, -1)) if redis_client else iter([])

    # Combine Redis and instance reports into a single generator
    reports = chain(redis_reports, BW_INSTANCES_UTILS.get_reports())

    # Set to track seen IDs
    seen_ids = set()

    return render_template(
        "reports.html",
        reports=(
            {
                **report,
                "date": datetime.fromtimestamp(report["date"]).astimezone().isoformat(),
            }
            for report in reports
            if report.get("id") not in seen_ids
            and not seen_ids.add(report["id"])  # Add to seen_ids if not already present
            and (400 <= report.get("status", 0) < 500 or report.get("security_mode") == "detect")
        ),
    )
