from flask import Blueprint, render_template
from flask_login import login_required


pro = Blueprint("pro", __name__)


@pro.route("/pro")
@login_required
def pro_page():
    return render_template("pro.html")
