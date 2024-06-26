import json

no_bans = []


bans = [
    {
        "reason": "ui",
        "date": 1719393920,
        "ip": "127.0.0.1",
        "remain": "23 hours and 49 minutes",
        "term": "hour(s)",
        "ban_start": 1719393920,
        "ban_end": 1719393920,
    },
    {
        "reason": "ui",
        "date": 1719393920,
        "ip": "127.0.0.1",
        "remain": "23 hours and 49 minutes",
        "term": "day(s)",
        "ban_start": 1719393920,
        "ban_end": 1719393920,
    },
    {
        "reason": "core",
        "date": 1719393920,
        "ip": "127.0.0.1",
        "remain": "23 hours and 49 minutes",
        "term": "hour(s)",
        "ban_start": 1719393920,
        "ban_end": 1719393920,
    },
    {
        "reason": "ui",
        "date": 1719393920,
        "ip": "127.0.0.1",
        "remain": "23 hours and 49 minutes",
        "term": "hour(s)",
        "ban_start": 1719393920,
        "ban_end": 1719393920,
    },
    {
        "reason": "ui",
        "date": 1719393920,
        "ip": "127.0.0.1",
        "remain": "23 hours and 49 minutes",
        "term": "hour(s)",
        "ban_start": 1719393920,
        "ban_end": 1719393920,
    },
    {
        "reason": "ui",
        "date": 1719393920,
        "ip": "127.0.0.1",
        "remain": "23 hours and 49 minutes",
        "term": "hour(s)",
        "ban_start": 1719393920,
        "ban_end": 1719393920,
    },
]
# Reoder bans dict
for ban in bans:
    ban.pop("date")
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

    if len(total_reasons) > 2:
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

    if len(total_terms) > 2:
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


def get_bans_list(bans):
    data = []
    # loop on each dict
    id = 0
    for ban in bans:
        id += 1
        item = []
        item.append(
            {
                "select": False,
                "type": "Fields",
                "data": {
                    "setting": {
                        "columns": {"pc": 12, "tablet": 12, "mobile": 12},
                        "disabled": False,
                        "value": "no",
                        "inpType": "checkbox",
                        "id": f"select-ban-{id}",
                        "name": f"select-ban-{id}",
                        "label": f"select-ban-{id}",
                        "hideLabel": True,
                    },
                },
            }
        )
        for k, v in ban.items():

            if k in ("date", "ban_start", "ban_end"):
                item.append(
                    {
                        k: json.dumps(v) if isinstance(v, dict) else str(v),
                        "type": "Fields",
                        "data": {
                            "setting": {
                                "columns": {"pc": 12, "tablet": 12, "mobile": 12},
                                "disabled": True,
                                "value": v,
                                "inpType": "datepicker",
                                "id": f"datepicker-ban-{k}-{id}".replace("_", "-"),
                                "name": f"datepicker-ban-{k}-{id}".replace("_", "-"),
                                "label": f"datepicker-ban-{k}-{id}".replace("_", "-"),
                                "hideLabel": True,
                            },
                        },
                    }
                )
                continue

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


def bans_builder(bans):

    builder = [
        {
            "type": "void",
            "widgets": [{"type": "Button", "data": {"text": "bans_not_found"}}],
        },
    ]

    if not bans:
        builder.append(
            {
                "type": "void",
                "widgets": [
                    {"type": "MessageUnmatch", "data": {"text": "bans_not_found"}}
                ],
            }
        )
        return builder

    filters = get_bans_filter(bans)
    bans_list = get_bans_list(bans)

    bans_table = {
        "type": "card",
        "containerColumns": {"pc": 12, "tablet": 12, "mobile": 12},
        "widgets": [
            {
                "type": "Title",
                "data": {"title": "bans_title"},
            },
            {
                "type": "Table",
                "data": {
                    "title": "bans_table_title",
                    "minWidth": "xl",
                    "header": [
                        "bans_table_select",
                        "bans_table_ip",
                        "bans_table_reason",
                        "bans_table_ban_start",
                        "bans_table_ban_end",
                        "bans_table_remain",
                        "bans_table_term",
                    ],
                    "positions": [1, 1, 1, 3, 3, 2, 1],
                    "items": bans_list,
                    "filters": filters,
                },
            },
        ],
    }

    builder.append(bans_table)

    return builder


output = bans_builder(bans)
# output = bans_builder(no_bans)

# store on a file
with open("bans.json", "w") as f:
    json.dump(output, f, indent=4)
