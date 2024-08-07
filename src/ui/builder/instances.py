from os.path import join, sep
from sys import path as sys_path
from typing import List

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from src.instance import Instance

from builder.utils.widgets import instance_widget


def instances_builder(instances: List[Instance]) -> str:
    """
    It returns the needed format from data to render the instances page in JSON format for the Vue.js builder
    """
    builder = []

    for instance in instances:
        # setup actions buttons
        actions = (
            ["restart", "stop"]
            if instance.hostname in ("localhost", "127.0.0.1") and instance.status == "up"
            else (
                ["reload", "stop"]
                if instance.hostname not in ("localhost", "127.0.0.1") and instance.status == "up"
                else ["start"] if instance.hostname in ("localhost", "127.0.0.1") and instance.status != "up" else []
            )
        )

        buttons = [
            {
                "attrs": {
                    "data-submit-form": f"""{{"INSTANCE_ID" : "{instance.hostname}", "operation" : "{action}" }}""",
                },
                "text": f"action_{action}",
                "color": "success" if action == "start" else "error" if action == "stop" else "warning",
            }
            for action in actions
        ]

        instance = instance_widget(
            containerColumns={"pc": 6, "tablet": 6, "mobile": 12},
            pairs=[
                {"key": "instances_method", "value": instance.method},
                {"key": "instances_creation_date", "value": instance.creation_date.strftime("%d-%m-%Y %H:%M:%S")},
                {"key": "instances_last_seen", "value": instance.last_seen.strftime("%d-%m-%Y %H:%M:%S")},
            ],
            status="success" if instance.status == "up" else "error",
            title=instance.hostname,
            buttons=buttons,
        )

        builder.append(instance)

    return builder
