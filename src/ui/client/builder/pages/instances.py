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
    add_column(title="Hostname", field="hostname", formatter="text"),
    add_column(title="Type", field="type", formatter="text"),
    add_column(title="Method", field="method", formatter="text"),
    add_column(title="Creation date", field="creation_date", formatter="text"),
    add_column(title="Last seen", field="last_seen", formatter="text"),
    add_column(title="health", field="health", formatter="icons"),
    add_column(title="Actions", field="actions", formatter="buttongroup"),
]


def instances_filter(healths: str, types: Optional[list] = None, methods: Optional[list] = None) -> list:  # healths = "up", "down", "loading"
    filters = [
        {
            "type": "like",
            "fields": ["name", "hostname"],
            "setting": {
                "id": "input-search-host-name",
                "name": "input-search-host-name",
                "label": "instances_search",  # keep it (a18n)
                "placeholder": "instances_search_placeholder",  # keep it (a18n)
                "value": "",
                "inpType": "input",
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "instances_search_popover",
                    }
                ],
                "fieldSize": "sm",
            },
        }
    ]

    if types is not None and len(types) >= 2:
        filters.append(
            {
                "type": "=",
                "fields": ["type"],
                "setting": {
                    "id": "select-type",
                    "name": "select-type",
                    "label": "instances_type",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + types,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    "popovers": [
                        {
                            "iconName": "info",
                            "text": "instances_type_popover",
                        }
                    ],
                    "fieldSize": "sm",
                },
            }
        )

    if methods is not None and len(methods) >= 2:
        filters.append(
            {
                "type": "=",
                "fields": ["method"],
                "setting": {
                    "id": "select-method",
                    "name": "select-method",
                    "label": "instances_method",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + methods,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    "popovers": [
                        {
                            "iconName": "info",
                            "text": "instances_method_popover",
                        }
                    ],
                    "fieldSize": "sm",
                },
            },
        )

    if healths is not None and len(healths) >= 2:
        filters.append(
            {
                "type": "=",
                "fields": ["health"],
                "setting": {
                    "id": "select-health",
                    "name": "select-health",
                    "label": "instances_health",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + healths,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    "popovers": [
                        {
                            "iconName": "info",
                            "text": "instances_health_popover",
                        }
                    ],
                    "fieldSize": "sm",
                },
            },
        )

    return filters


