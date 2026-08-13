#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from time import sleep, time
from typing import Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event

from httpx import Response
import httpx

from .http_common import perform_request


def handle(LOGGER: Logger, action: Any) -> None:
    """
    Handle limit testing actions for both rate limiting and connection limiting.

    This handler can:
    1. Test rate limiting by making multiple requests and checking for 429 responses
    2. Test connection limiting by establishing multiple connections
    3. Test recovery after rate limit periods
    4. Validate that limits are properly enforced
    """

    LOGGER.info(f"🚧 Starting limit test for URL: {action.url}")

    # If testing rate limiting
    if action.rate_limit or action.max_requests:
        _test_rate_limiting(LOGGER, action)

    # If testing connection limiting
    if action.max_connections:
        _test_connection_limiting(LOGGER, action)

    # If testing recovery after rate limit
    if action.test_recovery:
        _test_rate_limit_recovery(LOGGER, action)

    # Default behavior: single request test
    if not any([action.rate_limit, action.max_requests, action.max_connections, action.test_recovery]):
        _test_single_request(LOGGER, action)


def _test_rate_limiting(LOGGER: Logger, action: Any) -> None:
    """Test rate limiting functionality."""

    LOGGER.info(f"🔄 Testing rate limiting with limit: {action.rate_limit or action.max_requests}")

    responses: List[Response] = []
    errors: List[str] = []
    limited_count = 0

    # Determine number of requests to make
    if action.rate_exceeded_count:
        num_requests = action.rate_exceeded_count
    elif action.max_requests:
        num_requests = action.max_requests + 2  # Exceed the limit
    else:
        # Parse rate_limit string like "2r/s" to get the number
        rate_num = int(action.rate_limit.split("r/")[0])
        num_requests = rate_num + 2  # Exceed the limit

    LOGGER.info(f"🔄 Making {num_requests} requests to test rate limiting")

    start_time = time()

    for i in range(num_requests):
        ctx = perform_request(LOGGER, action)
        response = ctx.response

        if isinstance(response, str):
            errors.append(response)
            LOGGER.debug(f"Request {i + 1} failed: {response}")
        else:
            responses.append(response)
            if response.status_code == 429:
                limited_count += 1
                LOGGER.debug(f"Request {i + 1} was rate limited (429)")
            else:
                LOGGER.debug(f"Request {i + 1} succeeded with status {response.status_code}")

        # Small delay between requests to simulate realistic usage
        if action.cooldown > 0:
            sleep(action.cooldown)

    end_time = time()
    duration = end_time - start_time

    LOGGER.info(f"📊 Rate limiting test results: {limited_count} requests limited out of {len(responses)} successful requests")
    LOGGER.info(f"⏱️  Test duration: {duration:.2f} seconds")

    # Validate results based on expectations
    if action.expect_limited:
        if limited_count == 0:
            LOGGER.error("❌ Expected requests to be rate limited, but none were limited")
            exit(1)
        LOGGER.info(f"✅ Rate limiting working as expected: {limited_count} requests limited")
    else:
        if limited_count > 0:
            LOGGER.error(f"❌ Expected no rate limiting, but {limited_count} requests were limited")
            exit(1)
        LOGGER.info("✅ No rate limiting applied as expected")


