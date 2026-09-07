#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

from utils import run_command


def handle(LOGGER: Logger, integration: str, action: Any) -> None:
    LOGGER.info(f"🖲️ Running command {action.command!r} ...")

    # `tests/utils/k8s.py`'s exec stream yields output and no status, so `run_command` hands back a
    # hard-coded 0 on that arm. An `exit_code:` expectation there would assert nothing and pass
    # forever -- refuse it out loud instead of shipping a spec that only looks like it is checked.
    if action.exit_code != 0 and integration == "Kubernetes":
        LOGGER.error("🖲️ exit_code: cannot be asserted on the Kubernetes arm: the exec stream carries no status, exiting ...")
        exit(1)

    exit_code, ret = run_command(LOGGER, integration, action.command)
    LOGGER.debug(f"🖲️ Command output: {ret}")

    if exit_code != action.exit_code:
        LOGGER.error(f"🖲️ Command exited with {exit_code}, expected {action.exit_code}, exiting ...")
        LOGGER.error(f"🖲️ Command output: {ret}")
        exit(1)
    if action.exit_code != 0:
        LOGGER.info(f"🖲️ Command exited with {exit_code}, as expected")

    if action.result is not None:
        if action.result not in ret:
            LOGGER.error(f"🖲️ Result {action.result!r} not found in command output, exiting ...")
            LOGGER.error(f"🖲️ Command output: {ret}")
            exit(1)
        LOGGER.info(f"🖲️ Result {action.result!r} found in command output")

    if action.not_result is not None:
        if action.not_result in ret:
            LOGGER.error(f"🖲️ Result {action.not_result!r} found in command output but should not be, exiting ...")
            LOGGER.error(f"🖲️ Command output: {ret}")
            exit(1)
        LOGGER.info(f"🖲️ Result {action.not_result!r} not found in command output, as expected")
    LOGGER.info("🖲️ All commands ran successfully")
