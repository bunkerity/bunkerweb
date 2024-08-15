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
from typing import Optional

columns = [
    add_column(title="Name", field="name", formatter="text"),
    add_column(title="Type", field="type", formatter="text"),
    add_column(title="global", field="global", formatter="icons"),
    add_column(
        title="services", field="services", formatter="buttonGroup"
    ),  # We will display a button with a modal that show all services apply. Case global, show all services.
    add_column(
        title="actions", field="actions", formatter="buttonGroup"
    ),  # edit button that will switch to the form using display store + delete with modal to confirm
]


def configs_filter(types: Optional[list] = None) -> list:  # healths = "up", "down", "loading"
    filters = [
        {
            "type": "like",
            "fields": ["name"],
            "setting": {
                "id": "input-search-name",
                "name": "input-search-name",
                "label": "configs_search_name",  # keep it (a18n)
                "value": "",
                "inpType": "input",
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                "fieldSize": "sm",
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "configs_search_name_desc",
                    }
                ],
                "placeholder": "configs_search_name_placeholder",  # keep it (a18n)
            },
        },
        {
            "type": "=",
            "fields": ["global"],
            "setting": {
                "id": "select-global",
                "name": "select-global",
                "label": "configs_select_global",  # keep it (a18n)
                "value": "all",  # keep "all"
                "values": ["all", "yes", "no"],  # keep
                "inpType": "select",
                "onlyDown": True,
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                "fieldSize": "sm",
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "configs_select_global_desc",
                    }
                ],
            },
        },
    ]

    if types is not None and len(types) >= 2:
        filters.append(
            {
                "type": "=",
                "fields": ["type"],
                "setting": {
                    "id": "select-type",
                    "name": "select-type",
                    "label": "configs_select_type",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + types,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    "fieldSize": "sm",
                    "popovers": [
                        {
                            "iconName": "info",
                            "text": "configs_select_type_desc",
                        }
                    ],
                },
            }
        )

    return filters


