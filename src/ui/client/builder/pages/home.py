from .utils.widgets import stat_widget


def home_builder(data: dict) -> str:
    """
    It returns the needed format from data to render the home page in JSON format for the Vue.js builder
    """
    version_card = stat_widget(
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
        subtitleColor="success" if data.get("is_pro_version") else "warning",
        stat=(
            "home_pro"
            if data.get("is_pro_version")
            else (
                "home_pro_locked"
                if data.get("pro_status") == "active" and data.get("pro_overlapped")
                else "home_expired" if data.get("pro_status") == "expired" else "home_suspended" if data.get("pro_status") == "suspended" else "home_free"
            )
        ),
        iconName="crown" if data.get("is_pro_version") else "key",
    )

    version_num_card = stat_widget(
        title="home_version_number",
        subtitle=(
            "home_couldnt_find_remote"
            if not data.get("remote_version")
            else "home_latest_version" if data.get("remote_version") and data.get("check_version") else "home_update_available"
        ),
        subtitleColor=("error" if not data.get("remote_version") else "success" if data.get("remote_version") and data.get("check_version") else "warning"),
        stat=data.get("version"),
        iconName="wire",
    )

    instances_card = stat_widget(
        title="home_instances",
        subtitle="home_total_number",
        subtitleColor="info",
        stat=data.get("instances_number"),
        iconName="box",
    )

    services_card = stat_widget(
        title="home_services",
        subtitle="home_all_methods_included",
        subtitleColor="info",
        stat=data.get("services_number"),
        iconName="disk",
    )

    plugins_card = stat_widget(
        title="home_plugins",
        subtitle="home_errors_found" if data.get("plugins_errors") > 0 else "home_no_error",
        subtitleColor="error" if data.get("plugins_errors") > 0 else "success",
        stat=data.get("plugins_number"),
        iconName="puzzle",
    )

    builder = [
        {
            "type": "card",
            "link": "https://panel.bunkerweb.io/?utm_campaign=self&utm_source=ui#pro",
            "containerColumns": {"pc": 4, "tablet": 6, "mobile": 12},
            "widgets": [version_card],
        },
        {
            "type": "card",
            "link": "https://github.com/bunkerity/bunkerweb",
            "containerColumns": {"pc": 4, "tablet": 6, "mobile": 12},
            "widgets": [version_num_card],
        },
        {
            "type": "card",
            "link": "instances",
            "containerColumns": {"pc": 4, "tablet": 6, "mobile": 12},
            "widgets": [instances_card],
        },
        {
            "type": "card",
            "link": "services",
            "containerColumns": {"pc": 4, "tablet": 6, "mobile": 12},
            "widgets": [services_card],
        },
        {
            "type": "card",
            "link": "plugins",
            "containerColumns": {"pc": 4, "tablet": 6, "mobile": 12},
            "widgets": [plugins_card],
        },
    ]
    print(builder, flush=True)
    return builder
