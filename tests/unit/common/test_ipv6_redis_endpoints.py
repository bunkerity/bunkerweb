"""Redis endpoints use bare Python hosts and bracketed IPv6 URI authorities."""

import ast
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from limits._storage_scheme import parse_storage_uri

import common_utils
from redis_keys import cluster_config_error

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def reset_client(monkeypatch):
    monkeypatch.setattr(common_utils, "_REDIS_CLIENT_ENTRY", None)


@pytest.mark.parametrize("host", ["2001:db8::1", "[2001:db8::1]"])
def test_direct_python_host_is_bare(host):
    with patch("redis.StrictRedis") as client:
        assert common_utils.get_redis_client(use_redis=True, redis_host=host) is not None
    assert client.call_args.kwargs["host"] == "2001:db8::1"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("[2001:db8::1]:26380 redis:26381", [("2001:db8::1", 26380), ("redis", 26381)]),
        ("[2001:db8::1] 2001:db8::2", [("2001:db8::1", 26379), ("2001:db8::2", 26379)]),
        ([("[2001:db8::1]", "26380")], [("2001:db8::1", 26380)]),
    ],
)
def test_sentinel_python_endpoints(value, expected):
    with patch("redis.Sentinel") as sentinel:
        assert common_utils.get_redis_client(use_redis=True, redis_sentinel_hosts=value, redis_sentinel_master="master") is not None
    assert sentinel.call_args.args[0] == expected


@pytest.mark.parametrize("nodes", ["[2001:db8::1]", "[2001:db8::1]:6379"])
def test_cluster_python_hosts_are_bare(nodes):
    with patch("redis.cluster.RedisCluster") as client:
        assert common_utils.get_redis_client(use_redis=True, redis_cluster_nodes=nodes) is not None
    assert [(n.host, n.port) for n in client.call_args.kwargs["startup_nodes"]] == [("2001:db8::1", 6379)]


@pytest.fixture
def build_storage():
    # Isolate API configuration from the UI's same-named app package in the common suite.
    path = ROOT / "src/api/app/rate_limit.py"
    tree = ast.parse(path.read_text())
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_build_storage")
    env = dict(vars(common_utils))
    env.update(
        api_config=SimpleNamespace(API_RATE_LIMIT_STORAGE_OPTIONS=""),
        LOGGER=MagicMock(),
        getenv=lambda _: None,
        cluster_config_error=cluster_config_error,
    )
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), env)
    return lambda cfg: env["_build_storage"]({"USE_REDIS": "yes", "REDIS_DATABASE": "0", **cfg})


@pytest.mark.parametrize("host", ["2001:db8::1", "[2001:db8::1]"])
@pytest.mark.parametrize("ssl", ["yes", "no"])
def test_limiter_direct_ipv6_uri(build_storage, host, ssl):
    uri, _ = build_storage({"REDIS_HOST": host, "REDIS_PORT": "6380", "REDIS_SSL": ssl, "REDIS_USERNAME": "user", "REDIS_PASSWORD": "pass"})
    assert uri == ("rediss" if ssl == "yes" else "redis") + "://user:pass@[2001:db8::1]:6380/0"
    assert parse_storage_uri(uri).locations == [("2001:db8::1", 6380)]


@pytest.mark.parametrize("nodes", ["[2001:db8::1]", "[2001:db8::1]:6379"])
def test_limiter_cluster_default_port(build_storage, nodes):
    uri, options = build_storage({"REDIS_CLUSTER_NODES": nodes, "REDIS_SSL": "yes", "REDIS_SSL_VERIFY": "yes", "REDIS_PASSWORD": "pass"})
    assert parse_storage_uri(uri).locations == [("2001:db8::1", 6379)]
    assert [(n.host, n.port) for n in options["startup_nodes"]] == [("2001:db8::1", 6379)]
    assert (options["ssl"], options["ssl_cert_reqs"], options["password"]) == (True, "required", "pass")


@pytest.mark.parametrize(
    ("hosts", "expected"),
    [
        ("[2001:db8::1]:26380 [2001:db8::2]:26381", [("2001:db8::1", 26380), ("2001:db8::2", 26381)]),
        ("[2001:db8::1] 2001:db8::2", [("2001:db8::1", 26379), ("2001:db8::2", 26379)]),
        ("redis:26381 [2001:db8::1]:26380", [("2001:db8::1", 26380), ("redis", 26381)]),
    ],
)
def test_limiter_sentinel_endpoints(build_storage, hosts, expected):
    uri, options = build_storage(
        {"REDIS_SENTINEL_HOSTS": hosts, "REDIS_SENTINEL_MASTER": "master", "REDIS_PASSWORD": "master-pass", "REDIS_SENTINEL_PASSWORD": "sentinel-pass"}
    )
    assert parse_storage_uri(uri).locations == expected
    assert options["password"] == "master-pass"
    assert options["sentinel_kwargs"]["password"] == "sentinel-pass"


@pytest.mark.parametrize("cfg", [{"REDIS_HOST": "[broken]"}, {"REDIS_SENTINEL_HOSTS": "[broken]", "REDIS_SENTINEL_MASTER": "master"}])
def test_invalid_limiter_endpoint_falls_back(build_storage, cfg):
    assert build_storage(cfg)[0] == "memory://"


@pytest.mark.parametrize("script", ["test_ipv6_redis_lua.lua", "test_ipv6_redis_connector.lua", "test_lua_ipv6_rediscluster.lua"])
def test_lua_ipv6_endpoints(script):
    lua = shutil.which("lua5.4") or shutil.which("lua")
    if not lua or "Lua 5.4" not in subprocess.run([lua, "-v"], capture_output=True, text=True, check=False).stdout:
        pytest.skip("plain Lua 5.4 required")
    result = subprocess.run([lua, str(ROOT / "tests/unit" / script)], capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
