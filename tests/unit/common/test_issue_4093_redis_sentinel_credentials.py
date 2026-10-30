"""The Redis client authenticates to the Sentinel nodes themselves, not only to the master.

The Sentinel credentials and the TLS options were not sent to the Sentinel nodes (``sentinel_kwargs``), so a
Sentinel that requires authentication or TLS refused the Web UI's connection.

Refs: #4093
"""

import sys
import types

import pytest

import common_utils


class FakeRedis:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def ping(self):
        return True


class FakeSentinel:
    instances = []

    def __init__(self, hosts, **kwargs):
        self.hosts = hosts
        self.kwargs = kwargs
        FakeSentinel.instances.append(self)

    def discover_master(self, name):
        return ("127.0.0.1", 6379)

    def master_for(self, name, **kwargs):
        return FakeRedis(**kwargs)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    module = types.ModuleType("redis")
    module.StrictRedis = FakeRedis
    module.Sentinel = FakeSentinel
    monkeypatch.setitem(sys.modules, "redis", module)
    monkeypatch.setattr(common_utils, "_REDIS_CLIENT_ENTRY", None, raising=False)
    FakeSentinel.instances = []


def connect(**overrides):
    kwargs = {"use_redis": True, "redis_sentinel_hosts": [("s1", "26379")], "redis_sentinel_master": "mymaster", "redis_timeout": "2000.0"}
    assert common_utils.get_redis_client(**(kwargs | overrides)) is not None
    return FakeSentinel.instances[-1]


def test_sentinel_nodes_receive_their_own_credentials():
    sentinel = connect(redis_sentinel_username="sentinel-user", redis_sentinel_password="sentinel-pass", redis_password="master-pass")

    node_options = sentinel.kwargs.get("sentinel_kwargs", {})
    assert node_options.get("username") == "sentinel-user"
    assert node_options.get("password") == "sentinel-pass"


def test_sentinel_nodes_receive_the_tls_options():
    sentinel = connect(redis_ssl=True, redis_ssl_verify=False)

    node_options = sentinel.kwargs.get("sentinel_kwargs", {})
    assert node_options.get("ssl") is True
    assert node_options.get("ssl_cert_reqs") == "none"


def test_sentinel_nodes_receive_the_timeouts():
    sentinel = connect(redis_timeout="2500.0")

    assert sentinel.kwargs.get("sentinel_kwargs", {}).get("socket_timeout") == 2.5
    assert sentinel.kwargs.get("sentinel_kwargs", {}).get("socket_connect_timeout") == 2.5


def test_no_sentinel_credentials_are_invented():
    sentinel = connect(redis_password="master-pass")

    assert "password" not in sentinel.kwargs.get("sentinel_kwargs", {})
    assert "username" not in sentinel.kwargs.get("sentinel_kwargs", {})
