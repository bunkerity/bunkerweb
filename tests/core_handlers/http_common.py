#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from random import randint
from traceback import format_exc
from typing import Any, Union

from httpx import Client, Response


class HTTPContext:
    def __init__(self, response: Union[Response, str], http2: bool):
        self.response = response
        self.http2 = http2


essential_timeout = 10


def perform_request(LOGGER: Logger, action: Any) -> HTTPContext:
    url = action.url
    method = action.method
    headers = action.headers.copy()
    auth = action.auth
    follow_redirects = action.follow_redirects
    verify_ssl = action.verify_ssl
    http2 = action.http2
    body = action.body
    body_length = action.body_length

    LOGGER.info(f"Sending {method} request to {url} ...")
    LOGGER.debug(f"Request headers: {headers}")
    LOGGER.debug(f"Request auth: {auth}")
    LOGGER.debug(f"Allowing redirects: {follow_redirects}")
    LOGGER.debug(f"Verifying SSL: {verify_ssl}")

    # A null value means "send this request without the header", which is an assertion of
    # its own, so nothing below may add one back.
    dropped_headers = {key.lower() for key, value in headers.items() if value is None}

    for key, value in headers.copy().items():
        if value is None:
            headers.pop(key, None)

    if action.client_cert_key and not action.client_cert:
        raise ValueError("client_cert must be provided when client_cert_key is set")

    client_cert = None
    if action.client_cert:
        client_cert = action.client_cert if action.client_cert_key is None else (action.client_cert, action.client_cert_key)
        LOGGER.debug(f"Using client certificate {action.client_cert}" + (f" with key {action.client_cert_key}" if action.client_cert_key else ""))

    if headers.get("X-Forwarded-For", "").lower() == "random":
        headers["X-Forwarded-For"] = f"{randint(1, 255)}.{randint(1, 255)}.{randint(1, 255)}.{randint(1, 255)}"

    # httpx sends a raw body with no Content-Type, and CRS rules 920340 and 920640 answer
    # that with a 403 before the request reaches whatever the spec is testing. A spec that
    # wants the header missing can still say so with `Content-Type: null`.
    if (body or body_length) and "content-type" not in dropped_headers and not any(key.lower() == "content-type" for key in headers):
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    response: Union[Response, str]
    try:
        with Client(
            auth=auth,
            headers=headers,
            verify=verify_ssl,
            http1=not http2,
            http2=http2,
            timeout=essential_timeout,
            follow_redirects=follow_redirects,
            cert=client_cert,
        ) as client:
            response = client.request(method, url, data="a" * body_length if body_length > 0 else body)
    except BaseException:
        response = format_exc()

    if isinstance(response, Response):
        LOGGER.debug(f"Response: {response.text}")
        LOGGER.debug(f"Response URL: {response.url}")
        LOGGER.debug(f"Response status code: {response.status_code}")
        LOGGER.debug(f"Response headers: {response.headers}")

        if http2 and response.http_version != "HTTP/2":
            LOGGER.error(f"HTTP/2 not used, instead found {response.http_version}, exiting ...")
            exit(1)

    return HTTPContext(response, http2)
