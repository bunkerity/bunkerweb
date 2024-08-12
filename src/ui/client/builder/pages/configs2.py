from enum import StrEnum

from builder.utils.widgets import (
    input_widget,
    select_widget,
    checkbox_widget,
    combobox_widget,
    editor_widget,
    button_widget,
    button_group_widget,
    title_widget,
    text_widget,
    tabulator_widget,
)

from builder.utils.table import add_column


class Global(StrEnum):
    YES = "yes"
    NO = "no"


def config_form(
    filename: str = "",
    config_type: str = "",
    types: list = [],
    is_global: bool = False,
    services: list = [],
    config_value: str = "",
    is_new: bool = False,
    display_index: int = 1,
):
    return (
        {
            "type": "card",
            "display": ["main", display_index],  # Allow to toggle between each form using displayStore
            "widgets": [
                button_widget(
                    id=f"back-btn-{filename}" if not is_new else "back-btn",
                    text="action_back",  # keep it (a18n)
                    color="info",
                    size="normal",
                    display=["main", 0] if not is_new else [],  # Return to list if edit
                ),
                input_widget(
                    id=f"config-name-new" if is_new else f"config-name-{filename}",
                    name="config-name",
                    label="configs_filename",  # keep it (a18n)
                    value="" if is_new else filename,  # empty if new or replace by the filename value to edit (.conf excluded)
                    pattern="",  # add your pattern if needed
                    columns={"pc": 3, "tablet": 4, " mobile": 12},
                ),
                # Select between available types
                select_widget(
                    {
                        "id": "select-type",
                        "name": "select-type",
                        "label": "configs_types",  # keep it (a18n)
                        "value": "" if is_new else config_type,
                        "values": types,  # set all available types like ["http", "modsec"]
                        "inpType": "select",
                        "onlyDown": True,
                        "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                    },
                ),
                # Add script on Page.vue to disabled listcheck in case checkbox is checked
                # This checkbox is priority over services checklist
                # Check or not to used globally the conf
                checkbox_widget(
                    id="config-global",
                    name="config-global",
                    label="configs_global",  # keep it (a18n)
                    value="yes" if is_global else "no",  # no if new, else it depends of the current conf
                    columns={"pc": 3, "tablet": 4, " mobile": 12},
                ),
                # Case checkbox is checked, this checklist will be ignored on server
                # Combobox ATM but will be replace by a checklist
                # set services list ATM, we will update by a checklist with [{value : "service1", is_check : bool}, ...]
                combobox_widget(
                    {
                        "id": "combo-services",
                        "name": "combo-services",
                        "label": "configs_types",  # keep it (a18n)
                        "value": "",
                        "values": services,  # set services list ATM, we will update by a checklist with [{value : "service1", is_check : bool}, ...]
                        "inpType": "select",
                        "onlyDown": True,
                        "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                    },
                ),
                # Editor to edit the conf
                editor_widget(
                    {
                        "id": "config-value",
                        "name": "config-value",
                        "label": "configs_value",  # keep it (a18n)
                        "value": "" if is_new else config_value,
                        "inpType": "editor",
                        "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                    },
                ),
                input_widget(
                    id="operation",
                    name="operation",
                    label="configs_operation",  # keep it (a18n)
                    value="new" if is_new else "edit",
                    pattern="",  # add your pattern if needed
                    columns={"pc": 3, "tablet": 4, " mobile": 12},
                    inputClass="hidden",  # hide it
                ),
                button_widget(
                    id="update-config",
                    text="action_create" if is_new else "action_update",  # keep it (a18n)
                    color="success",
                    size="normal",
                ),
            ],
        },
    )


configs_columns = [
    add_column(title="Name", field="name", formatter="text"),
    add_column(title="Type", field="type", formatter="text"),
    add_column(title="global", field="global", formatter="text"),
    add_column(
        title="services", field="services", formatter="buttonGroup"
    ),  # We will display a button with a modal that show all services apply. Case global, show all services.
    add_column(
        title="actions", field="actions", formatter="buttonGroup"
    ),  # edit button that will switch to the form using display store + delete with modal to confirm
]


def configs_filter(types: list):
    return [
        {
            "type": "like",
            "fields": ["name"],
            "setting": {
                "id": "input-search-name",
                "name": "input-search-name",
                "label": "configs_search_name",  # keep it (a18n)
                "value": "",
                "inpType": "input",
                "columns": {"pc": 3, "tablet": 4, " mobile": 12},
            },
        },
        {
            "type": "=",
            "fields": ["type"],
            "setting": {
                "id": "select-type",
                "name": "select-type",
                "label": "configs_select_type",  # keep it (a18n)
                "value": "all",  # keep "all"
                "values": types,
                "inpType": "select",
                "onlyDown": True,
                "columns": {"pc": 3, "tablet": 4, " mobile": 12},
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
                "columns": {"pc": 3, "tablet": 4, " mobile": 12},
            },
        },
    ]


def config_item(filename: str, conf_type: str, is_global: Global, services: list, display_index: int):

    services_items = []
    # get id
    for index, service in enumerate(services):
        services_items.append(
            {
                "id": text_widget(text=index)["data"],
                "name": text_widget(text=service.get("name"))["data"],
            }
        )

    return (
        {
            "name": text_widget(text=filename)["data"],
            "type": text_widget(text=conf_type)["data"],
            "global": text_widget(text=is_global)["data"],
            "services": button_group_widget(
                buttons=[
                    button_widget(
                        id=f"services-btn-{filename}",
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
                                    id=f"table-services-{filename}",
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
                                                "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                                            },
                                        },
                                    ],
                                ),
                                button_group_widget(
                                    buttons=[
                                        button_widget(
                                            id=f"close-services-btn-{filename}",
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
            "actions": button_group_widget(
                buttons=[
                    button_widget(
                        id=f"edit-{filename}",
                        type="button",
                        iconName="pen",
                        iconColor="white",
                        text="configs_edit_config",  # keep it (a18n)
                        hideText=True,
                        color="yellow",
                        size="normal",
                        display=["main", display_index],
                    )["data"],
                    # Delete button with modal to confirm
                    button_widget(
                        id=f"delete-{filename}",
                        type="button",
                        iconName="trash",
                        iconColor="white",
                        text="configs_delete_config",  # keep it (a18n)
                        hideText=True,
                        color="error",
                        size="normal",
                        modal={
                            "widgets": [
                                title_widget(title="configs_delete_title"),  # keep it (a18n)
                                text_widget(text="configs_delete_subtitle"),  # keep it (a18n)
                                button_group_widget(
                                    buttons=[
                                        button_widget(
                                            id=f"close-delete-btn-{filename}",
                                            text="action_close",  # keep it (a18n)
                                            color="close",
                                            size="normal",
                                            attrs={"data-close-modal": ""},  # a11y
                                        )["data"],
                                    ]
                                ),
                                button_widget(
                                    id=f"delete-btn-{filename}",
                                    text="action_delete",  # keep it (a18n)
                                    color="delete",
                                    size="normal",
                                    attrs={
                                        "data-submit-form": f"""{{"conf_name" : "{filename}", "conf_type" : "{conf_type}" }}""",
                                        "data-submit-endpoint": "/delete",
                                    },
                                )["data"],
                            ],
                        },
                    )["data"],
                ]
            ),
        },
    )


def configs_builder(configs: list, config_types) -> list:
    configs_items = []
    configs_forms = []

    # Start adding the new config form
    configs_forms.append(config_form(is_new=True, display_index=1, types=config_types))
    # display_index start at 2 because 1 is the new and 0 is the configs table
    for index, config in enumerate(configs):
        display_index = index + 2
        configs_items.append(
            config_item(
                filename=config.get("filename"),
                conf_type=config.get("type"),
                is_global=config.get("is_global"),
                services=config.get("services"),
                display_index=display_index,
            )
        )
        configs_forms.append(
            config_form(
                id=config.get("id"),
                filename=config.get("filename"),
                type=config.get("type"),
                types=config_types,
                is_global=config.get("is_global"),
                services=config.get("services"),
                config_value=config.get("config_value"),
                display_index=display_index,
            )
        )

    return [
        {
            "type": "card",
            "display": ["main", 0],
            "widgets": [
                tabulator_widget(
                    id="table-configs",
                    columns=configs_columns,
                    items=configs_items,
                    filters=configs_filter(config_types),
                ),
            ],
        },
    ] + configs_forms
