#!/usr/bin/python3

from os import getenv, sep
from os.path import basename, join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("utils",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get
from logger import setup_logger  # type: ignore

logger = setup_logger("UPDATE-CHECK", getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    current_version = (
        f"v{Path('/usr/share/bunkerweb/VERSION').read_text(encoding='utf-8').strip()}"
    )

    response = get(
        "https://github.com/bunkerity/bunkerweb/releases/latest",
        allow_redirects=True,
        timeout=5,
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
