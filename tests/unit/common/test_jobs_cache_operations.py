"""Job cache contracts against temporary files and a fake persistence boundary."""

import hashlib
import io
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

import cache_restore
import jobs


@pytest.fixture
def job(tmp_path):
    instance = object.__new__(jobs.Job)
    instance.job_path = tmp_path / "plugin"
    instance.job_path.mkdir()
    instance.job_name = "download"
    instance.db = Mock()
    instance.db.upsert_job_cache.return_value = ""
    instance.db.delete_job_cache.return_value = ""
    instance.db.get_job_cache_file.return_value = None
    instance.db.get_jobs_cache_files.return_value = []
    instance.logger = Mock()
    return instance


@pytest.mark.parametrize("as_path", [False, True])
def test_cache_bytes_are_written_and_persisted_with_hash(job, as_path):
    name = Path("file.dat") if as_path else "file.dat"
    assert job.cache_file(name, b"payload", service_id="example.com") == (True, "")
    assert (job.job_path / "example.com/file.dat").read_bytes() == b"payload"
    job.db.upsert_job_cache.assert_called_once_with("example.com", "file.dat", b"payload", job_name="download", checksum=hashlib.sha512(b"payload").hexdigest())


@pytest.mark.parametrize("delete", [False, True])
def test_source_file_deleted_only_after_success(job, tmp_path, delete):
    source = tmp_path / "incoming"
    source.write_bytes(b"data")
    assert job.cache_file("copy", str(source), delete_file=delete, checksum="known") == (True, "")
    assert source.exists() is (not delete)
    assert (job.job_path / "copy").read_bytes() == b"data"
    assert job.db.upsert_job_cache.call_args.kwargs["checksum"] == "known"


@pytest.mark.parametrize("error", ["database full", RuntimeError("database failed")])
def test_persistence_failure_retains_source_for_retry(job, tmp_path, error):
    source = tmp_path / "incoming"
    source.write_bytes(b"data")
    if isinstance(error, Exception):
        job.db.upsert_job_cache.side_effect = error
    else:
        job.db.upsert_job_cache.return_value = error
    ok, message = job.cache_file("copy", source)
    assert not ok
    assert "database" in message
    assert source.read_bytes() == b"data"


def test_no_overwrite_preserves_disk_but_updates_database(job):
    target = job.job_path / "copy"
    target.write_bytes(b"old")
    assert job.cache_file("copy", b"new", overwrite_file=False) == (True, "")
    assert target.read_bytes() == b"old"
    assert job.db.upsert_job_cache.call_args.args[2] == b"new"


def test_caching_own_path_does_not_delete_it(job):
    target = job.job_path / "copy"
    target.write_bytes(b"keep")
    assert job.cache_file("copy", target) == (True, "")
    assert target.read_bytes() == b"keep"


@pytest.mark.parametrize("method", ["get_cache", "cache_hash", "del_cache", "cache_file"])
def test_path_traversal_never_reaches_database(job, method):
    result = getattr(job, method)("../escape", b"data") if method == "cache_file" else getattr(job, method)("../escape")
    if method in ("cache_file", "del_cache"):
        assert result[0] is False
    else:
        assert result is None
    assert job.db.mock_calls == []
    assert not (job.job_path.parent / "escape").exists()


def test_local_read_prefers_disk_and_merges_only_metadata(job):
    (job.job_path / "data").write_bytes(b"local")
    assert job.get_cache(Path("data")) == b"local"
    job.db.get_job_cache_file.assert_not_called()
    job.db.get_job_cache_file.return_value = {"checksum": "db-hash"}
    assert job.get_cache("data", with_info=True) == {"data": b"local", "checksum": "db-hash"}
    assert job.db.get_job_cache_file.call_args.kwargs["with_data"] is False


def test_missing_local_read_forwards_cache_scope(job):
    job.db.get_job_cache_file.return_value = {"data": b"db"}
    assert job.get_cache("missing", job_name="other", service_id="site", plugin_id="p", with_info=True) == {"data": b"db"}
    job.db.get_job_cache_file.assert_called_once_with("other", "missing", service_id="site", plugin_id="p", with_info=True, with_data=True)


@pytest.mark.parametrize("age,fresh", [(-1, False), (30, True), (3601, False)])
def test_cache_expiration_rejects_future_and_old_timestamps(job, age, fresh):
    job.db.get_job_cache_file.return_value = {"last_update": (datetime.now().astimezone() - timedelta(seconds=age)).timestamp()}
    assert job.is_cached_file(Path("data"), "hour") is fresh


def test_expiration_handles_database_exception(job):
    job.db.get_job_cache_file.side_effect = RuntimeError("unavailable")
    assert job.is_cached_file("data", "hour") is False


def test_cache_hash_prefers_disk_then_db_checksum(job):
    target = job.job_path / "data"
    target.write_bytes(b"disk")
    assert job.cache_hash(Path("data")) == hashlib.sha512(b"disk").hexdigest()
    job.db.get_job_cache_file.assert_not_called()
    target.unlink()
    job.db.get_job_cache_file.return_value = {"checksum": "db-hash"}
    assert job.cache_hash("data") == "db-hash"
    job.db.get_job_cache_file.return_value = None
    assert job.cache_hash("data") is None


