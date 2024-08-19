from .utils.widgets import (
    button_widget,
    button_group_widget,
    title_widget,
    subtitle_widget,
    text_widget,
    tabulator_widget,
    input_widget,
    select_widget,
    editor_widget,
    checkbox_widget,
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
    add_column(title="service", field="service", formatter="text", maxWidth=160),
    add_column(
        title="actions", field="actions", formatter="buttongroup"
    ),  # edit button that will switch to the form using display store + delete with modal to confirm
]


def configs_filter(config_types: Optional[list] = None) -> list:  # healths = "up", "down", "loading"
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
            "type": "like",
            "fields": ["service"],
            "setting": {
                "id": "input-search-service",
                "name": "input-search-service",
                "label": "configs_search_service",  # keep it (a18n)
                "value": "",
                "inpType": "input",
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                "fieldSize": "sm",
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "configs_search_service_desc",
                    }
                ],
                "placeholder": "configs_search_service_placeholder",  # keep it (a18n)
            },
        },
    ]

    if config_types is not None and (isinstance(config_types, list) and len(config_types) >= 2):
        filters.append(
            {
                "type": "=",
                "fields": ["type"],
                "setting": {
                    "id": "select-type",
                    "name": "select-type",
                    "label": "configs_select_type",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + config_types,
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
    filename: str = "",
    config_type: str = "",
    service: str = "",
    display_index: int = 1,
):

    actions = [
        button_widget(
            id=f"edit-user-{filename}-{service}",
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
            id=f"delete-user-{filename}-{service}",
            text="action_delete",  # keep it (a18n)
            color="error",
            size="normal",
            hideText=True,
            iconName="trash",
            iconColor="white",
            modal={
                "widgets": [
                    title_widget(title="configs_delete_title"),  # keep it (a18n)
                    text_widget(text="configs_delete_subtitle"),  # keep it (a18n)
                    text_widget(bold=True, text=filename),
                    button_group_widget(
                        buttons=[
                            button_widget(
                                id=f"close-delete-btn-{filename}-{service}",
                                text="action_close",  # keep it (a18n)
                                color="close",
                                size="normal",
                                attrs={"data-close-modal": ""},  # a11y
                            ),
                            button_widget(
                                id=f"delete-btn-{filename}-{service}",
                                text="action_delete",  # keep it (a18n)
                                color="delete",
                                size="normal",
                                iconName="trash",
                                iconColor="white",
                                attrs={
                                    "data-submit-form": f"""{{ "filename" : "{filename}", "is_global" : "{service}" }}""",
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
        "name": text_widget(text=filename)["data"],
        "type": text_widget(text=config_type)["data"],
        "service": text_widget(text=service)["data"],
        "actions": {"buttons": actions},
    }


def config_form(
    filename: str,
    config_type: str,
    config_value: str,
    config_types: Optional[list] = None,
    service: Optional[list] = None,
    services: Optional[list] = None,
    display_index: int = 1,
    is_new: bool = False,
) -> dict:
    # difference between edit or new form
    enabled_value_field_only = False if is_new else True
    filename = "new" if is_new else filename
    title = "configs_create_title" if is_new else "configs_edit_title"
    subtitle = "configs_create_subtitle" if is_new else "configs_edit_subtitle"

    return {
        "type": "card",
        "maxWidthScreen": "md",
        "display": ["main", display_index],
        "widgets": [
            title_widget(
                title=title,  # keep it (a18n)
            ),
            subtitle_widget(
                subtitle=subtitle,  # keep it (a18n)
            ),
            regular_widget(
                endpoint="/add" if is_new else "/edit",
                fields=[
                    get_fields_from_field(
                        input_widget(
                            id=f"configs-name-{filename}-{service}",
                            name="filename",
                            label="configs_filename",  # keep it (a18n)
                            value="",
                            required=True,
                            pattern="",  # add your pattern if needed
                            columns={"pc": 6, "tablet": 6, "mobile": 12},
                            placeholder="configs_filename_placeholder",  # keep it (a18n)
                            disabled=enabled_value_field_only,
                            containerClass="z-10",
                            popovers=[
                                {
                                    "iconName": "yellow-darker",
                                    "text": "configs_filename_warning_desc",  # can't add a service with same name and same type of existing one, will not be save.
                                },
                                {
                                    "iconName": "info",
                                    "text": "configs_filename_desc",
                                },
                            ],
                        )
                    ),
                    get_fields_from_field(
                        select_widget(
                            containerClass="z-9",
                            id=f"configs-type-{filename}-{service}",
                            name="type",
                            label="configs_type",  # keep it (a18n)
                            value=config_type,
                            values=config_types,
                            required=True,
                            requiredValues=config_types,
                            columns={"pc": 6, "tablet": 6, "mobile": 12},
                            disabled=enabled_value_field_only,
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "configs_type_desc",
                                },
                            ],
                        )
                    ),
                    get_fields_from_field(
                        select_widget(
                            containerClass="z-8",
                            id=f"configs-services-{filename}-{service}",
                            name="services",
                            label="configs_services",  # keep it (a18n)
                            value=service,
                            values=services,
                            required=True,
                            requiredValues=services,
                            columns={"pc": 6, "tablet": 6, "mobile": 12},
                            disabled=enabled_value_field_only,
                            popovers=[
                                {
                                    "iconName": "exclamation",
                                    "color": "yellow-darker",
                                    "text": "configs_services_warning_desc",  # if check, will apply to all services even if services are selected.
                                },
                                {
                                    "iconName": "info",
                                    "text": "configs_services_desc",
                                },
                            ],
                        )
                    ),
                    get_fields_from_field(
                        editor_widget(
                            containerClass="z-7",
                            id=f"configs-value-{filename}-{service}",
                            name="value",
                            label="configs_value",  # keep it (a18n)
                            value=config_value,
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            popovers=[
                                {
                                    "iconName": "yellow-darker",
                                    "text": "configs_value_warning_desc",  # config will not be save in case of script error
                                },
                                {
                                    "iconName": "info",
                                    "text": "configs_value_desc",
                                },
                            ],
                        )
                    ),
                ],
                buttons=[
                    button_widget(
                        id=f"back-{filename}-{service}",
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
                    button_widget(
                        id=f"configs-submit-{filename}-{service}",
                        text="action_create" if is_new else "action_edit",  # keep it (a18n)
                        iconName="plus" if is_new else "pen",
                        iconColor="white",
                        color="success" if is_new else "edit",
                        size="normal",
                        type="submit",
                    ),
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
                        display=["main", 0],
                        size="tab",
                        color="info",
                        iconColor="white",
                        iconName="list",
                    ),
                    button_widget(
                        text="configs_tab_add",
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


def configs_builder(configs: Optional[list] = None, config_types: Optional[list] = None, services: Optional[list] = None) -> list:

    if config_types is None or (isinstance(config_types, list) and len(config_types) == 0):
        return [fallback_message(msg="configs_missing_types")]

    if services is None or (isinstance(services, list) and len(services) == 0):
        return [fallback_message(msg="configs_missing_services")]

    configs_items = []
    configs_form = []
    # Start adding the new config form
    configs_form.append(
        config_form(
            service="",
            is_new=True,
            display_index=1,
            config_types=config_types,
            filename="",
            config_type="",
            config_value="",
            services=services,
        )
    )

    if configs is None or (isinstance(configs, list) and len(configs) == 0):
        return [
            # Tabs is button group with display value and a size tab inside a tabs container
            configs_tabs(),
            fallback_message(msg="configs_not_found", display=["main", 0]),
        ] + configs_form

    # Start adding the new config form
    # display_index start at 2 because 1 is the new and 0 is the configs table
    for index, config in enumerate(configs):
        display_index = index + 2
        configs_items.append(
            configs_item(
                filename=config.get("filename", ""),
                service=config.get("service", ""),
                config_type=config.get("config_type", ""),
                display_index=display_index,
            )
        )
        configs_form.append(
            config_form(
                config_types=config_types,
                service=config.get("service", ""),
                filename=config.get("filename", ""),
                config_type=config.get("config_type", ""),
                config_value=config.get("value", ""),
                services=services,
                display_index=display_index,
            )
        )

    return [
        # Tabs is button group with display value and a size tab inside a tabs container
        configs_tabs(),
        {
            "type": "card",
            "maxWidthScreen": "xl",
            "display": ["main", 0],
            "widgets": [
                title_widget(title="configs_list_title"),  # keep it (a18n)
                subtitle_widget(subtitle="configs_list_subtitle"),  # keep it (a18n)
                tabulator_widget(
                    id="table-configs",
                    columns=columns,
                    items=configs_items,
                    layout="fitColumns",
                    filters=configs_filter(config_types=config_types),
                ),
            ],
        },
    ] + configs_form
