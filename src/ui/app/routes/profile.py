from datetime import datetime
from typing import Dict, Generator, Tuple, Union
from os import getenv, sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for profile module")

from flask import Blueprint, Response, jsonify, redirect, render_template, request, stream_with_context, url_for, session
from flask_login import current_user, login_required
from user_agents import parse

from app.models.totp import totp as TOTP

from app.dependencies import DATA, DB
from app.utils import USER_PASSWORD_RX, flash, gen_password_hash

from app.routes.utils import cors_required, handle_error, verify_data_in_form

profile = Blueprint("profile", __name__)


# Retrieve paginated user session data for profile display with metadata.
# Returns session generator and total count for pagination and browser/device details.
def get_last_sessions(page: int, per_page: int) -> Tuple[Generator[Dict[str, Union[str, bool]], None, None], int]:
    if DEBUG_MODE:
        logger.debug(f"get_last_sessions() called with page={page}, per_page={per_page}")
    
    db_sessions = DB.get_ui_user_sessions(current_user.username, session.get("session_id"))
    total_sessions = len(db_sessions)
    if "session_id" not in session:
        total_sessions += 1
    
    if DEBUG_MODE:
        logger.debug(f"Retrieved {len(db_sessions)} DB sessions, total_sessions={total_sessions}")

    if total_sessions <= per_page:
        per_page = total_sessions
        page = 1
    elif total_sessions <= (page - 1) * per_page:
        page = total_sessions // per_page
    
    if DEBUG_MODE:
        logger.debug(f"Adjusted pagination - page={page}, per_page={per_page}")

    # Generate session data with user agent parsing and formatting for display.
    # Yields formatted session dictionaries with browser, OS, device, and activity info.
    def session_generator(page: int, per_page: int):
        if DEBUG_MODE:
            logger.debug(f"session_generator() called with page={page}, per_page={per_page}")
        
        additional_sessions = []
        if page == 1 and "session_id" not in session and per_page > 1:
            per_page -= 1
            additional_sessions.append(session)
            if DEBUG_MODE:
                logger.debug("Added current session to additional_sessions")

        for db_session in additional_sessions + db_sessions[(page - 1) * per_page : page * per_page]:  # noqa: E203
            ua_data = parse(db_session["user_agent"])
            
            if DEBUG_MODE:
                logger.debug(f"Processing session: {db_session.get('id', 'current')}")
            
            yield {
                "current": db_session["id"] == session.get("session_id") if "session_id" in session else "id" not in db_session,
                "browser": ua_data.get_browser(),
                "os": ua_data.get_os(),
                "device": ua_data.get_device(),
                "ip": db_session["ip"],
                "creation_date": db_session["creation_date"].astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
                "last_activity": (
                    db_session["last_activity"].astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
                    if "id" in db_session
                    else datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
                ),
            }

    return session_generator(page, per_page), total_sessions


# Display user profile page with TOTP setup and session management interface.
# Renders profile template with QR code generation and recent session data.
@profile.route("/profile", methods=["GET"])
@login_required
def profile_page():
    if DEBUG_MODE:
        logger.debug(f"profile_page() called for user: {current_user.username}")
    
    totp_qr_image = ""
    if not bool(current_user.totp_secret):
        session["tmp_totp_secret"] = TOTP.generate_totp_secret()
        totp_qr_image = TOTP.generate_qrcode(current_user.get_id(), session["tmp_totp_secret"])
        if DEBUG_MODE:
            logger.debug("Generated new TOTP secret and QR code for user")
    elif DEBUG_MODE:
        logger.debug("User already has TOTP enabled")

    last_sessions, total_sessions = get_last_sessions(1, 3)
    if DEBUG_MODE:
        logger.debug(f"Retrieved session data - total: {total_sessions}")

    if DEBUG_MODE:
        logger.debug("Rendering profile.html template")

    return render_template(
        "profile.html",
        is_totp=bool(current_user.totp_secret),
        totp_qr_image=totp_qr_image,
        totp_recovery_codes=session.pop("decrypted_recovery_codes", current_user.list_recovery_codes),
        is_recovery_refreshed=session.pop("totp_refreshed", False),
        totp_secret=TOTP.get_totp_pretty_key(session.get("tmp_totp_secret", "")),
        last_sessions=last_sessions,
        total_sessions=total_sessions,
    )


