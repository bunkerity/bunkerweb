from datetime import datetime
from os import getenv

from flask import Blueprint, current_app, flash as flask_flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user

from app.dependencies import DB
from app.utils import BISCUIT_PRIVATE_KEY_FILE, LOGGER, flash, _sanitize_internal_next
from app.models.biscuit import BiscuitTokenFactory, PrivateKey

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
            # Regenerate the session to mitigate session fixation
            session.clear()  # Clear the current session
            current_app.session_interface.regenerate(session)  # Regenerate the session ID

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

            always_remember = getenv("ALWAYS_REMEMBER", "no").lower() == "yes"
            remember_me = always_remember or request.form.get("remember-me") == "on"
            if remember_me:
                if always_remember:
                    LOGGER.info("ALWAYS_REMEMBER is set to yes, so the sessions will always be remembered")
                session.permanent = True

            if not login_user(ui_user, remember=remember_me):
                flask_flash("Couldn't log you in, please try again", "error")
                return (render_template("login.html", error="Couldn't log you in, please try again"),)

            # Generate and add Biscuit token to session
            try:
                if BISCUIT_PRIVATE_KEY_FILE.exists():
                    private_key = PrivateKey.from_hex(BISCUIT_PRIVATE_KEY_FILE.read_text().strip())
                    token_factory = BiscuitTokenFactory(private_key)
                    role = "super_admin" if ui_user.admin else [role.role_name for role in ui_user.roles][0]  # For now we shall only have one role per user
                    session["biscuit_token"] = token_factory.create_token_for_role(role, ui_user.username).to_base64()
                else:
                    LOGGER.warning("BISCUIT_PRIVATE_KEY_PATH not configured, skipping Biscuit token generation")
            except Exception as e:
                LOGGER.error(f"Failed to create Biscuit token: {e}")

            user_data = {
                "username": current_user.get_id(),
                "password": current_user.password.encode("utf-8"),
                "email": current_user.email,
                "totp_secret": current_user.totp_secret,
                "method": current_user.method,
                "theme": request.form.get("theme", "light"),
                "language": request.form.get("language", "en"),
            }

            ret = DB.update_ui_user(**user_data, old_username=current_user.get_id())
            if ret:
                LOGGER.error(f"Couldn't update the user {current_user.get_id()}: {ret}")

            LOGGER.info(f"User {ui_user.username} logged in successfully" + (" with remember me" if request.form.get("remember-me") == "on" else ""))

            if not ui_user.totp_secret:
                flash(
                    f'Please enable two-factor authentication to secure your account <a href="{url_for("profile.profile_page", _anchor="security")}">here</a>',
                    "warning",
                )

            # Internal redirect target
            raw_next = request.args.get("next") or ""
            # Support nested ?next= chaining
            if "?next=" in raw_next:
                raw_next = raw_next.split("?next=")[-1]

            try:
                safe_next = _sanitize_internal_next(raw_next, url_for("home.home_page"))
            except Exception:
                safe_next = url_for("home.home_page")

            return redirect(url_for("loading", next=safe_next))
        else:
            flask_flash("Invalid username or password", "error")
            fail = True

    kwargs = {
        "is_totp": bool(current_user.totp_secret),
    } | ({"error": "Invalid username or password"} if fail else {})

    return render_template("login.html", **kwargs), 401 if fail else 200
