from logging import getLogger
from os import getenv
from flask import request

# Default column visibility settings for Let's Encrypt certificate tables
# Key represents column index, value indicates if column is visible by default
COLUMNS_PREFERENCES_DEFAULTS = {
    "3": True,    # Common Name
    "4": True,    # Issuer  
    "5": True,    # Valid From
    "6": True,    # Valid To
    "7": True,    # Preferred Profile
    "8": True,    # Challenge
    "9": True,    # Key Type
    "10": True,   # OCSP Support
    "11": False,  # Serial Number (hidden by default)
    "12": False,  # Fingerprint (hidden by default)
    "13": True,   # Version
}


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


def context_processor():
    # Flask context processor to inject variables into templates.
    #
    # Provides template context data for the Let's Encrypt certificate
    # management interface. Injects column preferences and other UI
    # configuration data that templates need for proper rendering.
    logger = getLogger("UI")
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    debug_log(logger, "Context processor called")
    debug_log(logger, f"Request path: {request.path}")
    debug_log(logger, f"Request method: {request.method}")
    debug_log(logger, 
        f"Request endpoint: {getattr(request, 'endpoint', 'unknown')}")
    
    # Skip context processing for system/auth pages that don't need it
    excluded_paths = [
        "/check", "/setup", "/loading", 
        "/login", "/totp", "/logout"
    ]
    
    # Check if current path should be excluded
    path_excluded = request.path.startswith(tuple(excluded_paths))
    
    if path_excluded:
        debug_log(logger, 
            f"Path {request.path} is excluded from context processing")
        for excluded_path in excluded_paths:
            if request.path.startswith(excluded_path):
                debug_log(logger, 
                    f"  Matched exclusion pattern: {excluded_path}")
                break
        return None

    debug_log(logger, f"Processing context for path: {request.path}")
    debug_log(logger, "Column preferences to inject:")
    column_names = {
        "3": "Common Name", "4": "Issuer", "5": "Valid From", 
        "6": "Valid To", "7": "Preferred Profile", "8": "Challenge",
        "9": "Key Type", "10": "OCSP Support", "11": "Serial Number",
        "12": "Fingerprint", "13": "Version"
    }
    for col_id, visible in COLUMNS_PREFERENCES_DEFAULTS.items():
        col_name = column_names.get(col_id, f"Column {col_id}")
        debug_log(logger, 
            f"  {col_name} (#{col_id}): {'visible' if visible else 'hidden'}")

    # Prepare context data for templates
    data = {
        "columns_preferences_defaults_letsencrypt": COLUMNS_PREFERENCES_DEFAULTS
    }

    debug_log(logger, f"Context processor returning {len(data)} variables")
    debug_log(logger, f"Context data keys: {list(data.keys())}")
    debug_log(logger, 
        f"Let's Encrypt preferences: {len(COLUMNS_PREFERENCES_DEFAULTS)} "
        f"columns configured")

    return data