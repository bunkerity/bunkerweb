"""FastAPI /metrics/timings fanout contract.

Timings are the one metrics endpoint that is *not* served from the database: the aggregates
live in each instance's shared memory, so this router fans out and merges, the way the
web-cache router reads cache status. The merge arithmetic is what these tests pin — counts
and sums add across instances, max is the largest seen, and mean is derived at the edge.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = get


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_metrics": ModuleType("bw_metrics"),
        "bw_metrics.routers": ModuleType("bw_metrics.routers"),
        "bw_metrics.auth": ModuleType("bw_metrics.auth"),
        "bw_metrics.auth.guard": ModuleType("bw_metrics.auth.guard"),
        "bw_metrics.deps": ModuleType("bw_metrics.deps"),
        "bw_metrics.utils": ModuleType("bw_metrics.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_metrics"].__path__ = []
    names["bw_metrics.routers"].__path__ = []
    names["bw_metrics.auth"].__path__ = []
    names["bw_metrics.auth.guard"].guard = object()
    names["bw_metrics.deps"].get_instances_api_caller = object()
    names["bw_metrics.utils"].get_db = lambda: SimpleNamespace()
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "metrics.py"
        spec = importlib.util.spec_from_file_location("bw_metrics.routers.metrics", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


def _caller(ok, responses):
    caller = Mock()
    caller.send_to_apis.return_value = (ok, responses)
    return caller


def _agg(count, total, peak):
    return {"count": count, "sum": total, "max": peak}


def _ok(payload):
    return {"status": "success", "msg": payload}


def test_a_single_instance_is_reported_with_a_derived_mean():
    caller = _caller(True, {"bw-1": _ok({"blacklist": {"access": _agg(4, 0.8, 0.5)}})})

    response = ROUTER.query_metrics_timings(caller)

    assert response.status_code == 200
    stats = response.content["timings"]["blacklist"]["access"]
    assert stats["count"] == 4
    assert stats["sum"] == 0.8
    assert stats["max"] == 0.5
    assert stats["mean"] == 0.2
    caller.send_to_apis.assert_called_once_with("GET", "/metrics/timings", response=True)


def test_counts_and_sums_add_across_instances_and_max_is_the_largest():
    # The largest max is merged FIRST on purpose: if it came last, plain assignment would
    # produce the same answer as max() and the mutation would go unnoticed.
    caller = _caller(
        True,
        {
            "bw-1": _ok({"blacklist": {"access": _agg(3, 0.6, 0.9)}}),
            "bw-2": _ok({"blacklist": {"access": _agg(2, 0.4, 0.3)}}),
        },
    )

    stats = ROUTER.query_metrics_timings(caller).content["timings"]["blacklist"]["access"]

    assert stats["count"] == 5
    assert round(stats["sum"], 10) == 1.0
    assert stats["max"] == 0.9, "the peak is the worst seen anywhere, not the last one merged"
    assert round(stats["mean"], 10) == 0.2


def test_distinct_plugins_and_phases_stay_separate():
    caller = _caller(
        True,
        {
            "bw-1": _ok(
                {
                    "blacklist": {"access": _agg(1, 0.1, 0.1), "log": _agg(1, 0.02, 0.02)},
                    "metrics": {"request": _agg(1, 0.5, 0.5)},
                }
            )
        },
    )

    timings = ROUTER.query_metrics_timings(caller).content["timings"]

    assert set(timings) == {"blacklist", "metrics"}
    assert set(timings["blacklist"]) == {"access", "log"}
    assert timings["metrics"]["request"]["count"] == 1


def test_no_instance_answering_is_service_unavailable():
    response = ROUTER.query_metrics_timings(_caller(False, {}))

    assert response.status_code == 503
    assert response.content["status"] == "error"
    assert response.content["timings"] == {}
    assert response.content["message"]


def test_a_partial_fanout_is_multi_status_and_still_returns_what_answered():
    caller = _caller(False, {"bw-1": _ok({"blacklist": {"access": _agg(1, 0.1, 0.1)}})})

    response = ROUTER.query_metrics_timings(caller)

    assert response.status_code == 207
    assert response.content["status"] == "partial"
    assert response.content["timings"]["blacklist"]["access"]["count"] == 1


def test_an_unsuccessful_instance_is_skipped_not_merged():
    # The failing instance carries a well-formed dict payload, so only the status check can
    # reject it -- a shape check alone would let these numbers through.
    caller = _caller(
        True,
        {
            "bw-1": {"status": "error", "msg": {"blacklist": {"access": _agg(99, 99.0, 99.0)}}},
            "bw-2": _ok({"blacklist": {"access": _agg(2, 0.4, 0.3)}}),
        },
    )

    stats = ROUTER.query_metrics_timings(caller).content["timings"]["blacklist"]["access"]

    assert stats["count"] == 2, "the failing instance must not contribute"
    assert stats["max"] == 0.3


def test_a_malformed_payload_does_not_break_the_fanout():
    """One instance returning garbage must not lose the others' numbers."""
    caller = _caller(
        True,
        {
            "bw-1": _ok("not-a-dict"),
            "bw-2": _ok({"blacklist": "not-a-dict"}),
            "bw-3": _ok({"blacklist": {"access": "not-a-dict"}}),
            "bw-4": _ok({"blacklist": {"access": _agg(1, 0.1, 0.1)}}),
        },
    )

    response = ROUTER.query_metrics_timings(caller)

    assert response.status_code == 200
    assert response.content["timings"] == {"blacklist": {"access": {"count": 1, "sum": 0.1, "max": 0.1, "mean": 0.1}}}


def test_non_numeric_aggregate_fields_are_coerced_to_zero():
    caller = _caller(True, {"bw-1": _ok({"blacklist": {"access": {"count": "oops", "sum": None, "max": True}}})})

    stats = ROUTER.query_metrics_timings(caller).content["timings"]["blacklist"]["access"]

    assert stats == {"count": 0.0, "sum": 0.0, "max": 0.0, "mean": 0.0}, "a zero count must not divide"
