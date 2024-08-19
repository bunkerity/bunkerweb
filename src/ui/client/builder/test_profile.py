from utils import save_builder

from pages.profile import profile_builder

# Define data to put in profile widgets
# - username
# - email
# - created_method
# - is_superadmin
# - role
# - role_description
# - permissions (liste of permissions [])
# - creation_date
# - last_update (last time update user info)
user = {
    "profile": [
        {"key": "profile_username", "value": "username"},
        {"key": "profile_email", "value": "email"},
        {"key": "profile_created_method", "value": "created_method"},
        {"key": "profile_role", "value": "admin"},
        {"key": "profile_permissions", "value": "read, write, admin"},
        {"key": "profile_creation_date", "value": "date"},
        {"key": "profile_last_update", "value": "date"},
    ],
    "totp": {
        "is_totp": False,
        "totp_image": "",  # base 64 that will be add in an img tag src
        "totp_recovery_codes": [{"key": "0", "value": "code_0"}, {"key": "1", "value": "code_1"}, {"key": "2", "value": "code_2"}],
        "is_recovery_refreshed": False,
        "totp_secret": "totp_secret",
    },
}


builder = profile_builder(user=user)

save_builder(page_name="profile", output=builder, script_name="profile")
