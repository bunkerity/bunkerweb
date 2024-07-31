import base64
import json

from .utils.widgets import stat_widget


def home_builder(data: dict) -> str:
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
        stat=data.get("plugins_number"),
        icon_name="puzzle",
    )

    builder = [version_card, version_num_card, instances_card, services_card, plugins_card]

    return base64.b64encode(bytes(json.dumps(builder), "utf-8")).decode("ascii")
