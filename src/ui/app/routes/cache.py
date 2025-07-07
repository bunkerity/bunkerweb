from io import BytesIO
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
    logger.debug("Debug mode enabled for cache module")

from flask import Blueprint, Response, flash as flask_flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from werkzeug.utils import secure_filename

from app.dependencies import BW_CONFIG, DB
from app.utils import get_printable_content


cache = Blueprint("cache", __name__)

SHOWN_FILE_TYPES = ("text/plain", "text/html", "text/css", "text/javascript", "application/json", "application/xml")


# Display cache files management interface with service and plugin filtering capabilities.
# Renders cache overview with job-based organization and provides filtering by service,
# plugin, and job name for efficient cache file discovery and management operations.
@cache.route("/cache", methods=["GET"])
@login_required
def cache_page():
    if DEBUG_MODE:
        logger.debug("cache_page() called - initializing cache management interface")
        logger.debug(f"URL parameters: {dict(request.args)}")
    
    service = request.args.get("service", "")
    cache_plugin = request.args.get("plugin", "")
    cache_job_name = request.args.get("job_name", "")
    
    if DEBUG_MODE:
        logger.debug(f"Filter parameters - service: '{service}', plugin: '{cache_plugin}', job_name: '{cache_job_name}'")
    
    try:
        # Retrieve cache files without data for performance optimization in list view
        caches = DB.get_jobs_cache_files(with_data=False)
        server_name_config = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"]
        
        if DEBUG_MODE:
            logger.debug(f"Cache management data retrieved:")
            logger.debug(f"  - Cache files found: {len(caches)}")
            logger.debug(f"  - Available services: '{server_name_config}'")
            logger.debug("Rendering cache.html template with filtering options")
        
        return render_template(
            "cache.html",
            caches=caches,
            services=server_name_config,
            cache_service=service,
            cache_plugin=cache_plugin,
            cache_job_name=cache_job_name,
        )
    except Exception as e:
        logger.exception("Error retrieving cache files")
        if DEBUG_MODE:
            logger.debug(f"Failed to retrieve cache data: {type(e).__name__}: {e}")
        flask_flash("Failed to retrieve cache files", "error")
        return render_template("cache.html", caches=[], services="", cache_service=service, cache_plugin=cache_plugin, cache_job_name=cache_job_name)


# Display or download individual cache file with content type detection and security validation.
# Handles folder paths, file downloads, and content rendering with proper error handling
# and user feedback for missing files or invalid requests.
@cache.route("/cache/<string:service>/<string:plugin_id>/<string:job_name>/<string:file_name>", methods=["GET"])
@login_required
def cache_view(service: str, plugin_id: str, job_name: str, file_name: str):
    if DEBUG_MODE:
        logger.debug(f"cache_view() called for file access:")
        logger.debug(f"  - Service: {service}")
        logger.debug(f"  - Plugin: {plugin_id}")
        logger.debug(f"  - Job: {job_name}")
        logger.debug(f"  - File: {file_name}")
        logger.debug(f"  - Download requested: {request.args.get('download', False)}")
    
    # Handle folder path encoding for nested directory structures
    if file_name.startswith("folder:"):
        file_name = file_name.replace("_", "/")
        if DEBUG_MODE:
            logger.debug(f"Processed folder path: {file_name}")
    else:
        file_name = secure_filename(file_name)
        if DEBUG_MODE:
            logger.debug(f"Secured filename: {file_name}")

    # Retrieve cache file data from database with service normalization
    cache_file = DB.get_job_cache_file(
        job_name,
        file_name,
        service_id=service if service != "global" else None,
        plugin_id=plugin_id,
    )
    
    if DEBUG_MODE:
        logger.debug(f"Cache file retrieval result: {'found' if cache_file else 'not found'}")
        if cache_file:
            logger.debug(f"Cache file size: {len(cache_file)} bytes")

    # Handle download requests with proper file attachment headers
    download = request.args.get("download", False)
    if download:
        if DEBUG_MODE:
            logger.debug("Processing download request")
        
        if not cache_file:
            if DEBUG_MODE:
                logger.debug("Download failed - cache file not found")
            return Response("Cache file not found", status=404)
        
        if DEBUG_MODE:
            logger.debug(f"Serving file download: {file_name}")
        
        return send_file(BytesIO(cache_file), as_attachment=True, download_name=file_name)

    # Handle file not found with user notification and redirect
    if not cache_file:
        error_msg = f"Cache file {file_name} from job {job_name}, plugin {plugin_id}{', service ' + service if service != 'global' else ''} not found"
        if DEBUG_MODE:
            logger.debug(f"Cache file not found - showing error: {error_msg}")
        
        flask_flash(error_msg, "error")
        return redirect(url_for("cache.cache_page"))

    # Render cache file content with printable formatting for display
    if DEBUG_MODE:
        logger.debug("Rendering cache file content for viewing")
    
    try:
        printable_content = get_printable_content(cache_file)
        if DEBUG_MODE:
            logger.debug(f"Content processing successful - length: {len(printable_content)} characters")
        
        return render_template("cache_view.html", cache_file=printable_content)
    except Exception as e:
        logger.exception("Error processing cache file content")
        if DEBUG_MODE:
            logger.debug(f"Content processing failed: {type(e).__name__}: {e}")
        
        flask_flash("Error processing cache file content", "error")
        return redirect(url_for("cache.cache_page"))


