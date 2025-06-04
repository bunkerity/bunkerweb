from io import BytesIO
from json import JSONDecodeError, loads

from flask import Blueprint, Response, flash as flask_flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from werkzeug.utils import secure_filename

from app.dependencies import BW_CONFIG, DB
from app.utils import LOGGER, get_printable_content


cache = Blueprint("cache", __name__)

SHOWN_FILE_TYPES = ("text/plain", "text/html", "text/css", "text/javascript", "application/json", "application/xml")


@cache.route("/cache", methods=["GET"])
@login_required
def cache_page():
    service = request.args.get("service", "")
    cache_plugin = request.args.get("plugin", "")
    cache_job_name = request.args.get("job_name", "")
    return render_template(
        "cache.html",
        caches=DB.get_jobs_cache_files(with_data=False),
        services=BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"],
        cache_service=service,
        cache_plugin=cache_plugin,
        cache_job_name=cache_job_name,
    )


@cache.route("/cache/<string:service>/<string:plugin_id>/<string:job_name>/<string:file_name>", methods=["GET"])
@login_required
def cache_view(service: str, plugin_id: str, job_name: str, file_name: str):
    if file_name.startswith("folder:"):
        file_name = file_name.replace("_", "/")
    else:
        file_name = secure_filename(file_name)

    cache_file = DB.get_job_cache_file(
        job_name,
        file_name,
        service_id=service if service != "global" else None,
        plugin_id=plugin_id,
    )

    download = request.args.get("download", False)
    if download:
        if not cache_file:
            return Response("Cache file not found", status=404)
        return send_file(BytesIO(cache_file), as_attachment=True, download_name=file_name)

    if not cache_file:
        flask_flash(f"Cache file {file_name} from job {job_name}, plugin {plugin_id}{', service ' + service if service != 'global' else ''} not found", "error")
        return redirect(url_for("cache.cache_page"))

    return render_template("cache_view.html", cache_file=get_printable_content(cache_file))


@cache.route("/cache/delete", methods=["POST"])
@login_required
def cache_delete_bulk():
    if DB.readonly:
        return Response("Database is in read-only mode", status=403)

    try:
        cache_files = loads(request.form.get("cache_files", "[]"))
    except JSONDecodeError:
        return Response("Invalid cache files parameter", status=400)

    if not cache_files:
        return Response("No cache files selected", status=400)

    errors = []
    changed_plugins = set()
    deleted_count = 0

    for cache_file in cache_files:
        file_name = cache_file.get("fileName", "")
        job_name = cache_file.get("jobName", "")
        service = cache_file.get("service", "")
        plugin = cache_file.get("plugin", "")

        if file_name.startswith("folder:"):
            file_name = file_name.replace("_", "/")
        else:
            file_name = secure_filename(file_name)

        # Delete the cache file
        result = DB.delete_job_cache(
            file_name,
            job_name=job_name,
            service_id=service if service != "global" else None,
        )

        if result:
            errors.append(f"Error deleting {file_name}: {result}")
        else:
            changed_plugins.add(plugin)
            deleted_count += 1

    ret = DB.checked_changes(changes=["config"], plugins_changes=list(changed_plugins), value=True)
    if ret:
        LOGGER.warning("Cache deletion changes were not committed to the database")
        errors.append("Changes were not committed to the database")

    if errors:
        flask_flash(f"Deleted {deleted_count} files with {len(errors)} errors: {'; '.join(errors)}", "warning")
    else:
        flask_flash(f"Successfully deleted {deleted_count} cache file{'s' if deleted_count != 1 else ''}", "success")

    return redirect(url_for("cache.cache_page"))
