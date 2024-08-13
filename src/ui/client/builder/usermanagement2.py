import json
import base64

from builder.utils.widgets import button, button_group, title, text, tabulator, fields, upload, input, combobox, checkbox, select, editor, datepicker


# TODO : REMOVE operation by custom endpoint
def generate_form(
    username: str = "",
    password: str = "",
    email: str = "",
    is_new: bool = True,
    role: str = "",
    roles: list = [],
    display_index: int = 1,
):

    return (
        {
            "type": "card",
            "display": ["main", display_index],  # Allow to toggle between each form using displayStore
            "widgets": [
                input(
                    id=f"username-{'new' if is_new else username}",
                    name="username",
                    label="users_filename",  # keep it (a18n)
                    value="" if is_new else username,
                    pattern="",  # add your pattern if needed
                    columns={"pc": 3, "tablet": 4, "mobile": 12},
                ),
                input(
                    id=f"password-{'new' if is_new else username}",
                    name="password",
                    label="users_password",  # keep it (a18n)
                    value="" if is_new else password,
                    pattern="",  # add your pattern if needed
                    columns={"pc": 3, "tablet": 4, "mobile": 12},
                ),
                # Select between available types
                select(
                    {
                        "id": "select-role",
                        "name": "select-role",
                        "label": "users_role",  # keep it (a18n)
                        "value": role,  # current role
                        "values": roles,
                        "inpType": "select",
                        "onlyDown": True,
                        "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    },
                ),
                input(
                    id="operation",
                    name="operation",
                    label="users_operation",  # keep it (a18n)
                    value="new" if is_new else "edit",  # "new" if new or "edit" if edit
                    pattern="",  # add your pattern if needed
                    columns={"pc": 3, "tablet": 4, "mobile": 12},
                    inputClass="hidden",  # hide it
                ),
                input(
                    id="old_username",
                    name="old_username",
                    label="users_old_username",  # keep it (a18n)
                    value=username,  # "new" if new or "edit" if edit
                    inputClass="hidden",  # hide it
                ),
                button(
                    id="update-user",
                    text="action_save",  # action_new if new or action_edit if edit
                    color="success",
                    size="normal",
                ),
            ],
        },
    )


# TODO
def get_forms():
    """We need to generate an empty form for the new conf that will be display index 1.
    We need to generate a form for each conf that will be display index > 1 and unique.
    """
    forms = []
    # Start adding new form with display index 1
    # Then we will loop on each conf to add a form with display index > 1 (use loop index)
    return forms


users_columns = [
    {"title": "Username", "field": "username", "formatter": "text"},
    {"title": "Role", "field": "role", "formatter": "text"},
    {"title": "Creation date", "field": "creation_date", "formatter": "fields"},  # datepicker
    {"title": "Last login", "field": "last_login", "formatter": "fields"},  # datepicker of last login
    {"title": "Last login IP", "field": "last_login_ip", "formatter": "fields"},  # datepicker of last login
    {"title": "Login count", "field": "login_count", "formatter": "fields"},  # datepicker of last login
    {"title": "totp (state)", "field": "totp", "formatter": "icons"},  # icon check or cross
    {
        "title": "actions",
        "field": "actions",
        "formatter": "buttonGroup",
    },  # edit button that will switch to the form using display store + delete with modal to confirm
]


users_filters = [
    {
        "type": "like",
        "fields": ["username"],
        "setting": {
            "id": "input-search-username",
            "username": "input-search-username",
            "label": "users_search_username",  # keep it (a18n)
            "value": "",
            "inpType": "input",
            "columns": {"pc": 3, "tablet": 4, "mobile": 12},
        },
    },
    {
        "type": "=",
        "fields": ["role"],
        "setting": {
            "id": "select-role",
            "name": "select-role",
            "label": "users_select_role",  # keep it (a18n)
            "value": "all",  # keep "all"
            "values": ["all", "antibot"],  # keep "all" and add your roles
            "inpType": "select",
            "onlyDown": True,
            "columns": {"pc": 3, "tablet": 4, "mobile": 12},
        },
    },
    {
        "type": "=",
        "fields": ["totp"],
        "setting": {
            "id": "select-totp",
            "name": "select-totp",
            "label": "users_select_totp",  # keep it (a18n)
            "value": "all",  # keep "all"
            "values": ["all", "yes", "no"],  # keep
            "inpType": "select",
            "onlyDown": True,
            "columns": {"pc": 3, "tablet": 4, "mobile": 12},
        },
    },
]


users_items = [
    {
        "username": text(text="Name")["data"],  # replace Name by real name
        "role": text(text="Role")["data"],  # replace Role by real role
        "creation_date": datepicker(
            id="datepicker-date-id",  # replace id by unique id
            name="datepicker-date-id",  # replace by unique id
            label="reports_date",  # keep it (a18n)
            hideLabel=True,
            inputType="datepicker",
            value="my_date",  # replace my_date by timestamp value
            disabled=True,  # Readonly
        )["data"],
        "services": button_group(
            buttons=[
                button(
                    id="services-btn-confname",  # replace confname by real conf name
                    type="button",
                    iconName="disk",
                    iconColor="white",
                    text="users_show_services",  # keep it (a18n)
                    color="orange",
                    size="normal",
                    modal={
                        "widgets": [
                            title(title="users_services_title"),  # keep it (a18n)
                            text(text="users_services_subtitle"),  # keep it (a18n)
                            tabulator(
                                id="table-services-confname",  # replace confname by real conf name
                                columns=[{"title": "id", "field": "id", "formatter": "text"}, {"title": "Name", "field": "name", "formatter": "text"}],
                                # Add every services that apply to the conf. All if global.
                                items=[
                                    {
                                        "id": text(text="service_id")["data"],
                                        "name": text(text="service_name")["data"],
                                    },  # replace service_id and service_name by real values
                                ],
                                filters=[
                                    {
                                        "type": "like",
                                        "fields": ["name"],
                                        "setting": {
                                            "id": "input-search-service",
                                            "name": "input-search-service",
                                            "label": "users_search_service",  # keep it (a18n)
                                            "value": "",
                                            "inpType": "input",
                                            "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                                        },
                                    },
                                ],
                            ),
                            button_group(
                                buttons=[
                                    button(
                                        id="close-services-btn-confname",  # replace confname by real conf name
                                        text="action_close",  # keep it (a18n)
                                        color="close",
                                        size="normal",
                                        attrs={"data-close-modal": ""},  # a11y
                                    )["data"],
                                ]
                            ),
                        ],
                    },
                )["data"]
            ]
        ),
        "actions": button_group(
            buttons=[
                # Need a script at Page.vue level in order to update displayStore when clicking edit button using the data-display attributs
                button(
                    id="edit-confname",  # replace confname by real conf name
                    type="button",
                    iconName="pen",
                    iconColor="white",
                    text="users_edit_config",  # keep it (a18n)
                    hideText=True,
                    color="yellow",
                    size="normal",
                    attrs={"data-display": "display_index"},  # replace by the display index of the related in order to display it
                )["data"],
                # Delete button with modal to confirm
                button(
                    id="delete-confname",  # replace confname by real conf name
                    type="button",
                    iconName="trash",
                    iconColor="white",
                    text="users_delete_config",  # keep it (a18n)
                    hideText=True,
                    color="error",
                    size="normal",
                    modal={
                        "widgets": [
                            title(title="users_delete_title"),  # keep it (a18n)
                            text(text="users_delete_subtitle"),  # keep it (a18n)
                            button_group(
                                buttons=[
                                    button(
                                        id="close-delete-btn-confname",  # replace confname by real conf name
                                        text="action_close",  # keep it (a18n)
                                        color="close",
                                        size="normal",
                                        attrs={"data-close-modal": ""},  # a11y
                                    )["data"],
                                ]
                            ),
                            button(
                                id="delete-btn-confname",  # replace confname by the instance name
                                text="action_delete",  # keep it (a18n)
                                color="delete",
                                size="normal",
                                attrs={
                                    "data-submit-form": '{"conf_name" : "", "conf_type" : "", "operation" : "delete" }'
                                },  # replace values by needed ones to delete the config, data-submit-form attributs will parse and submit values
                            )["data"],
                        ],
                    },
                )["data"],
            ]
        ),
    },
]


builder = [
    {
        "type": "card",
        "display": ["main", 1],
        "widgets": [
            tabulator(
                id="table-core-plugins",
                columns=users_columns,
                items=users_items,
                filters=users_filters,
            ),
            get_forms(),
        ],
    },
]


with open("configs2.json", "w") as f:
    f.write(json.dumps(builder))

output_base64_bytes = base64.b64encode(bytes(json.dumps(builder), "utf-8"))

output_base64_string = output_base64_bytes.decode("ascii")


with open("configs2.txt", "w") as f:
    f.write(output_base64_string)
