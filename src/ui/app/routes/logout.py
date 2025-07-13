from os import sep
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
    title="UI-logout",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-logout")

from flask import Blueprint, redirect, session, url_for
from flask_login import current_user, logout_user

from app.dependencies import DATA

logout = Blueprint("logout", __name__)


@logout.route("/logout")
def logout_page():
    logger.debug("logout_page() called")
    
    try:
        if current_user.is_authenticated:
            logger.debug(f"Logging out authenticated user: {current_user.username}")
            DATA.load_from_file()

            # Track the revoked session ID to prevent token reuse
            if "session_id" in session:
                session_id = session["session_id"]
                logger.debug(f"Revoking session ID {session_id} for user {current_user.username}")
                
                if "REVOKED_SESSIONS" not in DATA:
                    DATA["REVOKED_SESSIONS"] = []
                    logger.debug("Created new REVOKED_SESSIONS list")
                
                if session_id not in DATA["REVOKED_SESSIONS"]:
                    DATA["REVOKED_SESSIONS"].append(session_id)
                    logger.debug(f"Added session {session_id} to revoked sessions list")
                    # Save changes to the DATA file
                    DATA.write_to_file()
                    logger.debug("Saved revoked sessions to data file")
                else:
                    logger.debug(f"Session {session_id} already in revoked sessions list")
            else:
                logger.debug("No session_id found in current session")

            # Log the logout event
            logger.info(f"User {current_user.username} logged out successfully")
        else:
            logger.debug("Logout called for unauthenticated user")

        # Clear session and logout user
        logger.debug("Clearing session and logging out user")
        session.clear()
        logout_user()

        # Add security headers to prevent cached credentials
        logger.debug("Adding security headers and redirecting to login")
        response = redirect(url_for("login.login_page"))
        response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage", "executionContexts"'
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        logger.debug("Logout completed successfully")
        return response
        
    except BaseException as e:
        logger.exception(f"Error during logout process")
        logger.error(f"Error during logout: {e}")
        logger.debug("Performing emergency session cleanup")
        session.clear()
        logout_user()
        return redirect(url_for("login.login_page"))
    