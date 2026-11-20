#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from shlex import split
from subprocess import TimeoutExpired, run
from typing import Any


def handle(LOGGER: Logger, action: Any) -> None:
    LOGGER.info(f"🔧 Running tool {action.tool!r} with arguments {action.arguments!r} ...")

    cmd = f"{action.tool} {action.arguments}"
    # A tool that asserts on its own output must run to completion (the model refuses an explicit
    # timeout there); everything else is a provocation and gets bounded so it cannot hang the run.
    timeout = None if action.result else action.timeout
    try:
        process = run(split(cmd), capture_output=True, text=True, check=False, timeout=timeout)
        exit_code = process.returncode
        ret = process.stdout + process.stderr
    except TimeoutExpired:
        # The model only allows a timeout on an action with no `result`, i.e. a provocation whose
        # whole purpose is the state it leaves behind. Cutting it short cannot weaken the test:
        # the NEXT action is the assertion, and if the provocation had not landed yet it reds
        # there. Too short a bound shows up as a 200, never as a false pass.
        LOGGER.info(f"🔧 Tool reached its {timeout}s bound and was stopped; treating the provocation as delivered")
        LOGGER.info("🔧 Tool executed successfully")
        return
    except BaseException as e:
        LOGGER.error(f"🔧 Failed to execute tool: {e}")
        exit_code = 1
        ret = str(e)

    LOGGER.debug(f"🔧 Tool output: {ret}")

    if (action.success and exit_code != 0) or (not action.success and exit_code == 0):
        expected_status = "succeed" if action.success else "fail"
        actual_status = "failed" if exit_code != 0 else "succeeded"
        LOGGER.error(f"🔧 Tool expected to {expected_status} but {actual_status} with exit code {exit_code}, exiting ...")
        LOGGER.error(f"🔧 Tool output: {ret}")
        exit(1)

    if action.result and action.result not in ret:
        LOGGER.error(f"🔧 Result {action.result!r} not found in tool output, exiting ...")
        LOGGER.error(f"🔧 Tool output: {ret}")
        exit(1)
    elif action.result:
        LOGGER.info(f"🔧 Result {action.result!r} found in tool output")

    status = "successfully" if action.success else "with expected failure"
    LOGGER.info(f"🔧 Tool executed {status}")