def configs_item(
    is_global: bool,  # "yes" or "no"
    filename: str = "",
    config_type: str = "",
    types: Optional[list] = None,
    services: Optional[list] = None,
    config_value: str = "",
    is_new: bool = False,
    display_index: int = 1,
):
    global_text = "yes" if is_global else "no"

    actions = [
        button_widget(
            id=f"edit-user-{filename}-{global_text}",
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
            id=f"delete-user-{filename}-{global_text}",
            text="action_delete",  # keep it (a18n)
            color="error",
            size="normal",
            hideText=True,
            iconName="trash",
            iconColor="white",
            modal={
                "widgets": [
                    title_widget(title="user_management_delete_title"),  # keep it (a18n)
                    text_widget(text="user_management_delete_global_subtitle" if is_global else "user_management_delete_no_global_subtitle"),  # keep it (a18n)
                    text_widget(bold=True, text=filename),
                    button_group_widget(
                        buttons=[
                            button_widget(
                                id=f"close-delete-btn-{filename}-{global_text}",
                                text="action_close",  # keep it (a18n)
                                color="close",
                                size="normal",
                                attrs={"data-close-modal": ""},  # a11y
                            ),
                            button_widget(
                                id=f"delete-btn-{filename}-{global_text}",
                                text="action_delete",  # keep it (a18n)
                                color="delete",
                                size="normal",
                                iconName="trash",
                                iconColor="white",
                                attrs={
                                    "data-submit-form": f"""{{ "filename" : "{filename}", "is_global" : "{global_text}" }}""",
                                    "data-submit-endpoint": "/delete",
                                },
                            ),
                        ]
                    ),
                ],
            },
        ),
    ]

    services_items = []
    # get id
    for index, service in enumerate(services):
        services_items.append(
            {
                "id": text_widget(text=index)["data"],
                "name": text_widget(text=service)["data"],
            }
        )

    services_detail = (
        button_group_widget(
            buttons=[
                button_widget(
                    id=f"services-btn-{filename}-{global_text}",
                    type="button",
                    iconName="disk",
                    iconColor="white",
                    text="configs_show_services",  # keep it (a18n)
                    color="orange",
                    size="normal",
                    modal={
                        "widgets": [
                            title_widget(title="configs_services_title"),  # keep it (a18n)
                            text_widget(text="configs_services_subtitle"),  # keep it (a18n)
                            tabulator_widget(
                                id=f"table-services-{filename}-{global_text}",
                                columns=[{"title": "id", "field": "id", "formatter": "text"}, {"title": "Name", "field": "name", "formatter": "text"}],
                                # Add every services that apply to the conf. All if global.
                                items=services_items,
                                filters=[
                                    {
                                        "type": "like",
                                        "fields": ["name"],
                                        "setting": {
                                            "id": "input-search-service",
                                            "name": "input-search-service",
                                            "label": "configs_search_service",  # keep it (a18n)
                                            "value": "",
                                            "inpType": "input",
                                            "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                                        },
                                    },
                                ],
                            ),
                            button_group_widget(
                                buttons=[
                                    button_widget(
                                        id=f"close-services-btn-{filename}-{global_text}",
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
    )

    return {
        "name": text_widget(text=filename)["data"],
        "type": text_widget(text=config_type)["data"],
        "is_global": icons_widget(
            iconName="check" if is_global == "up" else "cross" if is_global == "down" else "search",
            value=global_text,
        )["data"],
        "actions": {"buttons": actions},
    }


def configs_form(
    is_global: bool,  # "yes" or "no"
    filename: str = "",
    config_type: str = "",
    types: Optional[list] = None,
    services: Optional[list] = None,
    config_value: str = "",
    is_new: bool = False,
    display_index: int = 1,
) -> dict:
    global_text = "yes" if is_global else "no"

    return {
        "type": "card",
        "maxWidthScreen": "md",
        "display": ["main", 2],
        "widgets": [
            title_widget(
                title="configs_create_title",  # keep it (a18n)
            ),
            subtitle_widget(
                subtitle="configs_create_subtitle",  # keep it (a18n)
            ),
            regular_widget(
                maxWidthScreen="xs",
                endpoint="/add",
                fields=[
                    get_fields_from_field(
                        input_widget(
                            id="instance-name",
                            name="instance-name",
                            label="configs_name",  # keep it (a18n)
                            value="",
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="configs_name_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "configs_name_desc",
                                }
                            ],
                        )
                    ),
                    get_fields_from_field(
                        input_widget(
                            id="instance-hostname",
                            name="instance-hostname",
                            label="configs_hostname",  # keep it (a18n)
                            value="",
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="configs_hostname_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "configs_hostname_desc",
                                }
                            ],
                        )
                    ),
                ],
                buttons=[
                    button_widget(
                        id="create-instance-submit",
                        text="action_create",
                        iconName="plus",
                        iconColor="white",
                        color="success",
                        size="normal",
                        type="submit",
                        containerClass="flex justify-center",
                    )
                ],
            ),
        ],
    }


def configs_tabs():
    return {
        "type": "tabs",
        "widgets": [
            button_group_widget(
                buttons=[
                    button_widget(
                        text="configs_tab_list",
                        display=["main", 1],
                        size="tab",
                        color="info",
                        iconColor="white",
                        iconName="list",
                    ),
                    button_widget(
                        text="configs_tab_add",
                        color="success",
                        display=["main", 2],
                        size="tab",
                        iconColor="white",
                        iconName="plus",
                    ),
                ]
            )
        ],
    }


def configs_list(instances: Optional[list] = None, types: Optional[list] = None, methods: Optional[list] = None, healths: Optional[list] = None) -> dict:
    if instances is None or len(instances) == 0:
        return {
            "type": "card",
            "gridLayoutClass": "transparent",
            "widgets": [
                unmatch_widget(text="configs_not_found"),
            ],
        }

    items = []

    for instance in instances:
        items.append(
            instance_item(
                instance_name=instance.get("name", ""),
                hostname=instance.get("hostname", ""),
                instance_type=instance.get("type", ""),
                method=instance.get("method", ""),
                health=instance.get("health", ""),
                creation_date=instance.get("creation_date", ""),
                last_seen=instance.get("last_seen", ""),
            )
        )

    return {
        "type": "card",
        "display": ["main", 1],
        "widgets": [
            title_widget(
                title="configs_list_title",  # keep it (a18n)
            ),
            subtitle_widget(
                subtitle="configs_list_subtitle",  # keep it (a18n)
            ),
            tabulator_widget(
                id="table-instances",
                columns=columns,
                items=items,
                filters=configs_filter(types=types, methods=methods, healths=healths),
            ),
        ],
    }


def configs_builder(instances: Optional[list] = None, types: Optional[list] = None, methods: Optional[list] = None, healths: Optional[list] = None) -> list:
    return [
        # Tabs is button group with display value and a size tab inside a tabs container
        configs_tabs(),
        configs_list(instances=instances, types=types, methods=methods, healths=healths),
        configs_new_form(),
    ]
