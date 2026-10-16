"""Redis Cluster port acceptance at the existing client and durable-ban boundaries."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

import common_utils
from test_ban_projection import JOB, NOW, _ban
from test_redis_client_memo import _FakeRedis, _FakeSentinel

ROOT = Path(__file__).resolve().parents[3]


class ClusterNode:
    def __init__(self, host, port):
        self.host, self.port = host, port


class RedisCluster(_FakeRedis):
    def ping(self):
        self.pings += 1
        if self.kwargs["startup_nodes"][0].host == "down":
            raise ConnectionError("cluster unavailable")
        return True


@pytest.fixture
def clients(monkeypatch):
    redis = ModuleType("redis")
    redis.StrictRedis, redis.Sentinel = _FakeRedis, _FakeSentinel
    cluster = ModuleType("redis.cluster")
    cluster.RedisCluster, cluster.ClusterNode = RedisCluster, ClusterNode
    monkeypatch.setitem(sys.modules, "redis", redis)
    monkeypatch.setitem(sys.modules, "redis.cluster", cluster)
    monkeypatch.setattr(common_utils, "_REDIS_CLIENT_ENTRY", None)
    _FakeRedis.instances = []
    yield
    common_utils._REDIS_CLIENT_ENTRY = None


def connect(**overrides):
    return common_utils.get_redis_client(use_redis=True, redis_cluster_nodes="r1:7000 r2:7001", **overrides)


def test_cluster_client_uses_seed_nodes_acl_and_verified_private_ca(clients):
    client = connect(redis_username="bunkerweb", redis_password="secret", redis_ssl=True, redis_ssl_ca="/private.pem")
    assert isinstance(client, RedisCluster)
    assert [(node.host, node.port) for node in client.kwargs["startup_nodes"]] == [("r1", 7000), ("r2", 7001)]
    assert client.kwargs["username"] == "bunkerweb"
    assert client.kwargs["password"] == "secret"
    assert client.kwargs["ssl"] is True
    assert client.kwargs.get("ssl_cert_reqs", "required") == "required"
    assert client.kwargs["ssl_ca_certs"] == "/private.pem"
    assert "db" not in client.kwargs


@pytest.mark.parametrize("database", ["0", "00", 0])
def test_numeric_database_zero_is_accepted(clients, database):
    assert isinstance(connect(redis_db=database), RedisCluster)


@pytest.mark.parametrize("database", ["1", "-1", "invalid", "0.5"])
def test_cluster_rejects_nonzero_or_invalid_database_before_connect(clients, database):
    logger = Mock()
    assert connect(redis_db=database, logger=logger) is None
    assert not _FakeRedis.instances
    assert "REDIS_DATABASE" in str(logger.error.call_args_list)


def test_cluster_and_sentinel_are_rejected_before_connect(clients):
    logger = Mock()
    assert connect(redis_sentinel_hosts="s1:26379", logger=logger) is None
    assert not _FakeRedis.instances
    assert "REDIS_SENTINEL_HOSTS" in str(logger.error.call_args_list)


@pytest.mark.parametrize("nodes", ["r1:", "r1:0", "r1:65536", "r1:abc", "r1:7000 g@rbage", "::1:7000"])
def test_seed_nodes_reject_an_invalid_host_or_port(clients, nodes):
    logger = Mock()
    assert common_utils.get_redis_client(use_redis=True, redis_cluster_nodes=nodes, logger=logger) is None
    assert not _FakeRedis.instances
    assert "REDIS_CLUSTER_NODES" in str(logger.error.call_args_list)


def test_seed_node_without_a_port_uses_6379(clients):
    client = common_utils.get_redis_client(use_redis=True, redis_cluster_nodes="r1 r2:7001 [::1]")
    assert [(node.host, node.port) for node in client.kwargs["startup_nodes"]] == [("r1", 6379), ("r2", 7001), ("::1", 6379)]


def test_bracketed_ipv6_seed_is_accepted(clients):
    client = common_utils.get_redis_client(use_redis=True, redis_cluster_nodes="[::1]:7000")
    assert isinstance(client, RedisCluster)
    assert [(node.host, node.port) for node in client.kwargs["startup_nodes"]] == [("::1", 7000)]


def test_cluster_memo_includes_seeds_and_private_ca(clients):
    first = connect(redis_ssl=True, redis_ssl_ca="/one.pem")
    assert connect(redis_ssl=True, redis_ssl_ca="/one.pem") is first
    changed_ca = connect(redis_ssl=True, redis_ssl_ca="/two.pem")
    changed_nodes = common_utils.get_redis_client(use_redis=True, redis_cluster_nodes="r3:7002", redis_ssl=True, redis_ssl_ca="/two.pem")
    assert first is not changed_ca and changed_ca is not changed_nodes
    assert first.pings == 1


def test_cluster_negative_memo_does_not_hide_changed_seeds(clients):
    down = {"use_redis": True, "redis_cluster_nodes": "down:7000"}
    assert common_utils.get_redis_client(**down) is None
    attempts = len(_FakeRedis.instances)
    assert common_utils.get_redis_client(**down) is None
    assert len(_FakeRedis.instances) == attempts
    assert isinstance(connect(), RedisCluster)


def test_default_standalone_is_unchanged(clients):
    client = common_utils.get_redis_client(use_redis=True, redis_host="standalone", redis_db="2")
    assert type(client) is _FakeRedis
    assert client.kwargs["db"] == 2


@pytest.mark.parametrize("cluster", [False, True])
def test_projection_and_learning_preserve_raw_ip_and_service(clients, cluster):
    client = RedisCluster(startup_nodes=[ClusterNode("r1", 7000)]) if cluster else _FakeRedis()
    stored = {}
    client.set = lambda key, value, **kwargs: stored.__setitem__(key, value)
    client.get = lambda key: stored[key]
    client.scan_iter = lambda pattern: [key for key in stored if key.startswith("bans_service_" if "service" in pattern else "bans_ip_")]
    ban = _ban(ip="2001:db8::1", service="app{tenant}%name", ban_scope="service")
    assert JOB.project_bans([ban], {}, {}, client, NOW) == (1, 0)
    expected = "bans_service_app%7Btenant%7D%25name_ip_{2001:db8::1}" if cluster else "bans_service_app{tenant}%name_ip_2001:db8::1"
    assert list(stored) == [expected]
    assert json.loads(stored[expected])["service"] == ban["service"]
    record = JOB.records_from_redis(client)[0]
    assert (record["ip"], record["service"]) == (ban["ip"], ban["service"])


def test_learning_existing_cluster_keys_never_persists_hash_tags(clients):
    client = RedisCluster(startup_nodes=[ClusterNode("r1", 7000)])
    client.scan_iter = Mock(side_effect=[["bans_ip_{1.2.3.4}"], ["bans_service_app%7Btenant%7D_ip_{2001:db8::1}"]])
    client.get = Mock(return_value=json.dumps({"reason": "manual", "permanent": True}))
    records = JOB.records_from_redis(client)
    assert [(record["ip"], record["service"]) for record in records] == [("1.2.3.4", ""), ("2001:db8::1", "app{tenant}")]


def test_shared_key_helpers_keep_standalone_names_and_escape_cluster_prefixes():
    path = ROOT / "src/common/utils/redis_keys.py"
    assert path.is_file(), "the Redis-boundary key helper is missing"
    spec = importlib.util.spec_from_file_location("port_redis_keys", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    local_key = "bans_service_app{tenant}%name_ip_1.2.3.4"
    assert module.ban_key(local_key, False) == local_key
    assert module.ban_key(local_key, True) == "bans_service_app%7Btenant%7D%25name_ip_{1.2.3.4}"


@pytest.mark.parametrize("cluster", [False, True])
def test_db_projection_is_visible_to_real_lua_with_local_cache_names(clients, cluster):
    import os
    from test_ban_sync import UTILS_LUA, UTILS_PREAMBLE, _run_lua

    client = RedisCluster(startup_nodes=[ClusterNode("r1", 7000)]) if cluster else _FakeRedis()
    stored = {}
    client.set = lambda key, value, **kwargs: stored.__setitem__(key, value)
    ban = _ban(ip="2001:db8::1", service="app{tenant}%name", ban_scope="service")
    assert JOB.project_bans([ban], {}, {}, client, NOW) == (1, 0)
    remote_key, raw = next(iter(stored.items()))
    record = json.loads(raw)
    body = 'internal_store.variables.global.USE_REDIS = "yes"\n'
    if cluster:
        body += 'internal_store.variables.global.REDIS_CLUSTER_NODES = "r1:7000"\n'
    # Only the JSON transport is stubbed; the projected fields feed shipped Lua enforcement.
    body += f'redis_lookup_results[{json.dumps(remote_key)}] = {{json.encode({{reason={json.dumps(record["reason"])}, permanent=true}}), -1}}\n'
    body += "sync_store.ban_snapshot = json.encode({generation_epoch=1, bans={}})\n"
    body += 'local banned, reason = utils.is_banned("2001:db8::1", "app{tenant}%name")\n'
    body += 'assert(banned and reason == "badbehavior", "DB projection must reach Lua enforcement")\n'
    body += 'assert(main_store["ban_redis_cache_bans_service_app{tenant}%name_ip_2001:db8::1"] ~= nil, "local cache keys must retain raw service and IP")\n'
    _run_lua(UTILS_PREAMBLE, body, os.environ.get("REDIS_BRIDGE_SOURCE", str(UTILS_LUA)), "stream")
