"""The API limiter must honor Redis certificate verification on every backend."""

from os import environ

import pytest
from limits.storage import storage_from_string

from test_rate_limit_once import _load_rate_limit


@pytest.fixture
def rate_limit(monkeypatch):
    for name in list(environ):
        if name == "USE_REDIS" or name.startswith("REDIS_"):
            monkeypatch.delenv(name)
    return _load_rate_limit(monkeypatch)


@pytest.mark.parametrize(
    "backend",
    [
        {"REDIS_HOST": "redis.example.com"},
        {"REDIS_SENTINEL_HOSTS": "sentinel.example.com", "REDIS_SENTINEL_MASTER": "master"},
        {"REDIS_CLUSTER_NODES": "redis.example.com redis2.example.com"},
    ],
    ids=["standalone", "sentinel", "cluster"],
)
@pytest.mark.parametrize("ssl", ["yes", "no"])
@pytest.mark.parametrize("verify,expected", [("yes", "required"), ("no", "none"), (None, "required"), ("", "required"), ("other", "required")])
def test_verification_options_reach_each_redis_backend(rate_limit, backend, ssl, verify, expected):
    cfg = {"USE_REDIS": "yes", "REDIS_SSL": ssl, **backend}
    if verify is not None:
        cfg["REDIS_SSL_VERIFY"] = verify
    uri, options = rate_limit._build_storage(cfg)
    if ssl == "yes":
        assert options["ssl_cert_reqs"] == expected
    else:
        assert "ssl_cert_reqs" not in options

    if "REDIS_CLUSTER_NODES" in backend:
        assert options["ssl"] is (ssl == "yes")
        return  # RedisCluster connects eagerly; standalone and Sentinel construct lazily.

    storage = storage_from_string(uri, **options)
    try:
        pools = [storage.storage.connection_pool]
        if "REDIS_SENTINEL_HOSTS" in backend:
            pools.extend(client.connection_pool for client in storage.sentinel.sentinels)
        for pool in pools:
            if ssl == "yes":
                assert pool.connection_kwargs["ssl_cert_reqs"] == expected
            else:
                assert "ssl_cert_reqs" not in pool.connection_kwargs
    finally:
        for pool in pools:
            pool.disconnect()


def test_environment_verify_overrides_database_value(rate_limit, monkeypatch):
    monkeypatch.setenv("REDIS_SSL_VERIFY", "no")
    _, options = rate_limit._build_storage({"USE_REDIS": "yes", "REDIS_HOST": "redis.example.com", "REDIS_SSL": "yes", "REDIS_SSL_VERIFY": "yes"})
    assert options["ssl_cert_reqs"] == "none"
