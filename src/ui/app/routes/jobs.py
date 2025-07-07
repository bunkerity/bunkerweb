from json import JSONDecodeError, loads
from os import getenv, sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for jobs module")

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import DB
from app.utils import flash

from app.routes.utils import handle_error, verify_data_in_form

jobs = Blueprint("jobs", __name__)


# Display jobs management interface with current job status and configuration.
# Retrieves active jobs from database and renders job management dashboard.
@jobs.route("/jobs", methods=["GET"])
@login_required
def jobs_page():
    if DEBUG_MODE:
        logger.debug("jobs_page() called - retrieving job list")
    
    try:
        jobs_data = DB.get_jobs()
        if DEBUG_MODE:
            logger.debug(f"Retrieved {len(jobs_data)} jobs from database")
            for i, job in enumerate(jobs_data[:5]):  # Log first 5 jobs for debugging
                logger.debug(f"Job {i+1}: plugin='{job.get('plugin', 'unknown')}', name='{job.get('name', 'unknown')}'")
            if len(jobs_data) > 5:
                logger.debug(f"... and {len(jobs_data) - 5} more jobs")
        
        if DEBUG_MODE:
            logger.debug("Rendering jobs.html template")
        
        return render_template("jobs.html", jobs=jobs_data)
    except Exception as e:
        logger.exception("Error retrieving jobs from database")
        if DEBUG_MODE:
            logger.debug(f"Failed to retrieve jobs: {type(e).__name__}: {e}")
        return handle_error("Failed to retrieve jobs from database", "jobs")


# Execute selected jobs by triggering plugin runs through scheduler coordination.
# Validates job parameters and initiates background execution via scheduler.
@jobs.route("/jobs/run", methods=["POST"])
@login_required
def jobs_run():
    if DEBUG_MODE:
        logger.debug("jobs_run() called - processing job execution request")
        logger.debug(f"Request from IP: {request.remote_addr}")
        logger.debug(f"Form data keys: {list(request.form.keys())}")
    
    if DB.readonly:
        if DEBUG_MODE:
            logger.debug("Database is in read-only mode - rejecting job execution")
        return handle_error("Database is in read-only mode", "jobs")

    verify_data_in_form(
        data={"jobs": None},
        err_message="Missing jobs parameter on /jobs/run.",
        redirect_url="jobs",
        next=True,
    )
    
    jobs = request.form["jobs"]
    if DEBUG_MODE:
        logger.debug(f"Raw jobs parameter received: '{jobs}'")
        logger.debug(f"Jobs parameter length: {len(jobs)} characters")
    
    if not jobs:
        if DEBUG_MODE:
            logger.debug("Empty jobs parameter - no jobs selected")
        return handle_error("No jobs selected.", "jobs", True)
    
    try:
        jobs = loads(jobs)
        if DEBUG_MODE:
            logger.debug(f"Successfully parsed JSON jobs data")
            logger.debug(f"Number of jobs to execute: {len(jobs)}")
            logger.debug(f"Jobs structure type: {type(jobs)}")
            for i, job in enumerate(jobs):
                logger.debug(f"Job {i+1}: {job}")
    except JSONDecodeError as e:
        logger.exception("Failed to parse jobs JSON data")
        if DEBUG_MODE:
            logger.debug(f"JSON decode error: {e}")
            logger.debug(f"Invalid JSON content: '{jobs}'")
        return handle_error("Invalid jobs parameter on /jobs/run.", "jobs", True)

    # Extract plugin names for validation
    plugin_names = [job.get("plugin") for job in jobs if job.get("plugin")]
    if DEBUG_MODE:
        logger.debug(f"Extracted plugin names: {plugin_names}")
        logger.debug(f"Jobs with valid plugins: {len(plugin_names)}/{len(jobs)}")

    ret = DB.checked_changes(["config"], plugin_names, True)
    if DEBUG_MODE:
        logger.debug(f"Database change validation result: {ret}")
    
    if ret:
        logger.exception("Database change validation failed")
        if DEBUG_MODE:
            logger.debug(f"Change validation error: {ret}")
        return handle_error(ret, "jobs", True)

    # Prepare job execution details
    job_descriptions = [job.get('plugin') + '/' + job.get('name') for job in jobs]
    plural_suffix = 's' if len(jobs) > 1 else ''
    
    if DEBUG_MODE:
        logger.debug(f"Job execution approved for {len(jobs)} job{plural_suffix}")
        logger.debug(f"Job descriptions: {job_descriptions}")
        logger.debug("Jobs will be executed by scheduler in background")

    flash(f"Job{plural_suffix}'s plugins will be run in the background by the scheduler.")
    
    if DEBUG_MODE:
        logger.debug("Redirecting to loading page with job execution message")
    
    return redirect(
        url_for(
            "loading",
            next=url_for("jobs.jobs_page"),
            message=f"Run selected job{plural_suffix}'s plugins: {', '.join(job_descriptions)}",
        )
    )
