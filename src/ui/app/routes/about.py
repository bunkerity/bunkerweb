from flask import Blueprint, render_template
from flask_login import login_required


about = Blueprint("about", __name__)


@about.route("/about")
@login_required
def about_page():
    return render_template("about.html")
