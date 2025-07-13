from flask import request
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

# Initialize bw_logger module for Let's Encrypt UI hooks
logger = setup_logger(
    title="letsencrypt-ui-hooks",
    log_file_path="/var/log/bunkerweb/letsencrypt.log"
)

logger.debug("Debug mode enabled for letsencrypt-ui-hooks")

# Default column visibility settings for Let's Encrypt certificate tables.
# Controls which certificate information columns are shown by default in UI.
COLUMNS_PREFERENCES_DEFAULTS = {
    "3": True,   # Domain column
    "4": True,   # Common Name column
    "5": True,   # Issuer column
    "6": True,   # Valid From column
    "7": True,   # Valid To column
    "8": True,   # Serial Number column
    "9": False,  # Fingerprint column (hidden by default)
    "10": False, # Version column (hidden by default)
    "11": True,  # Challenge column
}

logger.debug(f"Column preferences initialized with {len(COLUMNS_PREFERENCES_DEFAULTS)} columns")

# Flask context processor to inject Let's Encrypt UI variables into templates.
# Provides column preferences and other UI configuration data.
def context_processor():
    logger.debug(f"Processing context for request path: {request.path}")
    
    # Skip context processing for authentication and system pages
    excluded_paths = ("/check", "/setup", "/loading", "/login", "/totp", "/logout")
    if request.path.startswith(excluded_paths):
        logger.debug("Skipping context processing for excluded path")
        return None

    # Prepare Let's Encrypt UI context data
    data = {
        "columns_preferences_defaults_letsencrypt": COLUMNS_PREFERENCES_DEFAULTS
    }
    
    logger.debug("Context processor completed - returning Let's Encrypt column preferences")
    return data

logger.debug("Let's Encrypt UI hooks module initialized successfully")
