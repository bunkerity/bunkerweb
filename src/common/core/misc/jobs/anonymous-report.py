#!/usr/bin/python3

from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Any, Dict

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("utils",),
        ("db",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore

from requests import post

logger = setup_logger("ANONYMOUS-REPORT", getenv("LOG_LEVEL", "INFO"))
status = 0

if getenv("SEND_ANONYMOUS_REPORT", "yes") != "yes":
    logger.info("Skipping the sending of anonymous report (disabled)")
    sys_exit(status)

try:
    db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI", None), pool=False)
    # ? Get version and integration of BunkerWeb
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

    response = post(
        "https://api.bunkerweb.io/data",
        json=data,
        headers={"User-Agent": f"BunkerWeb/{data['version']}"},
        allow_redirects=True,
        timeout=10,
    )
    response.raise_for_status()
except:
    status = 2
    logger.error(f"Exception while running anonymous-report.py :\n{format_exc()}")

sys_exit(status)
