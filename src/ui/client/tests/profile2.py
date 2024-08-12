import json
import base64

from builder.utils.widgets import button, button_group, title, text, tabulator, fields, upload, input, combobox, checkbox, select, editor

# Define data to put in profile widgets
profile_widgets = []

# Define data to put in profile form widgets
# - update password
# - update email
# - update username
user_widgets = []

# Define data to put in totp widgets
# - enable totp: what we need ?
# - disable totp: what we need ?
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
            user_widgets,
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
