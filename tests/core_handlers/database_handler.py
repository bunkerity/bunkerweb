#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

from utils import execute_query


def handle(LOGGER: Logger, integration: str, database: str, action: Any) -> None:
    LOGGER.info(f"🗃️ Running SQL query {action.query!r} ...")
    exit_code, ret = execute_query(LOGGER, integration, database, action.query)
    LOGGER.debug(f"🗃️ SQL query output: {ret}")

    if exit_code != 0:
        LOGGER.error(f"🗃️ SQL query failed with exit code {exit_code}, exiting ...")
        LOGGER.error(f"🗃️ SQL query output: {ret}")
        exit(1)

    if action.result is not None:
        if action.result not in ret:
            LOGGER.error(f"🗃️ Result {action.result!r} not found in SQL query output, exiting ...")
            LOGGER.error(f"🗃️ SQL query output: {ret}")
            exit(1)

        LOGGER.info(f"🗃️ Result {action.result!r} found in SQL query output")
    LOGGER.info("🗃️ All SQL queries ran successfully")
