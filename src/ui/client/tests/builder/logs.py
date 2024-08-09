from .utils.widgets import title_widget


def logs_builder(files: list[str] = [], current_file: str = "", raw_data: str = "") -> str:

    if not files:
        builder = [
            {
                "type": "void",
                "widgets": [{"type": "MessageUnmatch", "data": {"text": "logs_no_files_found"}}],
            }
        ]
        return builder

    file_select = {
        "type": "Fields",
        "data": {
            "setting": {
                "id": "logs-select-file",
                "label": "logs_log_file",
                "inpType": "select",
                "name": "logs-select-file",
                "onlyDown": True,
                "value": current_file or "Select a file",
                "values": files,
                "columns": {
                    "pc": 4,
                    "tablet": 6,
                    "mobile": 12,
                },
                "maxBtnChars": 20,
                "attrs": {
                    "data-log": "true",
                },
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "logs_select_file_info",
                    },
                ],
            }
        },
    }

    if not raw_data:
        builder = [
            {
                "type": "card",
                "containerColumns": {"pc": 12, "tablet": 12, "mobile": 12},
                "widgets": [title_widget("logs_title"), file_select, {"type": "MessageUnmatch", "data": {"text": "logs_not_selected_or_not_found"}}],
            }
        ]
        return builder

    editor = {
        "type": "Fields",
        "data": {
            "setting": {
                "containerClass": "mt-4",
                "id": "logs-file-content",
                "label": "logs_file_content",
                "inpType": "editor",
                "name": "logs-file-content",
                "value": raw_data,
                "columns": {
                    "pc": 12,
                    "tablet": 12,
                    "mobile": 12,
                },
                "editorClass" : "min-h-[500px]",
            }
        },
    }

    builder = [
        {
            "type": "card",
            "containerColumns": {"pc": 12, "tablet": 12, "mobile": 12},
            "widgets": [title_widget("logs_title"), file_select, editor],
        }
    ]

    return builder
