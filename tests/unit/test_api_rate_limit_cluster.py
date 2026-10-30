"""Regression tests for the API rate limiter's Redis Cluster storage (src/api/app/rate_limit.py).

Two failures fixed here, both crash-at-boot bugs for the API in cases where standalone/Sentinel
degrade gracefully instead:

1. A mixed IPv4/IPv6 REDIS_CLUSTER_NODES list (e.g. "a:7000 [::1]:7001") built a comma-joined
   URI that stdlib urlsplit rejects whenever a bracketed IPv6 literal is not the first token.
2. An unreachable Redis Cluster made the eager `RedisCluster()` constructor raise, and nothing
   caught it, so the API process failed to start.

Run against the unfixed module, both cases below fail; against the fixed module, they pass.
"""

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

from limits._storage_scheme import parse_storage_uri  # noqa: E402

from app import rate_limit  # noqa: E402


class BuildStorageClusterNodes(unittest.TestCase):
    """_build_storage must produce a URI that urlsplit accepts regardless of node order,
    and hand the full node list to RedisCluster through storage_options["startup_nodes"]
    (limits merges options over the URI-derived nodes, so this is what actually connects)."""

    def _build(self, cluster_nodes: str):
        cfg = {"USE_REDIS": "yes", "REDIS_CLUSTER_NODES": cluster_nodes, "REDIS_DATABASE": "0"}
        with patch.object(rate_limit, "getenv", return_value=None):
            return rate_limit._build_storage(cfg)

    def test_ipv6_not_first_builds_parseable_uri(self):
        storage, options = self._build("a:7000 [::1]:7001")
        # This is the exact string that raised "ValueError: Invalid IPv6 URL" before the fix.
        parsed = parse_storage_uri(storage)
        self.assertEqual(parsed.scheme, "redis+cluster")
        nodes = [(n.host, n.port) for n in options["startup_nodes"]]
        self.assertEqual(nodes, [("a", 7000), ("::1", 7001)])

    def test_all_bracketed_ipv6_builds_parseable_uri(self):
        storage, options = self._build("[::1]:7000 [::2]:7001")
        parse_storage_uri(storage)
        nodes = [(n.host, n.port) for n in options["startup_nodes"]]
        self.assertEqual(nodes, [("::1", 7000), ("::2", 7001)])

    def test_bare_host_defaults_to_6379(self):
        storage, options = self._build("b")
        parse_storage_uri(storage)
        nodes = [(n.host, n.port) for n in options["startup_nodes"]]
        self.assertEqual(nodes, [("b", 6379)])

    def test_bad_port_falls_back_to_memory(self):
        with patch.object(rate_limit.LOGGER, "error") as log_error:
            storage, _ = self._build("redis:abc")
        self.assertEqual(storage, "memory://")
        log_error.assert_called_once()

    def test_tls_verify_follows_setting(self):
        # redis-py verifies certificates unless told otherwise: an explicit "no" must reach it.
        cfg = {"USE_REDIS": "yes", "REDIS_CLUSTER_NODES": "a:7000", "REDIS_DATABASE": "0", "REDIS_SSL": "yes"}
        with patch.object(rate_limit, "getenv", return_value=None):
            _, off = rate_limit._build_storage({**cfg, "REDIS_SSL_VERIFY": "no"})
            _, on = rate_limit._build_storage({**cfg, "REDIS_SSL_VERIFY": "yes"})
        self.assertEqual(off["ssl_cert_reqs"], "none")
        self.assertEqual(on["ssl_cert_reqs"], "required")


class MakeLimiterFallback(unittest.TestCase):
    """_make_limiter must fall back to memory:// instead of letting a storage construction
    failure (an unreachable Redis Cluster at boot) propagate and crash the API process."""

    def test_storage_failure_falls_back_to_memory(self):
        boom = Exception("Redis Cluster cannot be connected")
        with patch.object(rate_limit, "Limiter") as limiter_cls:
            memory_limiter = MagicMock()
            limiter_cls.side_effect = [boom, memory_limiter]
            result = rate_limit._make_limiter(
                "redis+cluster://127.0.0.1:1",
                {"startup_nodes": []},
                key_func=lambda r: "0.0.0.0",
                default_limits=["100/minute"],
                strategy="fixed-window",
                headers_enabled=False,
            )
        self.assertIs(result, memory_limiter)
        self.assertEqual(limiter_cls.call_count, 2)
        first_kwargs, second_kwargs = limiter_cls.call_args_list[0].kwargs, limiter_cls.call_args_list[1].kwargs
        self.assertEqual(first_kwargs["storage_uri"], "redis+cluster://127.0.0.1:1")
        self.assertEqual(second_kwargs["storage_uri"], "memory://")

    def test_unreachable_cluster_storage_actually_raises_uncaught(self):
        """Sanity check for the premise: constructing RedisClusterStorage against an
        unreachable cluster raises, so _make_limiter's except path is not dead code."""
        from limits.storage.redis_cluster import RedisClusterStorage

        with self.assertRaises(Exception):
            RedisClusterStorage("redis+cluster://127.0.0.1:1", socket_connect_timeout=0.2)

    def test_success_returns_limiter_unchanged(self):
        with patch.object(rate_limit, "Limiter") as limiter_cls:
            ok_limiter = MagicMock()
            limiter_cls.return_value = ok_limiter
            result = rate_limit._make_limiter(
                "memory://",
                {},
                key_func=lambda r: "0.0.0.0",
                default_limits=["100/minute"],
                strategy="fixed-window",
                headers_enabled=False,
            )
        self.assertIs(result, ok_limiter)
        limiter_cls.assert_called_once()


if __name__ == "__main__":
    unittest.main()
