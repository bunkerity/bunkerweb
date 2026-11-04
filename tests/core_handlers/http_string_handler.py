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

    text = response.text.casefold() if action.ignore_case else response.text

    if action.string is not None:
        needle = action.string.casefold() if action.ignore_case else action.string
        if needle not in text:
            LOGGER.error(f"🕸️ String {action.string} not found in response, exiting ...")
            exit(1)
        LOGGER.info(f"🕸️ String {action.string} found in response")
    elif action.not_string is not None:
        needle = action.not_string.casefold() if action.ignore_case else action.not_string
        if needle in text:
            LOGGER.error(f"🕸️ String {action.not_string} found in response, exiting ...")
            exit(1)
        LOGGER.info(f"🕸️ String {action.not_string} not found in response")
