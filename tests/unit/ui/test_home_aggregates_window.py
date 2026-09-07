"""Every home-dashboard aggregate must answer for the SAME window.

`get_home_aggregates(hours=N)` windows the countries, the timeline and the status cards to the last
N hours, but read the top blocked IPs and the unique-IP count out of the Redis IP facet hash, which
counts the WHOLE retained list (up to `METRICS_MAX_BLOCKED_REQUESTS_REDIS`, days of traffic). The
two halves of one dashboard therefore described two different periods, and the tile with the biggest
number was the one nobody could reconcile.

Port of the `src/ui/app/models/instance.py` half of dev `b5da7332e` (the metrics half of that commit
is a 1.8 row: 1.7's facet writer emits no `requests:facets:initialized` certificate).
"""

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3] / "src"


@pytest.fixture(scope="module")
def instance_module():
    for path in (_SRC / "ui", _SRC / "common" / "utils", _SRC / "common" / "api", _SRC / "common" / "db"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location("instance_model_window_under_test", _SRC / "ui" / "app" / "models" / "instance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _no_aggregate_cache(instance_module):
    """`get_home_aggregates` memoizes per (hours, top_ips_limit) for 30s, in-process and in Redis."""
    instance_module._HOME_AGG_CACHE.clear()
    yield
    instance_module._HOME_AGG_CACHE.clear()


def _utils(module, reports):
    """`InstancesUtils` with the Redis plumbing replaced by a fixed report list."""
    utils = object.__new__(module.InstancesUtils)
    utils._get_max_blocked_requests_redis = lambda: 10000
    utils._get_redis_scan_start_index = lambda *_a, **_kw: 0
    utils._iter_redis_requests = lambda *_a, **_kw: iter(reports)
    # The IP facet hash the pre-port code read instead of counting in the window: one IP, 5 hits,
    # none of them inside the window the caller asked for. Without this the facet read raised on the
    # fake client and the old code fell through to the windowed count -- i.e. the test could not
    # fail on the unfixed code (Criticos R1).
    utils._iter_redis_hash = lambda *_a, **_kw: iter([(b"10.0.0.2", b"5")])
    utils._decode_redis_text = lambda raw: raw.decode() if isinstance(raw, bytes) else str(raw)
    utils._get_shared_home_aggregates = lambda *_a, **_kw: None
    utils._set_shared_home_aggregates = lambda *_a, **_kw: None
    return utils


def _report(ip, age_hours, *, report_id=None, status=403):
    return {
        "id": report_id if report_id is not None else f"{ip}-{age_hours}",
        "ip": ip,
        "status": status,
        "country": "FR",
        "date": (datetime.now().astimezone() - timedelta(hours=age_hours)).timestamp(),
    }


def test_the_top_blocked_ips_answer_for_the_selected_window(instance_module):
    """The regression: an IP blocked only outside the window used to top the tile."""
    reports = [_report("10.0.0.1", 0.5)] + [_report("10.0.0.2", 40 + i, report_id=f"old-{i}") for i in range(5)]
    utils = _utils(instance_module, reports)

    aggregates = utils.get_home_aggregates(hours=2, redis_client=object())

    assert aggregates["top_blocked_ips"] == {"10.0.0.1": {"blocked": 1}}, "an out-of-window IP reached the dashboard"
    assert aggregates["blocked_unique_ips"] == 1


def test_a_duplicated_report_is_counted_once(instance_module):
    """The retained list holds the same report twice whenever a sync round overlaps a push."""
    duplicated = _report("10.0.0.3", 0.5, report_id="same")
    utils = _utils(instance_module, [duplicated, dict(duplicated)])

    aggregates = utils.get_home_aggregates(hours=2, redis_client=object())

    assert aggregates["top_blocked_ips"] == {"10.0.0.3": {"blocked": 1}}
    assert sum(aggregates["time_buckets"].values()) == 1


def test_a_report_dated_in_the_future_is_not_counted(instance_module):
    """A skewed instance clock inflated the country and status tiles; no bucket ever took it."""
    utils = _utils(instance_module, [_report("10.0.0.4", -5)])

    aggregates = utils.get_home_aggregates(hours=2, redis_client=object())

    assert aggregates["request_countries"] == {}
    assert aggregates["top_blocked_ips"] == {}
    assert sum(aggregates["time_buckets"].values()) == 0


def test_a_report_that_cannot_be_decoded_is_dropped_by_the_decoder(instance_module):
    """`_decode_redis_report` is the one gate: an unhashable id would raise in the de-dup set."""
    decode = instance_module.InstancesUtils._decode_redis_report

    assert decode(b'{"id": "a", "date": 1}') == {"id": "a", "date": 1}
    assert decode(b"not json") is None
    assert decode(b'["not", "a", "dict"]') is None
    assert decode(b'{"id": {"unhashable": true}, "date": 1}') is None
    assert decode(b'{"id": "a", "date": "NaN"}') is None
    assert decode(b'{"id": "a", "date": "Infinity"}') is None


def test_a_report_without_a_date_still_sorts(instance_module):
    """`float(None)` raises; the whole reports page used to 500 on one such row."""
    utils = object.__new__(instance_module.InstancesUtils)

    ordered = utils._sort_reports([{"date": None}, {"date": 2}], "date", "desc")

    assert [report["date"] for report in ordered] == [2, None]
