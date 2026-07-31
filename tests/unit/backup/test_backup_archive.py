"""`write_backup_archive` — a backup file must never exist under its final name half-written.

Rotation globs `backup-*.zip` and unlinks the oldest to stay under BACKUP_ROTATION
(core/backup/jobs/backup-data.py:93-105), `update_cache_file` lists whatever that glob returns
(backup.py:46), and `bwcli restore` offers the newest. A run killed mid-archive used to leave a
truncated file that all three treated as a finished backup — so a crash could delete a good
backup to make room for a corrupt one. At-least-once delivery makes that more frequent; it was
never dependent on it.
"""

import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

_BACKUP = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

from backup import write_backup_archive  # noqa: E402

ROTATION_GLOB = "backup-*.zip"
FINAL_NAME = "backup-mariadb-2026-07-31_03-00-01.zip"


class TestSuccessfulWrite:
    def test_the_archive_lands_under_its_final_name_with_its_content(self, tmp_path):
        target = tmp_path / FINAL_NAME
        write_backup_archive(target, "dump.sql", b"CREATE TABLE t;")

        assert target.is_file()
        with ZipFile(target) as archive:
            assert archive.read("dump.sql") == b"CREATE TABLE t;"

    def test_no_temporary_file_survives_a_successful_write(self, tmp_path):
        write_backup_archive(tmp_path / FINAL_NAME, "dump.sql", b"x")
        assert list(tmp_path.glob("*.tmp")) == []

    def test_the_finished_backup_is_not_world_readable(self, tmp_path):
        target = tmp_path / FINAL_NAME
        write_backup_archive(target, "dump.sql", b"secret")
        assert target.stat().st_mode & 0o777 == 0o600

    def test_the_permissions_are_tightened_before_the_file_is_published(self, tmp_path, monkeypatch):
        """Checking the FINAL mode is not enough -- it reads 0600 whether the chmod happened
        before or after the rename. Only the ordering matters: the payload is the whole
        database, and chmod-after would expose it world-readable between the two syscalls. So
        observe the mode at the instant of publication.
        """
        import backup

        real_replace = backup.replace
        observed = {}

        def spy(src, dst):
            observed["mode"] = Path(src).stat().st_mode & 0o777
            return real_replace(src, dst)

        monkeypatch.setattr(backup, "replace", spy)
        write_backup_archive(tmp_path / FINAL_NAME, "dump.sql", b"secret")

        assert observed["mode"] == 0o600


class TestInterruptedWrite:
    """A SIGKILL cannot be simulated, but every observable consequence of one can: the process
    stops somewhere inside the zip write and never reaches the rename."""

    def _explode_midway(self, monkeypatch):
        import backup

        original = ZipFile.writestr

        def boom(self, *args, **kwargs):
            original(self, *args, **kwargs)
            raise KeyboardInterrupt("killed mid-archive")

        monkeypatch.setattr(backup.ZipFile, "writestr", boom)

    def test_the_final_name_never_appears(self, tmp_path, monkeypatch):
        self._explode_midway(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            write_backup_archive(tmp_path / FINAL_NAME, "dump.sql", b"partial")

        assert not (tmp_path / FINAL_NAME).exists()

    def test_rotation_cannot_see_what_was_left_behind(self, tmp_path, monkeypatch):
        """The heart of it: whatever the killed run left must not be counted as a backup, or
        rotation will delete a real one to stay under the limit."""
        self._explode_midway(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            write_backup_archive(tmp_path / FINAL_NAME, "dump.sql", b"partial")

        assert list(tmp_path.glob(ROTATION_GLOB)) == []

    def test_a_good_backup_beside_it_is_untouched(self, tmp_path, monkeypatch):
        good = tmp_path / "backup-mariadb-2026-07-30_03-00-01.zip"
        write_backup_archive(good, "dump.sql", b"yesterday")

        self._explode_midway(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            write_backup_archive(tmp_path / FINAL_NAME, "dump.sql", b"partial")

        assert [p.name for p in tmp_path.glob(ROTATION_GLOB)] == [good.name]
        with ZipFile(good) as archive:
            assert archive.read("dump.sql") == b"yesterday"

    def test_the_leftover_is_swept_by_the_jobs_own_glob(self, tmp_path, monkeypatch):
        """backup-data.py reaps `backup-*.zip.tmp` at start. Pin that the name it sweeps is the
        name this function actually leaves -- the two are in different files and would drift."""
        self._explode_midway(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            write_backup_archive(tmp_path / FINAL_NAME, "dump.sql", b"partial")

        leftovers = list(tmp_path.glob("backup-*.zip.tmp"))
        assert len(leftovers) == 1

        job_source = (_BACKUP / "jobs" / "backup-data.py").read_text(encoding="utf-8")
        assert 'glob("backup-*.zip.tmp")' in job_source
