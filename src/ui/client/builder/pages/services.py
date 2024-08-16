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
)
from .utils.table import add_column
from .utils.format import get_fields_from_field
from typing import Optional, Union

columns = [
    add_column(title="Name", field="name", formatter="text"),
    add_column(title="Method", field="method", formatter="text"),
    add_column(title="Draft", field="draft", formatter="icons"),
    add_column(title="Actions", field="actions", formatter="buttongroup"),
]


def services_filter(methods: Optional[list] = None) -> list:
    filters = [
        {
            "type": "like",
            "fields": ["name"],
            "setting": {
                "id": "services-keyword",
                "name": "services-keyword",
                "label": "services_search",  # keep it (a18n)
                "placeholder": "inp_keyword",  # keep it (a18n)
                "value": "",
                "inpType": "input",
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "services_search_desc",
                    }
                ],
                "fieldSize": "sm",
            },
        },
        {
            "type": "=",
            "fields": ["draft"],
            "setting": {
                "id": "select-draft",
                "name": "select-draft",
                "label": "services_select_draft",  # keep it (a18n)
                "value": "all",  # keep "all"
                "values": ["all", "online", "draft"],
                "inpType": "select",
                "onlyDown": True,
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "services_select_draft_desc",
                    }
                ],
                "fieldSize": "sm",
            },
        },
    ]

    if methods is not None and (isinstance(methods, list) and len(methods) >= 2):
        filters.append(
            {
                "type": "=",
                "fields": ["method"],
                "setting": {
                    "id": "select-methods",
                    "name": "select-methods",
                    "label": "services_select_methods",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": methods,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    "popovers": [
                        {
                            "iconName": "info",
                            "text": "services_select_methods_desc",
                        }
                    ],
                    "fieldSize": "sm",
                },
            },
        )

    return filters


def services_builder(services):
    # get method for each service["SERVER_NAME"]["method"]
    methods = list(set([service["SERVER_NAME"]["method"] for service in services]))

    services_list = get_services_list(services)

    builder = [
        {
            "type": "tabs",
            "widgets": [
                button_group_widget(
                    buttons=[
                        button_widget(
                            id="services-new",
                            text="services_new",
                            color="success",
                            iconName="plus",
                            iconColor="white",
                            modal=services_action(server_name="new", operation="new", title="services_new_title", subtitle="services_new_subtitle"),
                        )
                    ]
                )
            ],
        },
        {
            "type": "card",
            "columns": {"pc": 4, "tablet": 4, "mobile": 4},
            "widgets": [
                title_widget(title="services_title"),
                tabulator_widget(
                    id="services-table",
                    columns=columns,
                    layout="fitColumns",
                    items=services_list,
                    filters=services_filter(methods),
                ),
            ],
        },
    ]

    return builder


def services_settings(settings: dict) -> dict:
    # deep copy settings dict
    settings = settings.copy()
    server_name = settings.get("SERVER_NAME")
    # remove "SERVER_NAME" and "IS_DRAFT" key
    settings.pop("SERVER_NAME", None)
    settings.pop("IS_DRAFT", None)
    # Create table with settings remaining keys
    settings_columns = [
        add_column(title="plugin", field="plugin", formatter="text"),
        add_column(title="status", field="status", formatter="icons"),
    ]
    settings_table_items = []
    for key, value in settings.items():
        format_key = key.replace("USE_", "").replace("_", " ")
        settings_table_items.append(
            {
                "plugin": text_widget(text=format_key)["data"],
                "status": icons_widget(iconName="check" if value.get("value") == "yes" else "cross", value=value.get("value"))["data"],
            },
        )

    table = tabulator_widget(
        id=f"services-settings-{server_name}",
        columns=settings_columns,
        items=settings_table_items,
        layout="fitColumns",
    )

    return table


