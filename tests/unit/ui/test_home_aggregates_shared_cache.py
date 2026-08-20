"""Two UI workers must not show different totals on /home.

`InstancesUtils.get_home_aggregates` memoises its 7-day Redis aggregation for `_HOME_AGG_CACHE_TTL`
seconds. That cache is per *process*, so with several gunicorn workers each one computes and holds
its own snapshot, taken at a different instant. Two browser tabs, or one tab and a refresh, land on
different workers and read different numbers for the same dashboard — a wrong figure on screen, not
merely a slow one. The shared tier makes the first worker's snapshot the one they all read.

Only the shared tier is under test here: the aggregation itself is unchanged and covered elsewhere.
The detail worth pinning is the round trip, because JSON does not preserve it — `request_statuses`
is keyed by int in-process (`{200: 5}`) and comes back keyed by string (`{"200": 5}`). A port that
dropped the conversion would look correct in every unit that only checks totals, and would break
status grouping only once a second worker served the page.
"""

import importlib.util
import sys
from json import loads
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3] / "src"


@pytest.fixture(scope="module")
def instance_module():
    for path in (_SRC / "ui", _SRC / "common" / "utils", _SRC / "common" / "api", _SRC / "common" / "db"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location("instance_model_under_test", _SRC / "ui" / "app" / "models" / "instance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def utils(instance_module):
    # __init__ wants a live API client; none of the three methods under test touch it.
    return object.__new__(instance_module.InstancesUtils)


class FakeRedis:
    """Minimal stand-in: records writes, replays them, and can be told to fail."""

    def __init__(self, failing=False):
        self.store = {}
        self.writes = []
        self.failing = failing

    def get(self, key):
        if self.failing:
            raise RuntimeError("redis down")
        return self.store.get(key)

    def set(self, key, value, px=None):
        if self.failing:
            raise RuntimeError("redis down")
        self.store[key] = value
        self.writes.append((key, value, px))


AGGREGATES = {
    "total_requests": 42,
    "request_statuses": {200: 5, 403: 7},
    "top_ips": [["10.0.0.1", 3]],
}


def test_the_key_is_scoped_to_the_window_and_the_limit(utils, instance_module):
    # Two dashboards asking for different windows must not read each other's snapshot.
    assert instance_module.InstancesUtils._home_agg_redis_key((168, 10)) == "metrics:home_agg:168:10"
    assert instance_module.InstancesUtils._home_agg_redis_key((24, 5)) != instance_module.InstancesUtils._home_agg_redis_key((168, 5))


def test_a_snapshot_survives_the_round_trip_with_its_int_status_keys(utils):
    redis = FakeRedis()
    utils._set_shared_home_aggregates(redis, (168, 10), AGGREGATES)

    key, raw, px = redis.writes[0]
    assert key == "metrics:home_agg:168:10"
    # JSON stringifies the int keys on the way out - that is the trap.
    assert loads(raw)["request_statuses"] == {"200": 5, "403": 7}

    back = utils._get_shared_home_aggregates(redis, (168, 10))
    assert back["request_statuses"] == {200: 5, 403: 7}, "int status keys were not restored"
    assert back["total_requests"] == 42
    assert back["top_ips"] == [["10.0.0.1", 3]]


def test_the_snapshot_expires_with_the_same_ttl_as_the_local_cache(utils, instance_module):
    redis = FakeRedis()
    utils._set_shared_home_aggregates(redis, (168, 10), AGGREGATES)
    _, _, px = redis.writes[0]
    # Volatile, so it stays evictable under volatile-lru, and no longer-lived than the local tier.
    assert px == int(instance_module._HOME_AGG_CACHE_TTL * 1000)


def test_a_miss_returns_none_rather_than_an_empty_dashboard(utils):
    assert utils._get_shared_home_aggregates(FakeRedis(), (168, 10)) is None


def test_redis_being_down_is_a_miss_not_an_exception(utils):
    # /home must still render off the local tier when the shared one is unreachable.
    redis = FakeRedis(failing=True)
    assert utils._get_shared_home_aggregates(redis, (168, 10)) is None
    utils._set_shared_home_aggregates(redis, (168, 10), AGGREGATES)  # must not raise


def test_no_redis_client_at_all_is_handled(utils):
    assert utils._get_shared_home_aggregates(None, (168, 10)) is None
    utils._set_shared_home_aggregates(None, (168, 10), AGGREGATES)  # must not raise


def test_corrupt_json_in_redis_is_a_miss(utils):
    redis = FakeRedis()
    redis.store["metrics:home_agg:168:10"] = "{not json"
    assert utils._get_shared_home_aggregates(redis, (168, 10)) is None
