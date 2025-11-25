#!/usr/bin/env python3

from json import dumps
from os import getenv, sep
from os.path import join
from re import compile as re_compile
from sys import exit as sys_exit, path as sys_path, version
from traceback import format_exc
from typing import Any, Dict

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import get_os_info  # type: ignore
from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

from requests import post

LOGGER = getLogger("ANONYMOUS-REPORT")
status = 0

try:
    # Check if anonymous reporting is enabled via environment variable.
    if getenv("SEND_ANONYMOUS_REPORT", "yes") != "yes":
        LOGGER.info("Skipping the sending of anonymous report (disabled)")
        sys_exit(status)

    JOB = Job(LOGGER, __file__)
    # Prevent sending multiple reports within the same day.
    if JOB.is_cached_file("last_report.json", "day"):
        LOGGER.info("Skipping the sending of anonymous report (already sent today)")
        sys_exit(0)

    # Retrieve only the necessary metadata about the current installation.
    data: Dict[str, Any] = JOB.db.get_metadata()

    # Ensure the 'is_pro' field is a simple yes/no string.
    data["is_pro"] = "yes" if data["is_pro"] else "no"

    # Only keep essential keys for the report to avoid sending any extra sensitive data.
    for key in data.copy():
        if key not in ("version", "integration", "database_version", "is_pro"):
            data.pop(key, None)

    # Retrieve non-default settings and additional configuration.
    db_config = JOB.db.get_non_default_settings(methods=True, with_drafts=True)
    services = db_config.get("SERVER_NAME", {"value": ""})["value"].split(" ")
    multisite = db_config.get("MULTISITE", {"value": "no"})["value"] == "yes"

    # Extract and simplify the database version using a regex.
    DATABASE_VERSION_REGEX = re_compile(r"(\d+(?:\.\d+)*)")
    database_version = DATABASE_VERSION_REGEX.search(data.pop("database_version")) or "Unknown"
    if database_version != "Unknown":
        database_version = database_version.group(1)

    # Normalize the integration string and create a simple database descriptor.
    data["integration"] = data["integration"].lower()
    data["database"] = f"{JOB.db.database_uri.split(':')[0].split('+')[0]}/{database_version}"
    data["service_number"] = str(len(services))
    data["draft_service_number"] = 0
    data["python_version"] = version.split(" ")[0]

    data["use_ui"] = "no"
    # --- Process UI Settings for Multisite or Singlesite configurations ---
    if multisite:
        for server in services:
            # Check if UI is enabled for any service.
            if db_config.get(f"{server}_USE_UI", db_config.get("USE_UI", {"value": "no"}))["value"] == "yes":
                data["use_ui"] = "yes"
            # Count the number of draft services.
            if db_config.get(f"{server}_IS_DRAFT", db_config.get("IS_DRAFT", {"value": "no"}))["value"] == "yes":
                data["draft_service_number"] += 1
    else:
        if db_config.get("USE_UI", {"value": "no"})["value"] == "yes":
            data["use_ui"] = "yes"
        if db_config.get("IS_DRAFT", {"value": "no"})["value"] == "yes":
            data["draft_service_number"] = 1

    data["draft_service_number"] = str(data["draft_service_number"])

    # --- Collect Plugin Information (only non-sensitive plugin IDs and versions) ---
    data["external_plugins"] = []
    data["pro_plugins"] = []
    for plugin in JOB.db.get_plugins():
        if plugin["type"] in ("external", "ui"):
            data["external_plugins"].append(f"{plugin['id']}/{plugin['version']}")
        elif plugin["type"] == "pro":
            data["pro_plugins"].append(f"{plugin['id']}/{plugin['version']}")

    # Add operating system information.
    data["os"] = get_os_info()

    # --- Process Non-Default Settings and Templates
    non_default_settings = {}
    used_templates = {}
    for setting, setting_data in db_config.items():
        if not isinstance(setting_data, dict):
            continue

        # Remove server-specific prefixes from settings names.
        stripped = setting
        for server in services:
            prefix = server + "_"
            if setting.startswith(prefix):
                stripped = setting[len(prefix) :]  # noqa: E203
                break
        non_default_settings[stripped] = non_default_settings.get(stripped, 0) + 1

        # Count usage of templates if the setting indicates one is used.
        for server in services:
            template_prefix = server + "_USE_TEMPLATE"
            if setting.startswith(template_prefix) and setting_data.get("value"):
                used_templates[setting_data["value"]] = used_templates.get(setting_data["value"], 0) + 1

    # Convert counts to strings for consistency.
    data["non_default_settings"] = {k: str(v) for k, v in non_default_settings.items()}
    data["used_templates"] = {k: str(v) for k, v in used_templates.items()}

    # Include the number of BunkerWeb instances (as a simple count).
    data["bw_instances_number"] = str(len(JOB.db.get_instances()))

    # --- Process Custom Configurations
    # Remove any fields that might reveal sensitive configuration details.
    custom_configs = JOB.db.get_custom_configs(with_drafts=True, with_data=False, as_dict=True)
    for config in custom_configs.values():
        # Indicate if the configuration is attached to a service without sending the actual service ID.
        config["attached_to_service"] = bool(config.pop("service_id", None))

        # Replace underscores with hyphens in the type field
        config["type"] = config["type"].replace("_", "-")

        # Remove fields that could reveal details about the configuration.
        for field in ("name", "checksum"):
            config.pop(field, None)

    data["custom_configs"] = list(custom_configs.values())

    # --- Process UI Users and Their Sessions
    # Collect UI users while removing any personally identifiable information.
    ui_users = JOB.db.get_ui_users()
    data["ui_users"] = []
    data["ui_users_sessions"] = {}
    for idx, user in enumerate(ui_users, start=1):
        # Retrieve sessions associated with the user.
        sessions = JOB.db.get_ui_user_sessions(user.username)

        # Only include non-sensitive user data.
        data["ui_users"].append(
            {
                "id": str(idx),
                "method": user.method,
                "admin": user.admin,
                "theme": user.theme,
                "totp_enabled": bool(getattr(user, "totp_secret", None)),
                "roles": [role.role_name for role in user.roles],
            }
        )

        # Process each session: only include non-sensitive data.
        data["ui_users_sessions"][str(idx)] = [(session["last_activity"] - session["creation_date"]).total_seconds() for session in sessions]

    # --- Sending the Report with 3 Retries ---
    for attempt in range(1, 4):
        try:
            resp = post("https://api.bunkerweb.io/data", json=data, headers={"User-Agent": f"BunkerWeb/{data['version']}"}, allow_redirects=True, timeout=10)
            # Handle rate limiting: if too many reports are sent, skip the report for today.
            if resp.status_code == 429:
                LOGGER.warning("Anonymous report has been sent too many times, skipping for today")
                sys_exit(2)
            else:
                resp.raise_for_status()
                break
        except BaseException as e:
            LOGGER.warning(f"Attempt {attempt} failed with error: {e}")

        if attempt == 3:
            LOGGER.error("Failed to send anonymous report after 3 attempts.")
            sys_exit(2)

    # Cache the report data to prevent duplicate reporting within the day.
    cached, err = JOB.cache_file("last_report.json", dumps(data, indent=4).encode())
    if not cached:
        LOGGER.error(f"Failed to cache last_report.json :\n{err}")
        status = 2
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running anonymous-report.py :\n{e}")

sys_exit(status)
