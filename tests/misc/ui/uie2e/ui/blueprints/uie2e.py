from flask import Blueprint
from flask_login import login_required

uie2e = Blueprint("uie2e", __name__)


@uie2e.route("/uie2e", methods=["GET"])
@login_required
def uie2e_page():
    return "UI E2E blueprint page"
