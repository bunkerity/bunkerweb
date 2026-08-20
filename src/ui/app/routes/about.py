from flask import Blueprint, render_template
from flask_login import login_required

from app.dependencies import DATA
from app.utils import human_readable_number

about = Blueprint("about", __name__)


@about.route("/about")
@login_required
def about_page():
    # Refreshed hourly in the background (main.py `update_github_metadata`), never on this
    # request: the page must render at the same speed whether or not GitHub is reachable.
    stars = DATA.get("GITHUB_STARS")
    return render_template("about.html", github_stars=human_readable_number(stars) if stars else None)
