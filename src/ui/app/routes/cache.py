from io import BytesIO

from flask import Blueprint, Response, flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from magic import Magic
from werkzeug.utils import secure_filename

from app.dependencies import DB


cache = Blueprint("cache", __name__)

SHOWN_FILE_TYPES = ("text/plain", "text/html", "text/css", "text/javascript", "application/json", "application/xml")


@cache.route("/cache", methods=["GET"])
@login_required
def cache_page():
    return render_template("cache.html", caches=DB.get_jobs_cache_files(with_data=False))


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
        flash(f"Cache file {file_name} from job {job_name}, plugin {plugin_id}{', service ' + service if service != 'global' else ''} not found", "error")
        return redirect(url_for("cache.cache_page"))

    file_type = Magic(mime=True).from_buffer(cache_file)

    return render_template(
        "cache_view.html",
        cache_file=cache_file.decode("utf-8") if file_type in SHOWN_FILE_TYPES else f"File is of type {file_type}, Download it to view the content",
    )
