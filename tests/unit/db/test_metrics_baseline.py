"""DatabaseMetricsMixin — sampled traffic baseline persistence (bw_metrics_baseline).

Baseline carries no FKs (multi-instance, instance-agnostic), so the plain ``db`` fixture
suffices. Records mirror the shape the Lua ``/metrics/baseline`` endpoint returns.

The table exists separately from ``bw_metrics_requests`` on purpose: that one is filtered on
read by ``_report_clause()`` (4xx or detect), so a 200 stored there would be invisible to
every existing query — and removing the clause to expose it would break every count, facet,
timeseries and retention path built on it. These tests pin that separation.
"""

from datetime import datetime, timedelta, timezone

from model import Baseline, Requests  # type: ignore

# fixed epoch for determinism: 2024-01-01T00:00:00Z
EPOCH = 1704067200


def _sample(request_id, **over):
    record = {
        "id": request_id,
        "date": EPOCH,
        "server_name": "www.example.com",
        "method": "GET",
        "uri": "/api/user/<n>",
        "status": 200,
        "request_time": 0.042,
        "request_length": 512,
        "body_bytes_sent": 2048,
        "upstream_time": 0.031,
        "connection_requests": 3,
        "http_version": "2.0",
        "scheme": "https",
        "content_type": "application/json",
        "content_length": 128,
        "ssl_protocol": "TLSv1.3",
        "ssl_cipher": "TLS_AES_256_GCM_SHA384",
        "country": "FR",
        "asn_number": 3215,
        "ip_version": 4,
        "user_agent": "curl/8.5.0",
    }
    record.update(over)
    return record


def _rows(db):
    with db._db_session() as session:
        return session.query(Baseline).order_by(Baseline.request_id).all()


class TestBatchUpsert:
    def test_insert_and_read_back(self, db):
        assert db.batch_upsert_metrics_baseline([_sample("r1")], instance_hostname="bw-1") == ""
        rows = _rows(db)
        assert len(rows) == 1
        row = rows[0]
        assert row.request_id == "r1"
        assert row.instance_hostname == "bw-1"
        assert row.status == 200
        assert row.uri == "/api/user/<n>"
        assert row.request_time == 0.042
        assert row.country == "FR"
        assert row.asn_number == 3215
        assert row.ssl_cipher == "TLS_AES_256_GCM_SHA384"

    def test_empty_batch_is_noop(self, db):
        assert db.batch_upsert_metrics_baseline([], instance_hostname="bw-1") == ""
        assert _rows(db) == []

    def test_a_record_without_an_id_is_skipped(self, db):
        assert db.batch_upsert_metrics_baseline([{"date": EPOCH, "status": 200}], instance_hostname="bw-1") == ""
        assert _rows(db) == []

    def test_date_round_trips_as_exact_utc_epoch(self, db):
        db.batch_upsert_metrics_baseline([_sample("r1")], instance_hostname="bw-1")
        stored = _rows(db)[0].date
        if stored.tzinfo is None:
            stored = stored.replace(tzinfo=timezone.utc)
        assert int(stored.timestamp()) == EPOCH


class TestDedup:
    def test_rescraping_the_same_buffer_is_idempotent(self, db):
        """The job re-reads the whole Lua buffer every minute, so this is the normal case."""
        db.batch_upsert_metrics_baseline([_sample("r1"), _sample("r2")], instance_hostname="bw-1")
        db.batch_upsert_metrics_baseline([_sample("r1"), _sample("r2")], instance_hostname="bw-1")
        assert len(_rows(db)) == 2

    def test_duplicate_within_batch_collapses(self, db):
        db.batch_upsert_metrics_baseline([_sample("r1"), _sample("r1", status=204)], instance_hostname="bw-1")
        rows = _rows(db)
        assert len(rows) == 1
        assert rows[0].status == 204, "last record for an id wins"

    def test_same_request_id_from_two_instances_is_kept_twice(self, db):
        db.batch_upsert_metrics_baseline([_sample("r1")], instance_hostname="bw-1")
        db.batch_upsert_metrics_baseline([_sample("r1")], instance_hostname="bw-2")
        assert len(_rows(db)) == 2


