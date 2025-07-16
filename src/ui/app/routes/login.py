from datetime import datetime
from os import getenv, sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-login",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-login")

from flask import Blueprint, current_app, flash as flask_flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user

from app.dependencies import DB
from app.utils import BISCUIT_PRIVATE_KEY_FILE, flash
from app.models.biscuit import BiscuitTokenFactory, PrivateKey

login = Blueprint("login", __name__)


@login.route("/login", methods=["GET", "POST"])
def login_page():
    logger.debug(f"login_page() called from {request.remote_addr}")
    
    admin_user = DB.get_ui_user()
    if not admin_user:
        logger.debug("No admin user found, redirecting to setup")
        return redirect(url_for("setup.setup_page"))
    elif current_user.is_authenticated:  # type: ignore
        logger.debug(f"User already authenticated: {current_user.get_id()}, redirecting to home")
        return redirect(url_for("home.home_page"))

    fail = False
    if request.method == "POST" and "username" in request.form and "password" in request.form:
        username = request.form["username"]
        logger.debug(f"Processing login attempt for username: {username}")
        logger.warning(f"Login attempt from {request.remote_addr} with username \"{username}\"")

        ui_user = DB.get_ui_user(username=username)
        if ui_user and ui_user.username == username and ui_user.check_password(request.form["password"]):
            logger.debug(f"Authentication successful for user: {username}")
            
            # Regenerate the session to mitigate session fixation
            logger.debug("Regenerating session for security")
            session.clear()  # Clear the current session
            current_app.session_interface.regenerate(session)  # Regenerate the session ID

            # log the user in
            session["creation_date"] = datetime.now().astimezone()
            session["ip"] = request.remote_addr
            session["user_agent"] = request.headers.get("User-Agent")
            session["totp_validated"] = False
            session["flash_messages"] = []

            logger.debug(f"Setting up session for user {username} from {request.remote_addr}")

            ret = DB.mark_ui_user_login(ui_user.username, session["creation_date"], session["ip"], session["user_agent"])
            if isinstance(ret, str):
                logger.exception(f"Couldn't mark the user login: {ret}")
            else:
                session["session_id"] = ret
                logger.debug(f"Session ID created: {ret}")

            always_remember = getenv("ALWAYS_REMEMBER", "no").lower() == "yes"
            remember_me = always_remember or request.form.get("remember-me") == "on"
            
            if remember_me:
                if always_remember:
                    logger.debug("ALWAYS_REMEMBER is set, enabling permanent session")
                else:
                    logger.debug("Remember me requested by user")
                session.permanent = True

            if not login_user(ui_user, remember=remember_me):
                logger.debug("Flask-Login failed to log in user")
                flask_flash("Couldn't log you in, please try again", "error")
                return (render_template("login.html", error="Couldn't log you in, please try again"),)

            logger.debug("Flask-Login successful, generating Biscuit token")

            # Generate and add Biscuit token to session
            try:
                if BISCUIT_PRIVATE_KEY_FILE.exists():
                    private_key = PrivateKey.from_hex(BISCUIT_PRIVATE_KEY_FILE.read_text().strip())
                    token_factory = BiscuitTokenFactory(private_key)
                    role = "super_admin" if ui_user.admin else [role.role_name for role in ui_user.roles][0]  # For now we shall only have one role per user
                    session["biscuit_token"] = token_factory.create_token_for_role(role, ui_user.username).to_base64()
                    logger.debug(f"Biscuit token generated for role: {role}")
                else:
                    logger.debug("BISCUIT_PRIVATE_KEY_PATH not configured, skipping Biscuit token generation")
            except Exception as e:
                logger.exception(f"Failed to create Biscuit token: {e}")

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
                logger.exception(f"Couldn't update the user {current_user.get_id()}: {ret}")

            remember_status = " with remember me" if request.form.get("remember-me") == "on" else ""
            logger.info(f"User {ui_user.username} logged in successfully{remember_status}")

            if not ui_user.totp_secret:
                logger.debug("User does not have TOTP enabled, showing warning")
                flash(
                    f'Please enable two-factor authentication to secure your account <a href="{url_for("profile.profile_page", _anchor="security")}">here</a>',
                    "warning",
                )

            # redirect him to the page he originally wanted or to the home page
            next_url = request.args.get("next", "").split("?next=")[-1] or url_for("home.home_page")
            logger.debug(f"Redirecting authenticated user to: {next_url}")
            return redirect(url_for("loading", next=next_url))
        else:
            logger.debug(f"Authentication failed for username: {username}")
            flask_flash("Invalid username or password", "error")
            fail = True

    kwargs = {
        "is_totp": bool(current_user.totp_secret),
    } | ({"error": "Invalid username or password"} if fail else {})

    status_code = 401 if fail else 200
    logger.debug(f"Rendering login page with status: {status_code}")
    return render_template("login.html", **kwargs), status_code
