import json

no_bans = []


bans = [
    {
        "reason": "ui",
        "date": 1719393920,
        "ip": "127.0.0.1",
        "remain": "23 hours and 49 minutes",
        "term": "hour(s)",
        "ban_start": "26/06/2024 09:25:20",
        "ban_end": "27/06/2024 09:15:15",
    },
    {
        "reason": "ui",
        "date": 1719393920,
        "ip": "127.0.0.1",
        "remain": "23 hours and 49 minutes",
        "term": "hour(s)",
        "ban_start": "26/06/2024 09:25:20",
        "ban_end": "27/06/2024 09:15:15",
    },
]
# Reoder bans dict
for ban in bans:
    ban["ip"] = ban.pop("ip")
    ban["reason"] = ban.pop("reason")
    ban["ban_start"] = ban.pop("ban_start")
    ban["ban_end"] = ban.pop("ban_end")
    ban["remain"] = ban.pop("remain")
    ban["term"] = ban.pop("term")


def get_bans_filter(bans):

    if len(bans) <= 5:
        return []

    total_reasons = ["all"]
    total_terms = ["all"]

    for ban in bans:
        if ban.get("reason") and ban.get("reason") not in total_reasons:
            total_reasons.append(ban.get("reason"))

        if ban.get("term") and ban.get("term") not in total_terms:
            total_terms.append(ban.get("term"))

    filters = []

    filters.append(
        {
            "filter": "table",
            "filterName": "keyword",
            "type": "keyword",
            "value": "",
            "keys": ["ip", "ban_start", "ban_end"],
            "field": {
                "id": "bans-keyword",
                "value": "",
                "type": "text",
                "name": "bans-keyword",
                "label": "bans_search",
                "placeholder": "inp_keyword",
                "isClipboard": False,
                "popovers": [
                    {
                        "text": "bans_search_desc",
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
                    "id": "bans-reason",
                    "value": "all",
                    "values": total_reasons,
                    "name": "bans-reason",
                    "onlyDown": True,
                    "label": "bans_reason",
                    "popovers": [
                        {
                            "text": "bans_reason_desc",
                            "iconName": "info",
                        },
                    ],
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                },
            },
        )

        if len(total_terms) > 1:
            filters.append(
                {
                    "filter": "table",
                    "filterName": "term",
                    "type": "select",
                    "value": "all",
                    "keys": ["term"],
                    "field": {
                        "id": "bans-terms",
                        "value": "all",
                        "values": total_terms,
                        "name": "bans-terms",
                        "onlyDown": True,
                        "label": "bans_terms",
                        "popovers": [
                            {
                                "text": "bans_terms_desc",
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


def get_reports_details(details):
    return {
        "type": "card",
        "containerColumns": {"pc": 4, "tablet": 6, "mobile": 12},
        "widgets": [
            {
                "type": "Title",
                "data": {"title": "dashboard_details"},
            },
            {
                "type": "ListPairs",
                "data": {
                    "pairs": [
                        {"key": "reports_total", "value": details.get("total_reports")},
                        {"key": "reports_top_status", "value": details.get("top_code")},
                        {
                            "key": "reports_top_reason",
                            "value": details.get("top_reason"),
                        },
                    ],
                },
            },
        ],
    }


def reports_builder(reports, details=None):

    if not reports:
        return [
            {
                "type": "void",
                "widgets": [
                    {"type": "MessageUnmatch", "data": {"text": "reports_not_found"}}
                ],
            },
        ]

    details = get_reports_details(details)

    filters = get_bans_filter(reports)
    reports_list = get_reports_list(reports)

    reports_table = {
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
                    "minWidth": "xl",
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

    builder = [details, reports_table]

    return builder


# output = reports_builder(reports)
output = reports_builder(no_bans)

# store on a file
with open("reports.json", "w") as f:
    json.dump(output, f, indent=4)
