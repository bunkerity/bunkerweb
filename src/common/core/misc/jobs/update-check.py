#!/usr/bin/env python3

from os import getenv, sep
from os.path import basename, join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get

from common_utils import get_version  # type: ignore
from logger import setup_logger  # type: ignore

LOGGER = setup_logger("UPDATE-CHECK", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    current_version = f"v{get_version().strip()}"

    response = get("https://github.com/bunkerity/bunkerweb/releases/latest", headers={"User-Agent": "BunkerWeb"}, allow_redirects=True, timeout=10)
    response.raise_for_status()

    latest_version = basename(response.url)
    if current_version != latest_version:
        LOGGER.warning(f"* \n* \n* 🚨 A new version of BunkerWeb is available: {latest_version} (current: {current_version}) 🚨\n* \n* ")
    else:
        LOGGER.info(f"Latest version is already installed: {current_version}")
except:
    status = 2
    LOGGER.error(f"Exception while running update-check.py :\n{format_exc()}")

sys_exit(status)
