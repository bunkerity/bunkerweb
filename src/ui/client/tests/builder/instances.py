import base64
import json

from .utils.widgets import instance_widget


def instances_builder(instances: list) -> str:
    """
    It returns the needed format from data to render the instances page in JSON format for the Vue.js builder
    """
    builder = []

    for instance in instances:
        # setup actions buttons
        actions = (
            ["restart", "stop"]
            if instance._type == "local" and instance.health
            else (
                ["reload", "stop"]
                if not instance._type == "local" and instance.health
                else ["start"] if instance._type == "local" and not instance.health else []
            )
        )

        buttons = [
            {
                "attrs": {
                    "data-submit-form": f"""{{"INSTANCE_ID" : "{instance._id}", "operation" : "{action}" }}""",
                },
                "text": f"action_{action}",
                "color": "success" if action == "start" else "error" if action == "stop" else "warning",
            }
            for action in actions
        ]

        instance = instance_widget(
            containerColumns={"pc": 6, "tablet": 6, "mobile": 12},
            pairs=[
                {"key": "instances_hostname", "value": instance.hostname},
                {"key": "instances_type", "value": instance._type},
                {"key": "instances_status", "value": "instances_active" if instance.health else "instances_inactive"},
            ],
            status="success" if instance.health else "error",
            title=instance.name,
            buttons=buttons,
        )

        builder.append(instance)

    return base64.b64encode(bytes(json.dumps(builder), "utf-8")).decode("ascii")
