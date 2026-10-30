"""Regression tests for the API rate limiter when its Redis storage fails at request time (src/api/app/rate_limit.py).

Standalone and Sentinel Redis storages connect lazily, so `_make_limiter` never sees a bad host or
password: the first request does, inside slowapi's `_check_request_limit`. Without
`in_memory_fallback_enabled=True` the storage error propagates and every endpoint answers 500,
`/ping` and `/health` included.

Run against the unfixed module the cases below fail; against the fixed module they pass.
"""

import asyncio
import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(REPO_ROOT / "src/api"),
    str(REPO_ROOT / "src/common/utils"),
    str(REPO_ROOT / "src/api/utils"),
    str(REPO_ROOT / "src/common/db"),
    str(REPO_ROOT / "src/common"),
    str(REPO_ROOT / "src/deps/python"),
]

from fastapi import FastAPI  # noqa: E402
from limits.storage.redis import RedisStorage  # noqa: E402
from redis.exceptions import AuthenticationError, ConnectionError as RedisConnectionError  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from starlette.requests import Request  # noqa: E402

from app import rate_limit  # noqa: E402

LIMIT = 3


def _request(path: str = "/bans", method: str = "GET", client: str = "10.0.0.1") -> Request:
    return Request({"type": "http", "method": method, "path": path, "headers": [], "client": (client, 1234), "query_string": b""})


class RedisFailsAtRequestTime(unittest.TestCase):
    def _setup(self, failure: str):
        """Run the real `setup_rate_limiter` against a Redis storage that fails on use."""
        # Port 1 refuses at once: a real ConnectionError, no Docker and no network.
        storage = ("redis://127.0.0.1:1/0", {"socket_connect_timeout": 0.2})
        patches = [
            patch.object(rate_limit, "get_db", return_value=MagicMock(get_config=MagicMock(return_value={}))),
            patch.object(rate_limit, "_build_storage", return_value=storage),
            patch.object(rate_limit.api_config, "API_RATE_LIMIT_ENABLED", "yes"),
            patch.object(rate_limit.api_config, "API_RATE_LIMIT", f"{LIMIT}/minute"),
            patch.object(rate_limit.api_config, "API_RATE_LIMIT_RULES", None),
            patch.object(rate_limit.api_config, "API_RATE_LIMIT_AUTH", "off"),
            patch.object(rate_limit.api_config, "API_RATE_LIMIT_EXEMPT_IPS", ""),
            patch.object(rate_limit.api_config, "API_RATE_LIMIT_STRATEGY", "fixed-window"),
            patch.object(rate_limit.api_config, "API_RATE_LIMIT_HEADERS_ENABLED", "no"),
            # Restored on exit: `setup_rate_limiter` rebinds these module globals.
            patch.object(rate_limit, "_limiter", None),
            patch.object(rate_limit, "_enabled", False),
            patch.object(rate_limit, "_rules", []),
            patch.object(rate_limit, "_base_limits", []),
            patch.object(rate_limit, "_exempt_networks", []),
            patch.object(rate_limit, "_auth_limit", None),
        ]
        if failure == "auth":
            for method in ("incr", "get", "get_expiry", "check"):
                patches.append(patch.object(RedisStorage, method, side_effect=AuthenticationError("invalid username-password pair")))
        elif failure != "connection":
            raise AssertionError(failure)
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        rate_limit.setup_rate_limiter(FastAPI())
        self.addCleanup(rate_limit._reset_limit_cache)
        return rate_limit.limiter_dep_dynamic().dependency

    @staticmethod
    def _hit(dep) -> bool:
        """True when the request passes, False on a 429. Any other error propagates (the 500)."""
        try:
            asyncio.run(dep(_request()))
        except RateLimitExceeded:
            return False
        return True

    def test_connection_error_still_serves_requests(self):
        dep = self._setup("connection")
        self.assertTrue(self._hit(dep))

    def test_authentication_error_still_serves_requests(self):
        dep = self._setup("auth")
        self.assertTrue(self._hit(dep))

    def test_limit_is_still_enforced_from_memory(self):
        for failure in ("connection", "auth"):
            with self.subTest(failure=failure):
                dep = self._setup(failure)
                self.assertEqual([self._hit(dep) for _ in range(LIMIT + 2)], [True] * LIMIT + [False] * 2)

    def test_fallback_is_logged_once(self):
        dep = self._setup("auth")
        with self.assertLogs("slowapi", logging.WARNING) as logs:
            for _ in range(LIMIT + 2):
                self._hit(dep)
        self.assertEqual(sum("falling back to in-memory storage" in line for line in logs.output), 1)

    def test_exception_types_are_the_expected_ones(self):
        """Premise check: the real unreachable Redis raises a redis-py ConnectionError at use time."""
        storage = RedisStorage("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
        with self.assertRaises(RedisConnectionError):
            storage.incr("k", 60)


if __name__ == "__main__":
    unittest.main()
