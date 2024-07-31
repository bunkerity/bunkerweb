import base64
import json
import copy
from typing import Union


def title_widget(title: str) -> dict:
    return {
        "type": "Title",
        "data": {"title": title},
    }


def table_widget(positions: list[int], header: list[str], items: list[dict], filters: list[dict], minWidth: str, title: str) -> dict:
    return {
        "type": "Table",
        "data": {
            "title": title,
            "minWidth": minWidth,
            "header": header,
            "positions": positions,
            "items": items,
            "filters": filters,
        },
    }


def stat_widget(
    link: str, containerColums: dict, title: Union[str, int], subtitle: Union[str, int], subtitle_color: str, stat: Union[str, int], icon_name: str
) -> dict:
    """Return a valid format to render a Stat widget"""
    return {
        "type": "card",
        "link": link,
        "containerColumns": containerColums,
        "widgets": [
            {
                "type": "Stat",
                "data": {
                    "title": title,
                    "subtitle": subtitle,
                    "subtitleColor": subtitle_color,
                    "stat": stat,
                    "iconName": icon_name,
                },
            }
        ],
    }


def instance_widget(containerColumns: dict, pairs: list[dict], status: str, title: Union[str, int], buttons: list[dict]) -> dict:
    """Return a valid format to render an Instance widget"""
    return {
        "type": "card",
        "containerColumns": containerColumns,
        "widgets": [
            {
                "type": "Instance",
                "data": {
                    "pairs": pairs,
                    "status": status,
                    "title": title,
                    "buttons": buttons,
                },
            }
        ],
    }
