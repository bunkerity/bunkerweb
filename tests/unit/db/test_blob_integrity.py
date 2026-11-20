"""Chunked blobs reassemble in order, detect corruption, and shed obsolete chunks."""

from hashlib import sha256
from unittest.mock import Mock

import pytest

from Database import BLOB_CHUNK_MARKER
from fixtures.seed import make_external_plugin, seed_minimal, session
from model import Blob_chunks, Jobs_cache, Plugin_pages, Plugins

pytestmark = pytest.mark.multiengine


@pytest.fixture
def chunked(db, monkeypatch):
    seed_minimal(db)
    # Exercise the backend-independent chunk protocol using small, real SQL rows.
    monkeypatch.setattr(db, "_blob_chunk_size", lambda session: 4)
    return db


def test_cache_roundtrip_orders_chunks_and_replaces_obsolete_sets(chunked):
    db = chunked
    payload = b"0123456789abcdefgh"
    assert db.upsert_job_cache(None, "large.bin", payload, job_name="testjob", checksum="old") == ""
    assert db.get_job_cache_file("testjob", "large.bin") == payload
    with session(db) as s:
        row = s.query(Jobs_cache).one()
        assert row.data == BLOB_CHUNK_MARKER + sha256(payload).hexdigest().encode()
        chunks = s.query(Blob_chunks).filter_by(owner=f"bw_jobs_cache:{row.id}").order_by(Blob_chunks.idx).all()
        assert [chunk.data for chunk in chunks] == [payload[i : i + 4] for i in range(0, len(payload), 4)]  # noqa: E203
    assert db.upsert_job_cache(None, "large.bin", b"new", job_name="testjob", checksum="new") == ""
    assert db.get_job_cache_file("testjob", "large.bin") == b"new"
    with session(db) as s:
        assert s.query(Blob_chunks).count() == 0


def test_identical_blob_is_not_duplicated_and_cache_delete_sweeps_chunks(chunked):
    db = chunked
    payload = b"0123456789"
    assert db.upsert_job_cache(None, "large.bin", payload, job_name="testjob") == ""
    with session(db) as s:
        original = [(row.owner, row.checksum, row.idx, row.data) for row in s.query(Blob_chunks).order_by(Blob_chunks.idx)]
    assert db.upsert_job_cache(None, "large.bin", payload, job_name="testjob") == ""
    with session(db) as s:
        assert [(row.owner, row.checksum, row.idx, row.data) for row in s.query(Blob_chunks).order_by(Blob_chunks.idx)] == original
    assert db.delete_job_cache("large.bin", job_name="testjob", plugin_id="wrong") is None
    assert db.get_job_cache_file("testjob", "large.bin") == payload
    assert db.delete_job_cache("large.bin", job_name="testjob", plugin_id="general") == ""
    assert db.get_job_cache_file("testjob", "large.bin") is None
    with session(db) as s:
        assert s.query(Blob_chunks).count() == 0


def test_corrupt_blob_returns_none_and_logs_integrity_error(chunked, monkeypatch):
    db = chunked
    assert db.upsert_job_cache(None, "large.bin", b"0123456789", job_name="testjob") == ""
    with session(db) as s:
        s.query(Blob_chunks).filter_by(idx=1).update({Blob_chunks.data: b"bad"})
    log = Mock()
    monkeypatch.setattr(db, "logger", log)
    assert db.get_job_cache_file("testjob", "large.bin") is None
    assert "is incomplete, its chunks are missing or corrupted" in log.error.call_args.args[0]


def test_blob_reader_follows_new_owner_value_after_missing_old_chunks(chunked):
    db = chunked
    missing = BLOB_CHUNK_MARKER + sha256(b"old").hexdigest().encode()
    reread = Mock(return_value=b"current payload")
    with session(db) as s:
        assert db._blob_load(s, "bw_plugins:gone", missing, reread) == b"current payload"
    reread.assert_called_once_with()


def test_sweep_keeps_live_plugin_page_and_cache_sets_only(chunked):
    db = chunked
    payload = b"chunked-archive"
    with session(db) as s:
        plugin = s.query(Plugins).filter_by(id="general").one()
        plugin.data = db._blob_store(s, "bw_plugins:general", payload)
        page = Plugin_pages(plugin_id="general", checksum="page", data=db._blob_store(s, "bw_plugin_pages:general", payload))
        s.add(page)
        cache = Jobs_cache(job_name="testjob", file_name="blob.bin", data=b"", checksum="cache")
        s.add(cache)
        s.flush()
        cache.data = db._blob_store(s, f"bw_jobs_cache:{cache.id}", payload)
        cache_id = cache.id
        db._blob_store(s, "bw_plugins:deleted", b"orphaned-plugin")
        db._blob_store(s, "bw_jobs_cache:not-a-number", b"orphaned-cache")
        db._blob_sweep(s)
        assert {row.owner for row in s.query(Blob_chunks)} == {"bw_plugins:general", "bw_plugin_pages:general", f"bw_jobs_cache:{cache_id}"}
    assert db.get_plugin_page("general") == payload
    assert db.get_job_cache_file("testjob", "blob.bin") == payload
    assert db.get_plugins(with_data=True)[0]["data"] == payload


@pytest.mark.parametrize(
    "value,data,expected",
    [
        (None, None, True),
        (b"", b"", True),
        (b"plain", b"other", False),
        (BLOB_CHUNK_MARKER + sha256(b"value").hexdigest().encode(), b"value", True),
        (BLOB_CHUNK_MARKER + sha256(b"value").hexdigest().encode(), None, False),
        (BLOB_CHUNK_MARKER + sha256(b"value").hexdigest().encode(), b"different", False),
    ],
)
def test_stored_marker_matches_only_same_plaintext(db, value, data, expected):
    assert db._blob_matches(value, data) is expected


def test_plugin_data_roundtrip_uses_chunks(chunked, tmp_path, monkeypatch):
    import Database as module

    monkeypatch.setattr(module, "sep", str(tmp_path))
    payload = b"large-plugin-data"
    assert chunked.update_external_plugins([make_external_plugin(data=payload)]) == ""
    assert chunked.get_plugins(_type="external", with_data=True)[0]["data"] == payload
