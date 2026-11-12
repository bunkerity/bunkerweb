#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

from utils import execute_query


def handle_database(LOGGER: Logger, integration: str, database: str, step_data: Any) -> None:
    exit_code, output = execute_query(LOGGER, integration, database, step_data.query)  # type: ignore[arg-type]
    LOGGER.debug(f"🦊 SQL output: {output}")

    if exit_code != 0:
        LOGGER.error(f"🦊 SQL query {step_data.query!r} failed with exit code {exit_code}: {output}")
        exit(1)

    if step_data.result is not None and step_data.result not in output:
        LOGGER.error(f"🦊 Result {step_data.result!r} not found in the output of {step_data.query!r}: {output}")
        exit(1)
    LOGGER.info("🦊 SQL query ran successfully ✅")
