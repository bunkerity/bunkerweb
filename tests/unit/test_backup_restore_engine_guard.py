import sys
import unittest
from importlib import util
from os import getenv
from pathlib import Path
from sqlite3 import connect as sqlite_connect
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from sqlalchemy import create_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
for source_dir in (REPO_ROOT / "src/common/db", REPO_ROOT / "src/common/utils"):
    sys.path.insert(0, str(source_dir))

spec = util.spec_from_file_location("bw_backup", getenv("BACKUP_PY", REPO_ROOT / "src/common/core/backup/backup.py"))
backup = util.module_from_spec(spec)
spec.loader.exec_module(backup)

STAMP = "2026-10-23_10-00-00"
URIS = {
    "sqlite": "sqlite:////tmp/bw-guard/db.sqlite3",
    "mariadb": "mariadb+pymysql://bw:s@db:3306/bunkerweb",
    "mysql": "mysql+pymysql://bw:s@db:3306/bunkerweb",
    "postgresql": "postgresql+psycopg://bw:s@db:5432/bunkerweb",
}


def make_zip(directory, engine, member=None, payload=b"-- dump"):
    path = Path(directory, f"backup-{engine}-{STAMP}.zip")
    with ZipFile(path, "w") as zipf:
        zipf.writestr(member or path.with_suffix(".sql").name, payload)
    return path


def make_damaged_zip(directory, engine, compression):
    """Valid central directory and member name, but the member payload no longer matches its CRC."""
    path = Path(directory, f"backup-{engine}-{STAMP}.zip")
    payload = b"INSERT INTO bw_plugins VALUES (1, 'sentinel');\n" * 200
    with ZipFile(path, "w", compression=compression) as zipf:
        zipf.writestr(path.with_suffix(".sql").name, payload)
    raw = bytearray(path.read_bytes())
    # The local header (30 bytes + name) is followed by the payload: flip bytes inside it
    start = 30 + len(path.with_suffix(".sql").name)
    for offset in range(start + 8, start + 16):
        raw[offset] ^= 0xFF
    path.write_bytes(bytes(raw))
    return path


