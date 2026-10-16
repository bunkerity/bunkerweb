"""push-configs rewrites and snapshots the job cache under the cache publication lock (BW-214).

`Job.cache_file` writes the disk copy and then the DB row, both under `jobs.cache_publication_lock`.
`push-configs` used to read every cache row and write the blobs out WITHOUT that lock, so a job's
`cache_file` landing between the DB read and the disk write was overwritten on disk by the stale
blob: the DB held the new certificate, the disk (which is what gets pushed) the old one, and the
instance kept serving it. The failover snapshot copied the same tree unlocked, which is the same
race from the reader's side ("Failover snapshot failed: ... .bw-tmp: No such file").

`push-configs.py` runs on import, so the functions under test are lifted out of the source with
`ast`, the same way `tests/unit/ui/test_url_for_resolution.py` lifts the URL resolver.
"""

import ast
import threading
from contextlib import nullcontext
from datetime import datetime
from io import BytesIO
from pathlib import Path
from shutil import copytree, rmtree
from stat import S_IRGRP, S_IRUSR, S_IWUSR
from tarfile import TarInfo, open as tar_open
from unittest.mock import Mock

import jobs
import letsencrypt_consistency
import pytest

SOURCE = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "jobs" / "jobs" / "push-configs.py"
LIFTED = (
    "RETIRED_CACHE_ROWS",
    "RETIRED_CACHE_PATHS",
    "_cache_row_usable",
    "_is_letsencrypt_tree",
    "_materialize_cache_row",
    "_materialize_caches",
    "_snapshot_failover",
)


def _lift(tmp_path, **overrides):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name in LIFTED) or (isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) in LIFTED)
    ]
    namespace = {
        "CACHE_PATH": tmp_path / "cache",
        "CONFIG_PATH": tmp_path / "nginx",
        "FAILOVER_PATH": tmp_path / "failover",
        "FAILOVER_KEEP": 3,
        "LOGGER": Mock(),
        "Database": Mock,
        "BytesIO": BytesIO,
        "Path": Path,
        "datetime": datetime,
        "copytree": copytree,
        "rmtree": rmtree,
        "nullcontext": nullcontext,
        "tar_open": tar_open,
        "S_IRUSR": S_IRUSR,
        "S_IWUSR": S_IWUSR,
        "S_IRGRP": S_IRGRP,
        "_write_atomic": jobs._write_atomic,
        "CachePublicationLockError": jobs.CachePublicationLockError,
        "cache_publication_lock": jobs.cache_publication_lock,
        "le_cache_write_lock": letsencrypt_consistency.le_cache_write_lock,
    }
    namespace.update(overrides)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(SOURCE), "exec"), namespace)
    return namespace


@pytest.fixture
def cache_root(tmp_path, monkeypatch):
    """The cache tree, with the publication lock and the Let's Encrypt lock both inside tmp_path."""
    root = tmp_path / "cache"
    root.mkdir()
    monkeypatch.setattr(jobs, "CACHE_PATH", root)
    monkeypatch.setattr(letsencrypt_consistency, "LE_CACHE_LOCK_PATH", tmp_path / "le.lock")
    return root


def _row(file_name, data, plugin_id="certificates", service_id="www.example.com", job_name="deploy-certificates"):
    return {"plugin_id": plugin_id, "service_id": service_id, "file_name": file_name, "job_name": job_name, "data": data}


def _le_tgz(tree_root):
    """A Let's Encrypt cache archive that passes the skeleton check (`live/<name>/fullchain.pem`)."""
    buffer = BytesIO()
    with tar_open(fileobj=buffer, mode="w:gz") as tar:
        payload = b"NEW-LE-CERT"
        info = TarInfo("live/www.example.com/fullchain.pem")
        info.size = len(payload)
        tar.addfile(info, BytesIO(payload))
    return f"folder:{tree_root}.tgz", buffer.getvalue()


