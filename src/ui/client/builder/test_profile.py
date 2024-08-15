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
        {
            "profile_username": "username",
            "profile_email": "email",
            "profile_created_method": "created_method",
            "role": "admin",
            "role_description": "role_description",
            "permissions": "read, write, admin",
            "creation_date": "date",
            "last_update": "date",
        }
    ],
    "totp": {
        "is_totp": False,
        "totp_image": "",  # base 64 that will be add in an img tag src
        "totp_recovery_codes": [{"0": "code_0"}, {"1": "code_1"}, {"2": "code_2"}],
        "is_recovery_refreshed": False,
        "totp_secret": "totp_secret",
    },
}


builder = profile_builder(user=user)

save_builder(page_name="profile", output=builder, script_name="profile")
