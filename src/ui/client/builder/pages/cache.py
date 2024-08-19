from .utils.widgets import file_manager_widget, title_widget, subtitle_widget, unmatch_widget
from typing import Optional


def fallback_message(msg: str, display: Optional[list] = None) -> dict:

    return {
        "type": "void",
        "display": display if display else [],
        "widgets": [
            unmatch_widget(text=msg),
        ],
    }


def cache_builder(file_manager: Optional[dict] = None) -> str:

    if file_manager is None or (isinstance(file_manager, dict) and len(file_manager) == 0):
        return [fallback_message("cache_not_found")]

    return [
        {
            "type": "card",
            "widgets": [
                title_widget("cache_title"),  # keep it (a18n)
                subtitle_widget("cache_subtitle"),  # keep it (a18n)
                file_manager_widget(
                    data=file_manager,
                ),
            ],
        },
    ]
