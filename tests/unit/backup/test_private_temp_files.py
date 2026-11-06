"""Backup files that hold a full database dump are private from the moment they exist.

The pre-restore dump used to go to a fixed `/tmp/bunkerweb/backups` directory, and the archive was created
with the umask and only then restricted to 0600.
"""

import logging
import os
import runpy
import stat
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

_BACKUP = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
RESTORE = _BACKUP / "bwcli" / "restore.py"


@pytest.fixture
def restore(tmp_path, monkeypatch):
    """Run bwcli restore with a stubbed `backup` module and report where the pre-restore dump went."""
    archive = tmp_path / "backup-sqlite-2026-01-01_00-00-00.zip"
    archive.write_bytes(b"archive")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    seen = {}

    module = ModuleType("backup")
    module.BACKUP_DIR = tmp_path / "backups"
    module.LOGGER = logging.getLogger("restore-private-temp")
    module.DatabaseLockBusy = type("DatabaseLockBusy", (Exception,), {})
    module.acquire_db_lock = lambda: object()
    module.release_db_lock = lambda lock: None

    def backup_database(current_time, db=None, backup_dir=None):
        seen["dir"] = Path(backup_dir)
        seen["mode"] = stat.S_IMODE(os.stat(backup_dir).st_mode)
        return "db", Path(backup_dir) / "dump.zip"

    module.backup_database = backup_database
    module.restore_database = lambda file, db: seen.setdefault("restored", file)
    monkeypatch.setitem(sys.modules, "backup", module)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(sys, "argv", ["restore.py", str(archive)])
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    monkeypatch.setenv("TMPDIR", str(scratch))

    def run():
        with pytest.raises(SystemExit) as exit_info:
            runpy.run_path(str(RESTORE), run_name="__main__")
        seen["status"] = exit_info.value.code
        return seen

    return run, scratch


def test_the_pre_restore_dump_goes_to_a_private_random_directory(restore):
    run, scratch = restore

    seen = run()

    assert seen["status"] == 0 and "restored" in seen, seen
    assert seen["dir"] != Path("/tmp/bunkerweb/backups"), "the fixed predictable directory is still used"
    assert seen["dir"].parent == scratch, f"the dump must go under the temp directory, got {seen['dir']}"
    assert seen["mode"] == 0o700, f"the dump directory must be private, got {oct(seen['mode'])}"


def test_two_restores_never_share_a_dump_directory(restore):
    run, _ = restore
    first = run()["dir"]
    second = run()["dir"]

    assert first != second


# ---------------------------------------------------------------------------------------------
# archive created 0600 from the start
# ---------------------------------------------------------------------------------------------

sys.path.insert(0, str(_BACKUP))
import backup  # noqa: E402


def test_the_archive_is_never_group_or_world_readable(tmp_path, monkeypatch):
    """No window between creating the archive and restricting it: the later chmod is neutralised here."""
    monkeypatch.setattr(Path, "chmod", lambda self, mode, **kw: None)
    old_umask = os.umask(0o000)
    try:
        db = SimpleNamespace(database_uri="mariadb+pymysql://bw:s@db:3306/bunkerweb", sql_engine=MagicMock())
        with patch.object(backup, "inspect", create=True) as inspect_mock, patch.object(backup, "run", return_value=CompletedProcess([], 0, b"-- dump", b"")):
            inspect_mock.return_value.get_table_names.return_value = ["bw_plugins"]
            inspect_mock.return_value.get_view_names.return_value = []
            _, archive = backup.backup_database(datetime.now().astimezone(), db=db, backup_dir=tmp_path)
    finally:
        os.umask(old_umask)

    assert stat.S_IMODE(archive.stat().st_mode) == 0o600, oct(archive.stat().st_mode)
