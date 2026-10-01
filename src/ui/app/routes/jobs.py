from json import JSONDecodeError, loads
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import API_CLIENT
from app.i18n import translated
from app.api_client import ApiClientError, ApiUnavailableError
from app.utils import flash, is_readonly_request

from app.routes.utils import handle_error, verify_data_in_form

jobs = Blueprint("jobs", __name__)


@jobs.route("/jobs", methods=["GET"])
@login_required
def jobs_page():
    try:
        jobs_list = API_CLIENT.get_jobs()
    except (ApiClientError, ApiUnavailableError) as e:
        flash(translated("jobs.flash.error_fetching_jobs", message=e.message) or f"Error fetching jobs: {e.message}", "error")
        jobs_list = []

    return render_template("jobs.html", jobs=jobs_list)


@jobs.route("/jobs/run", methods=["POST"])
@login_required
def jobs_run():
    if API_CLIENT.readonly:
        return handle_error(translated("flash.database_read_only_mode") or "Database is in read-only mode", "jobs")
    if is_readonly_request(API_CLIENT.readonly):
        return handle_error(translated("flash.do_not_have_write_permission") or "You do not have the write permission", "jobs")

    verify_data_in_form(
        data={"jobs": None},
        err_message=translated("jobs.flash.missing_jobs_parameter_jobs_run") or "Missing jobs parameter on /jobs/run.",
        redirect_url="jobs",
        next=True,
    )
    jobs = request.form["jobs"]
    if not jobs:
        return handle_error(translated("jobs.flash.no_jobs_selected") or "No jobs selected.", "jobs", True)
    try:
        jobs = loads(jobs)
    except JSONDecodeError:
        return handle_error(translated("jobs.flash.invalid_jobs_parameter_jobs_run") or "Invalid jobs parameter on /jobs/run.", "jobs", True)

    try:
        API_CLIENT.run_jobs(jobs)
    except (ApiClientError, ApiUnavailableError) as e:
        return handle_error(e.message, "jobs", True)

    flash(
        translated("jobs.flash.jobs_plugins_will_run_background_by" if len(jobs) > 1 else "jobs.flash.job_plugins_will_run_background_by")
        or (
            "Jobs' plugins will be run in the background by the scheduler."
            if len(jobs) > 1
            else "Job's plugins will be run in the background by the scheduler."
        )
    )
    return redirect(
        url_for(
            "loading",
            next=url_for("jobs.jobs_page"),
            message=f"Run selected job{'s' if len(jobs) > 1 else ''}'s plugins: {', '.join([job.get('plugin') + '/' + job.get('name') for job in jobs])}",
        )
    )
