from flask import Blueprint, render_template
from flask_login import login_required

from app.dependencies import DB

jobs = Blueprint("jobs", __name__)


@jobs.route("/jobs", methods=["GET"])
@login_required
def jobs_page():
    return render_template("jobs.html", jobs=DB.get_jobs())
