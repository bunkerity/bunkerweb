#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

from httpx import ConnectError, ReadError, RemoteProtocolError, Response

from .http_common import perform_request


def _failure_kind(error: Exception | None) -> str | None:
    message = str(error)
    if isinstance(error, ConnectError):
        if "CERTIFICATE_VERIFY_FAILED" in message:
            return "tls_verify"
        if "Connection refused" in message:
            return "connection_refused"
    if isinstance(error, ReadError) and "Connection reset by peer" in message:
        return "connection_closed"
    if isinstance(error, RemoteProtocolError) and message in ("Server disconnected", "Server disconnected without sending a response."):
        return "connection_closed"
    return None


def handle(LOGGER: Logger, action: Any) -> None:
    # A closed port must read as a refused connection, not as whatever an unreachable AAAA answer adds.
    ctx = perform_request(LOGGER, action, ipv4_only=True)
    response = ctx.response

    if isinstance(response, str):
        kind = _failure_kind(ctx.error)
        if action.status is not None or kind not in action.expect_error:
            LOGGER.error(f"📃 Unexpected request failure ({kind}), expected status {action.status} or errors {action.expect_error}:\n{response}")
            exit(1)
        LOGGER.info(f"📃 Request failed with {kind}, as expected")
        return

    assert isinstance(response, Response)
    if not action.status:
        LOGGER.error("📃 Request succeeded, expected failure, exiting ...")
        exit(1)
    elif action.status != response.status_code:
        LOGGER.error(f"📃 Status code {action.status} not found in response, instead found {response.status_code}, exiting ...")
        exit(1)
    LOGGER.info(f"📃 Status code {action.status} found in response")
