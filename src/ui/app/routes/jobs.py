from json import JSONDecodeError, loads
from flask import Blueprint, Response, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.dependencies import DB
from app.utils import flash

from app.routes.utils import handle_error, verify_data_in_form

jobs = Blueprint("jobs", __name__)


@jobs.route("/jobs", methods=["GET"])
@login_required
def jobs_page():
    return render_template("jobs.html", jobs=DB.get_jobs())


@jobs.route("/jobs/run", methods=["POST"])
@login_required
def jobs_run():
    if "write" not in current_user.list_permissions:
        return Response("You don't have the required permissions to run jobs.", 403)
    elif DB.readonly:
        return handle_error("Database is in read-only mode", "jobs")

    verify_data_in_form(
        data={"jobs": None},
        err_message="Missing jobs parameter on /jobs/run.",
        redirect_url="jobs",
        next=True,
    )
    jobs = request.form["jobs"]
    if not jobs:
        return handle_error("No jobs selected.", "jobs", True)
    try:
        jobs = loads(jobs)
    except JSONDecodeError:
        return handle_error("Invalid jobs parameter on /jobs/run.", "jobs", True)

    ret = DB.checked_changes(["config"], [job.get("plugin") for job in jobs if job.get("plugin")], True)
    if ret:
        return handle_error(ret, "jobs", True)

    flash(f"Job{'s' if len(jobs) > 1 else ''}'s plugins will be run in the background by the scheduler.", "success")
    return redirect(
        url_for(
            "loading",
            next=url_for("jobs.jobs_page"),
            message=f"Run selected job{'s' if len(jobs) > 1 else ''}'s plugins: {', '.join([job.get('plugin') + '/' + job.get('name') for job in jobs])}",
        )
    )
