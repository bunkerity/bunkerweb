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
    logger.debug("Debug mode enabled for logout module")

from flask import Blueprint, redirect, session, url_for
from flask_login import current_user, logout_user

from app.dependencies import DATA
from app.utils import LOGGER

logout = Blueprint("logout", __name__)


# Handle comprehensive user logout with session security and token management.
# Processes authenticated user logout, revokes session tokens, applies security headers,
# and ensures complete session cleanup to prevent credential reuse or session hijacking.
@logout.route("/logout")
def logout_page():
    if DEBUG_MODE:
        logger.debug("logout_page() called - initiating secure logout process")
        logger.debug(f"Current session keys: {list(session.keys()) if session else 'No session'}")
        logger.debug(f"User authentication status: {current_user.is_authenticated}")
        if current_user.is_authenticated:
            logger.debug(f"Current user ID: {current_user.get_id()}, Username: {current_user.username}")
    
    try:
        if current_user.is_authenticated:
            if DEBUG_MODE:
                logger.debug(f"Processing authenticated logout for user: {current_user.username}")
                logger.debug(f"User has TOTP enabled: {bool(getattr(current_user, 'totp_secret', None))}")
                logger.debug(f"Session contains session_id: {'session_id' in session}")
            
            DATA.load_from_file()
            if DEBUG_MODE:
                logger.debug("Successfully loaded DATA from file for session management")
                logger.debug(f"Current REVOKED_SESSIONS count: {len(DATA.get('REVOKED_SESSIONS', []))}")

            # Track the revoked session ID to prevent token reuse
            if "session_id" in session:
                session_id = session["session_id"]
                if DEBUG_MODE:
                    logger.debug(f"Found session ID to revoke: {session_id}")
                    logger.debug(f"Session ID type: {type(session_id)}, length: {len(str(session_id))}")
                
                LOGGER.info(f"Revoking session ID {session_id} for user {current_user.username}")
                
                if "REVOKED_SESSIONS" not in DATA:
                    DATA["REVOKED_SESSIONS"] = []
                    if DEBUG_MODE:
                        logger.debug("Created new REVOKED_SESSIONS list in DATA structure")
                elif DEBUG_MODE:
                    logger.debug(f"REVOKED_SESSIONS already exists with {len(DATA['REVOKED_SESSIONS'])} entries")
                
                if session_id not in DATA["REVOKED_SESSIONS"]:
                    DATA["REVOKED_SESSIONS"].append(session_id)
                    if DEBUG_MODE:
                        logger.debug(f"Added session {session_id} to revocation list")
                        logger.debug(f"REVOKED_SESSIONS now contains {len(DATA['REVOKED_SESSIONS'])} entries")
                    
                    # Save changes to the DATA file
                    try:
                        DATA.write_to_file()
                        if DEBUG_MODE:
                            logger.debug("Successfully persisted REVOKED_SESSIONS to DATA file")
                    except Exception as e:
                        logger.exception("Failed to save REVOKED_SESSIONS to file")
                        if DEBUG_MODE:
                            logger.debug(f"File write error: {e}")
                elif DEBUG_MODE:
                    logger.debug(f"Session {session_id} already exists in revoked sessions list")
            elif DEBUG_MODE:
                logger.debug("No session_id found in current session - cannot revoke specific session")
                logger.debug(f"Available session keys: {list(session.keys())}")

            # Log the logout event
            LOGGER.info(f"User {current_user.username} logged out")
            if DEBUG_MODE:
                logger.debug(f"Logout event officially logged for user: {current_user.username}")
                logger.debug("Proceeding to session cleanup and user logout")
        elif DEBUG_MODE:
            logger.debug("User not authenticated - proceeding with anonymous session cleanup")
            logger.debug(f"Anonymous session keys to clear: {list(session.keys()) if session else 'Empty session'}")

        # Clear session and logout user
        if DEBUG_MODE:
            session_keys_before = list(session.keys()) if session else []
            logger.debug(f"Clearing session data - keys before: {session_keys_before}")
        
        session.clear()
        logout_user()
        
        if DEBUG_MODE:
            logger.debug("Session cleared and user logged out successfully")
            logger.debug("Flask-Login user state reset to anonymous")

        # Add security headers to prevent cached credentials
        if DEBUG_MODE:
            logger.debug("Creating secure redirect response with comprehensive security headers")
            logger.debug("Applying Clear-Site-Data header to remove browser cached data")
        
        response = redirect(url_for("login.login_page"))
        response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage", "executionContexts"'
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        if DEBUG_MODE:
            logger.debug("Security headers applied successfully:")
            logger.debug("  - Clear-Site-Data: Removes cache, cookies, storage, execution contexts")
            logger.debug("  - Cache-Control: Prevents response caching")
            logger.debug("  - Pragma: Legacy cache prevention")
            logger.debug("  - Expires: Immediate expiration")
            logger.debug("Logout process completed successfully - redirecting to login page")
        
        return response
    except BaseException as e:
        logger.exception("Critical error occurred during logout process")
        LOGGER.error(f"Error during logout: {e}")
        
        if DEBUG_MODE:
            logger.debug(f"Exception type: {type(e).__name__}")
            logger.debug(f"Exception details: {str(e)}")
            logger.debug("Performing emergency session cleanup to ensure security")
            logger.debug(f"Current user state before cleanup: authenticated={current_user.is_authenticated}")
        
        session.clear()
        logout_user()
        
        if DEBUG_MODE:
            logger.debug("Emergency session cleanup completed successfully")
            logger.debug("User state reset to anonymous despite error")
            logger.debug("Redirecting to login page for security")
        
        return redirect(url_for("login.login_page"))
