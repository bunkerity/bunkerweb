import json
import base64

# TODO : REMOVE operation by custom endpoint

from builder.utils.widgets import button, button_group, title, text, tabulator, fields, upload, input, combobox, checkbox, select, editor

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
profile_widgets = []

# Define data to put in profile form widgets
# - update password
# - update email
account_widgets = []

# Define data to put in totp widgets
# if want to enable totp (currently disabled):
# text with state
# show QRcode SVG
# - form (endpoint /totp-enable) : totp secret (type password), totp code, password
# Case currently enabled :
# text with state
# after first totp setup, show recovery codes
# form refresh recovery codes button that will redisplay recovery (endpoint /totp-refresh) : password (warning that will remove previous)
# form disabled (endpoint /totp-disable) : totp code || recovery code, password
totp_widgets = []

builder = [
    {
        "type": "card",
        "display": ["main", 1],
        "widgets": [
            profile_widgets,
        ],
    },
    {
        "type": "card",
        "display": ["main", 2],
        "widgets": [
            account_widgets,
        ],
    },
    {
        "type": "card",
        "display": ["main", 3],
        "widgets": [
            totp_widgets,
        ],
    },
]


with open("profile2.json", "w") as f:
    f.write(json.dumps(builder))

output_base64_bytes = base64.b64encode(bytes(json.dumps(builder), "utf-8"))

output_base64_string = output_base64_bytes.decode("ascii")


with open("profile2.txt", "w") as f:
    f.write(output_base64_string)
