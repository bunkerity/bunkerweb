from io import BytesIO
from json import JSONDecodeError, loads

from flask import Blueprint, Response, flash as flask_flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from werkzeug.utils import secure_filename

from app.dependencies import API_CLIENT, BW_CONFIG
from app.api_client import ApiClientError, ApiUnavailableError
from app.utils import flash, is_readonly_request

cache = Blueprint("cache", __name__)

SHOWN_FILE_TYPES = ("text/plain", "text/html", "text/css", "text/javascript", "application/json", "application/xml")


@cache.route("/cache", methods=["GET"])
@login_required
def cache_page():
    service = request.args.get("service", "")
    cache_plugin = request.args.get("plugin", "")
    cache_job_name = request.args.get("job_name", "")
    try:
        caches = API_CLIENT.get_cache_files()
    except (ApiClientError, ApiUnavailableError) as e:
        flash(f"Error fetching cache files: {e.message}", "error")
        caches = []

    return render_template(
        "cache.html",
        caches=caches,
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

    download = request.args.get("download", False)

    try:
        if download:
            resp = API_CLIENT.get_cache_file(service, plugin_id, job_name, file_name, download=True)
            return send_file(BytesIO(resp.content), as_attachment=True, download_name=file_name)

        data = API_CLIENT.get_cache_file(service, plugin_id, job_name, file_name)
        cache_content = data.get("file", {}).get("data", "")
        return render_template("cache_view.html", cache_file=cache_content)
    except ApiClientError as e:
        if e.status_code == 404:
            flask_flash(
                f"Cache file {file_name} from job {job_name}, plugin {plugin_id}{', service ' + service if service != 'global' else ''} not found", "error"
            )
            return redirect(url_for("cache.cache_page"))
        flask_flash(f"Error fetching cache file: {e.message}", "error")
        return redirect(url_for("cache.cache_page"))
    except ApiUnavailableError as e:
        flask_flash(f"API unavailable: {e.message}", "error")
        return redirect(url_for("cache.cache_page"))


@cache.route("/cache/delete", methods=["POST"])
@login_required
def cache_delete_bulk():
    if API_CLIENT.readonly:
        return Response("Database is in read-only mode", status=403)
    if is_readonly_request(API_CLIENT.readonly):
        return Response("You do not have the write permission", status=403)

    try:
        cache_files = loads(request.form.get("cache_files", "[]"))
    except JSONDecodeError:
        return Response("Invalid cache files parameter", status=400)

    if not cache_files:
        return Response("No cache files selected", status=400)

    try:
        result = API_CLIENT.delete_cache_files(cache_files)
        deleted_count = result.get("deleted", 0)
        errors = result.get("errors", [])

        if errors:
            flask_flash(f"Deleted {deleted_count} files with {len(errors)} errors: {'; '.join(errors)}", "warning")
        else:
            flask_flash(f"Successfully deleted {deleted_count} cache file{'s' if deleted_count != 1 else ''}", "success")
    except (ApiClientError, ApiUnavailableError) as e:
        flask_flash(f"Error deleting cache files: {e.message}", "error")

    return redirect(url_for("cache.cache_page"))