def test_a_job_write_cannot_land_between_the_db_read_and_the_disk_write(tmp_path, cache_root):
    materialize = _lift(tmp_path)["_materialize_caches"]
    target = cache_root / "certificates" / "www.example.com" / "cert.pem"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"OLD")
    stale = [_row("cert.pem", b"OLD")]
    finished = threading.Event()

    def job():  # what Job.cache_file does: write the disk copy under the lock
        with jobs.cache_publication_lock():
            jobs._write_atomic(target, b"NEW")
        finished.set()

    worker = threading.Thread(target=job)

    def get_jobs_cache_files(**kwargs):
        worker.start()
        finished.wait(timeout=0.5)  # unlocked: the job completes here; locked: it is blocked on flock
        return stale  # the snapshot predates the job's write

    materialize(Mock(get_jobs_cache_files=get_jobs_cache_files))
    worker.join(timeout=5)
    assert target.read_bytes() == b"NEW"  # the stale blob must not be written over the job's copy


def test_the_db_read_is_inside_the_lock(tmp_path, cache_root):
    materialize = _lift(tmp_path)["_materialize_caches"]
    db = Mock(get_jobs_cache_files=Mock(return_value=[]))

    with jobs.cache_publication_lock():
        runner = threading.Thread(target=materialize, args=(db,), daemon=True)
        runner.start()
        runner.join(timeout=0.5)
        assert runner.is_alive(), "materialize finished while a job held the publication lock"
        db.get_jobs_cache_files.assert_not_called()

    runner.join(timeout=5)
    assert not runner.is_alive()
    db.get_jobs_cache_files.assert_called()


def test_a_lock_timeout_fails_the_step_closed_without_reading_the_db(tmp_path, cache_root):
    namespace = _lift(tmp_path, cache_publication_lock=lambda logger=None: jobs.cache_publication_lock(logger, timeout=0.2))
    db = Mock(get_jobs_cache_files=Mock(return_value=[]))

    with jobs.cache_publication_lock():
        assert namespace["_materialize_caches"](db) is False

    db.get_jobs_cache_files.assert_not_called()
    assert namespace["_materialize_caches"](db) is True


def test_the_letsencrypt_tree_is_rebuilt_in_the_certbot_lock_order(tmp_path, cache_root):
    """certbot-new takes the LE lock and then the publication lock; materialize must not invert it.

    A holds the LE lock and waits for the publication lock while materialize still holds it for its
    first pass: an implementation that takes the LE lock while holding the publication lock
    deadlocks right here, which the 5 s join turns into a failure.
    """
    namespace = _lift(tmp_path)
    le_root = cache_root / "letsencrypt"
    file_name, blob = _le_tgz(le_root)
    row = _row(file_name, blob, plugin_id="letsencrypt", service_id="", job_name="certbot-new")
    holds_le_lock = threading.Event()
    calls = []

    def certbot():  # the order certbot-new.py and certbot-renew.py use
        with letsencrypt_consistency.le_cache_write_lock():
            holds_le_lock.set()
            with jobs.cache_publication_lock():
                pass

    certbot_thread = threading.Thread(target=certbot, daemon=True)

    def get_jobs_cache_files(**kwargs):
        calls.append(kwargs)
        if not kwargs:
            certbot_thread.start()
            assert holds_le_lock.wait(timeout=5)
        return [row]

    runner = threading.Thread(target=namespace["_materialize_caches"], args=(Mock(get_jobs_cache_files=get_jobs_cache_files),), daemon=True)
    runner.start()
    runner.join(timeout=5)
    certbot_thread.join(timeout=5)

    assert not runner.is_alive() and not certbot_thread.is_alive(), "lock-order deadlock"
    assert (le_root / "live" / "www.example.com" / "fullchain.pem").read_bytes() == b"NEW-LE-CERT"
    assert calls == [{}, {"plugin_id": "letsencrypt"}]  # the row is re-read inside the locks


def test_the_failover_snapshot_copies_the_cache_under_the_lock(tmp_path, cache_root):
    namespace = _lift(tmp_path)
    (tmp_path / "nginx").mkdir()
    (tmp_path / "nginx" / "nginx.conf").write_text("conf")
    (cache_root / "certificates").mkdir()
    (cache_root / "certificates" / "cert.pem").write_bytes(b"CERT")
    result = []

    with jobs.cache_publication_lock():
        runner = threading.Thread(target=lambda: result.append(namespace["_snapshot_failover"]()), daemon=True)
        runner.start()
        runner.join(timeout=0.5)
        assert runner.is_alive(), "the snapshot copied the cache while a job held the publication lock"

    runner.join(timeout=5)
    assert result and result[0] is not None
    assert result[0].joinpath("cache", "certificates", "cert.pem").read_bytes() == b"CERT"
