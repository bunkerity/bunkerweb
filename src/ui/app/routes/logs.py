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
    page = request.args.get("page")

    if current_file and current_file not in files:
        return Response("No such file", 404)

    if isabs(current_file) or ".." in current_file:
        return error_message("Invalid file path", 400)

    raw_logs = "Select a log file to view its contents"
    page_num = 1
    if current_file:
        with logs_path.joinpath(current_file).open(encoding="utf-8") as f:
            raw_logs = f.read().splitlines()
            page_num = len(raw_logs) // 10000 + 1
            if not page:
                page = page_num
            raw_logs = "\n".join(raw_logs[int(page) * 10000 - 10000 : int(page) * 10000])  # noqa: E203

    return render_template("logs.html", logs=raw_logs, files=files, current_file=current_file, current_page=int(page), page_num=page_num)