class TestPrivacyAndCoercion:
    def test_no_client_ip_is_stored(self, db):
        """The baseline models traffic shape, not identity. Even if a record carries an ip,
        there is no column for it and it must not leak into another field."""
        db.batch_upsert_metrics_baseline([_sample("r1", ip="203.0.113.9")], instance_hostname="bw-1")
        assert not hasattr(Baseline, "ip")
        row = _rows(db)[0]
        stored = [v for v in vars(row).values() if isinstance(v, str)]
        assert not any("203.0.113.9" in v for v in stored)

    def test_a_multi_upstream_time_is_dropped_rather_than_half_parsed(self, db):
        """$upstream_response_time is a comma-separated list when several upstreams were
        tried; a partial parse would be a quietly wrong number."""
        db.batch_upsert_metrics_baseline([_sample("r1", upstream_time="0.01, 0.02")], instance_hostname="bw-1")
        assert _rows(db)[0].upstream_time is None

    def test_numeric_strings_are_coerced(self, db):
        db.batch_upsert_metrics_baseline([_sample("r1", request_length="512", asn_number="3215")], instance_hostname="bw-1")
        row = _rows(db)[0]
        assert row.request_length == 512
        assert row.asn_number == 3215

    def test_an_overlong_field_is_truncated_not_rejected(self, db):
        """A cipher name past its column width would abort the whole batch on MySQL."""
        assert db.batch_upsert_metrics_baseline([_sample("r1", ssl_cipher="X" * 300)], instance_hostname="bw-1") == ""
        assert len(_rows(db)[0].ssl_cipher) == 64

    def test_missing_optional_fields_become_null(self, db):
        record = {"id": "r1", "date": EPOCH, "status": 200}
        assert db.batch_upsert_metrics_baseline([record], instance_hostname="bw-1") == ""
        row = _rows(db)[0]
        assert row.request_time is None and row.ssl_protocol is None and row.user_agent is None
        assert row.method == "" and row.country == ""


class TestSeparationFromReports:
    def test_baseline_rows_do_not_appear_in_the_reports_query(self, db):
        """The whole reason for a second table: a 200 in bw_metrics_requests is invisible
        behind _report_clause(), so the baseline must not live there."""
        db.batch_upsert_metrics_baseline([_sample("r1")], instance_hostname="bw-1")
        result = db.get_metrics_requests(start=0, length=10)
        assert result["data"] == []
        assert result["total"] == 0

    def test_the_two_tables_are_independent(self, db):
        db.batch_upsert_metrics_baseline([_sample("r1")], instance_hostname="bw-1")
        with db._db_session() as session:
            assert session.query(Requests).count() == 0
            assert session.query(Baseline).count() == 1


class TestRetention:
    def _insert_aged(self, db, request_id, days_old):
        db.batch_upsert_metrics_baseline([_sample(request_id)], instance_hostname="bw-1")
        with db._db_session() as session:
            row = session.query(Baseline).filter_by(request_id=request_id).one()
            row.date = datetime.now().astimezone() - timedelta(days=days_old)
            session.commit()

    def test_cleanup_by_age_removes_only_the_old(self, db):
        self._insert_aged(db, "old", 40)
        self._insert_aged(db, "new", 1)
        assert db.cleanup_baseline_by_age(14) == "Removed 1 baseline records by age"
        assert [r.request_id for r in _rows(db)] == ["new"]

    def test_cleanup_by_count_keeps_the_newest(self, db):
        self._insert_aged(db, "oldest", 5)
        self._insert_aged(db, "middle", 3)
        self._insert_aged(db, "newest", 1)
        assert db.cleanup_baseline_by_count(2) == "Removed 1 baseline records by count"
        assert sorted(r.request_id for r in _rows(db)) == ["middle", "newest"]

    def test_cleanup_by_count_under_the_cap_is_a_noop(self, db):
        self._insert_aged(db, "r1", 1)
        assert db.cleanup_baseline_by_count(10) == "Removed 0 baseline records by count"
        assert len(_rows(db)) == 1

    def test_baseline_retention_does_not_touch_reports(self, db):
        """Separate policies: the baseline default is 14 days, reports 90."""
        db.batch_upsert_metrics_requests(
            [{"id": "q1", "date": EPOCH, "ip": "203.0.113.1", "method": "GET", "url": "/", "status": 403, "reason": "blacklist", "security_mode": "block"}],
            instance_hostname="bw-1",
        )
        db.cleanup_baseline_by_age(1)
        with db._db_session() as session:
            assert session.query(Requests).count() == 1
