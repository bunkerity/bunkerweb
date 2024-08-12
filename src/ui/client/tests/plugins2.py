import json
import base64

from builder.utils.widgets import button, button_group, title, text, tabulator, fields, upload

core_columns = [
    {"title": "Name", "field": "name", "formatter": "text"},
    {"title": "Description", "field": "description", "formatter": "text"},
    {"title": "Documentation page", "field": "documentation_page", "formatter": "buttonGroup"},
    {"title": "Plugin page", "field": "plugin_page", "formatter": "buttonGroup"},
]


core_filters = [
    {
        "type": "like",
        "fields": ["name"],
        "setting": {
            "id": "input-search-core-name",
            "name": "input-search-core-name",
            "label": "plugins_search_name",  # keep it (a18n)
            "value": "",
            "inpType": "input",
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
]


core_items = [
    {
        "name": text(text="Name")["data"],
        "description": text(text="Description")["data"],
        "documentation_page": button_group(
            buttons=[
                button(
                    id="plugin-doc-plugin-id",  # replace by plugin_id custom page
                    text="plugins_documentation_page",  # keep it (a18n)
                    color="success",
                    hideText=True,
                    iconName="document",
                    iconColor="white",
                    size="normal",
                    attrs="""{ "data-link": "plugins/plugin_id" }""",  # replace by plugin_id custom page
                )["data"]
            ]
        ),
        "plugin_page": button_group(
            buttons=[
                button(
                    id="plugin-page-plugin-id",  # replace by plugin_id custom page
                    text="plugins_custom_page",  # keep it (a18n)
                    color="info",
                    hideText=True,
                    iconName="redirect",
                    iconColor="white",
                    size="normal",
                    attrs="""{ "data-link": "plugins/plugin_id" }""",  # replace by plugin_id custom page
                )["data"]
            ]
        ),
    },
]


register_columns = [
    {"title": "Select", "field": "select", "formatter": "fields"},  # checkbox
    {"title": "Name", "field": "name", "formatter": "text"},
    {"title": "Description", "field": "description", "formatter": "text"},
    {"title": "Type", "field": "type", "formatter": "text"},
    {"title": "Install", "field": "install", "formatter": "text"},
    {"title": "Documentation page", "field": "documentation_page", "formatter": "buttonGroup"},
    {"title": "Plugin page", "field": "plugin_page", "formatter": "buttonGroup"},
]


register_filters = [
    {
        "type": "like",
        "fields": ["name"],
        "setting": {
            "id": "input-search-register-name",
            "name": "input-search-register-name",
            "label": "plugins_search_name",  # keep it (a18n)
            "value": "",
            "inpType": "input",
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
    {
        "type": "=",
        "fields": ["type"],
        "setting": {
            "id": "select-register-type",
            "name": "select-register-type",
            "label": "plugins_select_type",  # keep it (a18n)
            "value": "all",
            "values": ["all", "pro", "external"],
            "inpType": "select",
            "onlyDown": True,
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
    {
        "type": "=",
        "fields": ["install"],
        "setting": {
            "id": "select-register-install",
            "name": "select-register-install",
            "label": "plugins_select_install",  # keep it (a18n)
            "value": "all",
            "values": ["all", "yes", "no"],
            "inpType": "select",
            "onlyDown": True,
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
]


register_items = [
    {
        "select": fields(
            inputType="checkbox",
            value="no",  # replace yes or no if installed or not
            label="plugin_is_installed",  # keep it (a18n)
            hideLabel=True,
            id="checkbox-plugin-id",  # replace by plugin_id
            name="checkbox-plugin-id",  # replace by plugin_id
            columns={"pc": 12, "tablet": 12, " mobile": 12},
        )["data"],
        "name": text(text="Name")["data"],
        "description": text(text="Description")["data"],
        "type": text(text="Type")["data"],  # replace yes or no if installed or not
        "install": text(text="no")["data"],
        "documentation_page": button_group(
            buttons=[
                button(
                    id="plugin-doc-plugin-id",  # replace by plugin_id custom page
                    text="plugins_documentation_page",  # keep it (a18n)
                    color="success",
                    hideText=True,
                    iconName="document",
                    iconColor="white",
                    size="normal",
                    attrs="""{ "data-link": "plugins/plugin_id" }""",  # replace by plugin_id custom page
                )["data"]
            ]
        ),
        "plugin_page": button_group(
            buttons=[
                button(
                    id="plugin-page-plugin-id",  # replace by plugin_id custom page
                    text="plugins_custom_page",  # keep it (a18n)
                    color="info",
                    hideText=True,
                    iconName="redirect",
                    iconColor="white",
                    size="normal",
                    attrs="""{ "data-link": "plugins/plugin_id" }""",  # replace by plugin_id custom page
                )["data"]
            ]
        ),
    },
]

upload_columns = [
    {"title": "Select", "field": "select", "formatter": "fields"},  # checkbox
    {"title": "Name", "field": "name", "formatter": "text"},
    {"title": "Description", "field": "description", "formatter": "text"},
    {"title": "Documentation page", "field": "documentation_page", "formatter": "buttonGroup"},
    {"title": "Plugin page", "field": "plugin_page", "formatter": "buttonGroup"},
]


upload_filters = [
    {
        "type": "like",
        "fields": ["name"],
        "setting": {
            "id": "input-search-upload-name",
            "name": "input-search-upload-name",
            "label": "plugins_search_name",  # keep it (a18n)
            "value": "",
            "inpType": "input",
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
]


upload_items = [
    {
        "select": fields(
            inputType="checkbox",
            value="no",  # replace yes or no if installed or not
            label="plugin_is_installed",  # keep it (a18n)
            hideLabel=True,
            id="checkbox-plugin-id",  # replace by plugin_id
            name="checkbox-plugin-id",  # replace by plugin_id
            columns={"pc": 12, "tablet": 12, " mobile": 12},
        )["data"],
        "name": text(text="Name")["data"],
        "description": text(text="Description")["data"],
        "documentation_page": button_group(
            buttons=[
                button(
                    id="plugin-doc-plugin-id",  # replace by plugin_id custom page
                    text="plugins_documentation_page",  # keep it (a18n)
                    color="success",
                    hideText=True,
                    iconName="document",
                    iconColor="white",
                    size="normal",
                    attrs="""{ "data-link": "plugins/plugin_id" }""",  # replace by plugin_id custom page
                )["data"]
            ]
        ),
        "plugin_page": button_group(
            buttons=[
                button(
                    id="plugin-page-plugin-id",  # replace by plugin_id custom page
                    text="plugins_custom_page",  # keep it (a18n)
                    color="info",
                    hideText=True,
                    iconName="redirect",
                    iconColor="white",
                    size="normal",
                    attrs="""{ "data-link": "plugins/plugin_id" }""",  # replace by plugin_id custom page
                )["data"]
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
                columns=core_columns,
                items=core_items,
                filters=core_filters,
            )
        ],
    },
    {
        "type": "card",
        "display": ["main", 2],
        "widgets": [
            tabulator(
                id="table-register-plugins",
                columns=register_columns,
                items=register_items,
                filters=register_filters,
            )
        ],
    },
    {
        "type": "card",
        "display": ["main", 3],
        "widgets": [
            upload(
                id="table-upload-plugins",
                type="plugins",
            ),
            tabulator(
                id="table-upload-plugins",
                columns=upload_columns,
                items=upload_items,
                filters=upload_filters,
            ),
        ],
    },
]


with open("plugins2.json", "w") as f:
    f.write(json.dumps(builder))

output_base64_bytes = base64.b64encode(bytes(json.dumps(builder), "utf-8"))

output_base64_string = output_base64_bytes.decode("ascii")


with open("plugins2.txt", "w") as f:
    f.write(output_base64_string)
