import json
import base64

home = [
    {
        "type": "card",
        "link": "https://panel.bunkerweb.io/?utm_campaign=self&utm_source=ui#pro",
        "containerColumns": {"pc": 4, "tablet": 6, "mobile": 12},
        "widgets": [
            {
                "type": "Stat",
                "data": {"title": "home_version", "stat": "home_free", "subtitle": "home_upgrade_to_pro", "iconName": "key", "subtitleColor": "warning"},
            }
        ],
    },
    {
        "type": "card",
        "link": "https://github.com/bunkerity/bunkerweb",
        "containerColumns": {"pc": 4, "tablet": 6, "mobile": 12},
        "widgets": [
            {
                "type": "Stat",
                "data": {
                    "title": "home_version_number",
                    "stat": "1.6.0-beta",
                    "subtitle": "home_update_available",
                    "iconName": "wire",
                    "subtitleColor": "warning",
                },
            }
        ],
    },
    {
        "type": "card",
        "link": "instances",
        "containerColumns": {"pc": 4, "tablet": 6, "mobile": 12},
        "widgets": [{"type": "Stat", "data": {"title": "home_instances", "stat": 1, "subtitle": "home_total_number", "iconName": "box"}}],
    },
    {
        "type": "card",
        "link": "services",
        "containerColumns": {"pc": 4, "tablet": 6, "mobile": 12},
        "widgets": [{"type": "Stat", "data": {"title": "home_services", "stat": 2, "subtitle": "home_all_methods_included", "iconName": "disk"}}],
    },
    {
        "type": "card",
        "link": "plugins",
        "containerColumns": {"pc": 4, "tablet": 6, "mobile": 12},
        "widgets": [
            {"type": "Stat", "data": {"title": "home_plugins", "stat": 38, "subtitle": "home_no_error", "iconName": "puzzle", "subtitleColor": "success"}}
        ],
    },
]


# store on a file
with open("home.json", "w") as f:
    json.dump(home, f, indent=4)
output_base64_bytes = base64.b64encode(bytes(json.dumps(home), "utf-8"))
output_base64_string = output_base64_bytes.decode("ascii")

with open("home.txt", "w") as f:
    f.write(output_base64_string)