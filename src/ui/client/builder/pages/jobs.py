from .utils.widgets import (
    button_widget,
    button_group_widget,
    title_widget,
    subtitle_widget,
    text_widget,
    tabulator_widget,
    input_widget,
    icons_widget,
    regular_widget,
    select_widget,
    unmatch_widget,
)
from .utils.table import add_column
from .utils.format import get_fields_from_field
from typing import Optional

columns = [
    add_column(title="Name", field="name", formatter="text"),
    add_column(title="Plugin id", field="plugin_id", formatter="text"),
    add_column(title="Interval", field="every", formatter="text"),
    add_column(title="reload", field="reload", formatter="icons"),
    add_column(title="success", field="success", formatter="icons"),
    add_column(title="history", field="history", formatter="buttongroup"),
    add_column(title="Cache", field="cache", formatter="buttongroup"),
]


def jobs_filter(intervals: Optional[list] = None) -> list:  # healths = "up", "down", "loading"

    filters = [
        {
            "type": "=",
            "fields": ["every"],
            "setting": {
                "id": "select-every",
                "name": "select-every",
                "label": "jobs_interval",  # keep it (a18n)
                "value": "all",  # keep "all"
                "values": intervals,
                "inpType": "select",
                "onlyDown": True,
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "jobs_interval_desc",
                    }
                ],
                "fieldSize": "sm",
            },
        },
        {
            "type": "=",
            "fields": ["reload"],
            "setting": {
                "id": "select-reload",
                "name": "select-reload",
                "label": "jobs_reload",  # keep it (a18n)
                "value": "all",  # keep "all"
                "values": ["all", "success", "failed"],
                "inpType": "select",
                "onlyDown": True,
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "jobs_reload_desc",
                    }
                ],
                "fieldSize": "sm",
            },
        },
        {
            "type": "=",
            "fields": ["success"],
            "setting": {
                "id": "select-success",
                "name": "select-success",
                "label": "jobs_success",  # keep it (a18n)
                "value": "all",  # keep "all"
                "values": ["all", "success", "failed"],
                "inpType": "select",
                "onlyDown": True,
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "jobs_success_desc",
                    }
                ],
                "fieldSize": "sm",
            },
        },
    ]

    if intervals is not None and (isinstance(intervals, list) and len(intervals) > 0):
        filters = [
            {
                "type": "like",
                "fields": ["name", "plugin_id"],
                "setting": {
                    "id": "input-search",
                    "name": "input-search",
                    "label": "jobs_search",  # keep it (a18n)
                    "placeholder": "inp_keyword",  # keep it (a18n)
                    "value": "",
                    "inpType": "input",
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    "popovers": [
                        {
                            "iconName": "info",
                            "text": "jobs_search_desc",
                        }
                    ],
                    "fieldSize": "sm",
                },
            },
        ] + filters

    return filters


def jobs_builder(jobs):

    intervals = ["all"]

    # loop on each job
    for name, value in jobs.items():
        if value.get("every") and value.get("every") not in intervals:
            intervals.append(value.get("every"))

    jobs_list = get_jobs_list(jobs)

    builder = [
        {
            "type": "card",
            "containerColumns": {"pc": 12, "tablet": 12, "mobile": 12},
            "widgets": [
                title_widget("jobs_title"),
                tabulator_widget(
                    id="table-list-jobs",
                    layout="fitColumns",
                    columns=columns,
                    items=jobs_list,
                    filters=jobs_filter(intervals),
                ),
            ],
        }
    ]

    return builder


