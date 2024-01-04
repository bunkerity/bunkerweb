# -*- coding: utf-8 -*-
from utils import create_action_format, log_format
from logging import Logger
from os.path import join, sep
from os import _exit
from sys import path as sys_path
import os
from ui import UiConfig
from pathlib import Path
from contextlib import suppress
from signal import SIGINT, signal, SIGTERM
from subprocess import PIPE, Popen, call

deps_path = join(sep, "usr", "share", "bunkerweb", "utils")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from logger import setup_logger  # type: ignore

LOGGER: Logger = setup_logger("UI")

UI_CONFIG = UiConfig("ui", **os.environ)
CORE_API = UI_CONFIG.CORE_ADDR


def stop_ui():
    Path(sep, "var", "run", "bunkerweb", "ui.pid").unlink(missing_ok=True)
    Path(sep, "var", "tmp", "bunkerweb", "ui.healthy").unlink(missing_ok=True)

def stop_log():
    LOGGER.warn(log_format("warn", "500", "", "EXIT ON FAILURE."))
    create_action_format("error", "500", "UI setup exception", "EXIT ON FAILURE.", ["exception", "ui", "setup"])


# Exception on main.py when we are starting UI
class setupUIException(Exception):
    def __init__(self, log_type, msg, send_action=True):
        # We can specify error or exception (traceback)
        if log_type == "error":
            LOGGER.error(log_format("exception", "500", "", msg))

        if log_type == "exception":
            LOGGER.exception(log_format("exception", "500", "", msg))

        # Try to store exception as action on core to keep track
        with suppress(BaseException):
            if send_action:
                create_action_format("error", "500", "UI setup exception", "Impossible to execute UI properly.", ["exception", "ui", "setup"])

        # Exit or not on failure
        if not UI_CONFIG.EXIT_ON_FAILURE or UI_CONFIG.EXIT_ON_FAILURE == "yes":
            LOGGER.warn(log_format("warn", "500", "", "Error while UI setup and exit on failure. Impossible to access UI."))
            if send_action:
                create_action_format("error", "500", "UI setup exception", "Error while UI setup and exit on failure. Impossible to access UI.", ["exception", "ui", "setup"])
            signal(SIGINT, stop_log)
            signal(SIGTERM, stop_log)
            _exit(500)

        else:
            LOGGER.warn(log_format("warn", "500", "", "Error while UI setup but keep running on failure. UI could not run correctly."))
            if send_action:
                create_action_format("error", "500", "UI setup exception", "Error while UI setup but keep running on failure. UI could not run correctly.", ["exception", "ui", "setup"])

        stop_ui()