# Return paginated session data as streaming JSON response for AJAX requests.
# Provides session information with browser/device details for profile sessions tab.
@profile.route("/profile/sessions", methods=["GET"])
@login_required
@cors_required
def get_sessions():
    page = request.args.get("page", 1, type=int)
    if DEBUG_MODE:
        logger.debug(f"get_sessions() called with page={page}")

    if page < 1:
        if DEBUG_MODE:
            logger.debug(f"Invalid page number: {page}")
        return Response("Invalid page number", status=400)

    session_generator = get_last_sessions(page, 3)[0]
    if DEBUG_MODE:
        logger.debug("Starting session data streaming")

    # Generate streaming JSON response for session data to handle large datasets.
    # Yields JSON array with session objects to avoid memory issues with many sessions.
    def generate_stream():
        if DEBUG_MODE:
            logger.debug("generate_stream() starting")
        
        yield "["
        first = True
        session_count = 0
        
        for session_data in session_generator:
            if not first:
                yield ","
            first = False
            session_count += 1
            yield jsonify(session_data).get_data(as_text=True)
        
        yield "]"
        
        if DEBUG_MODE:
            logger.debug(f"generate_stream() completed - streamed {session_count} sessions")

    return Response(stream_with_context(generate_stream()), content_type="application/json")


# Refresh TOTP recovery codes after password verification for security.
# Generates new recovery codes and invalidates old ones in database.
@profile.route("/profile/totp-refresh", methods=["POST"])
@login_required
def totp_refresh():
    if DEBUG_MODE:
        logger.debug(f"totp_refresh() called for user: {current_user.username}")
    
    if DB.readonly:
        if DEBUG_MODE:
            logger.debug("Database is in read-only mode")
        return handle_error("Database is in read-only mode", "profile")

    if not bool(current_user.totp_secret):
        if DEBUG_MODE:
            logger.debug("TOTP not enabled for user")
        return handle_error("Two-factor authentication is not enabled.", "profile")

    verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/totp-refresh.", redirect_url="profile")

    if not current_user.check_password(request.form["password"]):
        if DEBUG_MODE:
            logger.debug("Password verification failed")
        return handle_error("The current password is incorrect.", "profile")

    if DEBUG_MODE:
        logger.debug("Generating new TOTP recovery codes")
    
    totp_recovery_codes = TOTP.generate_recovery_codes()

    ret = DB.refresh_ui_user_recovery_codes(current_user.get_id(), totp_recovery_codes)
    if ret:
        logger.exception("Failed to refresh recovery codes in database")
        return handle_error(f"Couldn't refresh the recovery codes in the database: {ret}", "profile")

    session["totp_refreshed"] = True
    session["decrypted_recovery_codes"] = totp_recovery_codes
    
    if DEBUG_MODE:
        logger.debug("TOTP recovery codes refreshed successfully")

    flash("The recovery codes have been successfully refreshed. The old ones are no longer valid.")
    return redirect(url_for("profile.profile_page") + "#security")


# Disable TOTP authentication after password and token verification.
# Removes TOTP secret from user account and clears session validation.
@profile.route("/profile/totp-disable", methods=["POST"])
@login_required
def totp_disable():
    if DEBUG_MODE:
        logger.debug(f"totp_disable() called for user: {current_user.username}")
    
    if DB.readonly:
        if DEBUG_MODE:
            logger.debug("Database is in read-only mode")
        return handle_error("Database is in read-only mode", "profile")

    if not bool(current_user.totp_secret):
        if DEBUG_MODE:
            logger.debug("TOTP not enabled for user")
        return handle_error("Two-factor authentication is not enabled.", "profile")

    verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/totp-disable.", redirect_url="profile")

    if not current_user.check_password(request.form["password"]):
        if DEBUG_MODE:
            logger.debug("Password verification failed")
        return handle_error("The current password is incorrect.", "profile")

    verify_data_in_form(data={"totp_token": None}, err_message="Missing totp token parameter on /profile/totp-enable.", redirect_url="profile")

    if not TOTP.verify_totp(request.form["totp_token"], totp_secret=session.get("tmp_totp_secret", ""), user=current_user) and not TOTP.verify_recovery_code(
        request.form["totp_token"], user=current_user
    ):
        if DEBUG_MODE:
            logger.debug("TOTP token verification failed")
        return handle_error("The totp token is invalid.", "profile")

    if DEBUG_MODE:
        logger.debug("Disabling TOTP in database")

    ret = DB.update_ui_user(
        current_user.get_id(), current_user.password.encode("utf-8"), None, theme=current_user.theme, method=current_user.method, language=current_user.language
    )
    if ret:
        logger.exception("Failed to disable TOTP in database")
        return handle_error(f"Couldn't disable the two-factor authentication in the database: {ret}", "profile")

    session["totp_validated"] = False
    
    if DEBUG_MODE:
        logger.debug("TOTP disabled successfully")

    flash("The two-factor authentication has been successfully disabled.")
    return redirect(url_for("profile.profile_page") + "#security")


