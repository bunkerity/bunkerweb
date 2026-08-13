#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

from utils import run_command


def handle(LOGGER: Logger, integration: str, action: Any) -> None:
    LOGGER.info(f"🖲️ Running command {action.command!r} ...")
    exit_code, ret = run_command(LOGGER, integration, action.command)
    LOGGER.debug(f"🖲️ Command output: {ret}")

    if exit_code != 0:
        LOGGER.error(f"🖲️ Command failed with exit code {exit_code}, exiting ...")
        LOGGER.error(f"🖲️ Command output: {ret}")
        exit(1)

    if action.result not in ret:
        LOGGER.error(f"🖲️ Result {action.result!r} not found in command output, exiting ...")
        LOGGER.error(f"🖲️ Command output: {ret}")
        exit(1)

    LOGGER.info(f"🖲️ Result {action.result!r} found in command output")
    LOGGER.info("🖲️ All commands ran successfully")
