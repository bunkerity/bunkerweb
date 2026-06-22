"""DatabaseMetricsMixin — blocked-request reports persistence (bw_metrics_requests).

Requests carries no FKs (multi-instance, instance-agnostic), so the plain ``db``
fixture suffices — no seeding needed. Records mirror the per-request shape the Lua
``/metrics/requests/query`` endpoint returns (``date`` is a Unix epoch int).
"""

from datetime import datetime, timezone

# fixed epoch for determinism: 2024-01-01T00:00:00Z
EPOCH = 1704067200


def _rec(request_id, *, status=403, security_mode="block", date=EPOCH, **over):
    rec = {
        "id": request_id,
        "date": date,
        "ip": "1.2.3.4",
        "country": "US",
        "method": "GET",
        "url": "/admin",
        "status": status,
        "user_agent": "curl/8",
        "reason": "blacklist",
        "server_name": "app.example.com",
        "data": "",
        "security_mode": security_mode,
    }
    rec.update(over)
    return rec


class TestBatchUpsert:
    def test_insert_and_read_back(self, db):
        assert db.batch_upsert_metrics_requests([_rec("r1"), _rec("r2")], instance_hostname="bw-1") == ""
        res = db.get_metrics_requests()
        assert res["total"] == 2
        assert res["filtered"] == 2
        assert {r["request_id"] for r in res["data"]} == {"r1", "r2"}
        assert all(r["instance_hostname"] == "bw-1" for r in res["data"])

    def test_empty_batch_is_noop(self, db):
        assert db.batch_upsert_metrics_requests([], instance_hostname="bw-1") == ""
        assert db.get_metrics_requests()["total"] == 0

    def test_data_dict_round_trips(self, db):
        # the WAF detail blob arrives as a dict (JSON-decoded from the instance) and must round-trip
        payload = {"rule_id": "942100", "matched": "' OR 1=1"}
        assert db.batch_upsert_metrics_requests([_rec("r1", data=payload)], instance_hostname="bw-1") == ""
        assert db.get_metrics_requests()["data"][0]["data"] == payload

    def test_pre_existing_row_does_not_abort_batch(self, db):
        # a prior scrape already stored r1; a new batch with r1+r2 must still insert r2 (no batch abort)
        assert db.batch_upsert_metrics_requests([_rec("r1")], instance_hostname="bw-1") == ""
        assert db.batch_upsert_metrics_requests([_rec("r1"), _rec("r2")], instance_hostname="bw-1") == ""
        assert {r["request_id"] for r in db.get_metrics_requests()["data"]} == {"r1", "r2"}


class TestDedup:
    def test_same_instance_request_id_is_idempotent(self, db):
        assert db.batch_upsert_metrics_requests([_rec("r1")], instance_hostname="bw-1") == ""
        assert db.batch_upsert_metrics_requests([_rec("r1")], instance_hostname="bw-1") == ""
        assert db.get_metrics_requests()["total"] == 1

    def test_duplicate_within_batch_collapses(self, db):
        assert db.batch_upsert_metrics_requests([_rec("r1"), _rec("r1")], instance_hostname="bw-1") == ""
        assert db.get_metrics_requests()["total"] == 1

    def test_same_request_id_distinct_instances_both_kept(self, db):
        assert db.batch_upsert_metrics_requests([_rec("r1")], instance_hostname="bw-1") == ""
        assert db.batch_upsert_metrics_requests([_rec("r1")], instance_hostname="bw-2") == ""
        assert db.get_metrics_requests()["total"] == 2


class TestQueryFilterSearch:
    def test_report_filter_excludes_2xx_block(self, db):
        db.batch_upsert_metrics_requests([_rec("ok", status=200), _rec("bad", status=403)], instance_hostname="bw-1")
        res = db.get_metrics_requests()
        assert res["total"] == 2  # both stored
        assert res["filtered"] == 1  # only the 403 is a report
        assert [r["request_id"] for r in res["data"]] == ["bad"]

    def test_detect_mode_included_regardless_of_status(self, db):
        db.batch_upsert_metrics_requests([_rec("d", status=200, security_mode="detect")], instance_hostname="bw-1")
        res = db.get_metrics_requests()
        assert res["filtered"] == 1
        assert res["data"][0]["request_id"] == "d"

    def test_search_matches_substring(self, db):
        db.batch_upsert_metrics_requests([_rec("a", url="/admin"), _rec("b", url="/public")], instance_hostname="bw-1")
        res = db.get_metrics_requests(search="admin")
        assert res["filtered"] == 1
        assert res["data"][0]["request_id"] == "a"

    def test_pane_filter_by_field(self, db):
        db.batch_upsert_metrics_requests([_rec("a", ip="1.1.1.1"), _rec("b", ip="2.2.2.2")], instance_hostname="bw-1")
        res = db.get_metrics_requests(filters={"ip": ["1.1.1.1"]})
        assert res["filtered"] == 1
        assert res["data"][0]["request_id"] == "a"

    def test_order_and_pagination(self, db):
        db.batch_upsert_metrics_requests([_rec("old", date=EPOCH), _rec("new", date=EPOCH + 100)], instance_hostname="bw-1")
        newest_first = db.get_metrics_requests(order_column="date", order_dir="desc")
        assert [r["request_id"] for r in newest_first["data"]] == ["new", "old"]
        page = db.get_metrics_requests(length=1, start=0, order_column="date", order_dir="asc")
        assert [r["request_id"] for r in page["data"]] == ["old"]
        assert page["filtered"] == 2  # filtered count ignores pagination

    def test_count_only_returns_no_rows(self, db):
        db.batch_upsert_metrics_requests([_rec("a"), _rec("b")], instance_hostname="bw-1")
        res = db.get_metrics_requests(count_only=True)
        assert res["filtered"] == 2
        assert res["data"] == []


