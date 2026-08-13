#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

from httpx import Response

from .http_common import perform_request


def handle(LOGGER: Logger, action: Any) -> None:
    ctx = perform_request(LOGGER, action)
    response = ctx.response

    assert isinstance(response, Response), f"❌ Request failed:\n{response}"

    if action.raise_for_status:
        response.raise_for_status()

    if action.string is not None:
        if action.string not in response.text:
            LOGGER.error(f"🕸️ String {action.string} not found in response, exiting ...")
            exit(1)
        LOGGER.info(f"🕸️ String {action.string} found in response")
    elif action.not_string is not None:
        if action.not_string in response.text:
            LOGGER.error(f"🕸️ String {action.not_string} found in response, exiting ...")
            exit(1)
        LOGGER.info(f"🕸️ String {action.not_string} not found in response")
