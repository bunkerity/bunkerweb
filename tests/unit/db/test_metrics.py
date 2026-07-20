"""DatabaseMetricsMixin — blocked-request reports persistence (bw_metrics_requests).

Requests carries no FKs (multi-instance, instance-agnostic), so the plain ``db``
fixture suffices — no seeding needed. Records mirror the per-request shape the Lua
``/metrics/requests/query`` endpoint returns (``date`` is a Unix epoch int).
"""

import os
import time
from datetime import datetime, timezone

import pytest

from db_methods.metrics import MAX_TIMESERIES_BUCKETS

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

    def test_date_round_trips_as_exact_utc_epoch(self, db):
        # Regression guard: drivers that drop tzinfo on read-back (SQLite/MySQL/MariaDB) must not let
        # a naive-datetime .timestamp() apply the local system timezone instead of UTC. Pin TZ away
        # from UTC for the duration of the test — on a UTC CI runner, a naive .timestamp() would
        # coincidentally equal the correct value and this guard would silently stop catching the bug.
        original_tz = os.environ.get("TZ")
        os.environ["TZ"] = "America/New_York"
        time.tzset()
        try:
            db.batch_upsert_metrics_requests([_rec("r1", date=EPOCH)], instance_hostname="bw-1")
            assert db.get_metrics_requests()["data"][0]["date"] == EPOCH
        finally:
            if original_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = original_tz
            time.tzset()

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


