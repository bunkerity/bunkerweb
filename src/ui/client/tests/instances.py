import json
import base64


# Create instance class using keys from the instances list
class Instance:
    def __init__(self, _type, health, _id, hostname, name):
        self._type = _type
        self.health = health
        self._id = _id
        self.hostname = hostname
        self.name = name


instances = [
    Instance("manual", True, "bunkerweb", "bunkerweb", "bunkerweb"),
    Instance("manual", True, "bunkerweb", "bunkerweb", "bunkerweb"),
]


def instances_builder(instances: list):
    """
    It returns the home page in JSON format for the Vue.js builder
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

        component = {
            "type": "card",
            "containerColumns": {"pc": 6, "tablet": 6, "mobile": 12},
            "widgets": [
                {
                    "type": "Instance",
                    "data": {
                        "pairs": [
                            {"key": "instances_hostname", "value": instance.hostname},
                            {"key": "instances_type", "value": instance._type},
                            {"key": "instances_status", "value": "instances_active" if instance.health else "instances_inactive"},
                        ],
                        "status": "success" if instance.health else "error",
                        "title": instance.name,
                        "buttons": buttons,
                    },
                }
            ],
        }

        builder.append(component)

    return builder


builder = instances_builder(instances)

# store on a file
with open("instances.json", "w") as f:
    json.dump(builder, f)

output_base64_bytes = base64.b64encode(bytes(json.dumps(builder), "utf-8"))
output_base64_string = output_base64_bytes.decode("ascii")

with open("instances.txt", "w") as f:
    f.write(output_base64_string)
