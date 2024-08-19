from os.path import join, sep

from flask import Blueprint, current_app, render_template
from flask_login import login_required

from utils import path_to_dict


cache = Blueprint("cache", __name__)


@cache.route("/cache", methods=["GET"])
@login_required
def cache_page():  # TODO: refactor this function
    return render_template(
        "cache.html",
        folders=[
            path_to_dict(
                join(sep, "var", "cache", "bunkerweb"),
                is_cache=True,
                db_data=current_app.db.get_jobs_cache_files(),
                services=current_app.bw_config.get_config(global_only=True, methods=False, filtered_settings=("SERVER_NAME",))
                .get("SERVER_NAME", "")
                .split(" "),
            )
        ],
    )
