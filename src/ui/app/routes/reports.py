from math import floor

from flask import Blueprint, render_template
from flask_login import login_required

from app.dependencies import BW_INSTANCES_UTILS

reports = Blueprint("reports", __name__)


@reports.route("/reports", methods=["GET"])
@login_required
def reports_page():
    reports = BW_INSTANCES_UTILS.get_reports()
    reasons = set()
    countries = set()
    methods = set()
    codes = set()

    # Prepare data
    reports_items = []
    for i, report in enumerate(reports):
        report_item = {
            "id": str(i),
            "date": str(floor(report.pop("date"))),
        } | report
        reports_items.append(report_item)

        reasons.add(report["reason"])
        countries.add(report["country"])
        methods.add(report["method"])
        codes.add(report["code"])

    # builder = reports_builder(reports_items, list(reasons), list(countries), list(methods), list(codes))
    # return render_template("reports.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))
    return render_template("reports.html")
