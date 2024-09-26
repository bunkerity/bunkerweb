from datetime import datetime, timedelta

from flask import Blueprint, render_template
from flask_login import login_required

from app.dependencies import BW_INSTANCES_UTILS

reports = Blueprint("reports", __name__)


@reports.route("/reports", methods=["GET"])
@login_required
def reports_page():
    reports = BW_INSTANCES_UTILS.get_reports()
    current_date = datetime.now().astimezone()
    for i in range(len(reports)):
        date = datetime.fromtimestamp(reports[i]["date"]).astimezone()
        if date < current_date - timedelta(days=7):
            break
        reports[i]["date"] = date.isoformat()
    return render_template("reports.html", reports=list(filter(lambda x: 400 <= x["status"] < 500, reports)))  # TODO: check why we need to filter this