def get_jobs_list(jobs):
    data = []
    # loop on each dict
    for key, value in jobs.items():
        item = {"name": text_widget(text=key)["data"]}

        # loop on each value
        for k, v in value.items():
            # override widget type for some keys
            if k in ("reload", "history"):
                is_success = v if k == "reload" else v[0].get("success")
                item["reload" if k == "reload" else "success"] = icons_widget(
                    iconName="check" if is_success else "cross", value="success" if is_success else "failed"
                )["data"]

                if k not in ("history"):
                    continue

            if k in ("plugin_id", "every"):
                item[k] = text_widget(text=v)["data"]
                continue

            if k in ("history"):
                history_columns = [
                    add_column(title="Start date", field="start_date", formatter="text"),
                    add_column(title="End date", field="end_date", formatter="text"),
                    add_column(title="Success", field="success", formatter="icons"),
                ]

                items = []
                for hist in v:
                    items.append(
                        {
                            "start_date": text_widget(text=hist["start_date"])["data"],
                            "end_date": text_widget(text=hist["end_date"])["data"],
                            "success": icons_widget(iconName="check" if hist["success"] else "cross", value="success" if hist["success"] else "failed")["data"],
                        }
                    )

                item["history"] = button_group_widget(
                    buttons=[
                        button_widget(
                            id=f"open-modal-history-{key}",
                            text="jobs_history",
                            hideText=True,
                            color="success",
                            size="normal",
                            iconName="eye",
                            iconColor="white",
                            modal={
                                "widgets": [
                                    title_widget(title="jobs_history_title"),
                                    tabulator_widget(
                                        id=f"history-{key}",
                                        columns=history_columns,
                                        items=items,
                                        layout="fitDataFill",
                                    ),
                                    button_group_widget(
                                        buttons=[
                                            button_widget(
                                                id=f"close-history-{key}",
                                                text="action_close",
                                                color="close",
                                                size="normal",
                                                attrs={"data-close-modal": ""},
                                            )
                                        ]
                                    ),
                                ]
                            },
                        )
                    ]
                )["data"]

            if k in ("cache") and len(v) <= 0:
                item["cache"] = button_group_widget(
                    buttons=[
                        button_widget(
                            id=f"open-modal-cache-{key}",
                            text="jobs_no_cache",
                            hideText=True,
                            color="info",
                            size="normal",
                            iconName="document",
                            iconColor="white",
                            containerClass="hidden",
                        )
                    ]
                )["data"]
                continue

            if k in ("cache") and len(v) > 0:
                files = []
                # loop on each cache item
                for index, cache in enumerate(v):
                    file_name = f"{cache['file_name']} [{cache['service_id']}]" if cache["service_id"] else f"{cache['file_name']}"
                    files.append(
                        {
                            "id": text_widget(text=index)["data"],
                            "filename": text_widget(text=file_name)["data"],
                            "download": button_group_widget(
                                buttonGroupClass="button-group-table-content",
                                buttons=[
                                    button_widget(
                                        id=f"{key}-cache",
                                        text=f"action_download",
                                        hideText=True,
                                        color="info",
                                        size="normal",
                                        iconName="download",
                                        iconColor="white",
                                        attrs={
                                            "data-plugin-id": value.get("plugin_id", ""),
                                            "data-job-name": key,
                                        },
                                    ),
                                ],
                            )["data"],
                        }
                    )

                item["cache"] = button_group_widget(
                    buttons=[
                        button_widget(
                            id=f"open-modal-cache-{key}",
                            text="jobs_cache",
                            hideText=True,
                            color="info",
                            size="normal",
                            iconName="document",
                            iconColor="white",
                            modal={
                                "widgets": [
                                    title_widget(title="jobs_history_title"),
                                    tabulator_widget(
                                        id=f"cache-{key}",
                                        columns=[
                                            add_column(title="id", field="id", formatter="text", maxWidth=80),
                                            add_column(title="File name", field="filename", formatter="text"),
                                            add_column(title="Download", field="download", formatter="buttongroup"),
                                        ],
                                        items=files,
                                        layout="fitDataFill",
                                    ),
                                    button_group_widget(
                                        buttons=[
                                            button_widget(
                                                id=f"close-history-{key}",
                                                text="action_close",
                                                color="close",
                                                size="normal",
                                                attrs={"data-close-modal": ""},
                                            )
                                        ]
                                    ),
                                ]
                            },
                        )
                    ]
                )["data"]
                continue

        print(item)
        data.append(item)

    return data
