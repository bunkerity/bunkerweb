"""Cache batches keep writes/deletions atomic and refresh their stored data."""

from unittest.mock import Mock

import pytest
from sqlalchemy import event

from fixtures.seed import FIXED_DT, add_jobs_cache_row, seed_minimal, session
from model import Jobs_cache

pytestmark = pytest.mark.multiengine


def _entry(name, data=b"payload", checksum="sum"):
    return {"job_name": "testjob", "service_id": None, "file_name": name, "data": data, "checksum": checksum}


def test_batch_updates_inserts_and_deletes_atomically(db):
    seed_minimal(db)
    add_jobs_cache_row(db, file_name="keep.txt", data=b"old")
    add_jobs_cache_row(db, file_name="remove.txt", data=b"gone")
    assert db.upsert_job_caches([_entry("keep.txt", b"new"), _entry("added.txt")], deletions=[_entry("remove.txt")]) == ""
    with session(db) as s:
        rows = {row.file_name: row for row in s.query(Jobs_cache)}
        assert set(rows) == {"keep.txt", "added.txt"}
        assert (rows["keep.txt"].data, rows["keep.txt"].checksum) == (b"new", "sum")
        assert rows["added.txt"].data == b"payload"
        assert rows["keep.txt"].last_update.replace(tzinfo=None) > FIXED_DT.replace(tzinfo=None)


def test_equal_checksum_keeps_data_but_refreshes_timestamp(db):
    seed_minimal(db)
    add_jobs_cache_row(db, file_name="same.txt", data=b"old")
    assert db.upsert_job_caches([_entry("same.txt", b"ignored", "seedsum")]) == ""
    with session(db) as s:
        row = s.query(Jobs_cache).filter_by(file_name="same.txt").one()
        assert row.data == b"old"
        assert row.last_update.replace(tzinfo=None) > FIXED_DT.replace(tzinfo=None)
    assert db.upsert_job_caches([_entry("same.txt", b"forced", None)]) == ""
    with session(db) as s:
        assert s.query(Jobs_cache).filter_by(file_name="same.txt").one().data == b"forced"


@pytest.mark.parametrize("deletion", [True, False])
def test_malformed_batch_is_rejected_before_any_write(db, deletion):
    seed_minimal(db)
    bad = {"file_name": "missing-keys"}
    result = db.upsert_job_caches([_entry("new.txt")], deletions=[bad]) if deletion else db.upsert_job_caches([_entry("new.txt"), bad])
    assert result.startswith("Malformed job cache deletion" if deletion else "Malformed job cache entry")
    assert "job_name" in result and "service_id" in result
    with session(db) as s:
        assert s.query(Jobs_cache).count() == 0


def test_driver_error_rolls_back_entire_batch_and_redacts_payload(db, monkeypatch):
    seed_minimal(db)
    add_jobs_cache_row(db, file_name="original.txt", data=b"original")
    log = Mock()
    monkeypatch.setattr(db, "logger", log)

    def fail_second_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO bw_jobs_cache") and "second.txt" in str(parameters):
            raise RuntimeError("credential=secret payload=secret")

    event.listen(db.sql_engine, "before_cursor_execute", fail_second_insert)
    try:
        result = db.upsert_job_caches([_entry("first.txt", b"secret"), _entry("second.txt", b"secret")], deletions=[_entry("original.txt")])
    finally:
        event.remove(db.sql_engine, "before_cursor_execute", fail_second_insert)
    assert result == "An error occurred while saving job caches"
    log.error.assert_called_once_with("Failed to save job caches (RuntimeError)")
    with session(db) as s:
        assert [(row.file_name, row.data) for row in s.query(Jobs_cache)] == [("original.txt", b"original")]


def test_readonly_batch_preserves_existing_cache(db):
    seed_minimal(db)
    add_jobs_cache_row(db, file_name="original.txt", data=b"original")
    db.readonly = True
    assert db.upsert_job_caches([_entry("new.txt")], deletions=[_entry("original.txt")]) == "The database is read-only, the changes will not be saved"
    with session(db) as s:
        assert [(row.file_name, row.data) for row in s.query(Jobs_cache)] == [("original.txt", b"original")]
