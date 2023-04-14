#!/usr/bin/python3

import sys, traceback

sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")

import logger
import requests

status = 0

try:
    with open("/opt/bunkerweb/VERSION", "r") as f:
        current_version = f.read().strip()

    latest_version = requests.get(
        "https://raw.githubusercontent.com/bunkerity/bunkerweb/master/VERSION"
    ).text.strip()

    if current_version != latest_version:
        logger.log(
            "UPDATE-CHECK",
            "⚠️",
            "\n\n🚨 A new version of BunkerWeb is available: "
            + latest_version
            + " (current: "
            + current_version
            + ") 🚨\n\n",
        )
except:
    status = 2
    logger.log("UPDATE-CHECK", "❌", "Exception while running update-check.py :")
    print(traceback.format_exc())

sys.exit(status)
