from .utils.widgets import button_widget, button_group_widget, title_widget, text_widget, tabulator_widget, input_widget, icons_widget
from .utils.table import add_column


columns = [
    add_column(title="Name", field="name", formatter="text"),
    add_column(title="Hostname", field="hostname", formatter="text"),
    add_column(title="Type", field="type", formatter="text"),
    add_column(title="Method", field="method", formatter="text"),
    add_column(title="Creation date", field="creation_date", formatter="text"),
    add_column(title="Last seen", field="last_seen", formatter="text"),
    add_column(title="health", field="health", formatter="icons"),
    add_column(title="Actions", field="actions", formatter="buttonGroup"),
]


def instances_filter(healths: str, types: list = [], methods: list = []) -> list:  # healths = "up", "down", "loading"
    filters = [
        {
            "type": "like",
            "fields": ["name", "hostname"],
            "setting": {
                "id": "input-search-host-name",
                "name": "input-search-host-name",
                "label": "instances_search_host_name",  # keep it (a18n)
                "value": "",
                "inpType": "input",
                "columns": {"pc": 3, "tablet": 4, " mobile": 12},
            },
        }
    ]

    if len(types) >= 2:
        filters.append(
            {
                "type": "=",
                "fields": ["type"],
                "setting": {
                    "id": "select-type",
                    "name": "select-type",
                    "label": "instances_select_type",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + types,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                },
            }
        )

    if len(methods) >= 2:
        filters.append(
            {
                "type": "=",
                "fields": ["method"],
                "setting": {
                    "id": "select-method",
                    "name": "select-method",
                    "label": "instances_select_method",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + methods,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                },
            },
        )

    if len(healths) >= 2:
        filters.append(
            {
                "type": "=",
                "fields": ["health"],
                "setting": {
                    "id": "select-health",
                    "name": "select-health",
                    "label": "instances_select_health",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + healths,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, " mobile": 12},
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
    {
        "name": text_widget(text=instance_name)["data"],
        "hostname": text_widget(text=hostname)["data"],
        "type": text_widget(text=instance_type)["data"],
        "method": text_widget(text=method)["data"],
        "creation_date": text_widget(text=creation_date)["data"],
        "last_seen": text_widget(text=last_seen)["data"],
        "health": icons_widget(
            iconName="check" if health == "up" else "cross" if health == "down" else "search",
            value=health,
        ),
        "actions": {
            "buttons": [
                button_widget(
                    id=f"ping-instance-{instance_name}",
                    text="action_ping",  # keep it (a18n)
                    color="success",
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
                                    )["data"],
                                    button_widget(
                                        id=f"ping-btn-{instance_name}",
                                        text="action_ping",  # keep it (a18n)
                                        color="info",
                                        size="normal",
                                        attrs={
                                            "data-submit-form": f"""{{"instance_name" : "{instance_name}", "instance_hostname" : "{hostname}" }}""",
                                            "data-submit-endpoint": "/ping",
                                        },
                                    )["data"],
                                ]
                            ),
                        ],
                    },
                ),
                button_widget(
                    id=f"delete-instance-{instance_name}",
                    text="action_delete",  # keep it (a18n)
                    color="success",
                    size="normal",
                    hideText=True,
                    iconName="globe",
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
                                    )["data"],
                                    button_widget(
                                        id=f"delete-btn-{instance_name}",
                                        text="action_delete",  # keep it (a18n)
                                        color="delete",
                                        size="normal",
                                        attrs={
                                            "data-submit-form": f"""{{ "instance_name" : "{instance_name}", "instance_hostname" : "{hostname}" }}""",
                                            "data-submit-endpoint": "/delete",
                                        },
                                    )["data"],
                                ]
                            ),
                        ],
                    },
                ),
            ]
        },
    },


def instance_new_form() -> list:
    return [
        input_widget(
            id="instance-name",
            name="instance-name",
            label="instances_name",  # keep it (a18n)
            value="",
            pattern="",  # add your pattern if needed
            columns={"pc": 3, "tablet": 4, " mobile": 12},
        ),
        input_widget(
            id="instance-hostname",
            name="instance-hostname",
            label="instances_hostname",  # keep it (a18n)
            value="",
            pattern="",  # add your pattern if needed
            columns={"pc": 3, "tablet": 4, " mobile": 12},
        ),
        button_widget(
            id="create-instance",
            text="action_create",  # keep it (a18n)
            color="success",
            size="normal",
        ),
    ]


def instances_tabs():
    return [
        button_widget(
            text="instances_tab_list",
            display=["main", 1],
            size="tab",
            iconColor="white",
            iconName="list",
        ),
        button_widget(
            text="instances_tab_add",
            display=["main", 2],
            size="tab",
            iconColor="white",
            iconName="plus",
        ),
    ]


def instances_builder(instances: list, types: list = [], methods: list = [], healths: list = []) -> list:
    items = []
    for instance in instances:
        items.append(
            instance_item(
                instance_name=instance.get("name"),
                hostname=instance.get("hostname"),
                instance_type=instance.get("type"),
                method=instance.get("method"),
                health=instance.get("health"),
                creation_date=instance.get("creation_date"),
                last_seen=instance.get("last_seen"),
            )
        )

    return [
        # Tabs is button group with display value and a size tab inside a tabs container
        {
            "type": "tabs",
            "widgets": [button_group_widget(buttons=instances_tabs())],
        },
        {
            "type": "card",
            "display": ["main", 1],
            "widgets": [
                tabulator_widget(
                    id="table-instances",
                    columns=columns,
                    items=items,
                    filters=instances_filter(types=types, methods=methods, healths=healths),
                )
            ],
        },
        {
            "type": "card",
            "display": ["main", 2],
            "widgets": instance_new_form(),
        },
    ]
