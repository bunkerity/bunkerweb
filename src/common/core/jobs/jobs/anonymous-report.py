#!/usr/bin/env python3

from json import dumps
from os import getenv, sep
from os.path import join
from pathlib import Path
from platform import machine
from re import compile as re_compile
from sys import exit as sys_exit, path as sys_path, version
from traceback import format_exc
from typing import Any, Dict

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import cache_file, is_cached_file  # type: ignore

from requests import post

logger = setup_logger("ANONYMOUS-REPORT", getenv("LOG_LEVEL", "INFO"))
status = 0

if getenv("SEND_ANONYMOUS_REPORT", "yes") != "yes":
    logger.info("Skipping the sending of anonymous report (disabled)")
    sys_exit(status)

anonymous_report_path = Path(sep, "var", "cache", "bunkerweb", "anonymous_report")
anonymous_report_path.mkdir(parents=True, exist_ok=True)
tmp_anonymous_report_path = Path(sep, "var", "tmp", "bunkerweb", "anonymous_report")
tmp_anonymous_report_path.mkdir(parents=True, exist_ok=True)


try:
    db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI", None), pool=False)
    if is_cached_file(anonymous_report_path.joinpath("last_report.json"), "day", db):
        logger.info("Skipping the sending of anonymous report (already sent today)")
        sys_exit(0)

    # ? Get version and integration of BunkerWeb
    data: Dict[str, Any] = db.get_metadata()
    db_config = db.get_config(methods=True, with_drafts=True)
    services = db_config.get("SERVER_NAME", {"value": ""})["value"].split(" ")
    multisite = db_config.get("MULTISITE", {"value": "no"})["value"] == "yes"

    DATABASE_VERSION_REGEX = re_compile(r"(\d+(?:\.\d+)*)")
    database_version = DATABASE_VERSION_REGEX.search(data.pop("database_version")) or "Unknown"
    if database_version != "Unknown":
        database_version = database_version.group(1)

    data["integration"] = data["integration"].lower()
    data["database"] = f"{db.database_uri.split(':')[0].split('+')[0]}/{database_version}"
    data["service_number"] = str(len(services))
    data["python_version"] = version.split(" ")[0]

    data["use_ui"] = "no"
    # Multisite case
    if multisite:
        for server in services:
            if db_config.get(f"{server}_USE_UI", db_config.get("USE_UI", {"value": "no"}))["value"] == "yes":
                data["use_ui"] = "yes"
                break
    # Singlesite case
    elif db_config.get("USE_UI", {"value": "no"})["value"] == "yes":
        data["use_ui"] = "yes"

    data["external_plugins"] = [f"{plugin['id']}/{plugin['version']}" for plugin in db.get_plugins(external=True)]
    data["os"] = {
        "name": "Linux",
        "version": "Unknown",
        "version_id": "Unknown",
        "version_codename": "Unknown",
        "id": "Unknown",
        "arch": machine(),
    }
    os_release = Path("/etc/os-release")
    if os_release.exists():
        for line in os_release.read_text().splitlines():
            if "=" not in line or line.split("=")[0].strip().lower() not in data["os"]:
                continue
            data["os"][line.split("=")[0].lower()] = line.split("=")[1].strip('"')

    data["non_default_settings"] = {}
    for setting, setting_data in db_config.items():
        if isinstance(setting_data, dict) and setting_data["method"] != "default":
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

    data["bw_instances_number"] = str(len(db.get_instances()))

    tmp_anonymous_report_path.joinpath("last_report.json").write_text(dumps(data, indent=4), encoding="utf-8")

    response = post("https://api.bunkerweb.io/data", json=data, headers={"User-Agent": f"BunkerWeb/{data['version']}"}, allow_redirects=True, timeout=10)
    response.raise_for_status()

    cached, err = cache_file(tmp_anonymous_report_path.joinpath("last_report.json"), anonymous_report_path.joinpath("last_report.json"), None, db)
except SystemExit as e:
    status = e.code
except:
    status = 2
    logger.error(f"Exception while running anonymous-report.py :\n{format_exc()}")

sys_exit(status)
