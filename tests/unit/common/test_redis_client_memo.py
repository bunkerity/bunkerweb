"""One Redis client per process, and a down Redis costs one timeout, not one per request.

Port of dev c58b69e07. `get_redis_client` built a brand-new `StrictRedis` — a new connection
pool and a new `PING` — on every call. The Web UI calls it once per request *and* hands the
result to flask-session, so a worker ran several pools at once and paid a round trip to open
each one. Worse, when Redis was down every single call paid a full `REDIS_TIMEOUT` connect
timeout, because nothing remembered the previous failure.

The memo is keyed on the connection parameters, so a configuration change simply produces a
different key; there is no separate invalidation path to get wrong.
"""

import sys
import types

import pytest

import common_utils  # type: ignore


class _FakeRedis:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.pings = 0
        self.closed = False
        _FakeRedis.instances.append(self)

    def ping(self):
        self.pings += 1
        if self.kwargs.get("host") == "down":
            raise ConnectionError("connection refused")
        return True

    def close(self):  # pragma: no cover - the memo must never close a shared client
        self.closed = True


class _FakeSentinel:
    instances = []

    def __init__(self, hosts, **kwargs):
        self.hosts = hosts
        self.kwargs = kwargs
        _FakeSentinel.instances.append(self)

    def discover_master(self, name):
        if name == "unreachable":
            raise ConnectionError("no master")
        return ("127.0.0.1", 6379)

    def master_for(self, name, **kwargs):
        return _FakeRedis(host="sentinel-master", **kwargs)


@pytest.fixture(autouse=True)
def _fake_redis_package(monkeypatch):
    module = types.ModuleType("redis")
    module.StrictRedis = _FakeRedis
    module.Sentinel = _FakeSentinel
    monkeypatch.setitem(sys.modules, "redis", module)
    _FakeRedis.instances = []
    _FakeSentinel.instances = []
    # Module-level memo: never let one test's client or negative window leak into the next.
    monkeypatch.setattr(common_utils, "_REDIS_CLIENT_ENTRY", None, raising=False)
    yield
    common_utils._REDIS_CLIENT_ENTRY = None


def _connect(**overrides):
    kwargs = {"use_redis": True, "redis_host": "redis", "redis_timeout": "1000.0"}
    kwargs.update(overrides)
    return common_utils.get_redis_client(**kwargs)


# --------------------------------------------------------------------------------------
# The memo
# --------------------------------------------------------------------------------------
def test_the_same_configuration_reuses_one_client_and_one_ping():
    first = _connect()
    second = _connect()

    assert first is second
    assert len(_FakeRedis.instances) == 1, "a second client means a second connection pool"
    assert first.pings == 1, "the cache hit must not re-PING: it proves nothing about the next command"


def test_a_changed_setting_produces_a_new_client():
    first = _connect()
    second = _connect(redis_db="3")

    assert first is not second
    assert len(_FakeRedis.instances) == 2


def test_the_superseded_client_is_never_closed():
    """The Web UI hands the very same object to flask-session as `SESSION_REDIS`; closing it
    would break every live session in the worker."""
    first = _connect()
    _connect(redis_db="3")

    assert first.closed is False


def test_the_private_ca_is_part_of_the_key():
    """`REDIS_SSL_CA` changes what the connection trusts, so it cannot be memoised past."""
    first = _connect(redis_ssl=True, redis_ssl_ca="/a.pem")
    second = _connect(redis_ssl=True, redis_ssl_ca="/b.pem")

    assert first is not second


# --------------------------------------------------------------------------------------
# The negative window
# --------------------------------------------------------------------------------------
def test_a_down_redis_is_remembered_instead_of_re_timing_out(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(common_utils, "monotonic", lambda: clock[0])

    assert _connect(redis_host="down") is None
    attempts = len(_FakeRedis.instances)

    assert _connect(redis_host="down") is None
    assert len(_FakeRedis.instances) == attempts, "a second connect inside the window pays another full timeout"


def test_the_window_expires_and_another_connect_is_tried(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(common_utils, "monotonic", lambda: clock[0])

    assert _connect(redis_host="down") is None
    attempts = len(_FakeRedis.instances)

    clock[0] += common_utils.REDIS_NEGATIVE_CACHE_SECONDS + 1
    assert _connect(redis_host="down") is None
    assert len(_FakeRedis.instances) > attempts


def test_a_sentinel_failure_arms_the_window_too(monkeypatch):
    """The inner handler this replaces returned early, so the outer `except` never ran and
    every request paid a full `discover_master` timeout against a down Sentinel."""
    clock = [1000.0]
    monkeypatch.setattr(common_utils, "monotonic", lambda: clock[0])

    kwargs = {"redis_sentinel_hosts": [("s1", "26379")], "redis_sentinel_master": "unreachable", "redis_host": None}
    assert _connect(**kwargs) is None
    attempts = len(_FakeSentinel.instances)

    assert _connect(**kwargs) is None
    assert len(_FakeSentinel.instances) == attempts


def test_a_recovered_redis_replaces_the_negative_entry(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(common_utils, "monotonic", lambda: clock[0])

    assert _connect(redis_host="down") is None
    clock[0] += common_utils.REDIS_NEGATIVE_CACHE_SECONDS + 1
    assert _connect(redis_host="redis") is not None
    # A different key, so the healthy client is memoised on its own and hit again.
    before = len(_FakeRedis.instances)
    assert _connect(redis_host="redis") is not None
    assert len(_FakeRedis.instances) == before


# --------------------------------------------------------------------------------------
# Pool sizing
# --------------------------------------------------------------------------------------
def test_the_pool_covers_the_whole_process_not_one_nginx_worker(monkeypatch):
    """`REDIS_KEEPALIVE_POOL` sizes the per-NGINX-worker Lua keepalive pool and means nothing
    here. It was only safe as a Python `max_connections` while every call owned a private
    pool; one shared client needs a cap covering every thread that can check one out."""
    monkeypatch.setenv("MAX_THREADS", "64")

    client = _connect(redis_keepalive_pool="10")

    assert client.kwargs["max_connections"] == common_utils.shared_redis_pool_size()
    assert client.kwargs["max_connections"] > 10


@pytest.mark.parametrize(
    "env,expected",
    [
        ({"MAX_THREADS": "64"}, (64 + 8) * 2),
        ({"MAX_WORKERS": "4"}, (8 + 8) * 2),
        ({"MAX_THREADS": "1"}, 32),
        ({"MAX_THREADS": "not-a-number", "MAX_WORKERS": "not-a-number"}, 32),
    ],
)
def test_the_pool_size_formula(monkeypatch, env, expected):
    monkeypatch.delenv("MAX_THREADS", raising=False)
    monkeypatch.delenv("MAX_WORKERS", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    assert common_utils.shared_redis_pool_size() == expected


def test_the_floor_is_never_below_the_two_ui_executors(monkeypatch):
    """`dependencies.py` runs two 4-worker executors on top of the request threads, and
    redis-py *raises* once the pool is exhausted rather than blocking."""
    monkeypatch.setenv("MAX_THREADS", "0")

    assert common_utils.shared_redis_pool_size() >= 32
