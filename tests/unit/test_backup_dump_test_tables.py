import sys
import unittest
from datetime import datetime, timedelta
from importlib import util
from os import getenv
from pathlib import Path
from subprocess import CompletedProcess, run
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[2]
for source_dir in (REPO_ROOT / "src/common/db", REPO_ROOT / "src/common/utils"):
    sys.path.insert(0, str(source_dir))

spec = util.spec_from_file_location("bw_backup", getenv("BACKUP_PY", REPO_ROOT / "src/common/core/backup/backup.py"))
backup = util.module_from_spec(spec)
spec.loader.exec_module(backup)

PROBE = "test_" + "ab12" * 8
NOW = datetime.now().astimezone()


def fake_db(uri, tables):
    engine = MagicMock()
    return SimpleNamespace(database_uri=uri, sql_engine=engine, tables=tables)


class BackupTestTablesTest(unittest.TestCase):
    def run_backup(self, uri, tables, procs, views=(), **patches):
        db = fake_db(uri, tables)
        with TemporaryDirectory() as tmp, patch.object(backup, "inspect", create=True) as inspect_mock, patch.object(
            backup, "run", side_effect=procs
        ) as run_mock:
            inspect_mock.return_value.get_table_names.return_value = tables
            inspect_mock.return_value.get_view_names.return_value = list(views)
            result = backup.backup_database(NOW, db=db, backup_dir=Path(tmp))
        return result, run_mock

    def test_sqlite_dump_skips_leftover_probe(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp, "db.sqlite3")
            engine = create_engine(f"sqlite:///{path}")
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE bw_plugins (id INT PRIMARY KEY)"))
                conn.execute(text(f"CREATE TABLE {PROBE} (id INT PRIMARY KEY)"))
            db = SimpleNamespace(database_uri=f"sqlite:///{path}", sql_engine=engine)
            _, backup_file = backup.backup_database(NOW, db=db, backup_dir=Path(tmp))
            sql = ZipFile(backup_file).read(backup_file.with_suffix(".sql").name).decode()
        self.assertIn("bw_plugins", sql)
        self.assertNotIn(PROBE, sql)

    def test_sqlite_round_trip_keeps_indexes_views_triggers_and_sequences(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp, "db.sqlite3")
            engine = create_engine(f"sqlite:///{path}")
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT)"))
                conn.execute(text("CREATE UNIQUE INDEX items_code_uq ON items (code)"))
                conn.execute(text("CREATE TABLE audit (n INT)"))
                conn.execute(text("CREATE VIEW items_v AS SELECT code FROM items"))
                conn.execute(text("CREATE TRIGGER items_ai AFTER INSERT ON items BEGIN INSERT INTO audit VALUES (NEW.id); END"))
                conn.execute(text("INSERT INTO items (id, code) VALUES (100, 'a')"))
                conn.execute(text(f"CREATE TABLE {PROBE} (id INT PRIMARY KEY)"))
            db = SimpleNamespace(database_uri=f"sqlite:///{path}", sql_engine=engine)
            _, backup_file = backup.backup_database(NOW, db=db, backup_dir=Path(tmp))
            sql = ZipFile(backup_file).read(backup_file.with_suffix(".sql").name)

            restored = Path(tmp, "restored.sqlite3")
            run(["sqlite3", restored.as_posix()], input=sql, check=True)
            restored_engine = create_engine(f"sqlite:///{restored}")
            with restored_engine.begin() as conn:
                names = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master"))}
                conn.execute(text("INSERT INTO items (code) VALUES ('b')"))
                next_id = conn.execute(text("SELECT max(id) FROM items")).scalar()
                with self.assertRaises(Exception):
                    conn.execute(text("INSERT INTO items (code) VALUES ('a')"))
        self.assertTrue({"items_code_uq", "items_v", "items_ai", "audit"} <= names)
        self.assertNotIn(PROBE, names)
        self.assertEqual(next_id, 101)

    def test_mariadb_dumps_named_tables_and_views_whatever_the_database_name(self):
        ok = CompletedProcess([], 0, b"-- dump", b"")
        _, run_mock = self.run_backup("mariadb+pymysql://bw:s@db:3306/bunkerweb", ["bw_plugins", PROBE], [ok], views=["bw_view"])
        cmd = run_mock.call_args.args[0]
        self.assertNotIn(PROBE, cmd)
        self.assertIn("bw_plugins", cmd)
        self.assertIn("bw_view", cmd)
        self.assertIn("--routines", cmd)

    def test_postgresql_excludes_probe(self):
        ok = CompletedProcess([], 0, b"-- dump", b"")
        _, run_mock = self.run_backup("postgresql+psycopg://bw:s@db:5432/bunkerweb", ["bw_plugins"], [ok])
        cmd = run_mock.call_args.args[0]
        self.assertIn("--exclude-table=test_" + "[0-9a-f]" * 32, cmd)
        self.assertFalse([arg for arg in cmd if "?" in arg])

    def test_vanished_probe_is_retried_whatever_the_database_name(self):
        vanished = CompletedProcess([], 2, b"", f"Couldn't execute 'show create table `{PROBE}`': Table 'bunkerweb.{PROBE}' doesn't exist".encode())
        ok = CompletedProcess([], 0, b"-- dump", b"")
        (_, backup_file), run_mock = self.run_backup("mariadb+pymysql://bw:s@db:3306/bunkerweb", ["bw_plugins"], [vanished, ok])
        self.assertEqual(run_mock.call_count, 2)
        self.assertTrue(backup_file.name.startswith("backup-mariadb-"))

    def test_other_dump_failure_is_not_retried(self):
        denied = CompletedProcess([], 2, b"", b"Access denied for user")
        with self.assertRaises(SystemExit) as raised:
            self.run_backup("mariadb+pymysql://bw:s@db:3306/bunkerweb", ["bw_plugins"], [denied, denied])
        self.assertEqual(raised.exception.code, 1)

    def test_slow_successful_dump_is_not_a_failure(self):
        ok = CompletedProcess([], 0, b"-- dump", b"")
        clock = [NOW + timedelta(seconds=step * 12) for step in range(10)]
        with patch.object(backup, "datetime") as datetime_mock:
            datetime_mock.now.return_value.astimezone.side_effect = clock
            result, _ = self.run_backup("mariadb+pymysql://bw:s@db:3306/bunkerweb", ["bw_plugins"], [ok])
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
