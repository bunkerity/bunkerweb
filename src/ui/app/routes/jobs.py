from io import BytesIO

from flask import Blueprint, jsonify, render_template, request, send_file
from flask_login import login_required
from werkzeug.utils import secure_filename

from app.dependencies import DB

jobs = Blueprint("jobs", __name__)


@jobs.route("/jobs", methods=["GET"])
@login_required
def jobs_page():
    # builder = jobs_builder(DB.get_jobs())
    # return render_template("jobs.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))
    return render_template("jobs.html")  # TODO


@jobs.route("/jobs/download", methods=["GET"])
@login_required
def jobs_download():
    plugin_id = request.args.get("plugin_id", "")
    job_name = request.args.get("job_name", None)
    file_name = request.args.get("file_name", None)
    service_id = request.args.get("service_id", "")

    if not plugin_id or not job_name or not file_name:
        return jsonify({"status": "ko", "message": "plugin_id, job_name and file_name are required"}), 422

    cache_file = DB.get_job_cache_file(job_name, file_name, service_id=service_id, plugin_id=plugin_id)

    if not cache_file:
        return jsonify({"status": "ko", "message": "file not found"}), 404

    file = BytesIO(cache_file)
    return send_file(file, as_attachment=True, download_name=secure_filename(file_name))