def services_action(
    server_name: str = "",
    operation: str = "",
    title: str = "",
    subtitle: str = "",
    additional: str = "",
    is_draft: Union[bool, None] = None,
    service: dict = None,
) -> dict:

    buttons = [
        button_widget(
            id=f"close-service-btn-{server_name}",
            text="action_close",
            color="close",
            size="normal",
            attrs={"data-close-modal": ""},
        )
    ]

    if operation == "delete":
        buttons.append(
            button_widget(
                id=f"{operation}-service-btn-{server_name}",
                text=f"action_{operation}",
                color="delete",
                size="normal",
                iconColor="white",
                iconName="trash",
                attrs={
                    "data-submit-form": f"""{{"SERVER_NAME" : "{server_name}" }}""",
                    "data-submit-endpoint": f"/{operation}",
                },
            )
        )

    if operation == "draft":
        draft_value = "yes" if is_draft else "no"
        buttons.append(
            button_widget(
                id=f"{operation}-service-btn-{server_name}",
                text="action_switch",
                color="success",
                iconColor="white",
                iconName="globe" if is_draft else "document",
                size="normal",
                attrs={
                    "data-submit-form": f"""{{"SERVER_NAME" : "{server_name}", "OLD_SERVER_NAME" : "{server_name}", "IS_DRAFT" : "{draft_value}" }}""",
                    "data-submit-endpoint": f"/edit",
                },
            )
        )

    content = [
        {
            "type": "Title",
            "data": {
                "title": title,
            },
        },
    ]

    if subtitle:
        content.append(
            {
                "type": "Text",
                "data": {
                    "text": subtitle,
                },
            },
        )

    if additional:
        content.append(
            {
                "type": "Text",
                "data": {
                    "bold": True,
                    "text": additional,
                },
            }
        )

    if operation == "plugins":
        settings = services_settings(service)
        content.append(settings)

    if operation == "delete":
        content.append(
            {
                "type": "Text",
                "data": {
                    "text": "",
                    "bold": True,
                    "text": server_name,
                },
            }
        )

    if operation == "edit" or operation == "new":
        modes = ("easy", "advanced", "raw")
        mode_buttons = []
        for mode in modes:
            mode_buttons.append(
                button_widget(
                    id=f"{operation}-service-btn-{server_name}",
                    text=f"services_mode_{mode}",
                    color="back",
                    size="normal",
                    attrs={
                        "role": "link",
                        "data-link": f"modes?service_name={server_name}&mode={mode}" if operation != "new" else f"modes?mode={mode}",
                    },
                )
            )

        content.append(
            {
                "type": "ButtonGroup",
                "data": {"buttons": mode_buttons},
            }
        )

    content.append(
        {
            "type": "ButtonGroup",
            "data": {"buttons": buttons},
        },
    )

    modal = {
        "widgets": content,
    }

    return modal


def get_services_list(services):
    data = []
    for index, service in enumerate(services):
        server_name = service["SERVER_NAME"]["value"]
        server_method = service["SERVER_NAME"]["method"]
        is_draft = True if service["IS_DRAFT"]["value"] == "yes" else False
        is_deletable = False if server_method in ("autoconf", "scheduler") else True

        item = {}
        # Get name
        item["name"] = text_widget(text=server_name)["data"]
        item["method"] = text_widget(text=server_method)["data"]
        item["draft"] = icons_widget(iconName="check" if is_draft else "cross", value="draft" if is_draft else "online")["data"]
        item["actions"] = button_group_widget(
            buttons=[
                button_widget(
                    id=f"open-modal-plugins-{index}",
                    text="plugins",
                    hideText=True,
                    color="success",
                    size="normal",
                    iconName="eye",
                    iconColor="white",
                    modal=services_action(
                        server_name=server_name,
                        operation="plugins",
                        title="services_plugins_title",
                        subtitle="",
                        service=service,
                    ),
                ),
                button_widget(
                    id=f"open-modal-manage-{index}",
                    text="manage",
                    hideText=True,
                    color="edit",
                    size="normal",
                    iconName="pen",
                    iconColor="white",
                    modal=services_action(
                        server_name=server_name,
                        operation="edit",
                        title="services_edit_title",
                        subtitle="services_edit_subtitle",
                        additional=server_name,
                    ),
                    attrs={"data-server-name": server_name},
                ),
                button_widget(
                    attrs={"data-server-name": server_name, "data-is-draft": "yes" if is_draft else "no"},
                    id=f"open-modal-draft-{index}",
                    text="draft" if is_draft else "online",
                    hideText=True,
                    color="blue",
                    size="normal",
                    iconName="document" if is_draft else "globe",
                    iconColor="white",
                    modal=services_action(
                        server_name=server_name,
                        operation="draft",
                        title="services_draft_title",
                        subtitle="services_draft_subtitle" if is_draft else "services_online_subtitle",
                        additional="services_draft_switch_subtitle" if is_draft else "services_online_switch_subtitle",
                        is_draft=is_draft,
                    ),
                ),
                button_widget(
                    attrs={"data-server-name": server_name},
                    id=f"open-modal-delete-{index}",
                    text="delete",
                    disabled=not is_deletable,
                    hideText=True,
                    color="red",
                    size="normal",
                    iconName="trash",
                    iconColor="white",
                    modal=services_action(server_name=server_name, operation="delete", title="services_delete_title", subtitle="services_delete_subtitle"),
                ),
            ]
        )["data"]

        data.append(item)

    return data
