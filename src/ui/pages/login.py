from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user

from dependencies import DB
from utils import LOGGER

login = Blueprint("login", __name__)


@login.route("/login", methods=["GET", "POST"])
def login_page():
    admin_user = DB.get_ui_user()
    if not admin_user:
        return redirect(url_for("setup.setup_page"))
    elif current_user.is_authenticated:  # type: ignore
        return redirect(url_for("home.home_page"))

    fail = False
    if request.method == "POST" and "username" in request.form and "password" in request.form:
        LOGGER.warning(f"Login attempt from {request.remote_addr} with username \"{request.form['username']}\"")

        ui_user = DB.get_ui_user(username=request.form["username"])
        if ui_user and ui_user.username == request.form["username"] and ui_user.check_password(request.form["password"]):
            # log the user in
            session["user_agent"] = request.headers.get("User-Agent")
            session["totp_validated"] = False

            ui_user.last_login_at = datetime.now()
            ui_user.last_login_ip = request.remote_addr
            ui_user.login_count += 1

            DB.mark_ui_user_login(ui_user.username, ui_user.last_login_at, ui_user.last_login_ip)

            if not login_user(ui_user, remember=request.form.get("remember") == "on"):
                flash("Couldn't log you in, please try again", "error")
                return (render_template("login.html", error="Couldn't log you in, please try again"),)

            LOGGER.info(
                f"User {ui_user.username} logged in successfully for the {str(ui_user.login_count) + ('th' if 10 <= ui_user.login_count % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(ui_user.login_count % 10, 'th'))} time"
                + (" with remember me" if request.form.get("remember") == "on" else "")
            )

            # redirect him to the page he originally wanted or to the home page
            return redirect(url_for("loading", next=request.form.get("next") or url_for("home.home_page")))
        else:
            flash("Invalid username or password", "error")
            fail = True

    kwargs = {
        "is_totp": bool(current_user.totp_secret),
    } | ({"error": "Invalid username or password"} if fail else {})

    return render_template("login.html", **kwargs), 401 if fail else 200
