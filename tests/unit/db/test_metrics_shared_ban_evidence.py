"""Durable snapshots survive live expiry; only missing snapshots may be repaired."""

from test_metrics import _rec
from sqlalchemy import event

BAN_ID = "http:" + "x" * 32
SUMMARY = {"ban_id": BAN_ID, "counter": 30, "event_count": 1}
COMPLETE = {**SUMMARY, "events": [{"url": "/evidence", "server_name": "a.example"}]}
MISSING = {**SUMMARY, "evidence_missing": True}


def test_detail_reads_exact_id_and_instance_after_live_evidence_expires(db):
    assert db.batch_upsert_metrics_requests([_rec("same", reason="bad behavior", data=COMPLETE)], instance_hostname="one") == ""
    assert db.batch_upsert_metrics_requests([_rec("same", date=1704067201, data={"ids": [123]})], instance_hostname="two") == ""
    assert db.get_metrics_request_data("same", instance_hostname="one") == COMPLETE
    assert db.get_metrics_request_data("same") == {"ids": [123]}
    assert db.get_metrics_request_data("sam") is None
    assert db.get_metrics_request_data("same", instance_hostname="missing") is None


def test_missing_snapshot_can_upgrade_but_never_downgrade_or_cross_identity(db):
    def save(data, hostname="one"):
        return db.batch_upsert_metrics_requests([_rec("r", reason="bad behavior", data=data)], instance_hostname=hostname)

    def stored(hostname="one"):
        return next(row["data"] for row in db.get_metrics_requests()["data"] if row["instance_hostname"] == hostname)

    assert save(MISSING) == ""
    assert save({**COMPLETE, "ban_id": "http:" + "y" * 32}) == ""
    assert stored() == MISSING
    assert save(COMPLETE, "two") == ""
    assert stored() == MISSING
    assert save(COMPLETE) == ""
    assert stored() == COMPLETE
    assert save(MISSING) == ""
    assert stored() == COMPLETE


def test_legacy_inline_and_other_reasons_are_not_rewritten(db):
    for reason, data in [("bad behavior", [{"url": "/legacy"}]), ("modsecurity", MISSING)]:
        assert db.batch_upsert_metrics_requests([_rec(reason, reason=reason, data=data)]) == ""
        assert db.batch_upsert_metrics_requests([_rec(reason, reason=reason, data=COMPLETE)]) == ""
    assert {row["reason"]: row["data"] for row in db.get_metrics_requests()["data"]} == {"bad behavior": [{"url": "/legacy"}], "modsecurity": MISSING}


def test_failed_snapshot_repair_returns_error_and_keeps_original_json(db):
    assert db.batch_upsert_metrics_requests([_rec("r", reason="bad behavior", data=MISSING)]) == ""

    def fail_update(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("UPDATE bw_metrics_requests"):
            raise RuntimeError("snapshot repair failed")

    event.listen(db.sql_engine, "before_cursor_execute", fail_update)
    try:
        assert "snapshot repair failed" in db.batch_upsert_metrics_requests([_rec("r", reason="bad behavior", data=COMPLETE)])
    finally:
        event.remove(db.sql_engine, "before_cursor_execute", fail_update)
    assert db.get_metrics_requests()["data"][0]["data"] == MISSING
