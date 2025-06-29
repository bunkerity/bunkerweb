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
    "9": False,   # Serial Number (hidden by default)
    "10": False,  # Fingerprint (hidden by default)
    "11": True,   # Key Type
}


def context_processor():
    # Flask context processor to inject variables into templates.
    #
    # Provides template context data for the Let's Encrypt certificate
    # management interface. Injects column preferences and other UI
    # configuration data that templates need for proper rendering.
    # 
    # Returns:
    #     dict: Dictionary containing template context variables including
    #           column preferences for DataTables and page visibility settings.
    #           Returns None for excluded paths that don't need context injection.
    logger = getLogger("UI")
    is_debug = getenv("LOG_LEVEL") == "debug"
    
    if is_debug:
        logger.debug("Context processor called")
        logger.debug(f"Request path: {request.path}")
        logger.debug(f"Request method: {request.method}")
        logger.debug(f"Request endpoint: {getattr(request, 'endpoint', 'unknown')}")
    
    # Skip context processing for system/auth pages that don't need it
    excluded_paths = [
        "/check", "/setup", "/loading", 
        "/login", "/totp", "/logout"
    ]
    
    # Check if current path should be excluded
    path_excluded = request.path.startswith(tuple(excluded_paths))
    
    if path_excluded:
        if is_debug:
            logger.debug(f"Path {request.path} is excluded from context processing")
            for excluded_path in excluded_paths:
                if request.path.startswith(excluded_path):
                    logger.debug(f"  Matched exclusion pattern: {excluded_path}")
                    break
        return None

    if is_debug:
        logger.debug(f"Processing context for path: {request.path}")
        logger.debug(f"Column preferences to inject:")
        for col_id, visible in COLUMNS_PREFERENCES_DEFAULTS.items():
            logger.debug(f"  Column {col_id}: {'visible' if visible else 'hidden'}")

    # Prepare context data for templates
    data = {
        "columns_preferences_defaults_letsencrypt": COLUMNS_PREFERENCES_DEFAULTS
    }

    if is_debug:
        logger.debug(f"Context processor returning {len(data)} variables")
        logger.debug(f"Context data keys: {list(data.keys())}")
        logger.debug(f"Let's Encrypt preferences: {len(COLUMNS_PREFERENCES_DEFAULTS)} columns configured")

    return data