"""Every Redis read path paid two LLENs for the same list, and fanned out to the instances
one at a time.

Port of dev c58b69e07:

* `_get_redis_scan_start_index` issued an LLEN to compute the offset, then
  `_iter_redis_requests` issued its own LLEN for the same list on the same request to bound
  the scan. `_get_redis_scan_window` returns both, so the length travels with the offset.
* `_get_max_blocked_requests_redis` pulled the *whole* global configuration out of the
  central API on every one of those paths, and fell back to 100000 — ten times the cap the
  Redis list is actually trimmed to.
* `get_reports` walked the instances serially, so the page cost the sum of every instance's
  HTTP latency instead of the slowest one.
"""

import threading
import time
import types

import pytest


@pytest.fixture()
def model():
    from app.models import instance as instance_module

    return instance_module


class _Redis:
    def __init__(self, length=0, raises=False):
        self.length = length
        self.raises = raises
        self.llen_calls = 0
        self.ranges = []

    def llen(self, key):
        self.llen_calls += 1
        if self.raises:
            raise ConnectionError("redis down")
        return self.length

    def pipeline(self, *_, **__):
        return _Pipe(self)


class _Pipe:
    def __init__(self, redis):
        self.redis = redis
        self.queued = []

    def lrange(self, key, start, stop):
        self.queued.append((start, stop))

    def execute(self):
        out = []
        for start, stop in self.queued:
            self.redis.ranges.append((start, stop))
            out.append([] if start >= self.redis.length else [b'{"id": "r%d"}' % start])
        self.queued = []
        return out


class _Client:
    def __init__(self, settings=None, raises=None):
        self.settings = settings or {}
        self.raises = raises
        self.calls = []

    def get_global_settings(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        return self.settings


def _utils(model, client=None):
    obj = object.__new__(model.InstancesUtils)
    setattr(obj, "_InstancesUtils__api_client", client or _Client())
    return obj


# --------------------------------------------------------------------------------------
# One LLEN per read path
# --------------------------------------------------------------------------------------
def test_the_window_returns_the_length_it_already_read(model):
    redis = _Redis(length=25000)

    start, total = _utils(model)._get_redis_scan_window(redis, 10000)

    assert (start, total) == (15000, 25000)
    assert redis.llen_calls == 1


def test_the_iterator_does_not_re_read_a_length_it_was_handed(model):
    redis = _Redis(length=3)
    obj = _utils(model)
    start, total = obj._get_redis_scan_window(redis, 10000)

    list(obj._iter_redis_requests(redis, chunk_size=1, start_index=start, total=total))

    assert redis.llen_calls == 1, "the second LLEN is the one this port removes"


def test_the_iterator_still_bounds_itself_when_no_length_is_passed(model):
    """Callers that never computed a window keep the old contract."""
    redis = _Redis(length=2)

    list(_utils(model)._iter_redis_requests(redis, chunk_size=1))

    assert redis.llen_calls == 1


def test_a_cap_of_zero_scans_from_the_head_but_still_reports_the_length(model):
    redis = _Redis(length=42)

    assert _utils(model)._get_redis_scan_window(redis, 0) == (0, 42)


def test_an_unreadable_length_leaves_the_iterator_on_chunk_termination(model):
    """`None` is the iterator's signal to fall back to short/empty-chunk termination, which
    is the contract the original code kept on an LLEN error."""
    redis = _Redis(raises=True)
    obj = _utils(model)

    assert obj._get_redis_scan_window(redis, 10000) == (0, None)

    redis.raises = False
    redis.length = 2
    reports = list(obj._iter_redis_requests(redis, chunk_size=1, start_index=0, total=None))
    assert len(reports) == 2


# --------------------------------------------------------------------------------------
# The cap read
# --------------------------------------------------------------------------------------
def test_the_cap_read_is_filtered_to_the_one_setting_it_needs(model):
    client = _Client({"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "10k"})

    _utils(model, client)._get_max_blocked_requests_redis()

    assert client.calls[0].get("filtered_settings") == ("METRICS_MAX_BLOCKED_REQUESTS_REDIS",)


def test_the_fallback_no_longer_authorises_a_wider_scan_than_the_operator_configured(model):
    """The fallback used to be 100000 while the shipped default trims the list to 10k."""
    from json import loads
    from pathlib import Path

    from app.api_client import ApiUnavailableError

    manifest = loads((Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "metrics" / "plugin.json").read_text(encoding="utf-8"))
    shipped = manifest["settings"]["METRICS_MAX_BLOCKED_REQUESTS_REDIS"]["default"]

    obj = _utils(model, _Client(raises=ApiUnavailableError("api down")))

    assert obj._get_max_blocked_requests_redis() == model._parse_count(shipped, 0)


# --------------------------------------------------------------------------------------
# The instance fan-out
# --------------------------------------------------------------------------------------
def test_the_instances_are_queried_at_once_not_one_after_another(model):
    barrier = threading.Barrier(3, timeout=5)

    def collect(instance):
        # Deadlocks (and fails the test) if the calls are serialised.
        barrier.wait()
        return [{"id": instance}]

    result = model.InstancesUtils._gather_from_instances(["a", "b", "c"], collect)

    assert sorted(r["id"] for r in result) == ["a", "b", "c"]


def test_a_single_instance_is_not_worth_a_thread_pool(model):
    seen = {}

    def collect(instance):
        seen["thread"] = threading.current_thread()
        return [{"id": instance}]

    result = model.InstancesUtils._gather_from_instances(["only"], collect)

    assert result == [{"id": "only"}]
    assert seen["thread"] is threading.current_thread()


def test_no_instances_means_no_work(model):
    assert model.InstancesUtils._gather_from_instances([], lambda _: pytest.fail("must not be called")) == []


def test_get_reports_goes_through_the_parallel_gather(model, monkeypatch):
    calls = []

    def slow(instance):
        calls.append(instance.hostname)
        time.sleep(0.05)
        return (True, {instance.hostname: {"msg": {"requests": [{"id": instance.hostname, "date": 1.0}]}}})

    instances = [types.SimpleNamespace(hostname=f"bw-{i}", reports=lambda i=i: slow(types.SimpleNamespace(hostname=f"bw-{i}"))) for i in range(4)]
    obj = _utils(model)
    monkeypatch.setattr(type(obj), "get_instances", lambda self, **_: instances)

    started = time.monotonic()
    reports = obj.get_reports()
    elapsed = time.monotonic() - started

    assert sorted(r["id"] for r in reports) == ["bw-0", "bw-1", "bw-2", "bw-3"]
    assert elapsed < 0.05 * len(instances), "four 50 ms instances must not cost 200 ms"
