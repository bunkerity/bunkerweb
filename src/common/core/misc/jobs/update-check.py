#!/usr/bin/python3

from os import getenv
from os.path import basename
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
    current_version = f"v{Path('/usr/share/bunkerweb/VERSION').read_text().strip()}"

    response = get(
        "https://github.com/bunkerity/bunkerweb/releases/latest",
        allow_redirects=True,
    )
    response.raise_for_status()

    latest_version = basename(response.url)
    if current_version != latest_version:
        logger.warning(
            f"* \n* \n* 🚨 A new version of BunkerWeb is available: {latest_version} (current: {current_version}) 🚨\n* \n* ",
        )
    else:
        logger.info(f"Latest version is already installed: {current_version}")
except:
    status = 2
    logger.error(f"Exception while running update-check.py :\n{format_exc()}")

sys_exit(status)
