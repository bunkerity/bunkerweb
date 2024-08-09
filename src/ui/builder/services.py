from typing import Union

from os.path import join, sep
from sys import path as sys_path

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from builder.utils.widgets import title_widget, table_widget


def services_builder(services):
    # get method for each service["SERVER_NAME"]["method"]
    methods = list(set([service["SERVER_NAME"]["method"] for service in services]))

    services_list = get_services_list(services)

    builder = [
        {
            "type": "card",
            "containerColumns": {"pc": 12, "tablet": 12, "mobile": 12},
            "widgets": [
                title_widget("services_title"),
                {
                    "type": "Button",
                    "data": {
                        "id": "services-new",
                        "text": "services_new",
                        "color": "success",
                        "size": "normal",
                        "iconName": "plus",
                        "iconColor": "white",
                        "modal": services_action(server_name="new", operation="new", title="services_new_title", subtitle="services_new_subtitle"),
                        "containerClass": "col-span-12 flex justify-center",
                    },
                },
                table_widget(
                    positions=[4, 4, 4],
                    header=[
                        "services_table_name",
                        "services_table_method",
                        "services_table_actions",
                    ],
                    items=services_list,
                    filters=[
                        {
                            "filter": "table",
                            "filterName": "keyword",
                            "type": "keyword",
                            "value": "",
                            "keys": ["name"],
                            "field": {
                                "id": "services-keyword",
                                "value": "",
                                "type": "text",
                                "name": "services-keyword",
                                "label": "services_search",
                                "placeholder": "inp_keyword",
                                "isClipboard": False,
                                "popovers": [
                                    {
                                        "text": "services_search_desc",
                                        "iconName": "info",
                                    },
                                ],
                                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                            },
                        },
                        {
                            "filter": "table",
                            "filterName": "method",
                            "type": "select",
                            "value": "all",
                            "keys": ["method"],
                            "field": {
                                "id": "services-methods",
                                "value": "all",
                                "values": methods,
                                "name": "services-methods",
                                "onlyDown": True,
                                "label": "services_methods",
                                "popovers": [
                                    {
                                        "text": "services_methods_desc",
                                        "iconName": "info",
                                    },
                                ],
                                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                            },
                        },
                        {
                            "filter": "table",
                            "filterName": "draft",
                            "type": "select",
                            "value": "all",
                            "keys": ["draft"],
                            "field": {
                                "id": "services-draft",
                                "value": "all",
                                "values": ["all", "online", "draft"],
                                "name": "services-draft",
                                "onlyDown": True,
                                "label": "services_draft",
                                "popovers": [
                                    {
                                        "text": "services_draft_desc",
                                        "iconName": "info",
                                    },
                                ],
                                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                            },
                        },
                    ],
                    minWidth="md",
                    title="services_table_title",
                ),
            ],
        },
    ]

    return builder


def services_settings(settings: dict) -> dict:
    # deep copy settings dict
    settings = settings.copy()
    # remove "SERVER_NAME" and "IS_DRAFT" key
    settings.pop("SERVER_NAME", None)
    settings.pop("IS_DRAFT", None)
    # Create table with settings remaining keys
    settings_table_items = []
    for key, value in settings.items():
        format_key = key.replace("USE_", "").replace("_", " ")
        settings_table_items.append(
            [
                {
                    "type": "Text",
                    "data": {"text": format_key},
                },
                {
                    "type": "Icons",
                    "data": {
                        "iconName": "check" if value.get("value") == "yes" else "cross",
                    },
                },
            ]
        )

    table = table_widget(
        positions=[8, 4],
        header=["services_settings_table_name", "services_settings_table_status"],
        items=settings_table_items,
        filters=[],
        minWidth="",
        title="services_settings_table_title",
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
        {
            "id": f"close-service-btn-{server_name}",
            "text": "action_close",
            "disabled": False,
            "color": "close",
            "size": "normal",
            "attrs": {"data-close-modal": ""},
        },
    ]

    if operation == "delete":
        buttons.append(
            {
                "id": f"{operation}-service-btn-{server_name}",
                "text": f"action_{operation}",
                "disabled": False,
                "color": "delete",
                "size": "normal",
                "attrs": {
                    "data-submit-form": f"""{{"SERVER_NAME" : "{server_name}", "operation" : "{operation}" }}""",
                },
            },
        )

    if operation == "draft":
        # get reverse of current state for update
        draft_value = "no" if is_draft else "yes"
        buttons.append(
            {
                "id": f"{operation}-service-btn-{server_name}",
                "text": "action_switch",
                "disabled": False,
                "color": "success",
                "size": "normal",
                "attrs": {
                    "data-submit-form": f"""{{"SERVER_NAME" : "{server_name}", "OLD_SERVER_NAME" : "{server_name}", "operation" : "edit", "IS_DRAFT" : "{draft_value}" }}""",
                },
            },
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
                {
                    "id": f"{operation}-service-btn-{server_name}",
                    "text": f"services_mode_{mode}",
                    "disabled": False,
                    "color": "info",
                    "size": "normal",
                    "attrs": {
                        "role": "link",
                        "data-link": f"modes?service_name={server_name}&mode={mode}" if operation != "new" else f"modes?mode={mode}",
                    },
                },
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

        item = []
        # Get name
        item.append({"name": server_name, "type": "Text", "data": {"text": server_name}})
        item.append({"method": server_method, "type": "Text", "data": {"text": server_method}})
        item.append(
            {
                "type": "ButtonGroup",
                "data": {
                    "buttons": [
                        {
                            "id": f"open-modal-plugins-{index}",
                            "text": "plugins",
                            "hideText": True,
                            "color": "success",
                            "size": "normal",
                            "iconName": "eye",
                            "iconColor": "white",
                            "modal": services_action(
                                server_name=server_name,
                                operation="plugins",
                                title="services_plugins_title",
                                subtitle="",
                                service=service,
                            ),
                        },
                        {
                            "attrs": {"data-server-name": server_name},
                            "id": f"open-modal-manage-{index}",
                            "text": "manage",
                            "hideText": True,
                            "color": "edit",
                            "size": "normal",
                            "iconName": "pen",
                            "iconColor": "white",
                            "modal": services_action(
                                server_name=server_name,
                                operation="edit",
                                title="services_edit_title",
                                subtitle="services_edit_subtitle",
                                additional=server_name,
                            ),
                        },
                        {
                            "attrs": {"data-server-name": server_name, "data-is-draft": "yes" if is_draft else "no"},
                            "id": f"open-modal-draft-{index}",
                            "text": "draft" if is_draft else "online",
                            "hideText": True,
                            "color": "blue",
                            "size": "normal",
                            "iconName": "document" if is_draft else "globe",
                            "iconColor": "white",
                            "modal": services_action(
                                server_name=server_name,
                                operation="draft",
                                title="services_draft_title",
                                subtitle="services_draft_subtitle" if is_draft else "services_online_subtitle",
                                additional="services_draft_switch_subtitle" if is_draft else "services_online_switch_subtitle",
                                is_draft=is_draft,
                            ),
                        },
                        {
                            "attrs": {"data-server-name": server_name},
                            "id": f"open-modal-delete-{index}",
                            "text": "delete",
                            "disabled": not is_deletable,
                            "hideText": True,
                            "color": "red",
                            "size": "normal",
                            "iconName": "trash",
                            "iconColor": "white",
                            "modal": services_action(
                                server_name=server_name, operation="delete", title="services_delete_title", subtitle="services_delete_subtitle"
                            ),
                        },
                    ]
                },
            }
        )

        data.append(item)

    return data
