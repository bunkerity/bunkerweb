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
    add_column(title="global", field="is_global", formatter="icons", maxWidth=160),
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
            "type": "=",
            "fields": ["is_global"],
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

    if config_types is not None and len(config_types) >= 2:
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
    is_global: bool,  # "yes" or "no"
    filename: str = "",
    config_type: str = "",
    config_services: Optional[list] = None,
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
                    title_widget(title="configs_delete_title"),  # keep it (a18n)
                    text_widget(text="configs_delete_global_subtitle" if is_global else "configs_delete_no_global_subtitle"),  # keep it (a18n)
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

    services_columns = [{"title": "id", "field": "id", "formatter": "text", "maxWidth": 100}, {"title": "Name", "field": "name", "formatter": "text"}]
    services_items = []
    # get id
    for index, service in enumerate(config_services):
        services_items.append(
            {
                "id": text_widget(text=index)["data"],
                "name": text_widget(text=service)["data"],
            }
        )

    services_filter = [
        {
            "type": "like",
            "fields": ["name"],
            "setting": {
                "id": f"input-search-service-{filename}-{global_text}",
                "name": f"input-search-service-{filename}-{global_text}",
                "label": "configs_search_service",  # keep it (a18n)
                "value": "",
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                "fieldSize": "sm",
                "placeholder": "configs_search_service_placeholder",  # keep it (a18n)
                "inpType": "input",
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "configs_search_service_desc",
                    }
                ],
            },
        },
    ]

    services_detail = [
        button_widget(
            id=f"services-btn-{filename}-{global_text}",
            type="button",
            iconName="disk",
            hideText=True,
            iconColor="white",
            text="configs_show_services",  # keep it (a18n)
            color="orange",
            size="normal",
            modal={
                "widgets": [
                    title_widget(title="configs_services_title"),  # keep it (a18n)
                    tabulator_widget(
                        id=f"table-services-{filename}-{global_text}",
                        layout="fitColumns",
                        columns=services_columns,
                        # Add every services that apply to the conf. All if global.
                        items=services_items,
                        filters=services_filter,
                        paginationSize=5,
                        paginationSizeSelector=[5, 10],
                    ),
                    button_group_widget(
                        buttons=[
                            button_widget(
                                id=f"close-services-btn-{filename}-{global_text}",
                                text="action_close",  # keep it (a18n)
                                color="close",
                                size="normal",
                                attrs={"data-close-modal": ""},  # a11y
                            ),
                        ]
                    ),
                ],
            },
        )
    ]

    return {
        "name": text_widget(text=filename)["data"],
        "type": text_widget(text=config_type)["data"],
        "is_global": icons_widget(
            iconName="check" if is_global else "cross",
            value="yes" if is_global else "no",
        )["data"],
        "actions": {"buttons": services_detail + actions},
    }


def config_form(
    is_global: bool,  # "yes" or "no"
    filename: str,
    config_type: str,
    config_value: str,
    config_types: Optional[list] = None,
    config_services: Optional[list] = None,
    services: Optional[list] = None,
    display_index: int = 1,
    is_new: bool = False,
) -> dict:
    # difference between edit or new form
    enabled_value_field_only = False if is_new else True
    config_services = [] if is_global else config_services
    global_text = "yes" if is_global else "no"
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
                endpoint="/add",
                fields=[
                    get_fields_from_field(
                        input_widget(
                            id=f"configs-name-{filename}-{global_text}",
                            name="filename",
                            label="configs_filename",  # keep it (a18n)
                            value="",
                            required=True,
                            pattern="",  # add your pattern if needed
                            columns={"pc": 6, "tablet": 6, "mobile": 12},
                            placeholder="configs_filename_placeholder",  # keep it (a18n)
                            disabled=enabled_value_field_only,
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
                            id=f"configs-type-{filename}-{global_text}",
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
                            id=f"configs-services-{filename}-{global_text}",
                            name="services",
                            label="configs_services",  # keep it (a18n)
                            value="",
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
                            id=f"configs-value-{filename}-{global_text}",
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
                        id=f"back-from-create-user-{filename}-{global_text}",
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
                        id=f"configs-submit-{filename}-{global_text}",
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

    if config_types is None or len(config_types) == 0:
        return [fallback_message(msg="configs_missing_types")]

    if services is None or len(services) == 0:
        return [fallback_message(msg="configs_missing_services")]

    configs_items = []
    configs_form = []
    # Start adding the new config form
    configs_form.append(
        config_form(
            is_new=True,
            display_index=1,
            is_global=True,
            config_types=config_types,
            services=services,
            filename="",
            config_type="",
            config_value="",
            config_services=[],
        )
    )

    if configs is None or len(configs) == 0:
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
                is_global=config.get("is_global", ""),
                filename=config.get("filename", ""),
                config_services=config.get("config_services", ""),
                config_type=config.get("config_type", ""),
                display_index=display_index,
            )
        )
        configs_form.append(
            config_form(
                config_types=config_types,
                services=services,
                is_global=config.get("is_global", ""),
                filename=config.get("filename", ""),
                config_type=config.get("type", ""),
                config_value=config.get("value", ""),
                config_services=config.get("configs_services", []),
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