# Enable TOTP authentication with secret verification and recovery code generation.
# Validates temporary TOTP secret and stores permanent configuration in database.
@profile.route("/profile/totp-enable", methods=["POST"])
@login_required
def totp_enable():
    if DEBUG_MODE:
        logger.debug(f"totp_enable() called for user: {current_user.username}")
    
    if DB.readonly:
        if DEBUG_MODE:
            logger.debug("Database is in read-only mode")
        return handle_error("Database is in read-only mode", "profile")

    if bool(current_user.totp_secret):
        if DEBUG_MODE:
            logger.debug("TOTP already enabled for user")
        return handle_error("Two-factor authentication is already enabled.", "profile")

    verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/totp-enable.", redirect_url="profile")
    verify_data_in_form(data={"totp_token": None}, err_message="Missing totp token parameter on /profile/totp-enable.", redirect_url="profile")

    if not current_user.check_password(request.form["password"]):
        if DEBUG_MODE:
            logger.debug("Password verification failed")
        return handle_error("The current password is incorrect.", "profile")

    if not TOTP.verify_totp(request.form["totp_token"], totp_secret=session.get("tmp_totp_secret", ""), user=current_user) and not TOTP.verify_recovery_code(
        request.form["totp_token"], user=current_user
    ):
        if DEBUG_MODE:
            logger.debug("TOTP token verification failed")
        return handle_error("The totp token is invalid.", "profile")

    if DEBUG_MODE:
        logger.debug("Enabling TOTP and generating recovery codes")

    totp_recovery_codes = TOTP.generate_recovery_codes()
    totp_secret = session.pop("tmp_totp_secret", "")

    ret = DB.update_ui_user(
        current_user.get_id(),
        current_user.password.encode("utf-8"),
        totp_secret,
        theme=current_user.theme,
        totp_recovery_codes=totp_recovery_codes,
        method=current_user.method,
        language=current_user.language,
    )
    if ret:
        logger.exception("Failed to enable TOTP in database")
        return handle_error(f"Couldn't enable the two-factor authentication in the database: {ret}", "profile")

    session["totp_validated"] = True
    session["totp_refreshed"] = True
    session["decrypted_recovery_codes"] = totp_recovery_codes
    
    if DEBUG_MODE:
        logger.debug("TOTP enabled successfully")

    flash("The two-factor authentication has been successfully enabled.")
    return redirect(url_for("profile.profile_page") + "#security")


