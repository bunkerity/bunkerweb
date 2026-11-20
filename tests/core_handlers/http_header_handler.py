#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

from httpx import Response
from re import match as re_match

from .http_common import perform_request


def handle(LOGGER: Logger, action: Any) -> None:
    ctx = perform_request(LOGGER, action)
    response = ctx.response

    assert isinstance(response, Response), f"❌ Request failed:\n{response}"

    if action.raise_for_status:
        response.raise_for_status()

    for header_name, header_rx in action.response_headers.items():
        header = response.headers.get(header_name.lower(), None)
        if header is not None:
            if header_rx is None:
                LOGGER.error(f"📑 Header {header_name} found in response, exiting ...\nheaders: {response.headers}")
                exit(1)
            elif not re_match(header_rx, header):
                LOGGER.error(f"📑 Header {header_name} who matches regex {header_rx} not found in response, exiting ...\nheaders: {response.headers}")
                exit(1)
            LOGGER.info(f"📑 Header {header_name} who matches regex {header_rx} found in response")
        elif header_rx is not None:
            LOGGER.error(f"📑 Header {header_name} who matches regex {header_rx} not found in response, exiting ...\nheaders: {response.headers}")
            exit(1)
        else:
            LOGGER.info(f"📑 Header {header_name} not found in response")

    LOGGER.info("📑 All headers checked")
