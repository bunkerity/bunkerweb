"""When the gunicorn master picked Redis, a worker builds the Redis session whatever it sees at boot.

The master's choice (`UI_SESSION_BACKEND=redis`) still depended on the worker getting a client, so a worker
recycled by max_requests pinned itself to file sessions while its siblings stayed on Redis, and the user was
logged out on every other request. Two ways it happened:

- Redis was down when the worker booted, so the client builder (which pings) returned `None`;
- `USE_REDIS` had been changed to `no` after the master decided, and the worker re-read it.

main.py's real session block runs here with the real client builders (`app/routes/utils.py` and
`common_utils`) against a real `redis-server`, so it needs the packages the UI image ships.
"""

import shutil
import socket
from unittest.mock import Mock

import pytest

pytest.importorskip("flask_session")
pytest.importorskip("redis")
pytest.importorskip("msgspec")
pytest.importorskip("cachelib")

from flask import g, has_request_context  # noqa: E402

import common_utils  # type: ignore  # noqa: E402
from test_resilient_redis_session import build_app, redis_server  # noqa: E402,F401
from test_session_plumbing import UTILS, _shipped  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("redis-server") is None, reason="needs the redis-server binary")


def _worker_client_builder(monkeypatch, port: int, use_redis: str):
    """Namespace overrides: `get_redis_client` as shipped, over the real `common_utils` builder and a settings store that says `use_redis`."""
    monkeypatch.setattr(common_utils, "_REDIS_CLIENT_ENTRY", None)  # the process-wide memo, empty at worker boot
    bw_config = Mock()
    bw_config.get_config.return_value = {"USE_REDIS": use_redis, "REDIS_HOST": "127.0.0.1", "REDIS_PORT": str(port), "REDIS_TIMEOUT": "300"}
    namespace = _shipped(
        UTILS,
        ("get_redis_client",),
        {
            "BW_CONFIG": bw_config,
            "LOGGER": Mock(),
            "g": g,
            "has_request_context": has_request_context,
            "get_common_redis_client": common_utils.get_redis_client,
            "getenv_bool": common_utils.getenv_bool,
            "flash": Mock(),
            "translated": lambda *_a, **_k: "",
        },
    )
    return {"get_ui_redis_client": namespace["get_redis_client"], "BW_CONFIG": bw_config}


def _closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _is_resilient_redis(app) -> bool:
    from app.models.resilient_session import ResilientRedisSessionInterface

    return app.config["SESSION_TYPE"] == "redis" and isinstance(app.session_interface, ResilientRedisSessionInterface)


def test_redis_down_at_worker_boot_still_gets_the_resilient_redis_session(monkeypatch, tmp_path):
    monkeypatch.setenv("UI_SESSION_BACKEND", "redis")
    port = _closed_port()
    app, _ = build_app(port, tmp_path, **_worker_client_builder(monkeypatch, port, "yes"))
    assert _is_resilient_redis(app)


def test_use_redis_turned_off_after_the_master_decided_does_not_change_the_worker(monkeypatch, tmp_path, redis_server):  # noqa: F811
    monkeypatch.setenv("UI_SESSION_BACKEND", "redis")
    app, _ = build_app(redis_server.port, tmp_path, **_worker_client_builder(monkeypatch, redis_server.port, "no"))
    assert _is_resilient_redis(app)


def test_without_a_master_decision_use_redis_no_still_means_file_sessions(monkeypatch, tmp_path, redis_server):  # noqa: F811
    monkeypatch.delenv("UI_SESSION_BACKEND", raising=False)
    app, _ = build_app(redis_server.port, tmp_path, **_worker_client_builder(monkeypatch, redis_server.port, "no"))
    assert app.config["SESSION_TYPE"] == "cachelib"


def test_without_a_master_decision_a_down_redis_still_means_file_sessions(monkeypatch, tmp_path):
    monkeypatch.delenv("UI_SESSION_BACKEND", raising=False)
    port = _closed_port()
    app, _ = build_app(port, tmp_path, **_worker_client_builder(monkeypatch, port, "yes"))
    assert app.config["SESSION_TYPE"] == "cachelib"


def test_the_masters_filesystem_decision_wins_over_a_reachable_redis(monkeypatch, tmp_path, redis_server):  # noqa: F811
    monkeypatch.setenv("UI_SESSION_BACKEND", "filesystem")
    app, _ = build_app(redis_server.port, tmp_path, **_worker_client_builder(monkeypatch, redis_server.port, "yes"))
    assert app.config["SESSION_TYPE"] == "cachelib"


def _cluster_client_builder(monkeypatch, ports):
    """Like `_worker_client_builder`, but the settings describe a Redis Cluster whose seed nodes are `ports`."""
    monkeypatch.setattr(common_utils, "_REDIS_CLIENT_ENTRY", None)
    bw_config = Mock()
    bw_config.get_config.return_value = {
        "USE_REDIS": "yes",
        "REDIS_CLUSTER_NODES": " ".join(f"127.0.0.1:{port}" for port in ports),
        "REDIS_TIMEOUT": "300",
    }
    namespace = _shipped(
        UTILS,
        ("get_redis_client",),
        {
            "BW_CONFIG": bw_config,
            "LOGGER": Mock(),
            "g": g,
            "has_request_context": has_request_context,
            "get_common_redis_client": common_utils.get_redis_client,
            "getenv_bool": common_utils.getenv_bool,
            "flash": Mock(),
            "translated": lambda *_a, **_k: "",
        },
    )
    return {"get_ui_redis_client": namespace["get_redis_client"], "BW_CONFIG": bw_config}


def test_redis_cluster_down_at_worker_boot_still_gets_the_resilient_redis_session(monkeypatch, tmp_path):
    """RedisCluster() cannot be built without a reachable node, so the builder used to hand back None here."""
    monkeypatch.setenv("UI_SESSION_BACKEND", "redis")
    ports = [_closed_port(), _closed_port()]
    app, _ = build_app(ports[0], tmp_path, **_cluster_client_builder(monkeypatch, ports))
    assert _is_resilient_redis(app)
