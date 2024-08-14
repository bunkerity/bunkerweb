from utils import save_builder
from pages.user_management import user_management_builder


users = [
    {
        "username": "username1",
        "email": "email1",
        "role": "superadmin",
        "totp_state": "enable",
        "last_login": 1723641467658,  # timestamp
        "creation_date": 1723641467658,  # timestamp
        "last_update": 1723641467658,  # timestamp
    },
    {
        "username": "username2",
        "email": "",
        "role": "writer",
        "totp_state": "disable",
        "last_login": 1723641467658,  # timestamp
        "creation_date": 1723641467658,  # timestamp
        "last_update": 1723641467658,  # timestamp
    },
    {
        "username": "username3",
        "email": "fesfesf",
        "role": "reader",
        "totp_state": "disable",
        "last_login": 1723641467658,  # timestamp
        "creation_date": 1723641467658,  # timestamp
        "last_update": 1723641467658,  # timestamp
    },
    {
        "username": "username4",
        "email": "fesfesfgrd",
        "role": "reader",
        "totp_state": "enable",
        "last_login": 1723641467658,  # timestamp
        "creation_date": 1723641467658,  # timestamp
        "last_update": 1723641467658,  # timestamp
    },
]

roles = ["superadmin", "admin", "writer", "reader"]  # add superadmin-like role, this list will be use to filter the roles from list
roles_form = ["admin", "writer", "reader", "all"]  # here send only available roles, superadmin is not available for example
totp_state = ["enable", "disable"]

builder = user_management_builder(users=users, roles=roles, totp_states=totp_state, roles_form=roles_form)

save_builder(page_name="usermanagement", output=builder, script_name="usermanagement")
