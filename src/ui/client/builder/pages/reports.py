from .utils.table import add_column
from .utils.format import get_fields_from_field
from .utils.widgets import datepicker_widget, text_widget, tabulator_widget, title_widget, subtitle_widget, unmatch_widget
from typing import Optional

reports_columns = [
    add_column(title="Date", field="date", formatter="fields", minWidth=250),
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


def reports_filters(reasons: Optional[list] = None, countries: Optional[list] = None, methods: Optional[list] = None, codes: Optional[list] = None) -> list:
    reports_filters = [
        {
            "type": "like",
            "fields": ["ip", "url", "user_agent", "data"],
            "setting": {
                "id": "input-search-misc",
                "name": "input-search-misc",
                "label": "reports_search_misc",  # keep it (a18n)
                "placeholder": "reports_search_misc_placeholder",  # keep it (a18n)
                "value": "",
                "inpType": "input",
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                "fieldSize": "sm",
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "reports_search_misc_desc",
                    }
                ],
            },
        },
    ]

    if reasons is not None and len(reasons) >= 2:
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
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    "fieldSize": "sm",
                    "popovers": [
                        {
                            "iconName": "info",
                            "text": "reports_select_reason_desc",
                        }
                    ],
                },
            }
        )

    if countries is not None and len(countries) >= 2:
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
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    "fieldSize": "sm",
                    "popovers": [
                        {
                            "iconName": "info",
                            "text": "reports_select_country_desc",
                        }
                    ],
                },
            }
        )

    if methods is not None and len(methods) >= 2:
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
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    "fieldSize": "sm",
                    "popovers": [
                        {
                            "iconName": "info",
                            "text": "reports_select_method_desc",
                        }
                    ],
                },
            }
        )

    if codes is not None and len(codes) >= 2:
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
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    "fieldSize": "sm",
                    "popovers": [
                        {
                            "iconName": "info",
                            "text": "reports_select_code_desc",
                        }
                    ],
                },
            }
        )

    return reports_filters


# date = timestamp
def report_item(id: int, date: int, ip: str, country: str, method: str, url: str, code: str, user_agent: str, reason: str, data: str, server_name: str) -> dict:

    return {
        "date": get_fields_from_field(
            datepicker_widget(
                id=f"datepicker-date-{id}",
                name=f"datepicker-date-{id}",
                label="reports_date",  # keep it (a18n)
                hideLabel=True,
                value=date,
                disabled=True,  # Readonly
            )
        ),
        "server_name": text_widget(text=server_name)["data"],
        "ip": text_widget(text=ip)["data"],
        "country": text_widget(text=country)["data"],
        "method": text_widget(text=method)["data"],
        "url": text_widget(text=url)["data"],
        "code": text_widget(text=code)["data"],
        "user_agent": text_widget(text=user_agent)["data"],
        "reason": text_widget(text=reason)["data"],
        "data": text_widget(text=data)["data"],
    }


def fallback_message(msg: str, display: Optional[list] = None) -> dict:

    return {
        "type": "void",
        "display": display if display else [],
        "widgets": [
            unmatch_widget(text=msg),
        ],
    }


def reports_builder(
    reports: list, reasons: Optional[list] = None, countries: Optional[list] = None, methods: Optional[list] = None, codes: Optional[list] = None
) -> str:

    if reports is None or len(reports) == 0:
        return [fallback_message("reports_not_found")]

    reports_items = [report_item(**report, id=index) for index, report in enumerate(reports)]
    return [
        {
            "type": "card",
            "widgets": [
                title_widget("reports_title"),  # keep it (a18n)
                subtitle_widget("reports_subtitle"),  # keep it (a18n)
                tabulator_widget(
                    id="table-core-plugins",
                    columns=reports_columns,
                    items=reports_items,
                    filters=reports_filters(reasons, countries, methods, codes),
                ),
            ],
        },
    ]
