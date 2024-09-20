from datetime import datetime

from flask import Blueprint, render_template
from flask_login import login_required

from app.dependencies import BW_INSTANCES_UTILS

reports = Blueprint("reports", __name__)


@reports.route("/reports", methods=["GET"])
@login_required
def reports_page():
    reports = BW_INSTANCES_UTILS.get_reports()
    for i in range(len(reports)):
        reports[i]["date"] = datetime.fromtimestamp(reports[i]["date"]).astimezone().isoformat()
    return render_template("reports.html", reports=list(filter(lambda x: 400 <= x["status"] < 500, reports)))  # TODO: check why we need to filter this
