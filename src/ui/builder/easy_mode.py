import base64
import json

from .utils.form import get_forms, get_service_settings


def easy_mode_builder(templates: list[dict], plugins: list, global_config: dict, total_config: dict, service_name: str, is_new: bool = False) -> str:
    """Render forms with global config data.
    ATM we don't need templates but we need to pass at least one to the function (it will simply not override anything).
    """

    # We need
    settings = get_service_settings(service_name, global_config, total_config)
    builder = [
        {
            "type": "card",
            "containerColumns": {"pc": 12, "tablet": 12, "mobile": 12},
            "widgets": [
                {
                    "type": "Title",
                    "data": {
                        "title": service_name,
                        "type": "container",
                        "lowercase": True,
                    },
                },
                {
                    "type": "Subtitle",
                    "data": {"subtitle": "services_manage_subtitle", "type": "container", "subtitleClass": "mb-4"},
                },
                {
                    "type": "Templates",
                    "data": {
                        "templates": get_forms(templates, plugins, settings, ("easy",), is_new),
                        "operation": "new" if is_new else "edit",
                        "oldServerName": service_name if service_name else "",
                    },
                },
            ],
        }
    ]
    return base64.b64encode(bytes(json.dumps(builder), "utf-8")).decode("ascii")
