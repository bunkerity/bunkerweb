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
            "data": {"id": f"open-modal-settings-{index}", "text": "settings", "hideText": False, " color": "info", "size": "normal", "iconName": "settings"},
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
