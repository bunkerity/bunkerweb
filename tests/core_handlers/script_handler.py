#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from os import sep
from pathlib import Path
from subprocess import run
from typing import Any

# Where an example-backed run materialises the stack. A script ships next to the example
# it exercises, so that is where it runs from and how a bare filename resolves.
EXAMPLE_STACK_DIR = Path(sep, "tmp", "example-stack")
# The marker every OTHER consumer keys on: start.sh in five places and utils.sh's
# restart_stack. It is what the example cleanup removes (test-example-hook.sh) -- the
# directory is left behind. Keying the cwd on the directory alone therefore made every
# core spec's script action run from a leftover example stack instead of the repo root,
# for the whole rest of the session, so any repo-relative path in it failed.
EXAMPLE_STACK_MARKER = Path(sep, "tmp", "example_stack.txt")


def handle(LOGGER: Logger, action: Any) -> None:
    argv = list(action.script)
    cwd = EXAMPLE_STACK_DIR if EXAMPLE_STACK_MARKER.is_file() and EXAMPLE_STACK_DIR.is_dir() else None

    LOGGER.info(f"📜 Running script {' '.join(argv)!r}{f' from {cwd}' if cwd else ''} ...")

    try:
        process = run(argv, capture_output=True, text=True, check=False, cwd=cwd)
        exit_code = process.returncode
        output = process.stdout + process.stderr
    except BaseException as e:
        LOGGER.error(f"📜 Failed to execute script: {e}")
        exit_code = 1
        output = str(e)

    LOGGER.debug(f"📜 Script output: {output}")

    if (action.success and exit_code != 0) or (not action.success and exit_code == 0):
        expected = "succeed" if action.success else "fail"
        actual = "failed" if exit_code != 0 else "succeeded"
        LOGGER.error(f"📜 Script expected to {expected} but {actual} with exit code {exit_code}, exiting ...")
        LOGGER.error(f"📜 Script output: {output}")
        exit(1)

    if action.result and action.result not in output:
        LOGGER.error(f"📜 Result {action.result!r} not found in script output, exiting ...")
        LOGGER.error(f"📜 Script output: {output}")
        exit(1)
    elif action.result:
        LOGGER.info(f"📜 Result {action.result!r} found in script output")

    LOGGER.info("📜 Script executed successfully" if action.success else "📜 Script failed as expected")