class RestoreEngineGuardTest(unittest.TestCase):
    def restore(self, target, archive, db=None):
        db = db or SimpleNamespace(database_uri=URIS[target], sql_engine=MagicMock(), checked_changes=MagicMock(return_value=""))
        # Path.unlink is mocked so the SQLite simulation never touches the real /var/tmp/bunkerweb/...sql
        with (
            patch.object(backup.Base.metadata, "drop_all") as drop_all,
            patch.object(backup, "run") as run_mock,
            patch.object(backup, "safe_zip_extractall"),
            patch.object(Path, "unlink", autospec=True) as unlink_mock,
        ):
            run_mock.return_value = SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
            try:
                backup.restore_database(archive, db)
                code = None
            except SystemExit as exc:
                code = exc.code
        self.unlink_calls = [call.args[0] for call in unlink_mock.call_args_list]
        return code, drop_all, run_mock

    def assertRefused(self, target, archive):
        code, drop_all, run_mock = self.restore(target, archive)
        self.assertEqual(code, 1)
        drop_all.assert_not_called()
        run_mock.assert_not_called()

    def test_other_engine_is_refused_before_drop_all(self):
        with TemporaryDirectory() as tmp:
            for source, target in (("mariadb", "sqlite"), ("sqlite", "postgresql"), ("mariadb", "mysql"), ("mysql", "mariadb"), ("postgresql", "mariadb")):
                with self.subTest(source=source, target=target):
                    self.assertRefused(target, make_zip(tmp, source))

    def test_unknown_engine_is_refused(self):
        with TemporaryDirectory() as tmp:
            self.assertRefused("sqlite", make_zip(tmp, "oracle"))
            path = Path(tmp, "renamed.zip")
            with ZipFile(path, "w") as zipf:
                zipf.writestr("renamed.sql", b"-- dump")
            self.assertRefused("sqlite", path)

    def test_missing_member_is_refused(self):
        with TemporaryDirectory() as tmp:
            self.assertRefused("sqlite", make_zip(tmp, "sqlite", member="other.sql"))

    def test_corrupt_or_missing_archive_is_refused(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp, f"backup-sqlite-{STAMP}.zip")
            path.write_bytes(b"not a zip")
            self.assertRefused("sqlite", path)
            self.assertRefused("sqlite", Path(tmp, "backup-sqlite-2000-01-01_00-00-00.zip"))

    def test_crc_damaged_member_is_refused(self):
        with TemporaryDirectory() as tmp:
            for compression in (ZIP_STORED, ZIP_DEFLATED):
                with self.subTest(compression=compression):
                    self.assertRefused("sqlite", make_damaged_zip(tmp, "sqlite", compression))
                    self.assertEqual(self.unlink_calls, [])

    def test_same_engine_runs_the_existing_restore_once(self):
        with TemporaryDirectory() as tmp:
            for engine in ("sqlite", "mariadb", "mysql", "postgresql"):
                with self.subTest(engine=engine):
                    code, drop_all, run_mock = self.restore(engine, make_zip(tmp, engine))
                    self.assertIsNone(code)
                    drop_all.assert_called_once()
                    self.assertEqual(run_mock.call_count, 2 if engine == "sqlite" else 1)
                    # Only the SQLite temporary dump is cleaned up, and it was mocked, so the real file is untouched
                    expected = [Path("/var/tmp/bunkerweb", f"backup-{engine}-{STAMP}.sql")] if engine == "sqlite" else []
                    self.assertEqual(self.unlink_calls, expected)

    def test_refusal_keeps_sqlite_tables_and_rows(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp, "db.sqlite3")
            engine = create_engine(f"sqlite:///{path}")
            with engine.begin() as conn:
                conn.exec_driver_sql("CREATE TABLE bw_plugins (id INT PRIMARY KEY, name TEXT)")
                conn.exec_driver_sql("INSERT INTO bw_plugins VALUES (1, 'sentinel')")
            db = SimpleNamespace(database_uri=f"sqlite:///{path}", sql_engine=engine, checked_changes=MagicMock(return_value=""))
            archive = make_zip(tmp, "mariadb")
            # Extraction and Path.unlink are mocked so a guard regression never touches the real /var/tmp/bunkerweb
            with (
                patch.object(backup, "run") as run_mock,
                patch.object(backup, "safe_zip_extractall") as extract_mock,
                patch.object(Path, "unlink", autospec=True) as unlink_mock,
            ):
                with self.assertRaises(SystemExit):
                    backup.restore_database(archive, db)
            run_mock.assert_not_called()
            extract_mock.assert_not_called()
            unlink_mock.assert_not_called()
            # drop_all is real here: it must not have removed the sentinel table
            with closing_connect(path) as conn:
                self.assertEqual(conn.execute("SELECT name FROM bw_plugins").fetchall(), [("sentinel",)])

    def test_crc_damaged_archive_keeps_sqlite_tables_and_rows(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp, "db.sqlite3")
            engine = create_engine(f"sqlite:///{path}")
            with engine.begin() as conn:
                conn.exec_driver_sql("CREATE TABLE bw_plugins (id INT PRIMARY KEY, name TEXT)")
                conn.exec_driver_sql("INSERT INTO bw_plugins VALUES (1, 'sentinel')")
            db = SimpleNamespace(database_uri=f"sqlite:///{path}", sql_engine=engine, checked_changes=MagicMock(return_value=""))
            for compression in (ZIP_STORED, ZIP_DEFLATED):
                with self.subTest(compression=compression):
                    archive = make_damaged_zip(tmp, "sqlite", compression)
                    with (
                        patch.object(backup, "run") as run_mock,
                        patch.object(backup, "safe_zip_extractall") as extract_mock,
                        patch.object(Path, "unlink", autospec=True) as unlink_mock,
                    ):
                        with self.assertRaises(SystemExit) as raised:
                            backup.restore_database(archive, db)
                    self.assertEqual(raised.exception.code, 1)
                    run_mock.assert_not_called()
                    extract_mock.assert_not_called()
                    unlink_mock.assert_not_called()
                    # drop_all is real here: it must not have removed the sentinel table
                    with closing_connect(path) as conn:
                        self.assertEqual(conn.execute("SELECT name FROM bw_plugins").fetchall(), [("sentinel",)])


def closing_connect(path):
    from contextlib import closing

    return closing(sqlite_connect(path.as_posix()))


if __name__ == "__main__":
    unittest.main()
