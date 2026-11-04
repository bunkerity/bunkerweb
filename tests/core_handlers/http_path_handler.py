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
    if action.path not in str(response.url):
        if action.raise_for_status:
            response.raise_for_status()

        LOGGER.error(f"⤵️ Path {action.path} not found in response URL, instead found {response.url}, exiting ...")
        exit(1)
    LOGGER.info(f"⤵️ Path {action.path} found in response URL")
