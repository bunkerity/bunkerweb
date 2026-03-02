from flask import request

# Default column visibility for the Let's Encrypt certificates DataTable.
# Keys are DataTable column indices (as strings). Columns 0-2 are always visible
# (checkbox, domain, status). Columns 3+ are togglable. Update this dict whenever
# columns are added or reordered in main.js / letsencrypt.py DATATABLE_COLUMNS.
#
# Column index → field name:
#   3  valid_from        (visible)
#   4  valid_to          (visible)
#   5  issuer            (visible)
#   6  challenge         (visible)
#   7  authenticator     (visible)
#   8  preferred_profile (visible)
#   9  key_type          (visible)
#   10 key_size          (visible — new column showing bit length e.g. 256/384/4096)
#   11 serial_number     (hidden — too long for default view)
#   12 fingerprint       (hidden — too long for default view)
#   13 version           (visible)
COLUMNS_PREFERENCES_DEFAULTS = {
    "3": True,
    "4": True,
    "5": True,
    "6": True,
    "7": True,
    "8": True,
    "9": True,
    "10": True,
    "11": False,
    "12": False,
    "13": True,
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
