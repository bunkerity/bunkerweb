#!/usr/bin/env python3

from json import dumps
from os import getenv, sep
from os.path import join
from re import compile as re_compile
from sys import exit as sys_exit, path as sys_path, version
from typing import Any, Dict

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import get_os_info  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

from requests import post

LOGGER = setup_logger("ANONYMOUS-REPORT", getenv("LOG_LEVEL", "INFO"))
status = 0


try:
    if getenv("SEND_ANONYMOUS_REPORT", "yes") != "yes":
        LOGGER.info("Skipping the sending of anonymous report (disabled)")
        sys_exit(status)

    JOB = Job(LOGGER, __file__)
    if JOB.is_cached_file("last_report.json", "day"):
        LOGGER.info("Skipping the sending of anonymous report (already sent today)")
        sys_exit(0)

    # ? Get version and integration of BunkerWeb
    data: Dict[str, Any] = JOB.db.get_metadata()

    data["is_pro"] = "yes" if data["is_pro"] else "no"

    for key in data.copy():
        if key not in ("version", "integration", "database_version", "is_pro"):
            data.pop(key, None)

    db_config = JOB.db.get_non_default_settings(methods=True, with_drafts=True)
    services = db_config.get("SERVER_NAME", {"value": ""})["value"].split(" ")
    multisite = db_config.get("MULTISITE", {"value": "no"})["value"] == "yes"

    DATABASE_VERSION_REGEX = re_compile(r"(\d+(?:\.\d+)*)")
    database_version = DATABASE_VERSION_REGEX.search(data.pop("database_version")) or "Unknown"
    if database_version != "Unknown":
        database_version = database_version.group(1)

    data["integration"] = data["integration"].lower()
    data["database"] = f"{JOB.db.database_uri.split(':')[0].split('+')[0]}/{database_version}"
    data["service_number"] = str(len(services))
    data["draft_service_number"] = 0
    data["python_version"] = version.split(" ")[0]

    data["use_ui"] = "no"
    # Multisite case
    if multisite:
        for server in services:
            if db_config.get(f"{server}_USE_UI", db_config.get("USE_UI", {"value": "no"}))["value"] == "yes":
                data["use_ui"] = "yes"
            if db_config.get(f"{server}_IS_DRAFT", db_config.get("IS_DRAFT", {"value": "no"}))["value"] == "yes":
                data["draft_service_number"] += 1
    # Singlesite case
    else:
        if db_config.get("USE_UI", {"value": "no"})["value"] == "yes":
            data["use_ui"] = "yes"
        if db_config.get("IS_DRAFT", {"value": "no"})["value"] == "yes":
            data["draft_service_number"] = 1

    data["draft_service_number"] = str(data["draft_service_number"])
    data["external_plugins"] = []
    data["pro_plugins"] = []

    for plugin in JOB.db.get_plugins():
        if plugin["type"] in ("external", "ui"):
            data["external_plugins"].append(f"{plugin['id']}/{plugin['version']}")
        elif plugin["type"] == "pro":
            data["pro_plugins"].append(f"{plugin['id']}/{plugin['version']}")

    data["os"] = get_os_info()

    data["non_default_settings"] = {}
    for setting, setting_data in db_config.items():
        if isinstance(setting_data, dict):
            for server in services:
                if setting.startswith(server + "_"):
                    setting = setting[len(server) + 1 :]  # noqa: E203
                    if setting not in data["non_default_settings"]:
                        data["non_default_settings"][setting] = 1
                        break
                    data["non_default_settings"][setting] += 1
                    break
            else:
                if setting not in data["non_default_settings"]:
                    data["non_default_settings"][setting] = 1

    for key in data["non_default_settings"].copy():
        data["non_default_settings"][key] = str(data["non_default_settings"][key])

    data["bw_instances_number"] = str(len(JOB.db.get_instances()))

    resp = post("https://api.bunkerweb.io/data", json=data, headers={"User-Agent": f"BunkerWeb/{data['version']}"}, allow_redirects=True, timeout=10)

    if resp.status_code == 429:
        LOGGER.warning("Anonymous report has been sent too many times, skipping for today")
    else:
        resp.raise_for_status()

    cached, err = JOB.cache_file("last_report.json", dumps(data, indent=4).encode())
    if not cached:
        LOGGER.error(f"Failed to cache last_report.json :\n{err}")
        status = 2
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.error(f"Exception while running anonymous-report.py :\n{e}")

sys_exit(status)
