import json
import base64

services = [
    {
        "USE_REVERSE_PROXY": {"value": "yes", "method": "scheduler", "global": False},
        "IS_DRAFT": {"value": "no", "method": "default", "global": False},
        "SERVE_FILES": {"value": "no", "method": "scheduler", "global": True},
        "REMOTE_PHP": {"value": "", "method": "default", "global": True},
        "AUTO_LETS_ENCRYPT": {"value": "no", "method": "default", "global": True},
        "USE_CUSTOM_SSL": {"value": "no", "method": "default", "global": True},
        "USE_MODSECURITY": {"value": "yes", "method": "default", "global": True},
        "USE_BAD_BEHAVIOR": {"value": "yes", "method": "default", "global": True},
        "USE_LIMIT_REQ": {"value": "yes", "method": "default", "global": True},
        "USE_DNSBL": {"value": "yes", "method": "default", "global": True},
        "SERVER_NAME": {"value": "app1.example.com", "method": "scheduler", "global": False},
    },
    {
        "USE_REVERSE_PROXY": {"value": "yes", "method": "scheduler", "global": False},
        "IS_DRAFT": {"value": "no", "method": "default", "global": False},
        "SERVE_FILES": {"value": "no", "method": "scheduler", "global": True},
        "REMOTE_PHP": {"value": "", "method": "default", "global": True},
        "AUTO_LETS_ENCRYPT": {"value": "no", "method": "default", "global": True},
        "USE_CUSTOM_SSL": {"value": "no", "method": "default", "global": True},
        "USE_MODSECURITY": {"value": "yes", "method": "default", "global": True},
        "USE_BAD_BEHAVIOR": {"value": "yes", "method": "default", "global": True},
        "USE_LIMIT_REQ": {"value": "yes", "method": "default", "global": True},
        "USE_DNSBL": {"value": "yes", "method": "default", "global": True},
        "SERVER_NAME": {"value": "www.example.com", "method": "scheduler", "global": False},
    },
]

# Loop on each services dict and get the methods from SERVER_NAME key


def title_widget(title):
    return {
        "type": "Title",
        "data": {"title": title},
    }


def table_widget(positions, header, items, filters, minWidth, title):
    return {
        "type": "Table",
        "data": {
            "title": title,
            "minWidth": minWidth,
            "header": header,
            "positions": positions,
            "items": items,
            "filters": filters,
        },
    }


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
                "type": "Button",
                "data": {
                    "id": f"open-modal-settings-{index}",
                    "text": "settings",
                    "hideText": False,
                    " color": "info",
                    "size": "normal",
                    "iconName": "settings",
                },
            }
        )
        item.append(
            {
                "type": "Button",
                "data": {
                    "attrs": {"data-server-name": server_name},
                    "id": f"open-modal-manage-{index}",
                    "text": "manage",
                    "hideText": False,
                    " color": "green",
                    "size": "normal",
                    "iconName": "manage",
                },
            }
        )
        item.append(
            {
                "type": "Button",
                "data": {
                    "attrs": {"data-server-name": server_name, "data-is-draft": "yes" if is_draft else "no"},
                    "id": f"open-modal-draft-{index}",
                    "text": "draft" if is_draft else "online",
                    "hideText": False,
                    " color": "cyan",
                    "size": "normal",
                    "iconName": "draft" if is_draft else "online",
                },
            }
        )
        item.append(
            {
                "type": "Button",
                "data": {
                    "attrs": {"data-server-name": server_name},
                    "id": f"open-modal-delete-{index}",
                    "text": "delete",
                    "disabled": not is_deletable,
                    "hideText": False,
                    " color": "red",
                    "size": "normal",
                    "iconName": "trash",
                },
            }
        )

        data.append(item)

    return data


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
                table_widget(
                    positions=[2, 2, 2, 2, 2, 2],
                    header=[
                        "services_table_name",
                        "services_table_method",
                        "services_table_settings",
                        "services_table_manage",
                        "services_table_is_draft",
                        "services_table_delete",
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
                    minWidth="lg",
                    title="services_table_title",
                ),
            ],
        }
    ]
    return builder


output = services_builder(services)

# store on a file
with open("services.json", "w") as f:
    json.dump(output, f, indent=4)
output_base64_bytes = base64.b64encode(bytes(json.dumps(output), "utf-8"))
output_base64_string = output_base64_bytes.decode("ascii")

with open("services.txt", "w") as f:
    f.write(output_base64_string)
