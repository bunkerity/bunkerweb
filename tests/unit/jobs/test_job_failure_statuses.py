"""Script exit statuses must preserve the worker's success/change/failure protocol."""

import importlib.util
import logging
import runpy
import sys
from datetime import datetime
from json import dumps
from pathlib import Path
from sqlite3 import connect
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fixtures.seed import FIXED_DT, seed_minimal, session
from model import Jobs_runs

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("force", [False, True])
@pytest.mark.parametrize("dump_code", [0, 1, 2])
def test_backup_dump_status_preserves_archive_and_releases_lock(tmp_path, monkeypatch, force, dump_code):
    spec = importlib.util.spec_from_file_location("job_backup", ROOT / "src/common/core/backup/backup.py")
    backup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backup)
    monkeypatch.setitem(sys.modules, "backup", backup)
    db_path = tmp_path / "source.sqlite3"
    connect(db_path).close()
    db = SimpleNamespace(database_uri=f"sqlite:///{db_path}", get_metadata=lambda: {"scheduler_first_start": False})
    monkeypatch.setitem(sys.modules, "Database", SimpleNamespace(Database=lambda *a, **kw: db))
    monkeypatch.setitem(sys.modules, "logger", SimpleNamespace(getLogger=lambda *a: logging.getLogger("job-backup")))
    monkeypatch.setitem(sys.modules, "jobs", SimpleNamespace(Job=lambda *a: SimpleNamespace(db=db, get_cache=lambda *a: None)))
    monkeypatch.setattr(backup, "acquire_db_lock", lambda: 17)
    released = Mock()
    monkeypatch.setattr(backup, "release_db_lock", released)
    monkeypatch.setattr(backup, "ensure_backup_dir", lambda directory: directory)
    monkeypatch.setattr(backup, "run", Mock(return_value=SimpleNamespace(returncode=dump_code, stdout=b"-- fixture dump\n", stderr=b"dump refused")))
    monkeypatch.setattr(backup, "update_cache_file", Mock())
    monkeypatch.setenv("BACKUP_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("FORCE_BACKUP", "yes" if force else "no")
    monkeypatch.setenv("USE_BACKUP", "yes")
    monkeypatch.setenv("BACKUP_SCHEDULE", "daily")
    monkeypatch.setenv("BACKUP_ROTATION", "7")
    monkeypatch.setenv("BACKUP_ROTATION_STRATEGY", "fifo")
    old = tmp_path / "backup-sqlite-2000-01-01_00-00-00.zip"
    old.write_bytes(b"last good backup")

    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / "src/common/core/backup/jobs/backup-data.py"))

    assert old.read_bytes() == b"last good backup"
    released.assert_called_once_with(17)
    assert exc.value.code == (0 if dump_code == 0 else 2)
    assert len(list(tmp_path.glob("backup-*.zip"))) == (2 if dump_code == 0 else 1)


@pytest.mark.parametrize("limit", ["-1", "invalid", "0", "2"])
def test_history_cleanup_rejects_invalid_limit_before_deleting_rows(db, monkeypatch, limit, caplog):
    seed_minimal(db)
    with session(db) as s:
        s.add(Jobs_runs(job_name="testjob", start_date=FIXED_DT, end_date=FIXED_DT, success=True))
    monkeypatch.setitem(sys.modules, "Database", SimpleNamespace(Database=lambda *a, **kw: db))
    monkeypatch.setitem(sys.modules, "logger", SimpleNamespace(getLogger=lambda *a: logging.getLogger("job-cleanup")))
    monkeypatch.setenv("DATABASE_MAX_JOBS_RUNS", limit)

    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / "src/common/core/db/jobs/cleanup-excess-jobs-runs.py"))

    assert exc.value.code == (2 if limit in ("-1", "invalid") else 0)
    with session(db) as s:
        assert s.query(Jobs_runs).count() == (0 if limit == "0" else 1)
    if limit == "-1":
        assert "DATABASE_MAX_JOBS_RUNS must be non-negative" in caplog.text


def test_bunkernet_final_cache_failure_already_fails_job(monkeypatch, caplog):
    now = datetime.now().astimezone().isoformat()
    cached = dumps({"created": now, "reports": [{"date": now}]}).encode()
    job = SimpleNamespace(
        db=SimpleNamespace(get_metadata=lambda: {"scheduler_first_start": False}, get_instances=lambda **kw: []),
        get_cache=lambda name, **kw: b"unit-id" if name == "instance.id" else cached,
        cache_file=lambda *a: (False, "cache refused"),
    )
    monkeypatch.setitem(sys.modules, "jobs", SimpleNamespace(Job=lambda *a: job))
    monkeypatch.setitem(sys.modules, "logger", SimpleNamespace(getLogger=lambda *a: logging.getLogger("job-bunkernet")))
    monkeypatch.setitem(sys.modules, "API", SimpleNamespace(API=object()))
    monkeypatch.setitem(sys.modules, "ApiCaller", SimpleNamespace(ApiCaller=lambda *a: SimpleNamespace(send_to_apis=lambda *a, **kw: (True, {}))))
    monkeypatch.setitem(sys.modules, "bunkernet", SimpleNamespace(send_reports=Mock(side_effect=AssertionError("small fresh batch must not send"))))
    monkeypatch.setenv("MULTISITE", "no")
    monkeypatch.setenv("USE_BUNKERNET", "yes")

    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / "src/common/core/bunkernet/jobs/bunkernet-send.py"))

    assert exc.value.code == 2
    assert "cache refused" in caplog.text
