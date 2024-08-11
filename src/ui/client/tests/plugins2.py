import json
import base64

from builder.utils.widgets import button, button_group, title, text, tabulator

core_columns = [
    {"title": "Name", "field": "name", "formatter": "text"},
    {"title": "Description", "field": "description", "formatter": "text"},
    {"title": "Page", "field": "type", "formatter": "buttonGroup"},
]

# Because we are going to use built-in filters, we can't use the Filter component
# So we need this format in order to create under the hood fields that will be linked to the tabulator filter
# We need to pass on the setting key the same props as the Fields component. For example a "=" tabulator filter will be used with a select field, this one need "values" array to work.
# type : Choose between available tabulator built-in filters ("keywords", "like", "!=", ">", "<", ">=", "<=", "in", "regex", "!=")
core_filters = [
    {
        "type": "like",
        "fields": ["name"],
        "setting": {
            "id": "input-search-core_name",
            "name": "input-search-core_name",
            "label": "Search name",
            "value": "",
            "inpType": "input",
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
    {
        "type": "=",
        "fields": ["page"],
        "setting": {
            "id": "select-core-page",
            "name": "select-core-page",
            "label": "Select core-page",
            "value": "all",
            "values": ["all", "plugin page", "no plugin page"],
            "inpType": "select",
            "onlyDown": True,
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
]


core_items = [
    {
        "name": text(text="Name")["data"],
        "description": text(text="Description")["data"],
        "page": button_group(
            buttons=[
                button(
                    id="create-instance",
                    text="action_create",
                    color="success",
                    size="normal",
                )["data"]
            ]
        ),
    },
]


instance_create_form = {}

builder = [
    {
        "type": "card",
        "display": ["main", 1],
        "widgets": [
            tabulator(
                id="table-instances",
                columns=core_columns,
                items=core_items,
                filters=core_filters,
            )
        ],
    },
]


with open("instances2.json", "w") as f:
    f.write(json.dumps(builder))

output_base64_bytes = base64.b64encode(bytes(json.dumps(builder), "utf-8"))

output_base64_string = output_base64_bytes.decode("ascii")


with open("instances2.txt", "w") as f:
    f.write(output_base64_string)
