import json


reports = [
    {
        "url": "/admin/login?id=etc/passwd",
        "ip": "172.21.0.1",
        "reason": "modsecurity",
        "country": "local",
        "status": 403,
        "method": "GET",
        "date": "25/06/2024 07:40:23",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "data": {"fesfesfsefesfesfesfesfesfesfesfesfesfsefes": "fesfs"},
    },
    {
        "url": "/admin/login?id=e",
        "ip": "111111",
        "reason": " antibot",
        "country": "fr",
        "status": 403,
        "method": "POST",
        "date": "25/06/2024 07:40:23",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "data": {},
    },
    {
        "url": "/admin/login?id=e",
        "ip": "111111",
        "reason": " antibot",
        "country": "fr",
        "status": 403,
        "method": "POST",
        "date": "25/06/2024 07:40:23",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "data": {},
    },
    {
        "url": "/admin/login?id=e",
        "ip": "111111",
        "reason": " antibot",
        "country": "fr",
        "status": 403,
        "method": "POST",
        "date": "25/06/2024 07:40:23",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "data": {},
    },
    {
        "url": "/admin/login?id=e",
        "ip": "111111",
        "reason": " antibot",
        "country": "fr",
        "status": 403,
        "method": "POST",
        "date": "25/06/2024 07:40:23",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "data": {},
    },
    {
        "url": "/admin/login?id=e",
        "ip": "111111",
        "reason": " antibot",
        "country": "fr",
        "status": 403,
        "method": "POST",
        "date": "25/06/2024 07:40:23",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "data": {},
    },
]

# Reoder reports to get in order "date", "ip", "country", "method", "url", "code", "user_agent", "reason", "data"
for report in reports:
    report["date"] = report.pop("date")
    report["ip"] = report.pop("ip")
    report["country"] = report.pop("country")
    report["method"] = report.pop("method")
    report["url"] = report.pop("url")
    report["code"] = report.pop("status")
    report["user_agent"] = report.pop("user_agent")
    report["reason"] = report.pop("reason")
    report["raw_data"] = report.pop("data")


def get_reports_filter(reports):

    if len(reports) <= 5:
        return []

    total_countries = ["all"]
    total_methods = ["all"]
    total_status = ["all"]
    total_reasons = ["all"]

    for report in reports:
        if report.get("country") and report.get("country") not in total_countries:
            total_countries.append(report.get("country"))

        if report.get("method") and report.get("method") not in total_methods:
            total_methods.append(report.get("method"))

        if report.get("status") and report.get("status") not in total_status:
            total_status.append(str(report.get("status")))

        if report.get("reason") and report.get("reason") not in total_reasons:
            total_reasons.append(report.get("reason"))

    filters = []

    filters.append(
        {
            "filter": "table",
            "filterName": "keyword",
            "type": "keyword",
            "value": "",
            "keys": ["url", "ip", "date", "user_agent", "raw_data"],
            "field": {
                "id": "reports-keyword",
                "value": "",
                "type": "text",
                "name": "reports-keyword",
                "label": "reports_search",
                "placeholder": "inp_keyword",
                "isClipboard": False,
                "popovers": [
                    {
                        "text": "reports_search_desc",
                        "iconName": "info",
                    },
                ],
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
            },
        },
    )

    if len(total_countries) > 1:
        filters.append(
            {
                "filter": "table",
                "filterName": "country",
                "type": "select",
                "value": "all",
                "keys": ["country"],
                "field": {
                    "id": "reports-country",
                    "value": "all",
                    "values": total_countries,
                    "name": "reports-country",
                    "onlyDown": True,
                    "label": "reports_country",
                    "popovers": [
                        {
                            "text": "reports_country_desc",
                            "iconName": "info",
                        },
                    ],
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                },
            },
        )

    if len(total_methods) > 1:
        filters.append(
            {
                "filter": "table",
                "filterName": "method",
                "type": "select",
                "value": "all",
                "keys": ["method"],
                "field": {
                    "id": "reports-method",
                    "value": "all",
                    "values": total_methods,
                    "name": "reports-method",
                    "onlyDown": True,
                    "label": "reports_method",
                    "popovers": [
                        {
                            "text": "reports_method_desc",
                            "iconName": "info",
                        },
                    ],
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                },
            },
        )

    if len(total_status) > 1:
        filters.append(
            {
                "filter": "table",
                "filterName": "status",
                "type": "select",
                "value": "all",
                "keys": ["status"],
                "field": {
                    "id": "reports-status",
                    "value": "all",
                    "values": total_status,
                    "name": "reports-status",
                    "onlyDown": True,
                    "label": "reports_status",
                    "popovers": [
                        {
                            "text": "reports_status_desc",
                            "iconName": "info",
                        },
                    ],
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                },
            },
        )

    if len(total_reasons) > 1:
        filters.append(
            {
                "filter": "table",
                "filterName": "reason",
                "type": "select",
                "value": "all",
                "keys": ["reason"],
                "field": {
                    "id": "reports-reason",
                    "value": "all",
                    "values": total_reasons,
                    "name": "reports-reason",
                    "onlyDown": True,
                    "label": "reports_reason",
                    "popovers": [
                        {
                            "text": "reports_reason_desc",
                            "iconName": "info",
                        },
                    ],
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                },
            },
        )
    return filters


def get_reports_list(reports):
    data = []
    # loop on each dict
    for report in reports:
        item = []
        for k, v in report.items():
            item.append(
                {
                    k: json.dumps(v) if isinstance(v, dict) else str(v),
                    "type": "Text",
                    "data": {
                        "text": json.dumps(v) if isinstance(v, dict) else str(v),
                    },
                }
            )

        data.append(item)

    return data


def reports_builder(reports, data=None):

    if not reports:
        return [
            {
                "type": "void",
                "widgets": [
                    {"type": "MessageUnmatch", "data": {"text": "reports_not_found"}}
                ],
            },
        ]

    filters = get_reports_filter(reports)

    reports_list = get_reports_list(reports)

    builder = [
        {
            "type": "card",
            "containerColumns": {"pc": 12, "tablet": 12, "mobile": 12},
            "widgets": [
                {
                    "type": "Title",
                    "data": {"title": "reports_title"},
                },
                {
                    "type": "Table",
                    "data": {
                        "title": "reports_table_title",
                        "minWidth": "lg",
                        "header": [
                            "reports_table_date",
                            "reports_table_ip",
                            "reports_table_country",
                            "reports_table_method",
                            "reports_table_url",
                            "reports_table_status_code",
                            "reports_table_cache_user_agent",
                            "reports_table_reason",
                            "reports_table_data",
                        ],
                        "positions": [1, 1, 1, 1, 2, 1, 2, 1, 2],
                        "items": reports_list,
                        "filters": filters,
                    },
                },
            ],
        }
    ]

    return builder


output = reports_builder(reports)

# store on a file
with open("reports.json", "w") as f:
    json.dump(output, f, indent=4)
