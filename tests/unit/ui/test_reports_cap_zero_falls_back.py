"""`METRICS_MAX_BLOCKED_REQUESTS_REDIS=0` means "keep the reports out of Redis", not "there
are no reports".

Port of dev 27a8aa150. Every Redis read path answered an explicit *empty* result on a cap of
0 — an empty report list, zeroed home tiles, no report detail — while each instance still
held its own full buffer in the shared dict. Cap 0 has to behave like Redis being absent, so
the instance-API fallback runs.
"""

import sys
import types
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3] / "src"


@pytest.fixture()
def model():
    from app.models import instance as instance_module

    return instance_module


class _Client:
    """Only what `_get_max_blocked_requests_redis` reads."""

    def __init__(self, cap):
        self.cap = cap

    def get_global_settings(self, **_):
        return {"METRICS_MAX_BLOCKED_REQUESTS_REDIS": self.cap}


class _Redis:
    """A live, reachable Redis holding a trimmed-away (hence empty) list."""

    def __init__(self):
        self.calls = []

    def llen(self, key):
        self.calls.append(("llen", key))
        return 0

    def pipeline(self, *_, **__):  # pragma: no cover - must never be reached on cap 0
        raise AssertionError("cap 0 must not read the Redis list at all")


@pytest.fixture()
def utils(model, monkeypatch):
    def _build(cap, redis_client):
        stub = types.ModuleType("app.routes.utils")
        stub.get_redis_client = lambda: redis_client
        monkeypatch.setitem(sys.modules, "app.routes.utils", stub)
        obj = object.__new__(model.InstancesUtils)
        # Name-mangled: `__init__` wants a live client.
        setattr(obj, "_InstancesUtils__api_client", _Client(cap))
        return obj

    return _build


def _no_instances(obj, monkeypatch):
    """The instance fallback with nothing to fan out to: an empty answer that came from the
    *instances*, not from a Redis short-circuit."""
    monkeypatch.setattr(type(obj), "get_instances", lambda self, **_: [])


# --------------------------------------------------------------------------------------
# The defect, one call site at a time
# --------------------------------------------------------------------------------------
def test_the_report_table_asks_the_instances_instead_of_answering_empty(utils, monkeypatch):
    obj = utils("0", _Redis())
    instance = types.SimpleNamespace(
        hostname="bw-1",
        reports_query=lambda *args, **kwargs: (
            True,
            {"bw-1": {"msg": {"total": 1, "data": [{"id": "kept", "date": 1.0}]}}},
        ),
    )
    monkeypatch.setattr(type(obj), "get_instances", lambda self, **_: [instance])

    result = obj.get_reports_query(start=0, length=10)

    assert result["data"] == [{"id": "kept", "date": 1.0}], "cap 0 short-circuited to an empty page instead of the instances"


def test_a_report_detail_asks_the_instances_instead_of_answering_empty(utils, monkeypatch):
    obj = utils("0", _Redis())
    _no_instances(obj, monkeypatch)

    # No instances are up, so the honest answer is None — but only after the fallback ran.
    # The pre-fix code returned `{}` straight out of the Redis branch instead.
    assert obj.get_report_data("some-id") is None


def test_the_home_tiles_read_the_instance_buffers(utils, monkeypatch):
    obj = utils("0", _Redis())
    seen = {}

    def fake_iter(self):
        seen["called"] = True
        return iter(())

    monkeypatch.setattr(type(obj), "_iter_instance_api_requests", fake_iter)
    obj.get_home_aggregates(hours=1, redis_client=_Redis())

    assert seen.get("called"), "cap 0 returned zeroed tiles instead of reading the instances"


def test_requests_metrics_fall_through_rather_than_pinning_an_empty_list(utils, monkeypatch):
    """`{"requests": []}` is truthy, so it short-circuited the instance fan-out in
    `get_metrics`; `{}` is not, and falls through."""
    obj = utils("0", _Redis())
    instance = types.SimpleNamespace(
        hostname="bw-1",
        metrics=lambda plugin_id: (True, {"bw-1": {"status": "success", "data": {"requests": [{"id": "kept"}]}}}),
    )
    monkeypatch.setattr(type(obj), "get_instances", lambda self, **_: [instance])

    result = obj.get_metrics("requests")

    assert result.get("requests") == [{"id": "kept"}]


# --------------------------------------------------------------------------------------
# The non-zero path is untouched
# --------------------------------------------------------------------------------------
def test_a_configured_cap_still_reads_redis(utils, monkeypatch):
    obj = utils("10k", _Redis())
    seen = {}

    def fake_iter(self, redis_client, **kwargs):
        seen["kwargs"] = kwargs
        return iter(())

    monkeypatch.setattr(type(obj), "_iter_redis_requests", fake_iter)
    _no_instances(obj, monkeypatch)

    obj.get_report_data("some-id")

    assert seen.get("kwargs") is not None, "a real cap must still take the Redis path"
