"""Which backup `bwcli plugin backup restore` picks, and which ones rotation deletes.

Both used plain name order. The engine name sits before the timestamp
(`backup-<engine>-<date>.zip`), so name order is per-engine order: with backups of two engines
in one directory -- a SQLite install migrated to MariaDB, or the backup test suite -- restore
picked the newest SQLite dump over a MariaDB one taken minutes ago, and rotation deleted the
newest MariaDB backup believing it was the oldest file.
"""

import sys
from pathlib import Path

import pytest

_BACKUP = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

from backup import restore_database, sorted_backups  # noqa: E402


def _touch(directory: Path, *names: str) -> None:
    for name in names:
        (directory / name).write_bytes(b"")


class TestOrdering:
    def test_the_engine_name_does_not_outrank_the_date(self, tmp_path):
        _touch(
            tmp_path,
            "backup-sqlite-2026-08-14_15-13-42.zip",
            "backup-mariadb-2026-08-14_15-14-52.zip",
        )

        assert [p.name for p in sorted_backups(tmp_path)][-1] == "backup-mariadb-2026-08-14_15-14-52.zip"

    def test_rotation_removes_the_oldest_whatever_engine_took_it(self, tmp_path):
        _touch(
            tmp_path,
            "backup-sqlite-2026-08-01_03-00-00.zip",
            "backup-mariadb-2026-08-02_03-00-00.zip",
            "backup-mariadb-2026-08-03_03-00-00.zip",
        )

        # What backup-data.py does once the rotation limit is one file smaller than the count.
        assert [p.name for p in sorted_backups(tmp_path)][:1] == ["backup-sqlite-2026-08-01_03-00-00.zip"]

    def test_the_partial_file_an_interrupted_run_leaves_is_not_a_backup(self, tmp_path):
        _touch(tmp_path, "backup-mariadb-2026-08-02_03-00-00.zip", "backup-mariadb-2026-08-03_03-00-00.zip.tmp")

        assert [p.name for p in sorted_backups(tmp_path)] == ["backup-mariadb-2026-08-02_03-00-00.zip"]


class TestEngineGuard:
    class _ExplodingDatabase:
        """Any use beyond reading the URI means the refusal came too late."""

        database_uri = "mariadb+pymysql://user:pass@db:3306/db"

        @property
        def sql_engine(self):
            raise AssertionError("the database was touched before the engine mismatch was refused")

    def test_a_dump_from_another_engine_is_refused_before_anything_is_dropped(self, tmp_path):
        backup_file = tmp_path / "backup-sqlite-2026-08-14_15-13-42.zip"
        backup_file.write_bytes(b"")

        with pytest.raises(SystemExit) as refused:
            restore_database(backup_file, self._ExplodingDatabase())

        assert refused.value.code == 1


class TestOracleIsRefusedBeforeTheDatabaseIsCleared:
    """Oracle has no restore path, so a restore must not begin one.

    The refusal existed, but it sat *after* the clearing step: `restore_database` dropped the
    schema, reached `elif database == "oracle"`, logged "not supported" and returned — destroying
    the database and restoring nothing, which is the worst outcome of the three. Oracle is a
    documented URI (`docs/features.md`, `Database.py`), so this is reachable rather than theoretical,
    and the clear step is now schema-wide rather than model-wide, which would have widened the hole
    from the model's tables to every table present.

    Same shape and same reasoning as `TestEngineGuard` above: the stand-in raises on any use beyond
    reading the URI, so "refused before anything was dropped" is enforced rather than asserted.
    """

    class _ExplodingDatabase:
        database_uri = "oracle+oracledb://user:pass@db:1521/db"

        @property
        def sql_engine(self):
            raise AssertionError("the database was cleared before the unsupported engine was refused")

    def test_an_oracle_restore_is_refused_without_touching_the_database(self, tmp_path):
        # Named for Oracle, so the engine-tag guard above lets it through and this guard is what
        # stops it. A mismatched name would pass the test for the wrong reason.
        backup_file = tmp_path / "backup-oracle-2026-08-31_10-00-00.zip"
        backup_file.write_bytes(b"")

        with pytest.raises(SystemExit) as refused:
            restore_database(backup_file, self._ExplodingDatabase())

        assert refused.value.code == 1