def _test_connection_limiting(LOGGER: Logger, action: Any) -> None:
    """Test connection limiting functionality with concurrent burst.

    We simulate concurrent connections using a thread pool so that multiple
    requests overlap in time. Sequential requests were not triggering the
    limit because connections closed too quickly before the next one opened.
    If action.connection_hold > 0 we keep the TCP connection open by streaming
    the response and sleeping before reading/closing.
    """

    LOGGER.info(f"🔗 Testing connection limiting with configured max: {action.max_connections}")

    target = action.connection_exceed_count or ((action.max_connections + 3) if action.max_connections else 5)
    LOGGER.info(f"🔗 Preparing concurrent burst of {target} requests to exceed max {action.max_connections}")

    start_event = Event()

    def do_request(idx: int) -> int:
        start_event.wait()
        hold = getattr(action, "connection_hold", 0.0) or 0.0
        if hold > 0:
            # manual streaming request to keep connection open
            try:
                with httpx.Client(http2=action.http2, timeout=10.0) as client:
                    req = client.build_request(action.method, action.url, headers=action.headers or None)
                    resp = client.send(req, stream=True)
                    if resp.status_code == 429:
                        code = 429
                    else:
                        # keep connection open
                        sleep(hold)
                        code = resp.status_code
                    # ensure response closed
                    resp.close()
                    LOGGER.debug(f"Connection burst request {idx + 1} (hold={hold}s): status {code}")
                    return code
            except Exception as e:  # noqa: BLE001
                LOGGER.debug(f"Connection burst request {idx + 1} failed: {e}")
                return -1
        else:
            ctx = perform_request(LOGGER, action)
            resp = ctx.response
            if isinstance(resp, str):
                LOGGER.debug(f"Connection burst request {idx + 1} failed: {resp}")
                return -1
            code = resp.status_code
            LOGGER.debug(f"Connection burst request {idx + 1}: status {code}")
            return code

    blocked = 0
    successes = 0

    with ThreadPoolExecutor(max_workers=target) as executor:
        futures = [executor.submit(do_request, i) for i in range(target)]
        start_event.set()
        for fut in as_completed(futures):
            code = fut.result()
            if code == -1:
                continue
            if code == 429:
                blocked += 1
            else:
                successes += 1

    LOGGER.info(f"📊 Connection limiting burst results: blocked={blocked} success={successes}")

    if action.expect_blocked:
        if blocked == 0:
            LOGGER.error("❌ Expected at least one 429 due to connection limiting, got 0")
            exit(1)
        LOGGER.info(f"✅ Connection limiting enforced (>=1 blocked). Blocked count: {blocked}")
    else:
        if blocked > 0:
            LOGGER.error(f"❌ Did not expect connection limiting but saw {blocked} blocked (429)")
            exit(1)
        LOGGER.info("✅ No connection limiting observed as expected")


def _test_rate_limit_recovery(LOGGER: Logger, action: Any) -> None:
    """Test recovery after rate limit period."""

    LOGGER.info(f"⏳ Testing rate limit recovery after {action.recovery_delay} seconds")

    # First, trigger rate limiting
    LOGGER.info("🔄 Triggering rate limit...")
    for i in range(5):  # Make several requests to trigger limit
        ctx = perform_request(LOGGER, action)
        if action.cooldown > 0:
            sleep(action.cooldown)

    # Wait for recovery period
    LOGGER.info(f"⏳ Waiting {action.recovery_delay} seconds for rate limit recovery...")
    sleep(action.recovery_delay)

    # Test if requests are allowed again
    LOGGER.info("🔄 Testing if requests are allowed after recovery period...")
    ctx = perform_request(LOGGER, action)
    response = ctx.response

    if isinstance(response, str):
        LOGGER.error(f"❌ Request failed after recovery period: {response}")
        exit(1)
    elif response.status_code == 429:
        LOGGER.error("❌ Request still rate limited after recovery period")
        exit(1)
    else:
        LOGGER.info("✅ Rate limit recovery successful")


def _test_single_request(LOGGER: Logger, action: Any) -> None:
    """Perform a single request test (default behavior)."""

    LOGGER.info("📡 Performing single request test")

    ctx = perform_request(LOGGER, action)
    response = ctx.response

    if isinstance(response, str):
        if action.expect_limited or action.expect_blocked:
            LOGGER.info("📡 Request failed as expected")
        else:
            LOGGER.error(f"📡 Request failed unexpectedly: {response}")
            exit(1)
    else:
        if action.expect_limited and response.status_code != 429:
            LOGGER.error(f"📡 Expected 429 status, got {response.status_code}")
            exit(1)
        elif action.expect_blocked and response.status_code not in (403, 429):
            LOGGER.error(f"📡 Expected blocked status, got {response.status_code}")
            exit(1)
        elif not action.expect_limited and not action.expect_blocked and response.status_code == 429:
            LOGGER.error("📡 Unexpected rate limiting occurred")
            exit(1)
        else:
            LOGGER.info(f"📡 Request completed with status {response.status_code}")
