from datetime import datetime
from os.path import join, sep
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
    title="UI-models",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-models")

from bcrypt import checkpw
from flask_login import AnonymousUserMixin, UserMixin

from model import Users  # type: ignore


class AnonymousUser(AnonymousUserMixin):
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

    # Return the unique identifier for anonymous user sessions.
    # Uses username as the identifier for Flask-Login compatibility.
    def get_id(self):
        logger.debug("AnonymousUser.get_id() called")
        return self.username

    # Always deny password authentication for anonymous users.
    # Provides security by ensuring anonymous users cannot authenticate.
    def check_password(self, password: str) -> bool:
        logger.debug("AnonymousUser.check_password() called - always returns False")
        return False


class UiUsers(Users, UserMixin):
    # Return the unique identifier for authenticated user sessions.
    # Uses username as the primary identifier for Flask-Login.
    def get_id(self):
        logger.debug(f"UiUsers.get_id() called for username={getattr(self, 'username', 'unknown')}")
        return self.username

    # Verify user password using bcrypt hashing comparison.
    # Securely validates provided password against stored hash.
    def check_password(self, password: str) -> bool:
        username = getattr(self, 'username', 'unknown')
        logger.debug(f"UiUsers.check_password() called for username={username}")
        try:
            result = checkpw(password.encode("utf-8"), self.password.encode("utf-8"))
            logger.debug(f"Password check result for {username}: {'success' if result else 'failed'}")
            return result
        except Exception as e:
            logger.exception(f"Exception during password check for user {username}")
            return False