# Update user profile information including username, email, password, and theme.
# Handles different update types with appropriate validation and database updates.
@profile.route("/profile/edit", methods=["POST"])
@login_required
def edit_profile():
    if DEBUG_MODE:
        logger.debug(f"edit_profile() called for user: {current_user.username}")
        logger.debug(f"Form data keys: {list(request.form.keys())}")
    
    if DB.readonly:
        if DEBUG_MODE:
            logger.debug("Database is in read-only mode")
        return handle_error("Database is in read-only mode", "profile")

    user_data = {
        "username": current_user.get_id(),
        "password": current_user.password.encode("utf-8"),
        "email": current_user.email,
        "totp_secret": current_user.totp_secret,
        "method": current_user.method,
        "theme": current_user.theme,
        "language": current_user.language,
    }

    if "username" in request.form:
        if DEBUG_MODE:
            logger.debug("Processing username/email update")
        
        verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/edit.", redirect_url="profile")

        if not current_user.check_password(request.form["password"]):
            if DEBUG_MODE:
                logger.debug("Password verification failed")
            return handle_error("The current password is incorrect.", "profile")

        verify_data_in_form(data={"email": None}, err_message="Missing email parameter on /profile/edit.", redirect_url="profile")

        if request.form["email"] and request.form["email"] != current_user.email:
            if len(request.form["email"]) > 256:
                if DEBUG_MODE:
                    logger.debug(f"Email too long: {len(request.form['email'])} characters")
                return handle_error("The email is too long. It must be less than 256 characters.", "profile")
            user_data["email"] = request.form["email"] or None
            if DEBUG_MODE:
                logger.debug(f"Email will be updated to: {request.form['email']}")

        if request.form["username"] and request.form["username"] != current_user.get_id():
            if len(request.form["username"]) > 256:
                if DEBUG_MODE:
                    logger.debug(f"Username too long: {len(request.form['username'])} characters")
                return handle_error("The username is too long. It must be less than 256 characters.", "profile")
            user_data["username"] = request.form["username"]
            if DEBUG_MODE:
                logger.debug(f"Username will be updated to: {request.form['username']}")

        if request.form["email"] == (current_user.email or "") and request.form["username"] == current_user.get_id():
            if DEBUG_MODE:
                logger.debug("No changes detected in username/email")
            return handle_error("The username and email are the same as the current ones.", "profile")
            
    elif "new_password" in request.form:
        if DEBUG_MODE:
            logger.debug("Processing password update")
        
        verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/edit.", redirect_url="profile")

        if not current_user.check_password(request.form["password"]):
            if DEBUG_MODE:
                logger.debug("Current password verification failed")
            return handle_error("The current password is incorrect.", "profile")

        verify_data_in_form(
            data={"new_password_confirm": None},
            err_message="Missing new password confirm parameter on /profile/edit.",
            redirect_url="profile",
        )

        if request.form["new_password"] != request.form["new_password_confirm"]:
            if DEBUG_MODE:
                logger.debug("New password confirmation mismatch")
            return handle_error("The passwords do not match the confirm password.", "profile")
        elif not USER_PASSWORD_RX.match(request.form["new_password"]):
            if DEBUG_MODE:
                logger.debug("New password does not meet complexity requirements")
            return handle_error(
                "The new password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-).",
                "profile",
            )
        elif current_user.check_password(request.form["new_password"]):
            if DEBUG_MODE:
                logger.debug("New password is same as current password")
            return handle_error("The new password is the same as the current one.", "profile")

        user_data["password"] = gen_password_hash(request.form["new_password"])
        if DEBUG_MODE:
            logger.debug("Password hash generated for update")
            
    elif "theme" in request.form:
        if DEBUG_MODE:
            logger.debug(f"Processing theme update to: {request.form['theme']}")
        
        if request.form["theme"] not in ("dark", "light"):
            if DEBUG_MODE:
                logger.debug(f"Invalid theme value: {request.form['theme']}")
            return handle_error("The theme is invalid.", "profile")

        user_data["theme"] = request.form["theme"]
    else:
        if DEBUG_MODE:
            logger.debug("No valid update fields found in form")
        return handle_error("No fields were updated.", "profile")

    if DEBUG_MODE:
        logger.debug(f"Updating user in database with data: {list(user_data.keys())}")

    ret = DB.update_ui_user(**user_data, old_username=current_user.get_id())
    if ret:
        logger.exception("Failed to update user in database")
        return handle_error(f"Couldn't update the {current_user.get_id()} user in the database: {ret}", "profile")

    if DEBUG_MODE:
        logger.debug("User profile updated successfully")

    flash("The profile has been successfully updated.")

    if "new_password" in request.form:
        if DEBUG_MODE:
            logger.debug("Password changed - redirecting to logout")
        return redirect(url_for("logout.logout_page"))

    return redirect(url_for("profile.profile_page"))


# Revoke all other user sessions except current one after password verification.
# Marks sessions as revoked and removes them from database for security.
@profile.route("/profile/wipe-other-sessions", methods=["POST"])
@login_required
def wipe_old_sessions():
    if DEBUG_MODE:
        logger.debug(f"wipe_old_sessions() called for user: {current_user.username}")
    
    if DB.readonly:
        if DEBUG_MODE:
            logger.debug("Database is in read-only mode")
        return handle_error("Database is in read-only mode", "profile")

    verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/wipe-other-sessions.", redirect_url="profile")

    if not current_user.check_password(request.form["password"]):
        if DEBUG_MODE:
            logger.debug("Password verification failed")
        return handle_error("The current password is incorrect.", "profile")

    DATA["REVOKED_SESSIONS"] = [
        db_session["id"] for db_session in DB.get_ui_user_sessions(current_user.username) if db_session["id"] != session.get("session_id")
    ]
    
    if DEBUG_MODE:
        logger.debug(f"Revoking {len(DATA['REVOKED_SESSIONS'])} other sessions")

    ret = DB.delete_ui_user_old_sessions(current_user.username)
    if ret:
        logger.exception("Failed to delete old sessions from database")
        return handle_error(f"Couldn't wipe the other sessions in the database: {ret}", "profile")

    if DEBUG_MODE:
        logger.debug("Other sessions wiped successfully")

    flash("The other sessions have been successfully wiped.")
    return redirect(url_for("profile.profile_page") + "#sessions")
