import base64
import json


def stat_widget(link, containerColums, title, subtitle, subtitle_color, stat, icon_name):
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


def instance_widget(containerColumns, pairs, status, title, buttons):
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


def home_builder(data):
    """
    It returns the needed format from data to render the home page in JSON format for the Vue.js builder
    """
    version_card = stat_widget(
        link="https://panel.bunkerweb.io/?utm_campaign=self&utm_source=ui#pro",
        containerColums={"pc": 4, "tablet": 6, "mobile": 12},
        title="home_version",
        subtitle=(
            "home_all_features_available"
            if data.get("is_pro_version")
            else (
                "home_awaiting_compliance"
                if data.get("pro_status") == "active" and data.get("pro_overlapped")
                else (
                    "home_renew_license"
                    if data.get("pro_status") == "expired"
                    else "home_talk_to_team" if data.get("pro_status") == "suspended" else "home_upgrade_to_pro"
                )
            )
        ),
        subtitle_color="success" if data.get("is_pro_version") else "warning",
        stat=(
            "home_pro"
            if data.get("is_pro_version")
            else (
                "home_pro_locked"
                if data.get("pro_status") == "active" and data.get("pro_overlapped")
                else "home_expired" if data.get("pro_status") == "expired" else "home_suspended" if data.get("pro_status") == "suspended" else "home_free"
            )
        ),
        icon_name="crown" if data.get("is_pro_version") else "key",
    )

    version_num_card = stat_widget(
        link="https://github.com/bunkerity/bunkerweb",
        containerColums={"pc": 4, "tablet": 6, "mobile": 12},
        title="home_version_number",
        subtitle=(
            "home_couldnt_find_remote"
            if not data.get("remote_version")
            else "home_latest_version" if data.get("remote_version") and data.get("check_version") else "home_update_available"
        ),
        subtitle_color=("error" if not data.get("remote_version") else "success" if data.get("remote_version") and data.get("check_version") else "warning"),
        stat=data.get("version"),
        icon_name="wire",
    )

    instances_card = stat_widget(
        link="instances",
        containerColums={"pc": 4, "tablet": 6, "mobile": 12},
        title="home_instances",
        subtitle="home_total_number",
        subtitle_color="info",
        stat=data.get("instances_number"),
        icon_name="box",
    )

    services_card = stat_widget(
        link="services",
        containerColums={"pc": 4, "tablet": 6, "mobile": 12},
        title="home_services",
        subtitle="home_all_methods_included",
        subtitle_color="info",
        stat=data.get("services_number"),
        icon_name="disk",
    )

    plugins_card = stat_widget(
        link="plugins",
        containerColums={"pc": 4, "tablet": 6, "mobile": 12},
        title="home_plugins",
        subtitle="home_errors_found" if data.get("plugins_errors") > 0 else "home_no_error",
        subtitle_color="error" if data.get("plugins_errors") > 0 else "success",
        stat="42",
        icon_name="puzzle",
    )

    builder = [version_card, version_num_card, instances_card, services_card, plugins_card]

    return base64.b64encode(bytes(json.dumps(builder), "utf-8")).decode("ascii")


def instances_builder(instances: list):
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
