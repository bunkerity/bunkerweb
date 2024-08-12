import json
import base64

from builder.utils.widgets import button, button_group, title, text, tabulator, input

columns = [
    {"title": "Name", "field": "name", "formatter": "text"},
    {"title": "Hostname", "field": "hostname", "formatter": "text"},
    {"title": "Type", "field": "type", "formatter": "text"},
    {"title": "Method", "field": "method", "formatter": "text"},
    {"title": "Creation date", "field": "creation_date", "formatter": "text"},
    {"title": "Last seen", "field": "last_seen", "formatter": "text"},
    {
        "title": "Actions",
        "field": "actions",
        "formatter": "buttonGroup",
    },
]

# Because we are going to use built-in filters, we can't use the Filter component
# So we need this format in order to create under the hood fields that will be linked to the tabulator filter
# We need to pass on the setting key the same props as the Fields component. For example a "=" tabulator filter will be used with a select field, this one need "values" array to work.
# type : Choose between available tabulator built-in filters ("keywords", "like", "!=", ">", "<", ">=", "<=", "in", "regex", "!=")
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
    },
    {
        "type": "=",
        "fields": ["type"],
        "setting": {
            "id": "select-type",
            "name": "select-type",
            "label": "instances_select_type",  # keep it (a18n)
            "value": "all",  # keep "all"
            "values": ["all", "type1", "type2"],  # keep "all" but add your types
            "inpType": "select",
            "onlyDown": True,
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
    {
        "type": "=",
        "fields": ["method"],
        "setting": {
            "id": "select-method",
            "name": "select-method",
            "label": "instances_select_method",  # keep it (a18n)
            "value": "all",  # keep "all"
            "values": ["all", "method1", "method2"],  # keep "all" but add your methods
            "inpType": "select",
            "onlyDown": True,
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
]

actions = (
    {
        "buttons": [
            button(
                id="ping-instance-INSTANCE_NAME",  # replace INSTANCE_NAME by the instance name
                text="action_ping",  # keep it (a18n)
                color="success",
                size="normal",
                hideText=True,
                iconName="globe",
                iconColor="white",
                modal={
                    "widgets": [
                        title(title="instances_ping_title"),  # keep it (a18n)
                        text(text="instances_ping_subtitle"),  # keep it (a18n)
                        text(bold=True, text="INSTANCE_NAME"),  # replace INSTANCE_NAME by the instance name
                        button_group(
                            buttons=[
                                button(
                                    id="close-ping-btn-INSTANCE_NAME",  # replace INSTANCE_NAME by the instance name
                                    text="action_close",  # keep it (a18n)
                                    color="close",
                                    size="normal",
                                    attrs={"data-close-modal": ""},  # a11y
                                )["data"],
                                button(
                                    id="ping-btn-INSTANCE_NAME",  # replace INSTANCE_NAME by the instance name
                                    text="action_ping",  # keep it (a18n)
                                    color="info",
                                    size="normal",
                                    attrs={
                                        "data-submit-form": '{"instance_name" : ", "instance_hostname" : "", "operation" : "ping" }'
                                    },  # replace values by needed ones for ping operation, data-submit-form attributs will parse and submit values to the form
                                )["data"],
                            ]
                        ),
                    ],
                },
            ),
            button(
                id="delete-instance-INSTANCE_NAME",  # replace INSTANCE_NAME by the instance name
                text="action_delete",  # keep it (a18n)
                color="success",
                size="normal",
                hideText=True,
                iconName="globe",
                iconColor="white",
                modal={
                    "widgets": [
                        title(title="instances_delete_title"),  # keep it (a18n)
                        text(text="instances_delete_subtitle"),  # keep it (a18n)
                        text(bold=True, text="INSTANCE_NAME"),  # replace INSTANCE_NAME by the instance name
                        button_group(
                            buttons=[
                                button(
                                    id="close-delete-btn-INSTANCE_NAME",  # replace INSTANCE_NAME by the instance name
                                    text="action_close",  # keep it (a18n)
                                    color="close",
                                    size="normal",
                                    attrs={"data-close-modal": ""},  # a11y
                                )["data"],
                                button(
                                    id="delete-btn-INSTANCE_NAME",  # replace INSTANCE_NAME by the instance name
                                    text="action_delete",  # keep it (a18n)
                                    color="info",
                                    size="normal",
                                    attrs={
                                        "data-submit-form": '{"instance_name" : ", "instance_hostname" : "", "operation" : "delete" }'
                                    },  # replace values by needed ones for ping operation, data-submit-form attributs will parse and submit values
                                )["data"],
                            ]
                        ),
                    ],
                },
            ),
        ]
    },
)


items = [
    {
        "name": text(text="Name")["data"],
        "hostname": text(text="Hostname")["data"],
        "type": text(text="Type")["data"],
        "method": text(text="Method")["data"],
        "creation_date": text(text="Creation date")["data"],
        "last_seen": text(text="Last seen")["data"],
        "actions": actions,
    },
]


instance_create_form_widgets = [
    input(
        id="instance-name",
        name="instance-name",
        label="instances_name",  # keep it (a18n)
        value="",
        pattern="",  # add your pattern if needed
        columns={"pc": 3, "tablet": 4, " mobile": 12},
    ),
    input(
        id="instance-hostname",
        name="instance-hostname",
        label="instances_hostname",  # keep it (a18n)
        value="",
        pattern="",  # add your pattern if needed
        columns={"pc": 3, "tablet": 4, " mobile": 12},
    ),
    button(
        id="create-instance",
        text="action_create",  # keep it (a18n)
        color="success",
        size="normal",
    ),
]

builder = [
    {
        "type": "card",
        "display": ["main", 1],
        "widgets": [
            tabulator(
                id="table-instances",
                columns=columns,
                items=items,
                filters=filters,
            )
        ],
    },
    {
        "type": "card",
        "display": ["main", 2],
        "widgets": instance_create_form_widgets,
    },
]


with open("instances2.json", "w") as f:
    f.write(json.dumps(builder))

output_base64_bytes = base64.b64encode(bytes(json.dumps(builder), "utf-8"))

output_base64_string = output_base64_bytes.decode("ascii")


with open("instances2.txt", "w") as f:
    f.write(output_base64_string)
