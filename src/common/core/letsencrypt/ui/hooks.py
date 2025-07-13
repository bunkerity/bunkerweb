from flask import request

# Default column visibility settings for letsencrypt tables
COLUMNS_PREFERENCES_DEFAULTS = {
    "3": True,
    "4": True,
    "5": True,
    "6": True,
    "7": True,
    "8": True,
    "9": False,
    "10": False,
    "11": True,
}


def context_processor():
    """
    Flask context processor to inject variables into templates.

    This adds:
    - Column preference defaults for tables
    - Extra pages visibility based on user permissions
    """
    if request.path.startswith(("/check", "/setup", "/loading", "/login", "/totp", "/logout")):
        return None

    data = {"columns_preferences_defaults_letsencrypt": COLUMNS_PREFERENCES_DEFAULTS}

    return data
