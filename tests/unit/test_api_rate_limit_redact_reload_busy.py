"""Regression tests for the API lane.

1. The direct-Redis storage URI embeds user:password and used to be logged verbatim at INFO and in
   the unreachable-Redis error.
2. POST /instances/{hostname}/reload sent one request, so a 503 (instance busy) became a 502
   instead of going through the busy retry ApiCaller already has.
"""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(REPO_ROOT / "src/api"),
    str(REPO_ROOT / "src/common/utils"),
    str(REPO_ROOT / "src/api/utils"),
    str(REPO_ROOT / "src/common/db"),
    str(REPO_ROOT / "src/common/api"),
    str(REPO_ROOT / "src/common"),
    str(REPO_ROOT / "src/deps/python"),
]

# The real guard loads a Biscuit keypair at import time.
_guard_stub = types.ModuleType("app.auth.guard")
_guard_stub.guard = lambda: None
sys.modules.setdefault("app.auth.guard", _guard_stub)

import ApiCaller as api_caller_module  # noqa: E402
from app import rate_limit  # noqa: E402
from app.routers import instances  # noqa: E402

SECRET = "s3cr3t/p@ss"
URI = f"redis://user:{SECRET}@redis.local:6380/2"


def _logged(logger: MagicMock) -> str:
    return "\n".join(str(call.args[0]) for call in logger.method_calls if call.args)


class RedactStorageLogging(unittest.TestCase):
    def test_setup_does_not_log_password(self):
        config = MagicMock()
        config.rate_limit_enabled = True
        config.API_RATE_LIMIT_RULES = None
        config.API_RATE_LIMIT = "100/minute"
        config.API_RATE_LIMIT_AUTH = "10/minute"
        config.API_RATE_LIMIT_EXEMPT_IPS = ""
        config.API_RATE_LIMIT_STRATEGY = "fixed-window"
        config.rate_limit_headers_enabled = False
        logger = MagicMock()
        with (
            patch.object(rate_limit, "api_config", config),
            patch.object(rate_limit, "LOGGER", logger),
            patch.object(rate_limit, "get_db", side_effect=RuntimeError),
            patch.object(rate_limit, "_build_storage", return_value=(URI, {})),
            patch.object(rate_limit, "_make_limiter", return_value=MagicMock()) as make_limiter,
            patch.object(rate_limit, "_build_key_func", return_value=lambda request: "k"),
        ):
            rate_limit.setup_rate_limiter(MagicMock())

        out = _logged(logger)
        self.assertIn("Rate limiting enabled with storage=redis://", out)
        self.assertIn("redis.local:6380/2", out)
        self.assertNotIn(SECRET, out)
        self.assertNotIn("user:", out)
        # The limiter still gets the real URI.
        self.assertEqual(make_limiter.call_args.args[0], URI)

    def test_unreachable_redis_error_does_not_log_password(self):
        logger = MagicMock()
        calls = []

        def limiter(**kwargs):
            calls.append(kwargs["storage_uri"])
            if kwargs["storage_uri"] != "memory://":
                raise ConnectionError(f"cannot connect to {kwargs['storage_uri']}")
            return MagicMock()

        with patch.object(rate_limit, "LOGGER", logger), patch.object(rate_limit, "Limiter", side_effect=limiter):
            rate_limit._make_limiter(URI, {}, key_func=lambda r: "k", default_limits=[], strategy="fixed-window", headers_enabled=False)

        out = _logged(logger)
        self.assertIn("redis.local:6380/2", out)
        self.assertNotIn(SECRET, out)
        self.assertEqual(calls, [URI, "memory://"])

    def test_real_constructor_error_does_not_log_password_parts(self):
        # No mock of the parser: the library error may echo pieces of the URI that a
        # whole-URI replace would miss, for example the password up to its first "/".
        logger = MagicMock()
        uri = "redis://user:SUPERSECRET/with@tail@127.0.0.1:1/0"
        with patch.object(rate_limit, "LOGGER", logger):
            limiter = rate_limit._make_limiter(uri, {}, key_func=lambda r: "k", default_limits=[], strategy="fixed-window", headers_enabled=False)

        out = _logged(logger)
        self.assertTrue(logger.error.called, "the real constructor must fail on this URI")
        for part in ("SUPERSECRET", "with@tail", "user:"):
            self.assertNotIn(part, out)
        self.assertIn("127.0.0.1:1/0", out)
        self.assertEqual(type(limiter._storage).__name__, "MemoryStorage")

    def test_redacted_form_keeps_scheme_host_port_db(self):
        self.assertEqual(rate_limit._redact_storage(URI), "redis://redis.local:6380/2")
        self.assertEqual(rate_limit._redact_storage("rediss://:pw@h:6379/0"), "rediss://h:6379/0")
        self.assertEqual(rate_limit._redact_storage("memory://"), "memory://")
        self.assertEqual(rate_limit._redact_storage("redis+sentinel://a:26379,b:26379/mymaster"), "redis+sentinel://a:26379,b:26379/mymaster")


class FakeAPI:
    endpoint = "http://bw:5000/"

    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = []

    def request(self, method, url, files=None, data=None, timeout=(5, 10)):
        self.calls.append((method, url))
        status = self.statuses.pop(0)
        return True, None, status, {"status": "ok" if status == 200 else "error", "msg": "busy" if status == 503 else "ok"}


class ReloadOneBusyRetry(unittest.TestCase):
    def _reload(self, statuses):
        api = FakeAPI(statuses)
        with patch.object(api_caller_module, "sleep") as sleep:
            resp = instances.reload_one("bw", test=True, api=api)
        return resp, api, sleep

    def test_busy_then_ok_is_retried(self):
        resp, api, sleep = self._reload([503, 200])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(api.calls), 2)
        sleep.assert_called_once()

    def test_busy_every_attempt_is_502(self):
        resp, api, _ = self._reload([503] * api_caller_module.BUSY_ATTEMPTS)
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(len(api.calls), api_caller_module.BUSY_ATTEMPTS)

    def test_other_failure_is_not_retried(self):
        resp, api, _ = self._reload([500])
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(len(api.calls), 1)


if __name__ == "__main__":
    unittest.main()
