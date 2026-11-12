"""#4084: large ModSecurity reports survive the real query and Reports routes.

The synthetic report preserves the attachment's field types and string lengths;
no reporter payload or private request content is stored in the test suite.
Only Redis transport and database configuration are faked by existing harnesses.
"""

import json

import pytest

from app.models.instance import InstancesUtils
from redis_keys import facet_key
from ui.core._ui_core_helpers import FakeRedis, report, seed

CORS = {"Sec-Fetch-Mode": "cors"}
IP = "192.0.2.10"


@pytest.fixture
def large_report():
    return {
        "status": 403,
        "ip": IP,
        "url": "/wp-json/wp/v2/pages/1/autosaves".ljust(48, "x"),
        "synced": False,
        "security_mode": "block",
        "id": "f" * 32,
        "data": {
            "ids": ["941160", "941160", "949110"],
            "anomaly_score": ["10"],
            "msgs": ["x" * 36, "x" * 45, "x" * 32],
            "matched_vars": ['"' * 1000 + "x" * 17648] * 3,
            "matched_var_names": ["ARGS:json.content"] * 3,
        },
        "user_agent": "x" * 111,
        "reason": "modsecurity",
        "server_name": "example.test",
        "method": "POST",
        "date": 1792576199.353,
        "country": "FR",
    }


@pytest.fixture
def query_redis(h, monkeypatch):
    redis = FakeRedis()
    h.db.get_config.return_value = {"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "10000"}
    h.config.get_config.return_value = {}
    monkeypatch.setattr(h.utils, "get_redis_client", lambda: redis)
    monkeypatch.setattr(h.routes.reports, "BW_INSTANCES_UTILS", InstancesUtils(h.db))
    h.routes.reports.REPORTS_FILTERS_CACHE.clear()
    yield redis
    h.routes.reports.REPORTS_FILTERS_CACHE.clear()


@pytest.mark.parametrize("certified", [True, False], ids=["certified", "streaming"])
@pytest.mark.parametrize("ip_filter", [True, False], ids=["ip-filter", "unfiltered"])
def test_large_report_is_counted_returned_and_lazy_loaded(h, query_redis, large_report, certified, ip_filter):
    """Catches a payload-size cutoff or disagreement between count-only and row queries."""
    assert 59000 < len(json.dumps(large_report).encode()) < 62000
    seed(query_redis, [large_report], certified=certified)
    client = h.client()
    form = {"start": "0", "length": "10", "order[0][column]": "2", "order[0][dir]": "desc"}
    if ip_filter:
        form["searchPanes[ip][0]"] = IP

    filters = client.post("/reports/filters", headers=CORS, data=form)
    rows = client.post("/reports/fetch", headers=CORS, data=form)

    assert filters.status_code == rows.status_code == 200
    assert filters.get_json()["searchPanes"]["options"]["ip"] == [{"label": IP, "value": IP, "total": 1, "count": 1}]
    body = rows.get_json()
    assert (body["recordsTotal"], body["recordsFiltered"]) == (1, 1)
    assert len(body["data"]) == 1
    row = body["data"][0]
    assert row["request_id"] == "f" * 32
    assert row["has_data"] is True and row["data"] == "available"
    assert len(rows.data) < 2000  # Large matched data belongs in the lazy endpoint.
    details = client.post("/reports/data", headers=CORS, data={"report_id": "f" * 32})
    assert details.status_code == 200 and details.get_json()["data"] == large_report["data"]


@pytest.mark.xfail(strict=True, reason="#4084: balanced per-IP facet drift needs reconciliation in unowned app/models/instance.py / metrics writer")
def test_balanced_stale_ip_facets_match_the_retained_list(h, query_redis, large_report):
    """#4084's 46-vs-42 drift survives aggregate validation when another IP loses four counts."""
    large_reports = [large_report | {"id": f"{i:032x}"} for i in range(42)]
    small_reports = [report(i, ip="198.51.100.20") for i in range(106)]
    seed(query_redis, large_reports + small_reports)
    query_redis.hashes[facet_key(False, "ip")] = {IP.encode(): b"46", b"198.51.100.20": b"102"}
    client = h.client()

    options = client.post("/reports/filters", headers=CORS).get_json()["searchPanes"]["options"]["ip"]
    rows = client.post("/reports/fetch", headers=CORS, data={"searchPanes[ip][0]": IP, "length": "100"}).get_json()

    assert (rows["recordsTotal"], rows["recordsFiltered"], len(rows["data"])) == (148, 42, 42)
    affected = next(option for option in options if option["value"] == IP)
    assert affected["total"] == affected["count"] == 42
