import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src" / "common" / "utils"))

import common_utils  # noqa: E402


class Factory(unittest.TestCase):
    def setUp(self):
        common_utils._REDIS_CLIENT_ENTRY = None

    def test_cluster_nodes_build_redis_cluster(self):
        fake = MagicMock()
        with patch("redis.cluster.RedisCluster", return_value=fake) as cls:
            client = common_utils.get_redis_client(use_redis=True, redis_cluster_nodes="a:7000 [::1]:7001 b", redis_username=None, redis_password="pw")
        self.assertIs(client, fake)
        kwargs = cls.call_args.kwargs
        nodes = [(n.host, n.port) for n in kwargs["startup_nodes"]]
        self.assertEqual(nodes, [("a", 7000), ("::1", 7001), ("b", 6379)])
        self.assertNotIn("db", kwargs)
        self.assertEqual(kwargs["password"], "pw")
        fake.ping.assert_called_once()

    def test_conflict_refuses_redis(self):
        with patch("redis.cluster.RedisCluster") as cls, patch("redis.Sentinel") as sentinel:
            client = common_utils.get_redis_client(use_redis=True, redis_cluster_nodes="a:7000", redis_sentinel_hosts="s:26379", redis_sentinel_master="m")
        self.assertIsNone(client)
        cls.assert_not_called()
        sentinel.assert_not_called()

    def test_no_cluster_nodes_keeps_strictredis(self):
        with patch("redis.StrictRedis") as strict:
            common_utils.get_redis_client(use_redis=True, redis_host="h")
        strict.assert_called_once()

    def test_whitespace_only_cluster_nodes_keeps_strictredis(self):
        with patch("redis.cluster.RedisCluster") as cluster, patch("redis.StrictRedis") as strict:
            common_utils.get_redis_client(use_redis=True, redis_host="h", redis_cluster_nodes="  ")
        cluster.assert_not_called()
        strict.assert_called_once()


if __name__ == "__main__":
    unittest.main()
