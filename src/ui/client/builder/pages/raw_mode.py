from .utils.form import get_forms, get_service_settings
from typing import Union


def raw_mode_builder(
    templates: list[dict],
    plugins: list,
    global_config: dict,
    operation: str,
    mode: str,
    total_config: dict,
    service_name: str,
    is_new: bool = False,
    is_draft: Union[None, bool] = False,
) -> str:
    """Render forms with global config data.
    ATM we don't need templates but we need to pass at least one to the function (it will simply not override anything).
    """

    # We need
    settings = get_service_settings(service_name, global_config, total_config)

    builder = [
        {
            "type": "tabs",
            "widgets": [
                {
                    "type": "Buttongroup",
                    "data": {
                        "buttons": [
                            {
                                "type": "Button",
                                "data": {
                                    "text": "services_switch_mode",
                                    "id": "services-switch-mode",
                                    "color": "sky",
                                    "iconColor": "white",
                                    "iconName": "redirect",
                                    "modal": {
                                        "widgets": [
                                            {"type": "Title", "data": {"title": "services_switch_mode_title"}},
                                            {"type": "Text", "data": {"text": "services_switch_mode_subtitle"}},
                                            {
                                                "type": "ButtonGroup",
                                                "data": {
                                                    "buttons": [
                                                        {
                                                            "type": "Button",
                                                            "data": {
                                                                "text": "services_mode_easy",
                                                                "id": "switch-mode-btn-easy",
                                                                "color": "back",
                                                                "attrs": {
                                                                    "role": "link",
                                                                    "data-link": f"modes?service_name={'' if is_new else service_name}&mode=easy&operation={operation}",
                                                                },
                                                            },
                                                        },
                                                        {
                                                            "type": "Button",
                                                            "data": {
                                                                "text": "services_mode_advanced",
                                                                "id": "switch-mode-btn-advanced",
                                                                "color": "back",
                                                                "attrs": {
                                                                    "role": "link",
                                                                    "data-link": f"modes?service_name={'' if is_new else service_name}&mode=advanced&operation={operation}",
                                                                },
                                                            },
                                                        },
                                                        {
                                                            "type": "Button",
                                                            "data": {
                                                                "text": "services_mode_raw",
                                                                "id": "switch-mode-btn-raw",
                                                                "color": "back",
                                                                "attrs": {
                                                                    "role": "link",
                                                                    "data-link": f"modes?service_name={'' if is_new else service_name}&mode=raw&operation={operation}",
                                                                },
                                                            },
                                                        },
                                                    ]
                                                },
                                            },
                                            {
                                                "type": "ButtonGroup",
                                                "data": {
                                                    "buttons": [
                                                        {
                                                            "type": "Button",
                                                            "data": {
                                                                "text": "action_close",
                                                                "id": "close-service-btn-new",
                                                                "color": "close",
                                                                "attrs": {"data-close-modal": ""},
                                                            },
                                                        }
                                                    ]
                                                },
                                            },
                                        ]
                                    },
                                },
                            }
                        ]
                    },
                }
            ],
        },
        {
            "type": "card",
            "maxWidthScreen": "3xl",
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
                    "data": {"subtitle": "services_manage_subtitle", "type": "container"},
                },
                {
                    "type": "Templates",
                    "data": {
                        "templates": get_forms(templates, plugins, settings, ("raw",), is_new, True),
                        "operation": "new" if is_new else "edit",
                        "oldServerName": service_name if service_name else "",
                        "isDraft": False if is_draft is None else "yes" if is_draft else "no",
                    },
                },
            ],
        },
    ]
    return builder
