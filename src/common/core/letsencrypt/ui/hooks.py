from flask import current_app, request

# Default column visibility settings for letsencrypt tables
COLUMNS_PREFERENCES_DEFAULTS = {
    "letsencrypt": {
        "3": True,
        "4": True,
        "5": True,
        "6": True,
        "7": True,
        "8": True,
        "9": False,
        "10": False,
        "11": True,
    },
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

    env_config = current_app.config["ENV"]

    if "columns_preferences_defaults" in env_config:
        data = {"columns_preferences_defaults": env_config["columns_preferences_defaults"] | COLUMNS_PREFERENCES_DEFAULTS}
    else:
        data = {"columns_preferences_defaults": COLUMNS_PREFERENCES_DEFAULTS}

    return data
