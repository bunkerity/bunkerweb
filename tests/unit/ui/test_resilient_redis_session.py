"""D4: the UI keeps serving sessions when Redis fails after the worker started.

Flask-Session picks its backend once, so a Redis that dies later made every request carrying a
session raise. `chain_session_fallback` only covers a Redis that was down at boot.

The tests run main.py's real session statements (everything from `session_cache_dir` to the
`should_set_storage` override) against a real `redis-server` process they start, stop and restart,
with the real Flask-Session and the real helpers of `app/routes/utils.py`. They need the packages
the UI image ships, so they skip in `.venv-unit`; run them in `.venv`:

    .venv/bin/python -m pytest tests/unit/ui/test_resilient_redis_session.py
"""

import ast
import logging
import os
import shutil
import socket
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic, sleep
from unittest.mock import patch
from typing import Any, Dict, Optional

import pytest

flask = pytest.importorskip("flask")
pytest.importorskip("flask_session")
redis = pytest.importorskip("redis")
msgspec = pytest.importorskip("msgspec")
pytest.importorskip("cachelib")

from flask import Flask, session  # noqa: E402
from markupsafe import Markup  # noqa: E402

from test_session_plumbing import MAIN, UTILS, _shipped, _tree  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("redis-server") is None, reason="needs the redis-server binary")

_UI = MAIN.parent
COOKIE = "bw_ui_session"
PREFIX = "bunkerweb_ui_session:"