@pytest.mark.parametrize("error", [None, "db error", RuntimeError("db exception")])
def test_delete_removes_disk_and_reports_db_failure(job, error):
    target = job.job_path / "site/file"
    target.parent.mkdir()
    target.write_bytes(b"old")
    if isinstance(error, Exception):
        job.db.delete_job_cache.side_effect = error
    else:
        job.db.delete_job_cache.return_value = error or ""
    ok, message = job.del_cache(Path("file"), job_name="owner", service_id="site")
    assert ok is (error is None)
    assert not target.exists()
    assert not target.parent.exists()
    assert message == "" if error is None else "db" in message
    job.db.delete_job_cache.assert_called_once_with("file", job_name="owner", service_id="site")


def test_directory_archive_is_reproducible_and_contains_file(job, tmp_path):
    directory = tmp_path / "directory"
    directory.mkdir()
    (directory / "data").write_bytes(b"content")
    assert job.cache_dir(str(directory)) == (True, "")
    first = job.db.upsert_job_cache.call_args.args[2]
    assert job.cache_dir(directory) == (True, "")
    assert job.db.upsert_job_cache.call_args.args[2] == first
    with tarfile.open(fileobj=io.BytesIO(first), mode="r:gz") as archive:
        assert archive.extractfile("./data").read() == b"content"
    assert not list(job.job_path.iterdir())


def row(name="data", content=b"cached", owner="download", service=""):
    return {"file_name": name, "data": content, "job_name": owner, "service_id": service}


def test_empty_restore_keeps_existing_cache(job):
    target = job.job_path / "keep"
    target.write_bytes(b"important")
    assert job.restore_cache(manual=False)
    assert target.read_bytes() == b"important"


def test_restore_skips_sibling_payload_and_preserves_restored_parent(job):
    (job.job_path / "stale").mkdir()
    (job.job_path / "stale/delete").write_bytes(b"stale")
    job.db.get_jobs_cache_files.return_value = [row(), row("sibling", b"not ours", owner="other")]
    assert job.restore_cache(manual=False)
    assert (job.job_path / "data").read_bytes() == b"cached"
    assert not (job.job_path / "sibling").exists()
    # Restoring a root-level file preserves that directory's other files by design.
    assert (job.job_path / "stale/delete").read_bytes() == b"stale"


def test_restore_service_cache_sweeps_unowned_subtree(job):
    (job.job_path / "stale").mkdir()
    (job.job_path / "stale/delete").write_bytes(b"stale")
    job.db.get_jobs_cache_files.return_value = [row(service="site")]
    assert job.restore_cache(manual=False)
    assert (job.job_path / "site/data").read_bytes() == b"cached"
    assert not (job.job_path / "stale").exists()


@pytest.mark.parametrize(
    "metadata,restore_result,expected",
    [
        ({"scheduler_first_start": True}, True, True),
        ({"scheduler_first_start": False}, True, True),
        ({"scheduler_first_start": False}, False, False),
    ],
)
def test_job_initialization_records_restore_result(tmp_path, monkeypatch, metadata, restore_result, expected):
    real_path = Path

    def path(*parts):
        if parts[:4] == ("/", "var", "cache", "bunkerweb"):
            return tmp_path.joinpath(*parts[4:])
        return real_path(*parts)

    monkeypatch.setattr(jobs, "Path", path)
    restore = Mock(return_value=restore_result)
    monkeypatch.setattr(jobs.Job, "restore_cache", restore)
    db = Mock()
    db.get_metadata.return_value = metadata
    instance = jobs.Job(Mock(), tmp_path / "plugin/jobs/download.py", db=db)
    assert instance.job_name == "download"
    assert instance.job_path == tmp_path / "plugin"
    assert instance.restore_ok is expected
    assert restore.call_count == (0 if metadata["scheduler_first_start"] else 1)


def test_job_without_explicit_path_infers_calling_script(tmp_path, monkeypatch):
    script = tmp_path / "plugin/jobs/inferred.py"
    script.parent.mkdir(parents=True)
    script.write_text("# calling job\n")
    real_path = Path

    def path(*parts):
        if parts[:4] == ("/", "var", "cache", "bunkerweb"):
            return tmp_path.joinpath(*parts[4:])
        return real_path(*parts)

    monkeypatch.setattr(jobs, "Path", path)
    monkeypatch.setattr(jobs, "getframeinfo", lambda _: Mock(filename=str(script)))
    db = Mock()
    db.get_metadata.return_value = {"scheduler_first_start": True}
    instance = jobs.Job(Mock(), db=db)
    assert instance.job_name == "inferred"
    assert instance.job_path == tmp_path / "plugin"


def test_restore_refuses_unsafe_row_and_keeps_unrelated_files(job):
    (job.job_path / "keep").write_bytes(b"important")
    job.db.get_jobs_cache_files.return_value = [row("../escape")]
    assert job.restore_cache(manual=False) is False
    assert (job.job_path / "keep").read_bytes() == b"important"
    assert not (job.job_path.parent / "escape").exists()


def test_restore_archive_publishes_directory(job, monkeypatch):
    monkeypatch.setattr(cache_restore, "FOLDER_ROOTS", (job.job_path,))
    target = job.job_path / "tree"
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        info = tarfile.TarInfo("data")
        info.size = 7
        archive.addfile(info, io.BytesIO(b"payload"))
    job.db.get_jobs_cache_files.return_value = [row(f"folder:{target}.tgz", stream.getvalue())]
    assert job.restore_cache(manual=False)
    assert (target / "data").read_bytes() == b"payload"
    assert sorted(p.name for p in job.job_path.iterdir()) == ["tree"]
