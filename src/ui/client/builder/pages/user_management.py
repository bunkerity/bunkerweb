from .utils.widgets import (
    button_widget,
    button_group_widget,
    title_widget,
    subtitle_widget,
    text_widget,
    tabulator_widget,
    input_widget,
    icons_widget,
    regular_widget,
    unmatch_widget,
    select_widget,
    datepicker_widget,
)
from .utils.table import add_column
from .utils.format import get_fields_from_field
from typing import Optional, Union

# - created_method
# - is_superadmin
# - role
# - role_description
# - permissions (liste of permissions [])
# - creation_date
# - last_update (last time update user info)

users_columns = [
    add_column(title="Username", field="username", formatter="text"),
    add_column(title="Email", field="email", formatter="text"),
    add_column(title="Role", field="role", formatter="text"),  # superadmin, admin, writer...
    add_column(title="Totp", field="is_totp", formatter="icons"),
    add_column(title="Creation date", field="creation_date", formatter="fields", minWidth=250),  # datepicker
    add_column(title="Last login", field="last_login", formatter="fields", minWidth=250),  # datepicker
    add_column(title="Last update", field="last_update", formatter="fields", minWidth=250),  # datepicker
    add_column(title="Actions", field="actions", formatter="buttongroup"),
]


def users_filter(roles: Optional[list] = None, totp_states: Optional[list] = None) -> list:  # healths = "up", "down", "loading"
    filters = [
        {
            "type": "like",
            "fields": ["username", "email"],
            "setting": {
                "id": "input-search-username-email",
                "name": "input-search-username-email",
                "label": "user_management_search",  # keep it (a18n)
                "placeholder": "user_management_search_placeholder",  # keep it (a18n)
                "value": "",
                "inpType": "input",
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "user_management_search_desc",
                    }
                ],
                "fieldSize": "sm",
            },
        }
    ]

    if roles is not None and len(roles) >= 2:
        filters.append(
            {
                "type": "=",
                "fields": ["role"],
                "setting": {
                    "id": "select-role",
                    "name": "select-role",
                    "label": "user_management_select_role",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + roles,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    "popovers": [
                        {
                            "iconName": "info",
                            "text": "user_management_select_role_desc",
                        }
                    ],
                    "fieldSize": "sm",
                },
            }
        )

    if totp_states is not None and len(totp_states) >= 2:
        filters.append(
            {
                "type": "=",
                "fields": ["is_totp"],
                "setting": {
                    "id": "select-is-totp",
                    "name": "select-is-totp",
                    "label": "user_management_select_is_totp",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + totp_states,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    "popovers": [
                        {
                            "iconName": "info",
                            "text": "user_management_select_is_totp_desc",
                        }
                    ],
                    "fieldSize": "sm",
                },
            },
        )

    return filters


