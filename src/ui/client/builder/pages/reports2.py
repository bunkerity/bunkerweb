from builder.utils.table import add_column, format_field
from builder.utils.widgets import datepicker_widget, text_widget, tabulator_widget

reports_columns = [
    add_column(title="Date", field="date", formatter="fields"),
    add_column(title="IP", field="ip", formatter="text"),
    add_column(title="Country", field="country", formatter="text"),
    add_column(title="Server name", field="server_name", formatter="text"),
    add_column(title="Method", field="method", formatter="text"),
    add_column(title="URL", field="url", formatter="text"),
    add_column(title="Code", field="code", formatter="text"),
    add_column(title="User agent", field="user_agent", formatter="text"),
    add_column(title="Reason", field="reason", formatter="text"),
    add_column(title="Data", field="data", formatter="text"),
]


def reports_filters(reasons: list = [], countries: list = [], methods: list = [], codes: list = []) -> list:
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
    ]

    if reasons.length >= 2:
        reports_filters.append(
            {
                "type": "=",
                "fields": ["reason"],
                "setting": {
                    "id": "select-reason",
                    "name": "select-reason",
                    "label": "reports_select_reason",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + reasons,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                },
            }
        )

    if countries.length >= 2:
        reports_filters.append(
            {
                "type": "=",
                "fields": ["country"],
                "setting": {
                    "id": "select-country",
                    "name": "select-country",
                    "label": "reports_select_country",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + countries,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                },
            }
        )

    if methods.length >= 2:
        reports_filters.append(
            {
                "type": "=",
                "fields": ["method"],
                "setting": {
                    "id": "select-method",
                    "name": "select-method",
                    "label": "reports_select_method",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + methods,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                },
            }
        )

    if codes.length >= 2:
        reports_filters.append(
            {
                "type": "=",
                "fields": ["code"],
                "setting": {
                    "id": "select-code",
                    "name": "select-code",
                    "label": "reports_select_code",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + codes,
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                },
            }
        )

    return reports_filters


def report_item(id: int, date_timestamp: int, ip: str, country: str, method: str, url: str, code: str, user_agent: str, reason: str, data: str) -> dict:
    return (
        {
            "date": format_field(
                datepicker_widget(
                    id=f"datepicker-date-{id}",
                    name=f"datepicker-date-{id}",
                    label="reports_date",  # keep it (a18n)
                    hideLabel=True,
                    inputType="datepicker",
                    value=date_timestamp,
                    disabled=True,  # Readonly
                )
            ),
            "ip": text_widget(text=ip)["data"],
            "country": text_widget(text=country)["data"],
            "method": text_widget(text=method)["data"],
            "url": text_widget(text=url)["data"],
            "code": text_widget(text=code)["data"],
            "user_agent": text_widget(text=user_agent)["data"],
            "reason": text_widget(text=reason)["data"],
            "data": text_widget(text=data)["data"],
        },
    )


def reports_builder(reports: list, reasons: list = [], countries: list = [], methods: list = [], codes: list = []) -> str:
    reports_items = [report_item(**report) for report in reports]
    return [
        {
            "type": "card",
            "widgets": [
                tabulator_widget(
                    id="table-core-plugins",
                    columns=reports_columns,
                    items=reports_items,
                    filters=reports_filters(reasons, countries, methods, codes),
                ),
            ],
        },
    ]
