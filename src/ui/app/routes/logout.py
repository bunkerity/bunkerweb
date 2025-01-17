from flask import Blueprint, redirect, session, url_for
from flask_login import login_required, logout_user


logout = Blueprint("logout", __name__)


@logout.route("/logout")
@login_required
def logout_page():
    session.clear()
    logout_user()
    response = redirect(url_for("login.login_page"))
    response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage", "executionContexts"'
    return response