# Execute bulk deletion of selected cache files with comprehensive validation and error tracking.
# Processes JSON file list, validates database permissions, deletes files individually,
# and commits configuration changes while providing detailed success and error reporting.
@cache.route("/cache/delete", methods=["POST"])
@login_required
def cache_delete_bulk():
    if DEBUG_MODE:
        logger.debug("cache_delete_bulk() called - processing bulk deletion request")
        logger.debug(f"Form data keys: {list(request.form.keys())}")
    
    if DB.readonly:
        if DEBUG_MODE:
            logger.debug("Database is in read-only mode - rejecting deletion request")
        return Response("Database is in read-only mode", status=403)

    # Parse and validate cache files JSON data from form submission
    try:
        cache_files = loads(request.form.get("cache_files", "[]"))
        if DEBUG_MODE:
            logger.debug(f"Successfully parsed cache files JSON:")
            logger.debug(f"  - Number of files to delete: {len(cache_files)}")
            logger.debug(f"  - File list structure validated")
    except JSONDecodeError as e:
        logger.exception("JSON parsing error in cache deletion")
        if DEBUG_MODE:
            logger.debug(f"JSON parsing failed: {e}")
        return Response("Invalid cache files parameter", status=400)

    if not cache_files:
        if DEBUG_MODE:
            logger.debug("No cache files selected for deletion")
        return Response("No cache files selected", status=400)

    # Initialize tracking variables for deletion operation
    errors = []
    changed_plugins = set()
    deleted_count = 0
    
    if DEBUG_MODE:
        logger.debug("Starting individual file deletion process")

    # Process each cache file deletion with individual error handling
    for cache_file in cache_files:
        file_name = cache_file.get("fileName", "")
        job_name = cache_file.get("jobName", "")
        service = cache_file.get("service", "")
        plugin = cache_file.get("plugin", "")
        
        if DEBUG_MODE:
            logger.debug(f"Processing deletion for:")
            logger.debug(f"  - File: {file_name}")
            logger.debug(f"  - Job: {job_name}")
            logger.debug(f"  - Service: {service}")
            logger.debug(f"  - Plugin: {plugin}")

        # Handle folder path encoding for nested directory structures
        if file_name.startswith("folder:"):
            file_name = file_name.replace("_", "/")
            if DEBUG_MODE:
                logger.debug(f"Processed folder path for deletion: {file_name}")
        else:
            file_name = secure_filename(file_name)
            if DEBUG_MODE:
                logger.debug(f"Secured filename for deletion: {file_name}")

        # Execute individual cache file deletion with error capture
        result = DB.delete_job_cache(
            file_name,
            job_name=job_name,
            service_id=service if service != "global" else None,
        )

        if result:
            error_msg = f"Error deleting {file_name}: {result}"
            errors.append(error_msg)
            if DEBUG_MODE:
                logger.debug(f"Deletion failed: {error_msg}")
        else:
            changed_plugins.add(plugin)
            deleted_count += 1
            if DEBUG_MODE:
                logger.debug(f"Successfully deleted: {file_name}")

    if DEBUG_MODE:
        logger.debug(f"Deletion summary:")
        logger.debug(f"  - Files deleted: {deleted_count}")
        logger.debug(f"  - Errors encountered: {len(errors)}")
        logger.debug(f"  - Plugins affected: {len(changed_plugins)}")

    # Commit configuration changes for affected plugins
    ret = DB.checked_changes(changes=["config"], plugins_changes=list(changed_plugins), value=True)
    if ret:
        logger.warning("Cache deletion changes were not committed to the database")
        errors.append("Changes were not committed to the database")
        if DEBUG_MODE:
            logger.debug(f"Configuration commit failed: {ret}")
    elif DEBUG_MODE:
        logger.debug("Configuration changes committed successfully")

    # Provide comprehensive user feedback based on operation results
    if errors:
        error_summary = f"Deleted {deleted_count} files with {len(errors)} errors: {'; '.join(errors)}"
        flask_flash(error_summary, "warning")
        if DEBUG_MODE:
            logger.debug(f"Operation completed with errors: {error_summary}")
    else:
        success_msg = f"Successfully deleted {deleted_count} cache file{'s' if deleted_count != 1 else ''}"
        flask_flash(success_msg, "success")
        if DEBUG_MODE:
            logger.debug(f"Operation completed successfully: {success_msg}")

    if DEBUG_MODE:
        logger.debug("Redirecting to cache management page")

    return redirect(url_for("cache.cache_page"))