def user_management_item(
    id: Union[str, int],
    username: str,
    email: str,
    role: str,
    totp_state: str,
    last_login: int,
    creation_date: int,
    last_update: int,
    display_index: Union[str, int],
):

    actions = []

    # Can edit or delete only if not super admin
    if not "super" in role:
        actions = [
            button_widget(
                id=f"edit-user-{username}",
                text="action_edit",  # keep it (a18n)
                color="edit",
                size="normal",
                hideText=True,
                iconName="pen",
                iconColor="white",
                attrs={
                    "data-display-index": display_index,
                    "data-display-group": "main",
                },
            ),
            button_widget(
                id=f"delete-user-{username}",
                text="action_delete",  # keep it (a18n)
                color="error",
                size="normal",
                hideText=True,
                iconName="trash",
                iconColor="white",
                modal={
                    "widgets": [
                        title_widget(title="user_management_delete_title"),  # keep it (a18n)
                        text_widget(text="user_management_delete_subtitle"),  # keep it (a18n)
                        text_widget(bold=True, text=username),
                        button_group_widget(
                            buttons=[
                                button_widget(
                                    id=f"close-delete-btn-{username}",
                                    text="action_close",  # keep it (a18n)
                                    color="close",
                                    size="normal",
                                    attrs={"data-close-modal": ""},  # a11y
                                ),
                                button_widget(
                                    id=f"delete-btn-{username}",
                                    text="action_delete",  # keep it (a18n)
                                    color="delete",
                                    size="normal",
                                    iconName="trash",
                                    iconColor="white",
                                    attrs={
                                        "data-submit-form": f"""{{ "username" : "{username}" }}""",
                                        "data-submit-endpoint": "/delete",
                                    },
                                ),
                            ]
                        ),
                    ],
                },
            ),
        ]

    return {
        "username": text_widget(text=username)["data"],
        "email": text_widget(text=email)["data"],
        "role": text_widget(text=role)["data"],
        "is_totp": icons_widget(
            iconName="check" if totp_state == "enable" else "cross" if totp_state == "disable" else "search",
            value=totp_state,
        )["data"],
        "creation_date": get_fields_from_field(
            datepicker_widget(
                id=f"datepicker-user-creation-{id}",
                name=f"datepicker-user-creation-{id}",
                label="user_management_creation_date",  # keep it (a18n)
                hideLabel=True,
                value=creation_date,
                disabled=True,  # Readonly
                columns={"pc": 12, "tablet": 12, "mobile": 12},
            )
        ),
        "last_login": get_fields_from_field(
            datepicker_widget(
                id=f"datepicker-user-last-login-{id}",
                name=f"datepicker-user-last-login-{id}",
                label="user_management_last_login_date",  # keep it (a18n)
                hideLabel=True,
                value=last_login,
                disabled=True,  # Readonly
                columns={"pc": 12, "tablet": 12, "mobile": 12},
            )
        ),
        "last_update": get_fields_from_field(
            datepicker_widget(
                id=f"datepicker-user-last-update-{id}",
                name=f"datepicker-user-last-update-{id}",
                label="user_management_last_update_date",  # keep it (a18n)
                hideLabel=True,
                value=last_update,
                disabled=True,  # Readonly
                columns={"pc": 12, "tablet": 12, "mobile": 12},
            )
        ),
        "actions": {"buttons": actions},
    }


def user_management_form(
    username: str,
    role: str,
    display_index: Union[str, int],
    roles: Optional[list] = None,
    is_new: bool = False,
) -> dict:
    # Always main action button but back button is only for edit
    buttons = []

    if not is_new:
        buttons.append(
            button_widget(
                id=f"back-from-create-user-{'new' if is_new else username}",
                text="action_back",
                color="back",
                iconName="back",
                size="normal",
                type="button",
                attrs={
                    "data-display-index": 0,
                    "data-display-group": "main",
                },
            ),
        )

    buttons.append(
        button_widget(
            id=f"create-user-submit-{'new' if is_new else username}" if is_new else f"edit-user-submit-{'new' if is_new else username}",
            text="action_create" if is_new else "action_edit",
            iconName="plus" if is_new else "pen",
            color="success" if is_new else "edit",
            iconColor="white",
            size="normal",
            type="submit",
        ),
    )
    return {
        "type": "card",
        "maxWidthScreen": "md",
        "display": ["main", display_index],
        "widgets": [
            title_widget(
                title="user_management_create_title" if is_new else "user_management_edit_title",  # keep it (a18n)
            ),
            subtitle_widget(
                subtitle="user_management_create_subtitle" if is_new else "user_management_edit_subtitle",  # keep it (a18n)
            ),
            regular_widget(
                maxWidthScreen="xs",
                endpoint="/add" if is_new else "/edit",
                fields=[
                    get_fields_from_field(
                        input_widget(
                            id=f"user-username-{'new' if is_new else username}",
                            name="username",
                            label="user_management_form_username",  # keep it (a18n)
                            value="" if is_new else username,
                            required=True,
                            placeholder="user_management_form_username_placeholder",
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "user_management_form_username_desc",
                                }
                            ],
                        )
                    ),
                    get_fields_from_field(
                        select_widget(
                            id=f"user-role-{'new' if is_new else username}",
                            name="role",
                            label="user_management_form_role",  # keep it (a18n)
                            value="" if is_new else role,
                            values=roles,
                            requiredValues=roles,
                            required=True,
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "user_management_form_role_desc",
                                }
                            ],
                        )
                    ),
                    get_fields_from_field(
                        input_widget(
                            id=f"user-password-{'new' if is_new else username}",
                            name="password",
                            label="user_management_form_password" if is_new else "user_management_form_edit_password",  # keep it (a18n)
                            value="",
                            required=True if is_new else False,
                            pattern="",  # add your pattern if needed
                            placeholder="user_management_form_password_placeholder" if is_new else "user_management_form_edit_password_placeholder",
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "user_management_form_password_desc" if is_new else "user_management_form_edit_password_desc",
                                }
                            ],
                        )
                    ),
                    get_fields_from_field(
                        input_widget(
                            id=f"user-password-confirm-{'new' if is_new else username}",
                            name="password-confirm",
                            label="user_management_form_password_confirm" if is_new else "user_management_form_edit_password_confirm",  # keep it (a18n)
                            value="",
                            required=True if is_new else False,
                            pattern="",  # add your pattern if needed
                            placeholder=(
                                "user_management_form_password_confirm_placeholder" if is_new else "user_management_form_edit_password_confirm_placeholder"
                            ),
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                        )
                    ),
                ],
                buttons=buttons,
            ),
        ],
    }


