"""Exercise real storage construction without booting the API application."""

import ast
import sys
from pathlib import Path
from itertools import starmap
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import Mock

import pytest

from common_utils import parse_duration
from redis_keys import cluster_config_error, parse_nodes

SOURCE = Path(__file__).resolve().parents[3] / "src/api/app/rate_limit.py"


def load(name, **extra):
    tree = ast.parse(SOURCE.read_text())
    function = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name), None)
    assert function is not None, f"missing {name}"
    namespace = dict(
        Any=Any,
        Dict=Dict,
        List=List,
        Optional=Optional,
        Tuple=Tuple,
        Limiter=Mock,
        LOGGER=Mock(),
        cluster_config_error=cluster_config_error,
        parse_nodes=parse_nodes,
        parse_duration=parse_duration,
        starmap=starmap,
    )
    namespace.update(extra)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace[name]


@pytest.fixture
def storage(monkeypatch):
    cluster = ModuleType("redis.cluster")
    cluster.ClusterNode = lambda host, port: SimpleNamespace(host=host, port=port)
    monkeypatch.setitem(sys.modules, "redis.cluster", cluster)
    return load("_build_storage", getenv=lambda key: None, api_config=SimpleNamespace(API_RATE_LIMIT_STORAGE_OPTIONS=""))


def test_cluster_storage_includes_every_seed_acl_and_private_ca(storage):
    uri, options = storage(
        dict(
            USE_REDIS="yes",
            REDIS_CLUSTER_NODES="[::1]:7000 r2:7001",
            REDIS_USERNAME="bw",
            REDIS_PASSWORD="secret",
            REDIS_SSL="yes",
            REDIS_SSL_CA="/private.pem",
        )
    )
    assert uri == "redis+cluster://[::1]:7000"
    assert [(node.host, node.port) for node in options["startup_nodes"]] == [("::1", 7000), ("r2", 7001)]
    assert options["username"] == "bw" and options["password"] == "secret"
    assert options["ssl"] and options["ssl_ca_certs"] == "/private.pem"
    assert options.get("ssl_cert_reqs", "required") == "required"


@pytest.mark.parametrize(
    "extra", [{"REDIS_DATABASE": "3"}, {"REDIS_DATABASE": "bad"}, {"REDIS_SENTINEL_HOSTS": "s1:26379"}, {"REDIS_CLUSTER_NODES": "bad-port:99999"}]
)
def test_invalid_cluster_config_uses_memory_instead_of_standalone(storage, extra):
    uri, _ = storage(dict(USE_REDIS="yes", REDIS_HOST="standalone", REDIS_CLUSTER_NODES="r1:7000") | extra)
    assert uri == "memory://"


def test_cluster_seed_without_a_port_uses_6379(storage):
    uri, options = storage(dict(USE_REDIS="yes", REDIS_CLUSTER_NODES="r1 r2:7001"))
    assert uri == "redis+cluster://r1:6379"
    assert [(node.host, node.port) for node in options["startup_nodes"]] == [("r1", 6379), ("r2", 7001)]


@pytest.mark.parametrize(("value", "seconds"), [("1000", 1.0), ("2s", 2.0), ("500ms", 0.5), ("1m", 60.0), ("soon", 1.0)])
def test_redis_timeout_accepts_suffixes(storage, value, seconds):
    _, options = storage(dict(USE_REDIS="yes", REDIS_HOST="r", REDIS_TIMEOUT=value))
    assert options["socket_timeout"] == seconds and options["socket_connect_timeout"] == seconds


def test_initial_cluster_failure_constructs_memory_limiter():
    calls = []

    def limiter(**kwargs):
        calls.append(kwargs)
        if kwargs["storage_uri"].startswith("redis+cluster"):
            raise ConnectionError("cluster not yet formed")
        return "memory-limiter"

    make = load("_make_limiter", Limiter=limiter)
    assert (
        make("redis+cluster://r1:7000", {}, key_func=lambda: "ip", default_limits=["1/minute"], strategy="fixed-window", headers_enabled=True)
        == "memory-limiter"
    )
    assert len(calls) == 2 and calls[1]["storage_uri"] == "memory://"
