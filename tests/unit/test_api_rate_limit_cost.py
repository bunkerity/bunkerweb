"""Regression tests for the cost of the API rate limiter dependency (src/api/app/rate_limit.py).

`limiter_dep_dynamic()` used to decorate a fresh function on every request. slowapi names every
such function the same way, so each request appended one more limit to the shared route entry:
request N was charged N hits on one counter and the entry grew without bound.

Run against the unfixed module the cases below fail; against the fixed module they pass.
"""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(REPO_ROOT / "src/api"),
    str(REPO_ROOT / "src/common/utils"),
    str(REPO_ROOT / "src/api/utils"),
    str(REPO_ROOT / "src/common/db"),
    str(REPO_ROOT / "src/common"),
    str(REPO_ROOT / "src/deps/python"),
]

from slowapi import Limiter  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from starlette.requests import Request  # noqa: E402

from app import rate_limit  # noqa: E402


def _request(path: str = "/bans", method: str = "GET", client: str = "10.0.0.1") -> Request:
    return Request({"type": "http", "method": method, "path": path, "headers": [], "client": (client, 1234), "query_string": b""})


class LimiterDependencyCost(unittest.TestCase):
    def _setup(self, base_limits, rules=None, auth_limit=None):
        limiter = Limiter(key_func=rate_limit._client_identifier, storage_uri="memory://", key_prefix="bwapi-rl-", default_limits=base_limits)
        patches = [
            patch.object(rate_limit, "_limiter", limiter),
            patch.object(rate_limit, "_enabled", True),
            patch.object(rate_limit, "_base_limits", base_limits),
            patch.object(rate_limit, "_rules", rules or []),
            patch.object(rate_limit, "_auth_limit", auth_limit),
            patch.object(rate_limit, "_exempt_networks", []),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        rate_limit._reset_limit_cache()
        self.dep = rate_limit.limiter_dep_dynamic().dependency
        return limiter

    def _hit(self, **kwargs) -> bool:
        """True when the request passes, False when it is rejected with a 429."""
        try:
            asyncio.run(self.dep(_request(**kwargs)))
        except RateLimitExceeded:
            return False
        return True

    def test_base_limit_counts_one_hit_per_request(self):
        self._setup(["5/minute"])
        results = [self._hit() for _ in range(6)]
        self.assertEqual(results, [True] * 5 + [False])

    def test_route_limits_do_not_grow(self):
        limiter = self._setup(["1000/minute"])
        self._hit()

        def size():
            return sum(len(v) for v in limiter._route_limits.values()), sum(len(v) for v in limiter._Limiter__marked_for_limiting.values())

        before = size()
        for _ in range(50):
            self._hit()
        self.assertEqual(size(), before)

    def test_new_limiter_after_setup_gets_its_own_limits(self):
        self._setup(["2/minute"])
        self.assertEqual([self._hit() for _ in range(3)], [True, True, False])
        limiter = self._setup(["2/minute"])
        self.assertEqual([self._hit() for _ in range(3)], [True, True, False])
        self.assertEqual(sum(len(v) for v in limiter._route_limits.values()), 1)

    def test_rule_match_is_not_charged_to_base_limit(self):
        rule = rate_limit._Rule({"GET"}, rate_limit._compile_pattern("/bans"), 3, 60, "GET /bans 3r/m")
        self._setup(["2/minute"], rules=[rule])
        results = [self._hit(path="/bans") for _ in range(4)]
        self.assertEqual(results, [True] * 3 + [False])
        # The base limit (2/minute) was never touched by the rule-matched path.
        self.assertTrue(self._hit(path="/other"))
        self.assertTrue(self._hit(path="/other"))
        self.assertFalse(self._hit(path="/other"))

    def test_auth_limit_is_not_charged_to_base_limit(self):
        self._setup(["2/minute"], auth_limit="3/minute")
        results = [self._hit(path="/auth", method="POST") for _ in range(4)]
        self.assertEqual(results, [True] * 3 + [False])
        self.assertTrue(self._hit(path="/other"))

    def test_every_base_limit_is_enforced(self):
        self._setup(["2/minute", "5/hour"])
        self.assertEqual([self._hit() for _ in range(3)], [True, True, False])

    def test_second_base_limit_is_enforced(self):
        self._setup(["100/minute", "3/hour"])
        self.assertEqual([self._hit() for _ in range(4)], [True] * 3 + [False])


if __name__ == "__main__":
    unittest.main()
