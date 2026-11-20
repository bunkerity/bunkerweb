"""Regression tests for Database.cleanup_jobs_runs_excess.

A ranged `DELETE ... WHERE id IN (...)` fails with MariaDB error 1020 under snapshot isolation
(REPEATABLE READ + innodb_snapshot_isolation=1) when an ordinary job run is inserted between the id
selection and the DELETE. The method now deletes the selected rows by primary key.

SQLite always runs. MariaDB and PostgreSQL run against a disposable server when the matching URI is set:
    BW_TEST_MARIA_URI=mysql+pymysql://root:pw@127.0.0.1:3306/bw
    BW_TEST_PG_URI=postgresql+psycopg://postgres:pw@127.0.0.1:5432/bw
MariaDB must be started with --innodb-snapshot-isolation=1, otherwise the race test is skipped.
The nightly workflow sets it with SET GLOBAL and runs the race case alone, failing if it skips.
"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from os import environ
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[2]
for source_dir in (REPO_ROOT / "src/common/db", REPO_ROOT / "src/common/utils"):
    sys.path.insert(0, str(source_dir))

from sqlalchemy import event  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from Database import Database  # noqa: E402
from logger import getLogger  # noqa: E402
from model import Base, Jobs, Jobs_runs, Plugins  # noqa: E402

BASE_DATE = datetime(2026, 10, 1, tzinfo=timezone.utc)
RUNS = 100


class CleanupJobsRunsExcessCases:
    """Cases shared by every backend; subclasses provide `database_uri`."""

    maxDiff = None

    def database_uri(self) -> str:
        raise NotImplementedError

    def setUp(self):
        self.database = Database(getLogger("TEST"), self.database_uri(), log=False)
        Base.metadata.create_all(self.database.sql_engine)
        with self.database._db_session() as session:
            session.query(Jobs_runs).delete()
            session.query(Jobs).delete()
            session.query(Plugins).filter_by(id="p1").delete()
            session.add_all(
                [Plugins(id="p1", name="p1", description="", version="1", type="external"), Jobs(name="j1", plugin_id="p1", file_name="j1.py", every="day")]
            )
            session.commit()
        self.addCleanup(self.database.close)

    def seed(self, count: int = RUNS) -> dict:
        """Insert `count` runs whose end_date order differs from their id order; return {id: end_date}."""
        with self.database._db_session() as session:
            for i in range(count):
                end_date = BASE_DATE + timedelta(minutes=(i * 37) % count)
                session.add(Jobs_runs(job_name="j1", success=True, start_date=end_date, end_date=end_date))
            session.commit()
        return self.remaining()

    def remaining(self) -> dict:
        with self.database._db_session() as session:
            return {row.id: row.end_date.replace(tzinfo=None) for row in session.query(Jobs_runs.id, Jobs_runs.end_date)}

    def capture_deletes(self) -> list:
        statements = []

        def record(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("DELETE"):
                statements.append(statement)

        event.listen(self.database.sql_engine, "before_cursor_execute", record)
        self.addCleanup(event.remove, self.database.sql_engine, "before_cursor_execute", record)
        return statements

    def insert_during_cleanup(self):
        """Commit an ordinary job run from another connection right after the oldest ids were selected."""
        fired = []

        def after_select(conn, cursor, statement, parameters, context, executemany):
            if not fired and statement.lstrip().upper().startswith("SELECT BW_JOBS_RUNS.ID"):
                fired.append(True)
                with self.database.sql_engine.begin() as writer:
                    writer.execute(
                        Jobs_runs.__table__.insert().values(job_name="j1", success=True, start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=1))
                    )

        event.listen(self.database.sql_engine, "after_cursor_execute", after_select)
        self.addCleanup(event.remove, self.database.sql_engine, "after_cursor_execute", after_select)
        return fired

    def test_removes_oldest_by_end_date_and_reports_count(self):
        before = self.seed()
        newest = sorted(before, key=before.get)[-10:]

        self.assertEqual(self.database.cleanup_jobs_runs_excess(10), "Removed 90 excess jobs runs")

        self.assertCountEqual(self.remaining(), newest)

    def test_deletes_by_primary_key_not_by_range(self):
        self.seed()
        deletes = self.capture_deletes()

        self.database.cleanup_jobs_runs_excess(10)

        self.assertTrue(deletes)
        for statement in deletes:
            self.assertNotIn(" IN ", statement.upper(), statement[:60])

    def test_nothing_to_remove(self):
        self.assertEqual(self.database.cleanup_jobs_runs_excess(10), "Removed 0 excess jobs runs")
        before = self.seed(5)
        self.assertEqual(self.database.cleanup_jobs_runs_excess(10), "Removed 0 excess jobs runs")
        self.assertEqual(self.database.cleanup_jobs_runs_excess(5), "Removed 0 excess jobs runs")
        self.assertEqual(self.remaining(), before)

    def test_zero_keeps_nothing(self):
        self.seed(20)
        self.assertEqual(self.database.cleanup_jobs_runs_excess(0), "Removed 20 excess jobs runs")
        self.assertEqual(self.remaining(), {})

    def test_run_inserted_between_select_and_delete(self):
        before = self.seed()
        oldest = sorted(before, key=before.get)[:90]
        fired = self.insert_during_cleanup()

        self.assertEqual(self.database.cleanup_jobs_runs_excess(10), "Removed 90 excess jobs runs")

        self.assertTrue(fired)
        left = self.remaining()
        self.assertEqual(len(left), 11)
        self.assertFalse(set(oldest) & set(left))


class SqliteCleanupJobsRunsExcessTest(CleanupJobsRunsExcessCases, unittest.TestCase):
    def database_uri(self) -> str:
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return f"sqlite:///{tmp.name}/db.sqlite3"


@unittest.skipUnless(environ.get("BW_TEST_PG_URI"), "BW_TEST_PG_URI not set")
class PostgresqlCleanupJobsRunsExcessTest(CleanupJobsRunsExcessCases, unittest.TestCase):
    def database_uri(self) -> str:
        return environ["BW_TEST_PG_URI"]


@unittest.skipUnless(environ.get("BW_TEST_MARIA_URI"), "BW_TEST_MARIA_URI not set")
class MariadbCleanupJobsRunsExcessTest(CleanupJobsRunsExcessCases, unittest.TestCase):
    def database_uri(self) -> str:
        return environ["BW_TEST_MARIA_URI"]

    def test_run_inserted_between_select_and_delete(self):
        with self.database.sql_engine.connect() as conn:
            try:
                snapshot = conn.exec_driver_sql("SELECT @@innodb_snapshot_isolation").scalar()
            except OperationalError:
                snapshot = 0
            isolation = conn.exec_driver_sql("SELECT @@tx_isolation").scalar()
        if not snapshot or isolation != "REPEATABLE-READ":
            self.skipTest("needs REPEATABLE-READ with innodb_snapshot_isolation=1")
        super().test_run_inserted_between_select_and_delete()


if __name__ == "__main__":
    unittest.main()
