"""Report panes must describe the same retained, unique rows as report queries."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.models.instance import Instance, InstancesUtils, encode_search_panes
from _ui_core_helpers import FIELDS, report, seed
from redis_keys import facet_key, initialized_key


@pytest.fixture
def database():
    db = MagicMock()
    db.get_config.return_value = {"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "3"}
    return db


@pytest.fixture
def utils(redis, routes_utils, database):
    routes_utils.client = redis
    return InstancesUtils(database)


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.xfail(strict=True, reason="#4084: exact facet reconciliation deferred to 1.6.19 (writer-side design, no per-request scan)")
def test_balanced_bucket_drift_is_reconciled_for_every_pane(utils, redis, field):
    seed(redis, [report(1, **{field: "first"}), report(2, **{field: "second"}), report(3, **{field: "second"})])
    redis.hashes[facet_key(False, field)] = {b"first": b"2", b"second": b"1"}

    counts = utils.get_reports_pane_counts()

    assert counts[field] == {"first": {"total": 1, "count": 1}, "second": {"total": 2, "count": 2}}
    assert initialized_key(False) not in redis.kv


@pytest.mark.xfail(strict=True, reason="#4084: exact facet reconciliation deferred to 1.6.19 (writer-side design, no per-request scan)")
def test_facets_outside_the_query_cap_cannot_advertise_an_empty_ip_filter(utils, redis):
    seed(redis, [report(0, ip="old"), report(1, ip="current"), report(2, ip="current"), report(3, ip="current")])

    counts = utils.get_reports_pane_counts()
    query = utils.get_reports_query(count_only=True)
    old_ip_query = utils.get_reports_query(search_panes=encode_search_panes({"ip": ["old"]}))

    assert counts["ip"] == query["pane_counts"]["ip"] == {"current": {"total": 3, "count": 3}}
    assert query["total"] == query["filtered"] == 3
    assert old_ip_query["filtered"] == 0 and old_ip_query["data"] == []


def test_shared_dict_panes_deduplicate_worker_reports_like_the_query(utils, routes_utils, fake_caller):
    routes_utils.client = None
    rows = [report(1), report(1), report(2)]
    caller = fake_caller(
        replies={
            ("GET", "/metrics/requests/query"): (True, {"node": {"msg": {"data": rows, "total": 3}}}),
            ("GET", "/metrics/requests"): (True, {"node": {"msg": {"requests": rows}}}),
        }
    )
    node = Instance("node", "node", "manual", "up", "static", datetime.now(), datetime.now(), caller)

    counts = utils.get_reports_pane_counts(instances=[node])
    query = utils.get_reports_query(instances=[node])

    assert counts["ip"] == query["pane_counts"]["ip"] == {"10.0.0.1": {"total": 1, "count": 1}, "10.0.0.2": {"total": 1, "count": 1}}
    assert query["filtered"] == len(query["data"]) == 2


def test_uncertified_large_report_query_reads_one_small_batch_at_a_time(utils, database, redis, monkeypatch):
    database.get_config.return_value = {"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "1000"}
    seed(redis, [report(i, data={"matched_vars": ["x" * 60570]}) for i in range(300)], certified=False)
    ranges = []
    lrange = redis.lrange

    def read_batch(key, start, end):
        ranges.append((start, end))
        return lrange(key, start, end)

    monkeypatch.setattr(redis, "lrange", read_batch)
    query = utils.get_reports_query(count_only=True)

    assert query["total"] == query["filtered"] == 300
    assert all(end - start + 1 <= 256 for start, end in ranges)
