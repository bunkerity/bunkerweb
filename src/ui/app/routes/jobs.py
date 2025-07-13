from json import JSONDecodeError, loads
from os import sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-jobs",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-jobs")

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import DB
from app.utils import flash

from app.routes.utils import handle_error, verify_data_in_form

jobs = Blueprint("jobs", __name__)


@jobs.route("/jobs", methods=["GET"])
@login_required
def jobs_page():
    logger.debug("jobs_page() called")
    jobs_list = DB.get_jobs()
    logger.debug(f"Retrieved {len(jobs_list)} jobs from database")
    return render_template("jobs.html", jobs=jobs_list)


@jobs.route("/jobs/run", methods=["POST"])
@login_required
def jobs_run():
    logger.debug("jobs_run() called")
    
    if DB.readonly:
        logger.debug("Database is in read-only mode, blocking job execution")
        return handle_error("Database is in read-only mode", "jobs")

    verify_data_in_form(
        data={"jobs": None},
        err_message="Missing jobs parameter on /jobs/run.",
        redirect_url="jobs",
        next=True,
    )
    
    jobs_param = request.form["jobs"]
    if not jobs_param:
        logger.debug("No jobs selected for execution")
        return handle_error("No jobs selected.", "jobs", True)
    
    try:
        jobs = loads(jobs_param)
        logger.debug(f"Parsed {len(jobs)} jobs for execution: {[job.get('plugin') + '/' + job.get('name') for job in jobs]}")
    except JSONDecodeError:
        logger.exception("Invalid JSON in jobs parameter")
        return handle_error("Invalid jobs parameter on /jobs/run.", "jobs", True)

    # Extract plugin names for validation
    plugin_names = [job.get("plugin") for job in jobs if job.get("plugin")]
    logger.debug(f"Checking changes for plugins: {plugin_names}")
    
    ret = DB.checked_changes(["config"], plugin_names, True)
    if ret:
        logger.exception(f"Failed to check changes for job execution: {ret}")
        return handle_error(ret, "jobs", True)

    job_count = len(jobs)
    job_names = [job.get('plugin') + '/' + job.get('name') for job in jobs]
    
    logger.info(f"Starting execution of {job_count} job{'s' if job_count > 1 else ''}: {', '.join(job_names)}")
    
    flash(f"Job{'s' if job_count > 1 else ''}'s plugins will be run in the background by the scheduler.")
    return redirect(
        url_for(
            "loading",
            next=url_for("jobs.jobs_page"),
            message=f"Run selected job{'s' if job_count > 1 else ''}'s plugins: {', '.join(job_names)}",
        )
    )
