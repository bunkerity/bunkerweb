from .utils.widgets import instance_widget


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
                {"key": "instances_name", "value": instance.name},
                {"key": "instances_hostname", "value": instance.hostname},
                {"key": "instances_type", "value": instance.type},
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