def user_management_tabs():
    return {
        "type": "tabs",
        "widgets": [
            button_group_widget(
                buttons=[
                    button_widget(
                        text="user_management_tab_list",
                        display=["main", 0],
                        size="tab",
                        color="info",
                        iconColor="white",
                        iconName="list",
                    ),
                    button_widget(
                        text="user_management_tab_add",
                        color="success",
                        display=["main", 1],
                        size="tab",
                        iconColor="white",
                        iconName="plus",
                    ),
                ]
            )
        ],
    }


def fallback_message(msg: str, display: Optional[list] = None) -> dict:

    return {
        "type": "void",
        "display": display if display else [],
        "widgets": [
            unmatch_widget(text=msg),
        ],
    }


def user_management_builder(
    users: Optional[list] = None, roles: Optional[list] = None, roles_form: Optional[list] = None, totp_states: Optional[list] = None
) -> list:

    if roles is None or len(roles) == 0 or roles_form is None or len(roles_form) == 0:
        return [fallback_message("user_management_missing_roles")]

    users_items = []
    users_forms = []
    users_forms.append(user_management_form(is_new=True, display_index=1, role="", username="", roles=roles_form))

    if users is None or len(users) == 0:
        return [
            # Tabs is button group with display value and a size tab inside a tabs container
            user_management_tabs(),
            fallback_message(msg="user_management_users_not_found", display=["main", 0]),
        ] + users_forms

    # Start adding the new config form
    # display_index start at 2 because 1 is the new and 0 is the configs table
    for index, user in enumerate(users):
        display_index = index + 2
        users_items.append(
            user_management_item(
                id=index,
                username=user.get("username"),
                email=user.get("email"),
                role=user.get("role"),
                totp_state=user.get("totp_state"),
                last_login=user.get("last_login"),
                creation_date=user.get("creation_date"),
                last_update=user.get("last_update"),
                display_index=display_index,
            )
        )
        users_forms.append(
            user_management_form(
                username=user.get("username"),
                role=user.get("role"),
                roles=roles_form,
                display_index=display_index,
            )
        )

    return [
        # Tabs is button group with display value and a size tab inside a tabs container
        user_management_tabs(),
        {
            "type": "card",
            "maxWidthScreen": "3xl",
            "display": ["main", 0],
            "widgets": [
                title_widget(title="user_management_list_title"),  # keep it (a18n)
                subtitle_widget(subtitle="user_management_list_subtitle"),  # keep it (a18n)
                tabulator_widget(
                    id="table-configs",
                    columns=users_columns,
                    items=users_items,
                    layout="fitColumns",
                    filters=users_filter(roles=roles, totp_states=totp_states),
                ),
            ],
        },
    ] + users_forms
