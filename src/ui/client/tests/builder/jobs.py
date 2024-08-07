from .utils.widgets import title_widget, table_widget


def jobs_builder(jobs):

    jobs_list = get_jobs_list(jobs)

    intervals = ["all"]

    # loop on each job
    for job in jobs_list:
        # loop on each item
        for item in job:
            # get the interval if not already in intervals
            if item.get("every") and item.get("every") not in intervals:
                intervals.append(item.get("every"))

    builder = [
        {
            "type": "card",
            "containerColumns": {"pc": 12, "tablet": 12, "mobile": 12},
            "widgets": [
                title_widget("jobs_title"),
                table_widget(
                    positions=[3, 2, 1, 1, 1, 1, 3],
                    header=[
                        "jobs_table_name",
                        "jobs_table_plugin_id",
                        "jobs_table_interval",
                        "jobs_table_reload",
                        "jobs_table_success",
                        "jobs_table_history",
                        "jobs_table_cache_downloadable",
                    ],
                    items=jobs_list,
                    filters=[
                        {
                            "filter": "table",
                            "filterName": "keyword",
                            "type": "keyword",
                            "value": "",
                            "keys": ["name", "plugin_id"],
                            "field": {
                                "id": "jobs-keyword",
                                "value": "",
                                "type": "text",
                                "name": "jobs-keyword",
                                "label": "jobs_search",
                                "placeholder": "inp_keyword",
                                "isClipboard": False,
                                "popovers": [
                                    {
                                        "text": "jobs_search_desc",
                                        "iconName": "info",
                                    },
                                ],
                                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                            },
                        },
                        {
                            "filter": "table",
                            "filterName": "every",
                            "type": "select",
                            "value": "all",
                            "keys": ["every"],
                            "field": {
                                "id": "jobs-every",
                                "value": "all",
                                "values": intervals,
                                "name": "jobs-every",
                                "onlyDown": True,
                                "label": "jobs_interval",
                                "popovers": [
                                    {
                                        "text": "jobs_interval_desc",
                                        "iconName": "info",
                                    },
                                ],
                                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                            },
                        },
                        {
                            "filter": "table",
                            "filterName": "reload",
                            "type": "select",
                            "value": "all",
                            "keys": ["reload"],
                            "field": {
                                "id": "jobs-last-run",
                                "value": "all",
                                "values": ["all", "success", "failed"],
                                "name": "jobs-last-run",
                                "onlyDown": True,
                                "label": "jobs_reload",
                                "popovers": [
                                    {
                                        "text": "jobs_reload_desc",
                                        "iconName": "info",
                                    },
                                ],
                                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                            },
                        },
                        {
                            "filter": "table",
                            "filterName": "success",
                            "type": "select",
                            "value": "all",
                            "keys": ["success"],
                            "field": {
                                "id": "jobs-success",
                                "value": "all",
                                "values": ["all", "success", "failed"],
                                "name": "jobs-success",
                                "onlyDown": True,
                                "label": "jobs_success",
                                "popovers": [
                                    {
                                        "text": "jobs_success_desc",
                                        "iconName": "info",
                                    },
                                ],
                                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                            },
                        },
                    ],
                    minWidth="lg",
                    title="jobs_table_title",
                ),
            ],
        }
    ]

    return builder


def get_jobs_list(jobs):
    data = []
    # loop on each dict
    for key, value in jobs.items():
        item = []
        item.append({"name": key, "type": "Text", "data": {"text": key}})
        # loop on each value
        for k, v in value.items():
            # override widget type for some keys
            if k in ("reload", "history"):
                is_success = v if k == "reload" else v[0].get("success")
                item.append(
                    {
                        k: "success" if is_success else "failed",
                        "type": "Icons",
                        "data": {
                            "iconName": "check" if is_success else "cross",
                        },
                    }
                )

                if k not in ("history"):
                    continue

            if k in ("plugin_id", "every"):
                item.append({k: v, "type": "Text", "data": {"text": v}})
                continue

            if k in ("history"):
                items = []
                for hist in v:
                    items.append(
                        [
                            {
                                "type": "Text",
                                "data": {
                                    "text": hist["start_date"],
                                },
                            },
                            {
                                "type": "Text",
                                "data": {
                                    "text": hist["end_date"],
                                },
                            },
                            {
                                "type": "Icons",
                                "data": {
                                    "iconName": "check" if hist["success"] else "cross",
                                },
                            },
                        ]
                    )

                item.append(
                    {
                        "type": "Button",
                        "data": {
                            "id": f"open-modal-history-{k}",
                            "text": "jobs_history",
                            "hideText": True,
                            "color": "blue",
                            "size": "normal",
                            "iconName": "document",
                            "iconColor": "white",
                            "modal": {
                                "widgets": [
                                    {"type": "Title", "data": {"title": key}},
                                    {"type": "Subtitle", "data": {"subtitle": "jobs_history_subtitle"}},
                                    {
                                        "type": "Table",
                                        "data": {
                                            "title": "jobs_history_table_title",
                                            "minWidth": "",
                                            "header": [
                                                "jobs_table_start_run",
                                                "jobs_table_end_run",
                                                "jobs_table_success",
                                            ],
                                            "positions": [5, 5, 2],
                                            "items": items,
                                        },
                                    },
                                    {
                                        "type": "ButtonGroup",
                                        "data": {
                                            "buttons": [
                                                {
                                                    "id": f"close-history-{k}",
                                                    "text": "action_close",
                                                    "color": "close",
                                                    "size": "normal",
                                                    "attrs": {"data-close-modal": ""},
                                                }
                                            ]
                                        },
                                    },
                                ]
                            },
                        },
                    }
                )

            if k in ("cache") and len(v) <= 0:
                item.append({k: v, "type": "Text", "data": {"text": ""}})
                continue

            if k in ("cache") and len(v) > 0:
                files = []
                # loop on each cache item
                for cache in v:
                    file_name = f"{cache['file_name']} [{cache['service_id']}]" if cache["service_id"] else f"{cache['file_name']}"
                    files.append(file_name)

                item.append(
                    {
                        k: " ".join(files),
                        "type": "Fields",
                        "data": {
                            "setting": {
                                "attrs": {
                                    "data-plugin-id": value.get("plugin_id", ""),
                                    "data-job-name": key,
                                },
                                "id": f"{key}_cache",
                                "label": f"{key}_cache",
                                "hideLabel": True,
                                "inpType": "select",
                                "name": f"{key}_cache",
                                "value": "download file",
                                "values": files,
                                "columns": {
                                    "pc": 12,
                                    "tablet": 12,
                                    "mobile": 12,
                                },
                                "overflowAttrEl": "data-table-body",
                                "containerClass": "table download-cache-file",
                                "maxBtnChars": 16,
                                "popovers": [
                                    {
                                        "iconName": "info",
                                        "text": "jobs_download_cache_file",
                                    },
                                ],
                            }
                        },
                    }
                )
                continue

        data.append(item)

    return data
