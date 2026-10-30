"""SHA-256 checksums in backup archives, `bwcli plugin backup check`, and the disk-space pre-flight.

Every archive carries `<dump>.sql.sha256` next to the dump. A restore verifies it after the engine and
archive checks and before dropping a single table; `BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE=yes`
lets a restore through a mismatch as a last resort. Archives from before checksums still restore.
"""

import sys
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from runpy import run_path
from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

_BACKUP = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

import backup  # noqa: E402

URI = "mariadb+pymysql://bw:s@db:3306/bunkerweb"
DUMP = b"-- dump\nCREATE TABLE bw_plugins (id INT);\n"
OK = CompletedProcess([], 0, DUMP, b"")


def _db():
    return SimpleNamespace(database_uri=URI, sql_engine=MagicMock(), checked_changes=lambda **kwargs: "")


def _make_backup(tmp_path):
    with patch.object(backup, "inspect") as inspect_mock, patch.object(backup, "run", return_value=OK):
        inspect_mock.return_value.get_table_names.return_value = ["bw_plugins"]
        inspect_mock.return_value.get_view_names.return_value = []
        _, archive = backup.backup_database(datetime.now().astimezone(), db=_db(), backup_dir=tmp_path)
    return archive


def _rewrite(archive, **members):
    with ZipFile(archive) as zin:
        contents = {name: zin.read(name) for name in zin.namelist()}
    contents.update(members)
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zout:
        for name, data in contents.items():
            if data is not None:
                zout.writestr(name, data)


def _sha_name(archive):
    return archive.with_suffix(".sql").name + ".sha256"


def test_a_backup_stores_the_sha256_of_its_dump(tmp_path):
    archive = _make_backup(tmp_path)

    with ZipFile(archive) as zipf:
        sql_name = archive.with_suffix(".sql").name
        assert sorted(zipf.namelist()) == sorted([sql_name, _sha_name(archive)])
        assert zipf.read(_sha_name(archive)).decode() == f"{sha256(DUMP).hexdigest()}  {sql_name}\n"
    assert backup.verify_backup_checksum(archive)


def test_a_tampered_checksum_is_reported(tmp_path):
    archive = _make_backup(tmp_path)
    _rewrite(archive, **{_sha_name(archive): b"0" * 64 + b"  x.sql\n"})

    assert not backup.verify_backup_checksum(archive)


def test_an_archive_from_before_checksums_still_verifies(tmp_path):
    archive = _make_backup(tmp_path)
    _rewrite(archive, **{_sha_name(archive): None})

    assert backup.verify_backup_checksum(archive)


def test_an_unreadable_archive_fails_verification(tmp_path):
    archive = tmp_path / "backup-mariadb-2026-01-01_00-00-00.zip"
    archive.write_bytes(b"not a zip")

    assert not backup.verify_backup_checksum(archive)


def _restore(archive, monkeypatch, ignore):
    if ignore:
        monkeypatch.setenv("BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE", "yes")
    else:
        monkeypatch.delenv("BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE", raising=False)
    with patch.object(backup.Base.metadata, "drop_all") as drop_all, patch.object(backup, "run", return_value=OK) as run_mock:
        try:
            backup.restore_database(archive, db=_db())
        except SystemExit as e:
            return e.code, drop_all.called, run_mock.called
    return 0, drop_all.called, run_mock.called


def test_a_checksum_mismatch_aborts_the_restore_before_any_table_is_dropped(tmp_path, monkeypatch):
    archive = _make_backup(tmp_path)
    _rewrite(archive, **{_sha_name(archive): b"0" * 64 + b"  x.sql\n"})

    status, dropped, restored = _restore(archive, monkeypatch, ignore=False)

    assert status == 1
    assert not dropped and not restored


def test_the_ignore_setting_lets_a_mismatched_restore_through(tmp_path, monkeypatch):
    archive = _make_backup(tmp_path)
    _rewrite(archive, **{_sha_name(archive): b"0" * 64 + b"  x.sql\n"})

    status, dropped, restored = _restore(archive, monkeypatch, ignore=True)

    assert status == 0
    assert dropped and restored


def test_a_valid_backup_restores(tmp_path, monkeypatch):
    status, dropped, restored = _restore(_make_backup(tmp_path), monkeypatch, ignore=False)

    assert (status, dropped, restored) == (0, True, True)


def _check(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path)
    monkeypatch.setattr(sys, "argv", ["check.py"])
    with pytest.raises(SystemExit) as exit_info:
        run_path(str(_BACKUP / "bwcli" / "check.py"), run_name="__main__")
    return exit_info.value.code


def test_bwcli_check_passes_on_good_backups_and_fails_on_a_bad_one(tmp_path, monkeypatch):
    good = _make_backup(tmp_path)
    assert _check(tmp_path, monkeypatch) == 0

    bad = tmp_path / good.name.replace("backup-mariadb-", "backup-mariadb-9")
    bad.write_bytes(good.read_bytes())
    _rewrite(bad, **{_sha_name(bad): b"0" * 64 + b"  x.sql\n"})
    assert _check(tmp_path, monkeypatch) == 1


def test_bwcli_check_with_no_backups_succeeds(tmp_path, monkeypatch):
    assert _check(tmp_path, monkeypatch) == 0


# --- disk space ---------------------------------------------------------------------------------


def _engine_reporting(size):
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (size,)
    return SimpleNamespace(database_uri=URI, sql_engine=engine)


def test_too_little_free_space_stops_the_backup_before_the_dump(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "disk_usage", lambda path: SimpleNamespace(free=1_000))
    db = _engine_reporting(1_000)  # needs 2x the database size

    with patch.object(backup, "run") as run_mock, pytest.raises(SystemExit) as exit_info:
        backup.backup_database(datetime.now().astimezone(), db=db, backup_dir=tmp_path)

    assert exit_info.value.code == 1
    assert not run_mock.called
    assert list(tmp_path.iterdir()) == []


def test_enough_free_space_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "disk_usage", lambda path: SimpleNamespace(free=2_000))

    assert backup.check_disk_space("mariadb", _engine_reporting(1_000), tmp_path)


def test_a_failing_size_query_never_blocks_the_backup(tmp_path):
    engine = MagicMock()
    engine.connect.side_effect = RuntimeError("Access denied for user")

    assert backup.check_disk_space("mariadb", SimpleNamespace(sql_engine=engine), tmp_path)


def test_sqlite_uses_the_database_file_size(tmp_path, monkeypatch):
    db_file = tmp_path / "db.sqlite3"
    db_file.write_bytes(b"x" * 600)
    monkeypatch.setattr(backup, "disk_usage", lambda path: SimpleNamespace(free=1_000))

    assert not backup.check_disk_space("sqlite", None, tmp_path, db_path=db_file)
