"""Cache recovery preserves committed files and rejects corrupt journals and pairs."""

import json
from unittest.mock import Mock

import pytest

import cache_restore as cache
import jobs


@pytest.mark.parametrize("failures", [1, 2, 3])
def test_atomic_file_write_retries_transient_missing_parent(tmp_path, monkeypatch, failures):
    target = tmp_path / "payload"
    target.write_bytes(b"old")
    target.chmod(0o640)
    original = cache.replace
    attempts = 0

    def replace(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts <= failures:
            raise FileNotFoundError("fixture transient parent removal")
        return original(source, destination)

    monkeypatch.setattr(cache, "replace", replace)
    if failures == 3:
        with pytest.raises(FileNotFoundError, match="fixture transient"):
            cache.write_atomic(target, b"new")
        assert target.read_bytes() == b"old"
    else:
        cache.write_atomic(target, b"new")
        assert target.read_bytes() == b"new" and target.stat().st_mode & 0o777 == 0o640
    assert attempts == min(failures + 1, 3)
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("state", [[], {"had_target": "yes"}, {"had_target": True, "extra": 1}, {"data": "eA==", "had_target": True}])
def test_corrupt_or_unexpected_journal_does_not_erase_target(tmp_path, state):
    target = tmp_path / "tree"
    target.mkdir()
    (target / "keep").write_bytes(b"good")
    journal = tmp_path / ".tree.cache-journal"
    journal.write_text(json.dumps(state))
    with pytest.raises(ValueError, match="journal"):
        cache.recover_directory(target)
    assert (target / "keep").read_bytes() == b"good"
    assert json.loads(journal.read_text()) == state


@pytest.mark.parametrize("companion_before", [None, b"old manifest"])
def test_uncommitted_generation_rolls_back_companion_and_directory(tmp_path, companion_before):
    target = tmp_path / "tree"
    target.mkdir()
    (target / "payload").write_bytes(b"old generation")
    companion = tmp_path / "manifest.json"
    if companion_before is not None:
        companion.write_bytes(companion_before)
    with cache.StagedDirectory(target, companion) as staged:
        (staged.path / "payload").write_bytes(b"new generation")
        staged.publish(b"new manifest")
        assert (target / "payload").read_bytes() == b"new generation"
        assert companion.read_bytes() == b"new manifest"
    assert (target / "payload").read_bytes() == b"old generation"
    assert companion.read_bytes() == companion_before if companion_before is not None else not companion.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == (["manifest.json", "tree"] if companion_before is not None else ["tree"])


def test_committed_journal_keeps_new_generation_after_cleanup_failure(tmp_path, monkeypatch):
    target = tmp_path / "tree"
    target.mkdir()
    (target / "payload").write_bytes(b"old")
    original = cache.rmtree
    with pytest.raises(OSError, match="fixture cleanup"):
        with cache.StagedDirectory(target) as staged:
            (staged.path / "payload").write_bytes(b"new")
            staged.publish()
            monkeypatch.setattr(cache, "rmtree", Mock(side_effect=OSError("fixture cleanup failed")))
            staged.commit()
    assert (target / "payload").read_bytes() == b"new"
    assert json.loads(staged.journal.read_text()) == {"committed": True}
    monkeypatch.setattr(cache, "rmtree", original)
    cache.recover_directory(target)
    assert (target / "payload").read_bytes() == b"new"
    assert not staged.backup.exists() and not staged.journal.exists()


def test_orphan_backup_gets_recoverable_journal(tmp_path):
    target = tmp_path / "tree"
    backup = tmp_path / ".tree.cache-backup"
    backup.mkdir()
    (backup / "payload").write_bytes(b"last good")
    cache.recover_directory(target, keep_journal=True)
    assert (target / "payload").read_bytes() == b"last good"
    assert json.loads((tmp_path / ".tree.cache-journal").read_text()) == {"had_target": True}
    assert not backup.exists()


def test_invalid_companion_encoding_preserves_generation(tmp_path):
    target = tmp_path / "tree"
    target.mkdir()
    journal = tmp_path / ".tree.cache-journal"
    journal.write_text(json.dumps({"had_target": True, "data": "not-base64!"}))
    with pytest.raises(ValueError):
        cache.recover_directory(target, tmp_path / "manifest")
    assert target.is_dir() and not (tmp_path / "manifest").exists()


@pytest.mark.parametrize("damage", ["crl-without-ca", "non-bytes", "nested-service"])
def test_mtls_pair_validation_preserves_existing_credentials(tmp_path, damage):
    root = tmp_path / "mtls"
    existing = root / "site.example"
    existing.mkdir(parents=True)
    (existing / "ca.pem").write_bytes(b"last good CA")
    row = dict(file_name="ca.pem", service_id="site.example", data=b"new CA")
    if damage == "crl-without-ca":
        row["file_name"] = "crl.pem"
    elif damage == "non-bytes":
        row["data"] = None
    else:
        row["service_id"] = "nested/site.example"
    with pytest.raises(ValueError, match="mTLS"):
        cache.restore_mtls_cache(root, [row])
    assert (existing / "ca.pem").read_bytes() == b"last good CA"


def test_mtls_pair_publication_sets_modes_and_preserves_transaction_markers(tmp_path):
    root = tmp_path / "mtls"
    root.mkdir()
    rows = [dict(file_name=name, service_id="site.example", data=data) for name, data in (("ca.pem", b"CA"), ("crl.pem", b"CRL"))]
    preserved = cache.restore_mtls_cache(root, rows)
    target = root / "site.example"
    assert target in preserved and cache.transaction_markers(target) <= preserved
    assert target.stat().st_mode & 0o777 == 0o750
    for name, content in (("ca.pem", b"CA"), ("crl.pem", b"CRL")):
        assert (target / name).read_bytes() == content
        assert (target / name).stat().st_mode & 0o777 == 0o640


def test_mtls_empty_rows_roll_back_and_keep_live_ca(tmp_path):
    root = tmp_path / "mtls"
    root.mkdir()
    target = root / "site.example"
    backup = root / ".site.example.cache-backup"
    backup.mkdir()
    (backup / "ca.pem").write_bytes(b"last good CA")
    assert target in cache.restore_mtls_cache(root, [])
    assert (target / "ca.pem").read_bytes() == b"last good CA"
    assert not (root / ".site.example.cache-journal").exists()


def test_cache_tree_does_not_descend_into_untrusted_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_bytes(b"keep")
    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    assert list(cache.cache_tree(root)) == [root / "link"]
    assert list(cache.cache_tree(root / "link")) == []


@pytest.fixture
def job(tmp_path):
    instance = object.__new__(jobs.Job)
    instance.job_name = "download"
    instance.job_path = tmp_path / "plugin"
    instance.job_path.mkdir()
    instance.db = Mock()
    instance.logger = Mock()
    return instance


@pytest.mark.parametrize("kind", ["mtls", "crs-pair", "crs-recovery", "archive-recovery"])
def test_job_restore_failures_keep_disk_and_report_error(job, monkeypatch, kind):
    (job.job_path / "keep").write_bytes(b"last good")
    if kind == "mtls":
        job.job_path = job.job_path.rename(job.job_path.with_name("mtls"))
        job.job_name = "client-cert"
        job.db.get_jobs_cache_files.return_value = [dict(file_name="crl.pem", service_id="site.example", data=b"CRL", job_name=job.job_name)]
    elif kind.startswith("crs"):
        job.job_path = job.job_path.rename(job.job_path.with_name("modsecurity"))
        job.job_name = "download-crs-plugins"
        job.db.get_jobs_cache_files.return_value = [dict(file_name="crs-plugins.json", service_id="", data=b"{}", job_name=job.job_name)]
        if kind == "crs-recovery":
            monkeypatch.setattr(jobs, "recover_directory", Mock(side_effect=OSError("fixture journal unreadable")))
    else:
        job.db.get_jobs_cache_files.return_value = [dict(file_name="folder:/outside/target.tgz", service_id="", data=b"bad", job_name=job.job_name)]
    assert job.restore_cache(manual=False) is False
    assert (job.job_path / "keep").read_bytes() == b"last good"
    assert job.logger.error.called
    message = job.logger.error.call_args.args[0]
    expected = {
        "mtls": "Error restoring mTLS cache pairs",
        "crs-pair": "Incomplete CRS plugin cache pair",
        "crs-recovery": "Error recovering CRS plugin publication",
        "archive-recovery": "Error recovering cache directory",
    }[kind]
    assert expected in message
