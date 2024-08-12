import json
import base64

from builder.utils.widgets import button, button_group, title, text, tabulator, fields, upload, datepicker

# TODO : REMOVE operation by custom endpoint

reports_columns = [
    {"title": "Date", "field": "date", "formatter": "fields"},  # datepicker
    {"title": "IP", "field": "ip", "formatter": "text"},
    {"title": "Country", "field": "country", "formatter": "text"},
    {"title": "Server name", "field": "server_name", "formatter": "text"},
    {"title": "Method", "field": "method", "formatter": "text"},
    {"title": "URL", "field": "url", "formatter": "text"},
    {"title": "Code", "field": "code", "formatter": "text"},
    {"title": "User agent", "field": "user_agent", "formatter": "text"},
    {"title": "Reason", "field": "reason", "formatter": "text"},
    {"title": "Data", "field": "data", "formatter": "text"},
]


reports_filters = [
    {
        "type": "like",
        "fields": ["ip"],
        "setting": {
            "id": "input-search-ip",
            "name": "input-search-ip",
            "label": "reports_search_ip",  # keep it (a18n)
            "value": "",
            "inpType": "input",
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
    {
        "type": "=",
        "fields": ["reason"],
        "setting": {
            "id": "select-reason",
            "name": "select-reason",
            "label": "reports_select_reason",  # keep it (a18n)
            "value": "all",  # keep "all"
            "values": ["all", "antibot"],  # keep "all" and add your reasons
            "inpType": "select",
            "onlyDown": True,
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
    {
        "type": "like",
        "fields": ["url"],
        "setting": {
            "id": "input-search-url",
            "name": "input-search-url",
            "label": "reports_search_url",  # keep it (a18n)
            "value": "",
            "inpType": "input",
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
    {
        "type": "like",
        "fields": ["user_agent", "data"],
        "setting": {
            "id": "input-search-misc",
            "name": "input-search-misc",
            "label": "reports_search_misc",  # keep it (a18n)
            "value": "",
            "inpType": "input",
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
    {
        "type": "=",
        "fields": ["country"],
        "setting": {
            "id": "select-country",
            "name": "select-country",
            "label": "reports_select_country",  # keep it (a18n)
            "value": "all",  # keep "all"
            "values": ["all", "antibot"],  # keep "all" and add your countries
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
            "label": "reports_select_method",  # keep it (a18n)
            "value": "all",  # keep "all"
            "values": ["all", "antibot"],  # keep "all" and add your methods
            "inpType": "select",
            "onlyDown": True,
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
    {
        "type": "=",
        "fields": ["code"],
        "setting": {
            "id": "select-code",
            "name": "select-code",
            "label": "reports_select_code",  # keep it (a18n)
            "value": "all",  # keep "all"
            "values": ["all", "antibot"],  # keep "all" and add your codes
            "inpType": "select",
            "onlyDown": True,
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
]

reports_items = [
    {
        "data": datepicker(
            id="datepicker-date-id",  # replace id by unique id
            name="datepicker-date-id",  # replace by unique id
            label="reports_date",  # keep it (a18n)
            hideLabel=True,
            inputType="datepicker",
            value="my_date",  # replace my_date by timestamp value
            disabled=True,  # Readonly
        )["data"],
        "ip": text(text="IP")["data"],
        "country": text(text="Country")["data"],
        "method": text(text="Method")["data"],
        "url": text(text="URL")["data"],
        "code": text(text="Code")["data"],
        "user_agent": text(text="User agent")["data"],
        "reason": text(text="Reason")["data"],
        "data": text(text="Data")["data"],
    },
]


builder = [
    {
        "type": "card",
        "display": ["main", 1],
        "widgets": [
            tabulator(
                id="table-core-plugins",
                columns=reports_columns,
                items=reports_items,
                filters=reports_filters,
            ),
        ],
    },
]


with open("reports2.json", "w") as f:
    f.write(json.dumps(builder))

output_base64_bytes = base64.b64encode(bytes(json.dumps(builder), "utf-8"))

output_base64_string = output_base64_bytes.decode("ascii")


with open("reports2.txt", "w") as f:
    f.write(output_base64_string)
