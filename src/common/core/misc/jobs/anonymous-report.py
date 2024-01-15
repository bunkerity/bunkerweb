#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from json import dumps
from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Any, Dict

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("db",), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import setup_logger  # type: ignore
from database import Database  # type: ignore
from jobs import Job  # type: ignore

from requests import post

LOGGER = setup_logger("ANONYMOUS-REPORT", getenv("LOG_LEVEL", "INFO"))
JOB = Job()
status = 0

if getenv("SEND_ANONYMOUS_REPORT", "yes") != "yes":
    LOGGER.info("Skipping the sending of anonymous report (disabled)")
    sys_exit(status)

tmp_anonymous_report_path = Path(sep, "var", "tmp", "bunkerweb", "anonymous_report")
tmp_anonymous_report_path.mkdir(parents=True, exist_ok=True)


try:
    if JOB.is_cached_file("last_report.json", "day")[1]:
        LOGGER.info("Skipping the sending of anonymous report (already sent today)")
        sys_exit(0)

    # ? Get version and integration of BunkerWeb
    db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI", None))
    data: Dict[str, Any] = db.get_metadata()
    data["integration"] = data["integration"].lower()
    data["database"] = db.database_uri.split(":")[0].split("+")[0]
    data["service_number"] = str(len(getenv("SERVER_NAME", "").split(" ")))
    data["use_ui"] = getenv("USE_UI", "no")
    if data["use_ui"] == "no":
        for server in getenv("SERVER_NAME", "").split(" "):
            if getenv(f"{server}_USE_UI", "no") == "yes":
                data["use_ui"] = "yes"
                break
    data["external_plugins"] = [plugin["id"] for plugin in db.get_plugins(external=True)]
    tmp_anonymous_report_path.joinpath("last_report.json").write_text(dumps(data, indent=4), encoding="utf-8")

    # response = post("https://api.bunkerweb.io/data", json=data, headers={"User-Agent": f"BunkerWeb/{data['version']}"}, allow_redirects=True, timeout=10)
    response = post("http://api:8080/data", json=data, headers={"User-Agent": f"BunkerWeb/{data['version']}"}, allow_redirects=True, timeout=10)
    response.raise_for_status()

    cached, err = JOB.cache_file("last_report.json", tmp_anonymous_report_path.joinpath("last_report.json"))
except SystemExit as e:
    status = e.code
except:
    status = 2
    LOGGER.error(f"Exception while running anonymous-report.py :\n{format_exc()}")

sys_exit(status)
