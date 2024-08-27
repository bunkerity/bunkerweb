from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user

from app.dependencies import DB
from app.utils import LOGGER

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
        LOGGER.debug(request.form)
        LOGGER.warning(f"Login attempt from {request.remote_addr} with username \"{request.form['username']}\"")

        ui_user = DB.get_ui_user(username=request.form["username"])
        if ui_user and ui_user.username == request.form["username"] and ui_user.check_password(request.form["password"]):
            # log the user in
            session["creation_date"] = datetime.now().astimezone()
            session["ip"] = request.remote_addr
            session["user_agent"] = request.headers.get("User-Agent")
            session["totp_validated"] = False
            session["flash_messages"] = []

            ret = DB.mark_ui_user_login(ui_user.username, session["creation_date"], session["ip"], session["user_agent"])
            if isinstance(ret, str):
                LOGGER.error(f"Couldn't mark the user login: {ret}")
            else:
                session["session_id"] = ret

            if not login_user(ui_user, remember=request.form.get("remember-me") == "on"):
                flash("Couldn't log you in, please try again", "error")
                return (render_template("login.html", error="Couldn't log you in, please try again"),)

            LOGGER.info(f"User {ui_user.username} logged in successfully" + (" with remember me" if request.form.get("remember-me") == "on" else ""))

            # redirect him to the page he originally wanted or to the home page
            return redirect(url_for("loading", next=request.form.get("next") or url_for("home.home_page")))
        else:
            flash("Invalid username or password", "error")
            fail = True

    kwargs = {
        "is_totp": bool(current_user.totp_secret),
    } | ({"error": "Invalid username or password"} if fail else {})

    return render_template("login.html", **kwargs), 401 if fail else 200