class RedisServer:
    """A throwaway `redis-server` the test can stop and bring back on the same port, keys included."""

    def __init__(self, workdir: Path):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.workdir = workdir
        self.process: Optional[subprocess.Popen] = None

    def start(self) -> None:
        self.process = subprocess.Popen(
            [
                "redis-server",
                "--port",
                str(self.port),
                "--bind",
                "127.0.0.1",
                "--save",
                "",
                "--appendonly",
                "yes",
                "--appendfsync",
                "always",
                "--dir",
                str(self.workdir),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = monotonic() + 10
        while monotonic() < deadline:
            try:
                redis.Redis(port=self.port, socket_connect_timeout=0.2).ping()
                return
            except redis.RedisError:
                sleep(0.05)
        raise RuntimeError("redis-server did not start")

    def stop(self) -> None:
        if self.process is not None:
            self.process.terminate()
            self.process.wait(timeout=10)
            self.process = None


@pytest.fixture
def redis_server(tmp_path):
    server = RedisServer(tmp_path)
    server.start()
    yield server
    server.stop()


def _session_statements():
    """main.py's session setup, from the cache directory to the storage-throttle override."""
    for node in ast.walk(_tree(MAIN)):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue

        def assigns(n, target):
            return isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == target

        first = next((i for i, n in enumerate(body) if assigns(n, "session_cache_dir")), None)
        if first is None:
            continue
        last = next(i for i, n in enumerate(body) if assigns(n, "app.session_interface.should_set_storage"))
        return body[first : last + 1]
    pytest.fail("main.py no longer has the session setup block")


def build_app(redis_port: int, tmp_path: Path, **overrides):
    """A Flask app wired by main.py's own session statements, talking to the redis-server."""
    from cachelib.file import FileSystemCache  # noqa: F401
    from flask_session import Session
    from flask_session.cachelib import CacheLibSessionInterface

    from app.models.safe_session_cache import SafeFileSystemCache

    app = Flask("bw_ui_d4_test")
    app.config.update(
        SECRET_KEY="test",
        SESSION_COOKIE_NAME="__Host-bw_ui_session",
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_PATH="/",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        SESSION_REFRESH_EACH_REQUEST=True,
        SESSION_ID_LENGTH=64,
    )
    client = redis.Redis(port=redis_port, socket_timeout=0.3, socket_connect_timeout=0.3)
    utils = _shipped(
        UTILS,
        (
            "PROXIED_SESSION_COOKIE",
            "DIRECT_SESSION_COOKIE",
            "session_cookie_for",
            "bind_session_cookie_per_request",
            "chain_session_fallback",
            "ANONYMOUS_SESSION_SECONDS",
            "cap_anonymous_session_lifetime",
            "SESSION_STORAGE_REFRESH_RATIO",
            "SESSION_LAST_STORED_KEY",
            "session_storage_due",
        ),
        {
            "Any": Any,
            "Dict": Dict,
            "Optional": Optional,
            "Tuple": tuple,
            "timedelta": timedelta,
            "time": monotonic,
            "request": flask.request,
            "SimpleNamespace": __import__("types").SimpleNamespace,
        },
    )
    namespace = {
        "app": app,
        "LIB_DIR": tmp_path,
        "LOGGER": logging.getLogger("bw_ui_d4_test"),
        "SafeFileSystemCache": SafeFileSystemCache,
        "get_ui_redis_client": lambda: client,
        "is_cluster": lambda _client: False,
        "Session": Session,
        "CacheLibSessionInterface": CacheLibSessionInterface,
        "BW_CONFIG": None,
        "getenv": os.getenv,
        "getenv_bool": __import__("common_utils").getenv_bool,
        **{
            name: utils[name] for name in ("chain_session_fallback", "bind_session_cookie_per_request", "cap_anonymous_session_lifetime", "session_storage_due")
        },
    }
    namespace.update(overrides)
    exec(compile(ast.Module(body=_session_statements(), type_ignores=[]), str(MAIN), "exec"), namespace)  # noqa: S102

    @app.route("/login")
    def login():
        session["user"] = "alice"
        session["created"] = datetime(2026, 10, 15, 12, 0, 0).astimezone()
        return "ok"

    @app.route("/whoami")
    def whoami():
        return session.get("user", "anonymous")

    @app.route("/logout")
    def logout():
        session.clear()
        return "bye"

    return app, client


@pytest.fixture
def stack(redis_server, tmp_path):
    app, client = build_app(redis_server.port, tmp_path)
    return app, client, redis_server


def _cookie(browser) -> str:
    cookie = browser.get_cookie(COOKIE)
    assert cookie is not None, "no session cookie was issued"
    return cookie.value


def _reopen_breaker(app) -> None:
    """The interface leaves an unreachable Redis alone for breaker_seconds; skip the wait."""
    app.session_interface._breaker_until = 0.0


def _present(browser, value: str) -> None:
    browser.set_cookie(COOKIE, value, domain="localhost")


def test_sanity_everything_works_while_redis_is_up(stack):
    app, _, _ = stack
    browser = app.test_client()
    assert browser.get("/login").status_code == 200
    assert browser.get("/whoami").get_data(as_text=True) == "alice"


def test_redis_down_at_read_does_not_break_the_request(stack):
    app, _, server = stack
    browser = app.test_client()
    browser.get("/login")
    server.stop()

    response = browser.get("/whoami")

    assert response.status_code == 200, "a session read must not 500 while Redis is down"
    assert response.get_data(as_text=True) == "anonymous"


def test_redis_down_at_write_keeps_the_login(stack):
    app, _, server = stack
    server.stop()
    browser = app.test_client()

    assert browser.get("/login").status_code == 200, "a session write must not 500 while Redis is down"
    assert browser.get("/whoami").get_data(as_text=True) == "alice", "the session was written to the local store"

    server.start()
    _reopen_breaker(app)

    assert browser.get("/whoami").get_data(as_text=True) == "alice", "the session survives Redis coming back"
    assert redis.Redis(port=server.port).exists(PREFIX + _cookie(browser)), "and is written back to Redis"


def test_the_local_store_keeps_datetimes_the_msgspec_way(stack):
    app, client, server = stack
    server.stop()
    browser = app.test_client()
    browser.get("/login")
    server.start()
    _reopen_breaker(app)

    with browser.session_transaction() as stored:
        assert isinstance(stored["created"], datetime)
        assert stored["created"] == datetime(2026, 10, 15, 12, 0, 0).astimezone()


def test_redis_down_at_logout_revokes_the_cookie_once_redis_returns(stack):
    app, _, server = stack
    browser = app.test_client()
    browser.get("/login")
    old_cookie = _cookie(browser)
    server.stop()

    assert browser.get("/logout").status_code == 200, "a logout must not 500 while Redis is down"

    server.start()
    _reopen_breaker(app)
    stale = app.test_client()
    _present(stale, old_cookie)

    assert stale.get("/whoami").get_data(as_text=True) == "anonymous", "the cookie sent at logout must not log anyone in again"


def test_an_unreachable_redis_is_skipped_not_asked_on_every_request(stack):
    app, client, server = stack
    server.stop()
    browser = app.test_client()
    browser.get("/login")

    with patch.object(client, "execute_command", wraps=client.execute_command) as asked:
        for _ in range(5):
            browser.get("/whoami")

    assert asked.call_count == 0, "after the first failure the interface must leave Redis alone until the breaker reopens"


def test_a_delete_that_missed_redis_is_not_undone_when_it_returns(stack):
    """2a39b094c: the tombstone, so the stale copy Redis still holds is not read back."""
    app, client, server = stack
    interface = app.session_interface
    store_id = interface._get_store_id("abc")
    interface._upsert_session(timedelta(hours=1), {"user": "alice"}, store_id)
    server.stop()

    interface._delete_session(store_id)
    server.start()
    _reopen_breaker(app)

    assert interface._retrieve_session_data(store_id) is None
    assert client.exists(store_id) == 0, "the delete is replayed against Redis"


def test_a_write_that_missed_redis_wins_over_the_stale_copy(stack):
    """2a39b094c: the local copy only exists after a Redis write failed, so it is the newer one."""
    app, client, server = stack
    interface = app.session_interface
    store_id = interface._get_store_id("abc")
    interface._upsert_session(timedelta(hours=1), {"user": "alice", "step": 1}, store_id)
    server.stop()

    interface._upsert_session(timedelta(hours=1), {"user": "alice", "step": 2}, store_id)
    server.start()
    _reopen_breaker(app)

    assert interface._retrieve_session_data(store_id) == {"user": "alice", "step": 2}
    assert interface.serializer.decode(client.get(store_id)) == {"user": "alice", "step": 2}, "and Redis is brought up to date"


def test_a_non_redis_client_is_kept_as_is(tmp_path):
    """flask-session swaps any client that is not a redis.Redis (a RedisCluster) for localhost."""
    from app.models.resilient_session import ResilientRedisSessionInterface
    from app.models.safe_session_cache import SafeFileSystemCache

    app = Flask("bw_ui_d4_cluster")
    app.config["SESSION_ID_LENGTH"] = 64
    cluster = object()

    interface = ResilientRedisSessionInterface(
        app, client=cluster, fallback=SafeFileSystemCache(cache_dir=tmp_path, threshold=0), logger=logging.getLogger("t"), key_prefix=PREFIX, sid_length=64
    )

    assert interface.client is cluster


def test_the_serializer_still_refuses_markup_and_stores_plain_str(stack):
    """flask-session-msgspec-refuses-markup: the resilient class must not loosen or replace it."""
    app, _, server = stack
    interface = app.session_interface

    with pytest.raises(TypeError):
        interface.serializer.encode({"_flashes": [("message", Markup("<b>x</b>"))]})

    browser = app.test_client()
    with app.test_request_context():
        pass
    browser.get("/login")
    with browser.session_transaction() as stored:
        stored["_flashes"] = [("message", str(Markup("<b>x</b>")))]
    server.stop()
    server.start()
    assert browser.get("/whoami").get_data(as_text=True) in ("alice", "anonymous")
    raw = redis.Redis(port=server.port).get(PREFIX + _cookie(browser))
    if raw is not None:
        decoded = interface.serializer.decode(raw)
        assert type(decoded["_flashes"][0][1]) is str
