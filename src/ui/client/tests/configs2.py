import json
import base64

from builder.utils.widgets import button, button_group, title, text, tabulator, fields, upload, input, combobox, checkbox, select, editor


def generate_form(
    id: str = "",
    filename: str = "",
    type: str = "",
    is_global: bool = False,
    services: list = [],
    config_value: str = "",
    is_new: bool = True,
    display_index: int = 1,
):

    return (
        {
            "type": "card",
            "display": ["main", display_index],  # Allow to toggle between each form using displayStore
            "widgets": [
                input(
                    id=id,  # replace conf-id by value to use in the form for submit
                    name=id,  # replace conf-id by value to use in the form for submit
                    label="configs_filename",  # keep it (a18n)
                    value=filename,  # empty if new or replace by the filename value to edit (.conf excluded)
                    pattern="",  # add your pattern if needed
                    columns={"pc": 3, "tablet": 4, " mobile": 12},
                ),
                # Select between available types
                select(
                    {
                        "id": "select-type",
                        "name": "select-type",
                        "label": "configs_types",  # keep it (a18n)
                        "value": type,  # empty if new else set current type
                        "values": ["http", "modsec"],  # set all available types
                        "inpType": "select",
                        "onlyDown": True,
                        "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                    },
                ),
                # Add script on Page.vue to disabled listcheck in case checkbox is checked
                # This checkbox is priority over services checklist
                # Check or not to used globally the conf
                checkbox(
                    id="config-global",
                    name="config-global",
                    label="configs_global",  # keep it (a18n)
                    value="yes" if is_global else "no",  # no if new, else it depends of the current conf
                    columns={"pc": 3, "tablet": 4, " mobile": 12},
                ),
                # Case checkbox is checked, this checklist will be ignored on server
                # Combobox ATM but will be replace by a checklist
                # set services list ATM, we will update by a checklist with [{value : "service1", is_check : bool}, ...]
                combobox(
                    {
                        "id": "combo-services",
                        "name": "combo-services",
                        "label": "configs_types",  # keep it (a18n)
                        "value": "",  # empty if new else set current type
                        "values": services,  # set services list ATM, we will update by a checklist with [{value : "service1", is_check : bool}, ...]
                        "inpType": "select",
                        "onlyDown": True,
                        "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                    },
                ),
                # Editor to edit the conf
                editor(
                    {
                        "id": "config-value",
                        "name": "config-value",
                        "label": "configs_value",  # keep it (a18n)
                        "value": config_value,  # empty if new else set current type
                        "inpType": "editor",
                        "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                    },
                ),
                input(
                    id="operation",
                    name="operation",
                    label="configs_operation",  # keep it (a18n)
                    value="new" if is_new else "edit",  # "new" if new or "edit" if edit
                    pattern="",  # add your pattern if needed
                    columns={"pc": 3, "tablet": 4, " mobile": 12},
                    inputClass="hidden",  # hide it
                ),
                button(
                    id="update-config",
                    text="action_create",  # action_new if new or action_edit if edit
                    color="success",
                    size="normal",
                ),
            ],
        },
    )


# TODO
def get_forms():
    """We need to generate an empty form for the new conf that will be display index 1.
    We need to generate a form for each conf that will be display index > 1 and unique.
    """
    forms = []
    # Start adding new form with display index 1
    # Then we will loop on each conf to add a form with display index > 1 (use loop index)
    return forms


configs_columns = [
    {"title": "Name", "field": "name", "formatter": "text"},
    {"title": "Type", "field": "type", "formatter": "text"},
    {"title": "global", "field": "global", "formatter": "text"},
    {
        "title": "services",
        "field": "services",
        "formatter": "buttonGroup",
    },  # We will display a button with a modal that show all services apply. Case global, show all services.
    {
        "title": "actions",
        "field": "actions",
        "formatter": "buttonGroup",
    },  # edit button that will switch to the form using display store + delete with modal to confirm
]


configs_filters = [
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
            "values": ["all", "antibot"],  # keep "all" and add your types
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


configs_items = [
    {
        "name": text(text="Name")["data"],  # replace Name by real name
        "type": text(text="Type")["data"],  # replace Type by real type
        "global": text(text="global")["data"],  # replace global by real global ("yes" or "no")
        "services": button_group(
            buttons=[
                button(
                    id="services-btn-confname",  # replace confname by real conf name
                    type="button",
                    iconName="disk",
                    iconColor="white",
                    text="configs_show_services",  # keep it (a18n)
                    color="orange",
                    size="normal",
                    modal={
                        "widgets": [
                            title(title="configs_services_title"),  # keep it (a18n)
                            text(text="configs_services_subtitle"),  # keep it (a18n)
                            tabulator(
                                id="table-services-confname",  # replace confname by real conf name
                                columns=[{"title": "id", "field": "id", "formatter": "text"}, {"title": "Name", "field": "name", "formatter": "text"}],
                                # Add every services that apply to the conf. All if global.
                                items=[
                                    {
                                        "id": text(text="service_id")["data"],
                                        "name": text(text="service_name")["data"],
                                    },  # replace service_id and service_name by real values
                                ],
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
                            button_group(
                                buttons=[
                                    button(
                                        id="close-services-btn-confname",  # replace confname by real conf name
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
        "actions": button_group(
            buttons=[
                # Need a script at Page.vue level in order to update displayStore when clicking edit button using the data-display attributs
                button(
                    id="edit-confname",  # replace confname by real conf name
                    type="button",
                    iconName="pen",
                    iconColor="white",
                    text="configs_edit_config",  # keep it (a18n)
                    hideText=True,
                    color="yellow",
                    size="normal",
                    attrs={"data-display": "display_index"},  # replace by the display index of the related in order to display it
                )["data"],
                # Delete button with modal to confirm
                button(
                    id="delete-confname",  # replace confname by real conf name
                    type="button",
                    iconName="trash",
                    iconColor="white",
                    text="configs_delete_config",  # keep it (a18n)
                    hideText=True,
                    color="error",
                    size="normal",
                    modal={
                        "widgets": [
                            title(title="configs_delete_title"),  # keep it (a18n)
                            text(text="configs_delete_subtitle"),  # keep it (a18n)
                            button_group(
                                buttons=[
                                    button(
                                        id="close-delete-btn-confname",  # replace confname by real conf name
                                        text="action_close",  # keep it (a18n)
                                        color="close",
                                        size="normal",
                                        attrs={"data-close-modal": ""},  # a11y
                                    )["data"],
                                ]
                            ),
                            button(
                                id="delete-btn-confname",  # replace confname by the instance name
                                text="action_delete",  # keep it (a18n)
                                color="delete",
                                size="normal",
                                attrs={
                                    "data-submit-form": '{"conf_name" : "", "conf_type" : "", "operation" : "delete" }'
                                },  # replace values by needed ones to delete the config, data-submit-form attributs will parse and submit values
                            )["data"],
                        ],
                    },
                )["data"],
            ]
        ),
    },
]


builder = [
    {
        "type": "card",
        "display": ["main", 1],
        "widgets": [
            tabulator(
                id="table-core-plugins",
                columns=configs_columns,
                items=configs_items,
                filters=configs_filters,
            ),
            get_forms(),
        ],
    },
]


with open("configs2.json", "w") as f:
    f.write(json.dumps(builder))

output_base64_bytes = base64.b64encode(bytes(json.dumps(builder), "utf-8"))

output_base64_string = output_base64_bytes.decode("ascii")


with open("configs2.txt", "w") as f:
    f.write(output_base64_string)