class TestFacets:
    def test_facets_total_and_count_per_value(self, db):
        db.batch_upsert_metrics_requests(
            [_rec("a", country="US", ip="1.1.1.1"), _rec("b", country="US", ip="2.2.2.2"), _rec("c", country="FR", ip="1.1.1.1")],
            instance_hostname="bw-1",
        )
        facets = db.get_metrics_facets()
        assert facets["country"] == {"US": {"total": 2, "count": 2}, "FR": {"total": 1, "count": 1}}
        assert facets["ip"] == {"1.1.1.1": {"total": 2, "count": 2}, "2.2.2.2": {"total": 1, "count": 1}}

    def test_facets_respect_report_filter(self, db):
        db.batch_upsert_metrics_requests([_rec("ok", status=200, country="US"), _rec("bad", status=403, country="FR")], instance_hostname="bw-1")
        assert db.get_metrics_facets()["country"] == {"FR": {"total": 1, "count": 1}}  # the 2xx-block is not a report

    def test_search_splits_total_from_count(self, db):
        db.batch_upsert_metrics_requests([_rec("a", url="/admin", country="US"), _rec("b", url="/public", country="FR")], instance_hostname="bw-1")
        # total ignores search (both countries are reports); count reflects the "admin" search
        assert db.get_metrics_facets(search="admin")["country"] == {"US": {"total": 1, "count": 1}, "FR": {"total": 1, "count": 0}}

    def test_pane_selection_filters_count_keeps_total(self, db):
        # Lua-faithful (metrics.lua:772-785): a pane selection narrows `count` on ALL panes (its own
        # included, no self-exclusion); `total` keeps every value visible.
        db.batch_upsert_metrics_requests([_rec("a", country="US", ip="1.1.1.1"), _rec("b", country="FR", ip="2.2.2.2")], instance_hostname="bw-1")
        facets = db.get_metrics_facets(filters={"country": ["US"]})
        assert facets["country"] == {"US": {"total": 1, "count": 1}, "FR": {"total": 1, "count": 0}}
        assert facets["ip"] == {"1.1.1.1": {"total": 1, "count": 1}, "2.2.2.2": {"total": 1, "count": 0}}


class TestRetention:
    def test_cleanup_by_age_removes_old(self, db):
        recent = int(datetime.now(tz=timezone.utc).timestamp())
        db.batch_upsert_metrics_requests([_rec("old", date=EPOCH), _rec("fresh", date=recent)], instance_hostname="bw-1")
        assert db.cleanup_metrics_by_age(30).startswith("Removed 1")
        assert [r["request_id"] for r in db.get_metrics_requests()["data"]] == ["fresh"]

    def test_cleanup_by_age_noop_when_all_fresh(self, db):
        recent = int(datetime.now(tz=timezone.utc).timestamp())
        db.batch_upsert_metrics_requests([_rec("fresh", date=recent)], instance_hostname="bw-1")
        assert db.cleanup_metrics_by_age(30) == "Removed 0 metrics requests by age"

    def test_cleanup_by_count_keeps_newest(self, db):
        db.batch_upsert_metrics_requests(
            [_rec("r1", date=EPOCH), _rec("r2", date=EPOCH + 10), _rec("r3", date=EPOCH + 20)],
            instance_hostname="bw-1",
        )
        assert db.cleanup_metrics_by_count(2).startswith("Removed 1")
        assert {r["request_id"] for r in db.get_metrics_requests()["data"]} == {"r2", "r3"}  # oldest dropped

    def test_cleanup_by_count_under_limit_noop(self, db):
        db.batch_upsert_metrics_requests([_rec("r1")], instance_hostname="bw-1")
        assert db.cleanup_metrics_by_count(10) == "Removed 0 metrics requests by count"
