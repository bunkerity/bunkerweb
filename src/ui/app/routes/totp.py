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
    logger.debug("Debug mode enabled for totp module")

from flask import Blueprint, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.dependencies import DB
from app.models.totp import totp as TOTP
from app.routes.utils import flash, handle_error, verify_data_in_form

totp = Blueprint("totp", __name__)


# Handle TOTP authentication for two-factor authentication.
# Validates TOTP tokens or recovery codes and manages session state
# for authenticated users with 2FA enabled.
@totp.route("/totp", methods=["GET", "POST"])
@login_required
def totp_page():
    if DEBUG_MODE:
        logger.debug(f"totp_page() called with method: {request.method}")
        logger.debug(f"Current user ID: {current_user.get_id()}")
        logger.debug(f"User has TOTP secret: {bool(current_user.totp_secret)}")
        logger.debug(f"TOTP validated in session: {session.get('totp_validated', False)}")
    
    if request.method == "POST":
        if DEBUG_MODE:
            logger.debug("Processing TOTP POST request")
            logger.debug(f"Form keys present: {list(request.form.keys())}")
        
        verify_data_in_form(data={"totp_token": None}, err_message="No token provided on /totp.", redirect_url="totp")

        totp_token = request.form["totp_token"]
        if DEBUG_MODE:
            logger.debug(f"TOTP token received (length: {len(totp_token) if totp_token else 0})")

        if not TOTP.verify_totp(totp_token, user=current_user):
            if DEBUG_MODE:
                logger.debug("TOTP token verification failed, checking recovery codes")
            
            recovery_code = TOTP.verify_recovery_code(totp_token, user=current_user)
            if not recovery_code:
                if DEBUG_MODE:
                    logger.debug("Recovery code verification also failed")
                return handle_error("The token is invalid.", "totp")
            
            if DEBUG_MODE:
                logger.debug("Recovery code verified successfully")
                logger.debug(f"User has {len(current_user.list_recovery_codes)} recovery codes remaining")
            
            flash(f"You've used one of your recovery codes. You have {len(current_user.list_recovery_codes)} left.")
            
            try:
                DB.use_ui_user_recovery_code(current_user.get_id(), recovery_code)
                if DEBUG_MODE:
                    logger.debug("Recovery code marked as used in database")
            except Exception as e:
                if DEBUG_MODE:
                    logger.debug(f"Failed to mark recovery code as used: {e}")
        else:
            if DEBUG_MODE:
                logger.debug("TOTP token verified successfully")

        session["totp_validated"] = True
        if DEBUG_MODE:
            logger.debug("TOTP validation set in session")
        
        next_url = request.form.get("next") or url_for("home.home_page")
        if DEBUG_MODE:
            logger.debug(f"Redirecting to loading page with next URL: {next_url}")
        
        return redirect(url_for("loading", next=next_url, message="Validating TOTP token."))

    # GET request handling
    if DEBUG_MODE:
        logger.debug("Processing TOTP GET request")
    
    has_totp_secret = bool(current_user.totp_secret)
    is_totp_validated = session.get("totp_validated", False)
    
    if DEBUG_MODE:
        logger.debug(f"User TOTP status - has_secret: {has_totp_secret}, validated: {is_totp_validated}")

    if not has_totp_secret or is_totp_validated:
        if DEBUG_MODE:
            if not has_totp_secret:
                logger.debug("User has no TOTP secret configured, redirecting to home")
            else:
                logger.debug("TOTP already validated in session, redirecting to home")
        
        return redirect(url_for("home.home_page"))

    if DEBUG_MODE:
        logger.debug("Rendering TOTP authentication page")

    return render_template("totp.html")
