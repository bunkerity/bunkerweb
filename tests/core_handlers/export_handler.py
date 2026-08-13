#!/usr/bin/python3
# -*- coding: utf-8 -*-

from contextlib import suppress
from logging import Logger
from os import environ
from typing import Any, Dict

from redis import Redis
from httpx import Response

from .http_common import perform_request


def _get_by_path(data: Dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split(".") if path else []:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(path)
    return current


def handle(LOGGER: Logger, action: Any) -> None:
    # Perform the HTTP request and ensure we have a proper response
    ctx = perform_request(LOGGER, action)
    if not isinstance(ctx.response, Response):
        LOGGER.error("Request failed, no HTTP response available for export action")
        LOGGER.debug(str(ctx.response))
        exit(1)

    try:
        payload = ctx.response.json()
    except Exception as e:
        LOGGER.exception(f"Failed to parse JSON response: {e}")
        exit(1)

    exports = getattr(action, "exports", {}) or {}
    if not exports:
        LOGGER.warning("No exports mapping provided; nothing to export")
        return

    # Connect to Redis for cross-process availability of exported values
    try:
        redis_client = Redis(host="localhost", port=6379, db=0, decode_responses=True)
        redis_client.ping()
    except Exception:
        redis_client = None

    for env_key, json_path in exports.items():
        try:
            value = _get_by_path(payload, json_path)
        except KeyError:
            LOGGER.error(f"Export path {json_path!r} not found in response payload")
            exit(1)

        # Normalize value to string
        if not isinstance(value, str):
            from json import dumps as _dumps

            value = _dumps(value)

        environ[env_key] = value
        if redis_client:
            with suppress(Exception):
                redis_client.set(env_key, value)

        LOGGER.info(f"Exported {env_key} from {json_path}")
