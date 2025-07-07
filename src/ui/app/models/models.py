from datetime import datetime
from os import getenv, sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

from bcrypt import checkpw
from flask_login import AnonymousUserMixin, UserMixin

from model import Users  # type: ignore

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for models module")


class AnonymousUser(AnonymousUserMixin):
    # Anonymous user class for unauthenticated sessions with default safe values.
    # Provides secure defaults and prevents access to protected functionality without authentication.
    username = "Anonymous"
    email = None
    password = ""
    method = "manual"
    admin = False
    theme = "light"
    language = "en"
    totp_secret = None
    creation_date = datetime.now().astimezone()
    update_date = datetime.now().astimezone()
    list_roles = []
    list_permissions = []
    list_recovery_codes = []

    # Get unique identifier for anonymous user sessions.
    # Returns username for session tracking and logging purposes without exposing sensitive data.
    def get_id(self):
        if DEBUG_MODE:
            logger.debug("AnonymousUser.get_id() called - returning 'Anonymous'")
        return self.username

    # Check password for anonymous user (always fails for security).
    # Prevents authentication bypass and ensures anonymous users cannot authenticate with any password.
    def check_password(self, password: str) -> bool:
        if DEBUG_MODE:
            logger.debug("AnonymousUser.check_password() called - always returns False for security")
        return False


class UiUsers(Users, UserMixin):
    # UI user class extending base Users model with Flask-Login integration.
    # Provides authentication methods and user session management for the web interface.
    
    # Get unique identifier for authenticated user sessions.
    # Returns username for session tracking and user identification in logs and database operations.
    def get_id(self):
        if DEBUG_MODE:
            logger.debug(f"UiUsers.get_id() called for user: {getattr(self, 'username', 'Unknown')}")
        return self.username

    # Check password against stored bcrypt hash for user authentication.
    # Validates user credentials securely using bcrypt comparison to prevent timing attacks.
    def check_password(self, password: str) -> bool:
        username = getattr(self, 'username', 'Unknown')
        if DEBUG_MODE:
            logger.debug(f"UiUsers.check_password() called for user: {username}")
        
        try:
            # Perform bcrypt password verification
            result = checkpw(password.encode("utf-8"), self.password.encode("utf-8"))
            
            if DEBUG_MODE:
                logger.debug(f"Password verification for user {username}: {'SUCCESS' if result else 'FAILED'}")
            
            # Log authentication attempts for security monitoring
            if result:
                logger.info(f"Successful password verification for user: {username}")
            else:
                logger.warning(f"Failed password verification for user: {username}")
            
            return result
        except Exception as e:
            logger.exception(f"Exception during password verification for user: {username}")
            # Return False on any exception for security
            return False