class TestTopRules:
    def test_tallies_rule_ids_from_modsecurity_rows(self, db):
        db.batch_upsert_metrics_requests(
            [
                _rec("m1", reason="modsecurity", data={"ids": ["942100", "932100"]}, date=EPOCH),
                _rec("m2", reason="modsecurity", data={"ids": ["942100"]}, date=EPOCH + 60),
                _rec("nm", reason="blacklist", date=EPOCH),
            ],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_top_rules(start=EPOCH - 1, end=EPOCH + 3600)
        assert res[0] == {"rule_id": "942100", "count": 2}
        assert {"rule_id": "932100", "count": 1} in res

    def test_no_modsecurity_rows_returns_empty(self, db):
        db.batch_upsert_metrics_requests([_rec("a", reason="blacklist", date=EPOCH)], instance_hostname="bw-1")
        assert db.get_metrics_top_rules(start=EPOCH - 1, end=EPOCH + 3600) == []

    def test_tied_counts_break_ties_by_rule_id_ascending(self, db):
        # Regression guard: ties must not depend on the DB's (unordered) row-return order, which
        # can differ across SQLite/PostgreSQL/MariaDB. The sort key breaks ties on rule_id ascending.
        db.batch_upsert_metrics_requests(
            [
                _rec("m1", reason="modsecurity", data={"ids": ["999200"]}, date=EPOCH),
                _rec("m2", reason="modsecurity", data={"ids": ["111100"]}, date=EPOCH + 60),
            ],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_top_rules(start=EPOCH - 1, end=EPOCH + 3600)
        tied = [r["rule_id"] for r in res if r["rule_id"] in ("999200", "111100")]
        assert tied == ["111100", "999200"]


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


class TestAsnAttribution:
    def test_asn_fields_round_trip(self, db):
        db.batch_upsert_metrics_requests([_rec("a", asn_number=4134, asn_org="China Telecom")], instance_hostname="bw-1")
        row = db.get_metrics_requests()["data"][0]
        assert row["asn_number"] == 4134
        assert row["asn_org"] == "China Telecom"

    def test_asn_fields_default_to_none(self, db):
        db.batch_upsert_metrics_requests([_rec("a")], instance_hostname="bw-1")
        row = db.get_metrics_requests()["data"][0]
        assert row["asn_number"] is None
        assert row["asn_org"] is None


class TestTimeseries:
    def test_buckets_and_totals(self, db):
        db.batch_upsert_metrics_requests([_rec("a", date=EPOCH), _rec("b", date=EPOCH + 3600)], instance_hostname="bw-1")
        res = db.get_metrics_timeseries(start=EPOCH, end=EPOCH + 7200, bucket="hour")
        assert res["total"] == 2
        assert res["counts"] == [1, 1]
        assert res["buckets"][0] == EPOCH

    def test_bucket_index_correct_regardless_of_host_timezone(self, db):
        # Regression guard: the bucket-index loop in get_metrics_timeseries must use
        # _to_datetime(d).timestamp() rather than a bare d.timestamp() — same reasoning as
        # TestBatchUpsert.test_date_round_trips_as_exact_utc_epoch above. On a UTC CI runner a
        # naive datetime's bare .timestamp() coincidentally matches the correct UTC value, so
        # this guard pins TZ away from UTC to make a regression fail deterministically
        # regardless of the host's ambient timezone.
        original_tz = os.environ.get("TZ")
        os.environ["TZ"] = "America/New_York"
        time.tzset()
        try:
            db.batch_upsert_metrics_requests([_rec("a", date=EPOCH), _rec("b", date=EPOCH + 3600)], instance_hostname="bw-1")
            res = db.get_metrics_timeseries(start=EPOCH, end=EPOCH + 7200, bucket="hour")
            assert res["counts"] == [1, 1]
            assert res["buckets"][0] == EPOCH
        finally:
            if original_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = original_tz
            time.tzset()

    def test_trend_pct_vs_previous_window(self, db):
        db.batch_upsert_metrics_requests(
            [_rec("p1", date=EPOCH - 7200), _rec("p2", date=EPOCH - 3600), _rec("c1", date=EPOCH)],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_timeseries(start=EPOCH, end=EPOCH + 7200, bucket="hour")
        assert res["prev_total"] == 2
        assert res["total"] == 1
        assert res["trend_pct"] == -50.0

    def test_no_previous_window_data_gives_none_trend(self, db):
        db.batch_upsert_metrics_requests([_rec("a", date=EPOCH)], instance_hostname="bw-1")
        res = db.get_metrics_timeseries(start=EPOCH, end=EPOCH + 3600, bucket="hour")
        assert res["prev_total"] == 0
        assert res["trend_pct"] is None

    def test_oversized_window_is_rejected_before_allocating_buckets(self, db):
        # Regression guard (authenticated DoS): bucket_count = ceil(window / bucket_seconds) was
        # sized straight from the caller-controlled start/end with no cap, so a crafted multi-decade
        # window would allocate tens of millions of list entries. One bucket past the cap must raise
        # before any list is built or the DB is queried.
        window = (MAX_TIMESERIES_BUCKETS + 1) * 3600
        with pytest.raises(ValueError, match="requested range too large"):
            db.get_metrics_timeseries(start=0, end=window, bucket="hour")

    def test_real_30d_hourly_window_still_succeeds(self, db):
        # The guard must not be so tight it breaks the UI's own largest preset: 30 days of
        # hourly buckets = 720, far under the cap.
        res = db.get_metrics_timeseries(start=0, end=30 * 86400, bucket="hour")
        assert len(res["buckets"]) == 720
        assert len(res["counts"]) == 720

    def test_out_of_range_epoch_raises_value_error_not_uncaught_exception(self, db):
        # start beyond the platform's representable range (datetime.fromtimestamp raises
        # OverflowError/OSError/ValueError depending on how far out of range) must normalize to a
        # clean ValueError rather than propagate a raw stdlib exception up to the API as a 500.
        huge = 10**18
        with pytest.raises(ValueError):
            db.get_metrics_timeseries(start=huge, end=huge + 3600, bucket="hour")


class TestTopOffenders:
    def test_ranks_by_block_count_with_attribution(self, db):
        db.batch_upsert_metrics_requests(
            [
                _rec("a1", ip="9.9.9.9", country="RU", asn_number=12389, asn_org="Rostelecom", date=EPOCH),
                _rec("a2", ip="9.9.9.9", country="RU", asn_number=12389, asn_org="Rostelecom", date=EPOCH + 60, reason="modsecurity"),
                _rec("b1", ip="1.1.1.1", country="US", date=EPOCH),
            ],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_top_offenders(start=EPOCH - 1, end=EPOCH + 3600)
        assert res[0]["ip"] == "9.9.9.9"
        assert res[0]["blocks"] == 2
        assert res[0]["asn_org"] == "Rostelecom"
        assert res[0]["first_seen"] == EPOCH
        assert res[0]["last_seen"] == EPOCH + 60
        assert res[1]["ip"] == "1.1.1.1"

    def test_limit_caps_results(self, db):
        db.batch_upsert_metrics_requests(
            [_rec(f"r{i}", ip=f"1.1.1.{i}", date=EPOCH) for i in range(5)],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_top_offenders(start=EPOCH - 1, end=EPOCH + 3600, limit=2)
        assert len(res) == 2

    def test_first_last_seen_correct_regardless_of_host_timezone(self, db):
        # Regression guard: get_metrics_top_offenders must run first_seen/last_seen through
        # _to_datetime() before .timestamp(), same reasoning as
        # TestBatchUpsert.test_date_round_trips_as_exact_utc_epoch and
        # TestTimeseries.test_bucket_index_correct_regardless_of_host_timezone above. On a UTC CI
        # runner a naive datetime's bare .timestamp() coincidentally matches the correct UTC value,
        # so this guard pins TZ away from UTC to make a regression fail deterministically regardless
        # of the host's ambient timezone.
        original_tz = os.environ.get("TZ")
        os.environ["TZ"] = "America/New_York"
        time.tzset()
        try:
            db.batch_upsert_metrics_requests(
                [
                    _rec("a1", ip="9.9.9.9", date=EPOCH),
                    _rec("a2", ip="9.9.9.9", date=EPOCH + 60),
                ],
                instance_hostname="bw-1",
            )
            res = db.get_metrics_top_offenders(start=EPOCH - 1, end=EPOCH + 3600)
            assert res[0]["first_seen"] == EPOCH
            assert res[0]["last_seen"] == EPOCH + 60
        finally:
            if original_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = original_tz
            time.tzset()

    def test_attribution_backfills_partial_fields_from_multiple_rows(self, db):
        # Regression guard: neither single row is fully populated (row 1 has asn_number but not
        # asn_org, row 2 has the reverse) — plain first-row-wins setdefault would leave one field
        # permanently null; the coalesce must merge the non-null field from each row.
        db.batch_upsert_metrics_requests(
            [
                _rec("a1", ip="8.8.4.4", country="US", asn_number=15169, asn_org=None, date=EPOCH),
                _rec("a2", ip="8.8.4.4", country="US", asn_number=None, asn_org="Google LLC", date=EPOCH + 60),
            ],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_top_offenders(start=EPOCH - 1, end=EPOCH + 3600)
        assert res[0]["ip"] == "8.8.4.4"
        assert res[0]["asn_number"] == 15169
        assert res[0]["asn_org"] == "Google LLC"

    def test_attribution_backfills_regardless_of_insertion_order(self, db):
        # Regression guard: an IP with one post-migration row (real country/ASN) and one
        # pre-migration row (country/asn_number/asn_org all NULL) must show the real
        # attribution — with the NULL row inserted FIRST, proving the result is
        # order-independent rather than merely "first row happened to be populated".
        db.batch_upsert_metrics_requests(
            [
                _rec("a1", ip="8.8.8.8", country=None, asn_number=None, asn_org=None, date=EPOCH),
                _rec("a2", ip="8.8.8.8", country="US", asn_number=15169, asn_org="Google LLC", date=EPOCH + 60),
            ],
            instance_hostname="bw-1",
        )
        res = db.get_metrics_top_offenders(start=EPOCH - 1, end=EPOCH + 3600)
        assert res[0]["ip"] == "8.8.8.8"
        assert res[0]["country"] == "US"
        assert res[0]["asn_number"] == 15169
        assert res[0]["asn_org"] == "Google LLC"
