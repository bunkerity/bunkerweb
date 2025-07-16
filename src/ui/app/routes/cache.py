from io import BytesIO
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
    title="UI-cache",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-cache")

from flask import Blueprint, Response, flash as flask_flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from werkzeug.utils import secure_filename

from app.dependencies import BW_CONFIG, DB
from app.utils import get_printable_content


cache = Blueprint("cache", __name__)

SHOWN_FILE_TYPES = ("text/plain", "text/html", "text/css", "text/javascript", "application/json", "application/xml")


@cache.route("/cache", methods=["GET"])
@login_required
def cache_page():
    logger.debug("cache_page() called")
    
    service = request.args.get("service", "")
    cache_plugin = request.args.get("plugin", "")
    cache_job_name = request.args.get("job_name", "")
    
    logger.debug(f"Loading cache page with filters: service='{service}', plugin='{cache_plugin}', job_name='{cache_job_name}'")
    
    caches = DB.get_jobs_cache_files(with_data=False)
    services_config = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"]
    
    logger.debug(f"Retrieved {len(caches)} cache files")
    
    return render_template(
        "cache.html",
        caches=caches,
        services=services_config,
        cache_service=service,
        cache_plugin=cache_plugin,
        cache_job_name=cache_job_name,
    )


@cache.route("/cache/<string:service>/<string:plugin_id>/<string:job_name>/<string:file_name>", methods=["GET"])
@login_required
def cache_view(service: str, plugin_id: str, job_name: str, file_name: str):
    logger.debug(f"cache_view() called: service={service}, plugin={plugin_id}, job={job_name}, file={file_name}")
    
    original_file_name = file_name
    if file_name.startswith("folder:"):
        file_name = file_name.replace("_", "/")
        logger.debug(f"Processed folder path: {original_file_name} -> {file_name}")
    else:
        file_name = secure_filename(file_name)
        logger.debug(f"Secured filename: {original_file_name} -> {file_name}")

    cache_file = DB.get_job_cache_file(
        job_name,
        file_name,
        service_id=service if service != "global" else None,
        plugin_id=plugin_id,
    )

    download = request.args.get("download", False)
    if download:
        logger.debug(f"Download requested for cache file: {file_name}")
        if not cache_file:
            logger.debug("Cache file not found for download")
            return Response("Cache file not found", status=404)
        
        logger.debug(f"Sending cache file download: {file_name}, size: {len(cache_file)} bytes")
        return send_file(BytesIO(cache_file), as_attachment=True, download_name=file_name)

    if not cache_file:
        logger.debug(f"Cache file not found: {file_name}")
        flask_flash(f"Cache file {file_name} from job {job_name}, plugin {plugin_id}{', service ' + service if service != 'global' else ''} not found", "error")
        return redirect(url_for("cache.cache_page"))

    logger.debug(f"Displaying cache file: {file_name}, size: {len(cache_file)} bytes")
    printable_content = get_printable_content(cache_file)
    logger.debug(f"Processed printable content length: {len(printable_content)}")
    
    return render_template("cache_view.html", cache_file=printable_content)


@cache.route("/cache/delete", methods=["POST"])
@login_required
def cache_delete_bulk():
    logger.debug("cache_delete_bulk() called")
    
    if DB.readonly:
        logger.debug("Database is in read-only mode, blocking cache deletion")
        return Response("Database is in read-only mode", status=403)

    try:
        cache_files_param = request.form.get("cache_files", "[]")
        cache_files = loads(cache_files_param)
        logger.debug(f"Parsed {len(cache_files)} cache files for deletion")
    except JSONDecodeError:
        logger.exception("Invalid JSON in cache_files parameter")
        return Response("Invalid cache files parameter", status=400)

    if not cache_files:
        logger.debug("No cache files selected for deletion")
        return Response("No cache files selected", status=400)

    errors = []
    changed_plugins = set()
    deleted_count = 0

    logger.debug(f"Starting bulk deletion of {len(cache_files)} cache files")

    for i, cache_file in enumerate(cache_files):
        file_name = cache_file.get("fileName", "")
        job_name = cache_file.get("jobName", "")
        service = cache_file.get("service", "")
        plugin = cache_file.get("plugin", "")

        logger.debug(f"Processing file {i+1}/{len(cache_files)}: {file_name} (job: {job_name}, plugin: {plugin}, service: {service})")

        original_file_name = file_name
        if file_name.startswith("folder:"):
            file_name = file_name.replace("_", "/")
            logger.debug(f"Processed folder path for deletion: {original_file_name} -> {file_name}")
        else:
            file_name = secure_filename(file_name)

        # Delete the cache file
        result = DB.delete_job_cache(
            file_name,
            job_name=job_name,
            service_id=service if service != "global" else None,
        )

        if result:
            error_msg = f"Error deleting {file_name}: {result}"
            logger.exception(error_msg)
            errors.append(error_msg)
        else:
            changed_plugins.add(plugin)
            deleted_count += 1
            logger.debug(f"Successfully deleted cache file: {file_name}")

    logger.debug(f"Deletion completed: {deleted_count} successful, {len(errors)} errors")
    logger.debug(f"Changed plugins: {changed_plugins}")

    # Commit changes to database
    if changed_plugins:
        logger.debug("Committing cache deletion changes to database")
        ret = DB.checked_changes(changes=["config"], plugins_changes=list(changed_plugins), value=True)
        if ret:
            logger.exception(f"Failed to commit cache deletion changes: {ret}")
            errors.append("Changes were not committed to the database")
        else:
            logger.debug("Cache deletion changes committed successfully")

    # Provide user feedback
    if errors:
        error_summary = f"Deleted {deleted_count} files with {len(errors)} errors: {'; '.join(errors)}"
        logger.info(error_summary)
        flask_flash(error_summary, "warning")
    else:
        success_msg = f"Successfully deleted {deleted_count} cache file{'s' if deleted_count != 1 else ''}"
        logger.info(success_msg)
        flask_flash(success_msg, "success")

    return redirect(url_for("cache.cache_page"))
