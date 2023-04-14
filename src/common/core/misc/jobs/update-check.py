#!/usr/bin/python3

from os import getenv
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

sys_path.extend(
    (
        "/usr/share/bunkerweb/deps/python",
        "/usr/share/bunkerweb/utils",
    )
)

from requests import get
from logger import setup_logger

logger = setup_logger("UPDATE-CHECK", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    current_version = Path("/usr/share/bunkerweb/VERSION").read_text().strip()

    latest_version = get(
        "https://raw.githubusercontent.com/bunkerity/bunkerweb/master/VERSION"
    ).text.strip()

    if current_version != latest_version:
        logger.warning(
            f"\n\n🚨 A new version of BunkerWeb is available: {latest_version} (current: {current_version}) 🚨\n\n",
        )
except:
    status = 2
    logger.error(f"Exception while running update-check.py :\n{format_exc()}")

sys_exit(status)
