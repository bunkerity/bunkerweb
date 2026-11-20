"""Runtime MMDB selection preserves good data when metadata or restores fail."""

import hashlib
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import mmdb


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(mmdb, "open_database", lambda _: nullcontext())
    monkeypatch.setattr(mmdb, "download_verified_candidate", Mock(side_effect=AssertionError("unexpected download")))
    monkeypatch.setattr(mmdb, "fetch_metadata", Mock(side_effect=mmdb.MetadataError("offline")))
    active = tmp_path / "cache"
    active.mkdir()
    job = SimpleNamespace(job_path=active, job_name="download-asn", db=None, restore_ok=True, get_cache=Mock(return_value=None))

    def cache(name, source, **kwargs):
        (active / name).write_bytes(source.read_bytes())
        return True, ""

    job.cache_file = Mock(side_effect=cache)
    return job, tmp_path / "bundled.mmdb", tmp_path / "work"


def update(runtime):
    job, fallback, work = runtime
    return mmdb.update_runtime_mmdb(mmdb.ASN, job, fallback, temp_root=work)


@pytest.mark.parametrize("source", ["active", "fallback", "database", "none"])
def test_metadata_outage_uses_best_available_copy(runtime, source):
    job, fallback, _ = runtime
    active = job.job_path / mmdb.ASN.local_name
    if source == "active":
        active.write_bytes(b"active")
    elif source == "fallback":
        fallback.write_bytes(b"fallback")
    elif source == "database":
        job.db = Mock()
        job.db.get_job_cache_file.return_value = {"data": b"database"}
    assert update(runtime) == {"active": 0, "fallback": 1, "database": 1, "none": 2}[source]
    if source != "none":
        assert active.read_bytes() == source.encode()
    else:
        assert not active.exists()


@pytest.mark.parametrize("checksum_matches", [True, False])
def test_matching_active_database_skips_download_or_repairs_metadata(runtime, monkeypatch, checksum_matches):
    job, _, _ = runtime
    content = b"current"
    (job.job_path / mmdb.ASN.local_name).write_bytes(content)
    metadata = mmdb.DBIPMetadata(hashlib.sha1(content).hexdigest(), "unused")
    monkeypatch.setattr(mmdb, "fetch_metadata", lambda *_, **__: metadata)
    job.get_cache.return_value = {"checksum": hashlib.sha512(content).hexdigest() if checksum_matches else "stale"}
    assert update(runtime) == (0 if checksum_matches else 1)
    assert job.cache_file.call_count == (0 if checksum_matches else 1)
    mmdb.download_verified_candidate.assert_not_called()


@pytest.mark.parametrize("source", ["fallback", "database"])
def test_matching_fallback_or_db_blob_restores_without_download(runtime, monkeypatch, source):
    job, fallback, _ = runtime
    content = b"verified"
    monkeypatch.setattr(mmdb, "fetch_metadata", lambda *_, **__: mmdb.DBIPMetadata(hashlib.sha1(content).hexdigest(), "unused"))
    if source == "fallback":
        fallback.write_bytes(content)
    else:
        job.get_cache.side_effect = [None, {"data": content}]
    assert update(runtime) == 1
    assert (job.job_path / mmdb.ASN.local_name).read_bytes() == content
    mmdb.download_verified_candidate.assert_not_called()


@pytest.mark.parametrize("error", [mmdb.IntegrityError("expected", "actual"), mmdb.DownloadError("offline"), OSError("disk full")])
def test_failed_update_keeps_existing_active_file(runtime, monkeypatch, error):
    job, _, _ = runtime
    active = job.job_path / mmdb.ASN.local_name
    active.write_bytes(b"old good copy")
    monkeypatch.setattr(mmdb, "fetch_metadata", lambda *_, **__: mmdb.DBIPMetadata("0" * 40, "unused"))
    monkeypatch.setattr(mmdb, "download_verified_candidate", Mock(side_effect=error))
    assert update(runtime) == 2
    assert active.read_bytes() == b"old good copy"
    job.cache_file.assert_not_called()


def test_failed_restore_publishes_fallback_locally_without_overwriting_db(runtime):
    job, fallback, _ = runtime
    job.restore_ok = False
    fallback.write_bytes(b"fallback")
    assert update(runtime) == 1
    assert (job.job_path / mmdb.ASN.local_name).read_bytes() == b"fallback"
    job.cache_file.assert_not_called()
    assert update(runtime) == 0


def test_verified_download_can_repair_failed_restore(runtime, monkeypatch):
    job, _, _ = runtime
    job.restore_ok = False
    monkeypatch.setattr(mmdb, "fetch_metadata", lambda *_, **__: mmdb.DBIPMetadata("a" * 40, "unused"))

    def downloaded(descriptor, metadata, work, **kwargs):
        candidate = work / descriptor.local_name
        candidate.write_bytes(b"fresh verified")
        return mmdb.VerifiedCandidate(candidate, metadata, "a" * 40, hashlib.sha512(candidate.read_bytes()).hexdigest())

    monkeypatch.setattr(mmdb, "download_verified_candidate", downloaded)
    assert update(runtime) == 1
    assert (job.job_path / mmdb.ASN.local_name).read_bytes() == b"fresh verified"
    job.cache_file.assert_called_once()


def test_failed_cache_write_returns_failure(runtime):
    job, fallback, _ = runtime
    fallback.write_bytes(b"fallback")
    job.cache_file.side_effect = None
    job.cache_file.return_value = False, "database unavailable"
    assert update(runtime) == 2
    assert not (job.job_path / mmdb.ASN.local_name).exists()


def test_invalid_database_blob_is_discarded(runtime, monkeypatch):
    job, _, work = runtime
    job.get_cache.side_effect = [None, {"data": b"invalid"}]
    monkeypatch.setattr(mmdb, "open_database", Mock(side_effect=ValueError("invalid")))
    assert update(runtime) == 2
    assert list(work.iterdir()) == []


def test_duplicate_local_candidate_is_not_read_twice(tmp_path, monkeypatch):
    candidate = tmp_path / "one.mmdb"
    candidate.write_bytes(b"valid")
    reader = Mock(return_value=nullcontext())
    monkeypatch.setattr(mmdb, "open_database", reader)
    results = mmdb._collect_runtime_candidates(candidate, candidate, mmdb.LOGGER)
    assert len(results) == 1
    assert results[0].source == "active"
    reader.assert_called_once()