def instance_item(
    instance_name: str,
    hostname: str,
    instance_type: str,
    method: str,
    health: str,
    creation_date: str,
    last_seen: str,
):

    # Always ping action, but delete only if ui, manual or default
    actions = [
        button_widget(
            id=f"ping-instance-{instance_name}",
            text="action_ping",  # keep it (a18n)
            color="info",
            size="normal",
            hideText=True,
            iconName="globe",
            iconColor="white",
            modal={
                "widgets": [
                    title_widget(title="instances_ping_title"),  # keep it (a18n)
                    text_widget(text="instances_ping_subtitle"),  # keep it (a18n)
                    text_widget(bold=True, text=instance_name),
                    button_group_widget(
                        buttons=[
                            button_widget(
                                id=f"close-ping-btn-{instance_name}",
                                text="action_close",  # keep it (a18n)
                                color="close",
                                size="normal",
                                attrs={"data-close-modal": ""},  # a11y
                            ),
                            button_widget(
                                id=f"ping-btn-{instance_name}",
                                text="action_ping",  # keep it (a18n)
                                color="info",
                                size="normal",
                                iconName="globe",
                                iconColor="white",
                                attrs={
                                    "data-submit-form": f"""{{ "instance_hostname" : "{hostname}" }}""",
                                    "data-submit-endpoint": "/ping",
                                },
                            ),
                        ]
                    ),
                ],
            },
        ),
        button_widget(
            id=f"reload-instance-{instance_name}",
            text="action_reload",  # keep it (a18n)
            color="success",
            size="normal",
            hideText=True,
            iconName="refresh",
            iconColor="white",
            modal={
                "widgets": [
                    title_widget(title="instances_reload_title"),  # keep it (a18n)
                    text_widget(text="instances_reload_subtitle"),  # keep it (a18n)
                    text_widget(bold=True, text=instance_name),
                    button_group_widget(
                        buttons=[
                            button_widget(
                                id=f"close-reload-btn-{instance_name}",
                                text="action_close",  # keep it (a18n)
                                color="close",
                                size="normal",
                                attrs={"data-close-modal": ""},  # a11y
                            ),
                            button_widget(
                                id=f"reload-btn-{instance_name}",
                                text="action_reload",  # keep it (a18n)
                                color="info",
                                size="normal",
                                iconName="globe",
                                iconColor="white",
                                attrs={
                                    "data-submit-form": f"""{{ "instance_hostname" : "{hostname}" }}""",
                                    "data-submit-endpoint": "/reload",
                                },
                            ),
                        ]
                    ),
                ],
            },
        ),
    ]

    if method.strip() in ("ui", "manual", "default"):
        actions.append(
            button_widget(
                id=f"delete-instance-{instance_name}",
                text="action_delete",  # keep it (a18n)
                color="error",
                size="normal",
                hideText=True,
                iconName="trash",
                iconColor="white",
                modal={
                    "widgets": [
                        title_widget(title="instances_delete_title"),  # keep it (a18n)
                        text_widget(text="instances_delete_subtitle"),  # keep it (a18n)
                        text_widget(bold=True, text=instance_name),
                        button_group_widget(
                            buttons=[
                                button_widget(
                                    id=f"close-delete-btn-{instance_name}",
                                    text="action_close",  # keep it (a18n)
                                    color="close",
                                    size="normal",
                                    attrs={"data-close-modal": ""},  # a11y
                                ),
                                button_widget(
                                    id=f"delete-btn-{instance_name}",
                                    text="action_delete",  # keep it (a18n)
                                    color="delete",
                                    size="normal",
                                    iconName="trash",
                                    iconColor="white",
                                    attrs={
                                        "data-submit-form": f"""{{ "instance_hostname" : "{hostname}" }}""",
                                        "data-submit-endpoint": "/delete",
                                    },
                                ),
                            ]
                        ),
                    ],
                },
            ),
        )

    return {
        "name": text_widget(text=instance_name)["data"],
        "hostname": text_widget(text=hostname)["data"],
        "type": text_widget(text=instance_type)["data"],
        "method": text_widget(text=method)["data"],
        "creation_date": text_widget(text=creation_date)["data"],
        "last_seen": text_widget(text=last_seen)["data"],
        "health": icons_widget(
            iconName="check" if health == "up" else "cross" if health == "down" else "search",
            value=health,
        )["data"],
        "actions": {"buttons": actions},
    }


def instances_new_form() -> dict:
    return {
        "type": "card",
        "maxWidthScreen": "md",
        "display": ["main", 2],
        "widgets": [
            title_widget(
                title="instances_create_title",  # keep it (a18n)
            ),
            subtitle_widget(
                subtitle="instances_create_subtitle",  # keep it (a18n)
            ),
            regular_widget(
                maxWidthScreen="xs",
                endpoint="/add",
                fields=[
                    get_fields_from_field(
                        input_widget(
                            id="instance-name",
                            name="instance_name",
                            label="instances_name",  # keep it (a18n)
                            value="",
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="instances_name_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "instances_name_desc",
                                }
                            ],
                        )
                    ),
                    get_fields_from_field(
                        input_widget(
                            id="instance-hostname",
                            name="instance_hostname",
                            label="instances_hostname",  # keep it (a18n)
                            value="",
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="instances_hostname_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "instances_hostname_desc",
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


def instances_tabs():
    return {
        "type": "tabs",
        "widgets": [
            button_group_widget(
                buttons=[
                    button_widget(
                        text="instances_tab_list",
                        display=["main", 1],
                        size="tab",
                        color="info",
                        iconColor="white",
                        iconName="list",
                    ),
                    button_widget(
                        text="instances_tab_add",
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


def instances_list(instances: Optional[list] = None, types: Optional[list] = None, methods: Optional[list] = None, healths: Optional[list] = None) -> dict:
    if instances is None or len(instances) == 0:
        return {
            "type": "card",
            "gridLayoutClass": "transparent",
            "widgets": [
                unmatch_widget(text="instances_not_found"),
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
                title="instances_list_title",  # keep it (a18n)
            ),
            subtitle_widget(
                subtitle="instances_list_subtitle",  # keep it (a18n)
            ),
            tabulator_widget(
                id="table-instances",
                columns=columns,
                items=items,
                filters=instances_filter(types=types, methods=methods, healths=healths),
            ),
        ],
    }


def instances_builder(instances: Optional[list] = None, types: Optional[list] = None, methods: Optional[list] = None, healths: Optional[list] = None) -> list:
    return [
        # Tabs is button group with display value and a size tab inside a tabs container
        instances_tabs(),
        instances_list(instances=instances, types=types, methods=methods, healths=healths),
        instances_new_form(),
    ]
