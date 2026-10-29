#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

from httpx import Response

from .http_common import perform_request


def handle(LOGGER: Logger, action: Any) -> None:
    ctx = perform_request(LOGGER, action)
    response = ctx.response

    if isinstance(response, str):
        if action.status:
            LOGGER.error(f"📃 Request failed, expected status code {action.status}, exiting ...")
            exit(1)
        LOGGER.info("📃 Request failed, as expected")
        return

    assert isinstance(response, Response)
    if not action.status:
        LOGGER.error("📃 Request succeeded, expected failure, exiting ...")
        exit(1)
    elif action.status != response.status_code:
        LOGGER.error(f"📃 Status code {action.status} not found in response, instead found {response.status_code}, exiting ...")
        exit(1)
    LOGGER.info(f"📃 Status code {action.status} found in response")
