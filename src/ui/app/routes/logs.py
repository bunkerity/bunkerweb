from os.path import isabs, sep
from pathlib import Path

from flask import Blueprint, Response, render_template, request
from flask_login import login_required
from werkzeug.utils import secure_filename

from app.routes.utils import error_message


logs = Blueprint("logs", __name__)


@logs.route("/logs", methods=["GET"])
@login_required
def logs_page():
    logs_path = Path(sep, "var", "log", "bunkerweb")

    files = []
    if logs_path.is_dir():
        for file in logs_path.glob("*.log"):
            if file.is_file():
                files.append(file.name)

    current_file = secure_filename(request.args.get("file", ""))

    if current_file and current_file not in files:
        return Response("No such file", 404)

    if isabs(current_file) or ".." in current_file:
        return error_message("Invalid file path", 400)

    # raw_logs = ""
    # if current_file:
    #     with logs_path.joinpath(current_file).open(encoding="utf-8") as f:
    #         raw_logs = f.read()

    # builder = logs_builder(files, current_file, raw_logs)
    # return render_template("logs.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))
    return render_template("logs.html")  # TODO
