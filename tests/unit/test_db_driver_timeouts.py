#!/usr/bin/env python3

from logging import getLogger
from os import environ, getenv
from pathlib import Path
from sys import path as sys_path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
import unittest

ROOT = Path(__file__).resolve().parents[2]
# DB_SRC points the test at another copy of src/common/db (used to run it against the unfixed code).
for rel in (getenv("DB_SRC", "src/common/db"), "src/common/utils", "src/common/api"):
    sys_path.insert(0, str(rel if rel.startswith("/") else ROOT / rel))

import Database as database_module  # type: ignore  # noqa: E402
from Database import Database  # type: ignore  # noqa: E402

MYSQL_URI = "mysql+pymysql://u:p@db:3306/bw"
POSTGRES_URI = "postgresql+psycopg://u:p@db:5432/bw"
PG_KEEPALIVES = {"keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 3, "tcp_user_timeout": 60000}


def engine_kwargs_for(uri, **kwargs):
    """Return the kwargs `retry_connection` hands to create_engine for `uri`, without opening a connection."""
    db = object.__new__(Database)
    db.logger = getLogger("test")
    db.sql_engine = MagicMock()
    db.database_uri = uri
    db.database_uri_readonly = ""
    db._session_factory = None
    db._engine_kwargs = {"future": True}
    db._connect_timeout = getattr(database_module, "DEFAULT_CONNECT_TIMEOUT", None)
    db._read_timeout = getattr(database_module, "DEFAULT_READ_TIMEOUT", None)
    with patch.object(database_module, "create_engine", return_value=MagicMock()) as create_engine:
        db.retry_connection(readonly=True, **kwargs)
    return create_engine.call_args.kwargs.get("connect_args")


class TestDriverTimeouts(unittest.TestCase):
    def test_mysql_defaults(self):
        self.assertEqual(engine_kwargs_for(MYSQL_URI), {"connect_timeout": 10, "read_timeout": 300, "write_timeout": 300})

    def test_postgres_defaults(self):
        self.assertEqual(engine_kwargs_for(POSTGRES_URI), {"connect_timeout": 10} | PG_KEEPALIVES)

    def test_sqlite_unchanged(self):
        self.assertIsNone(engine_kwargs_for("sqlite:////tmp/x.sqlite3"))

    def test_uri_option_wins(self):
        self.assertEqual(
            engine_kwargs_for(MYSQL_URI + "?read_timeout=7&connect_timeout=3"),
            {"write_timeout": 300},
        )
        self.assertEqual(engine_kwargs_for(POSTGRES_URI + "?connect_timeout=3&keepalives=0"), {k: v for k, v in PG_KEEPALIVES.items() if k != "keepalives"})

    def test_caller_connect_args_win(self):
        self.assertEqual(
            engine_kwargs_for(MYSQL_URI, connect_args={"read_timeout": 5}),
            {"connect_timeout": 10, "read_timeout": 5, "write_timeout": 300},
        )

    def test_zero_read_timeout_is_not_sent(self):
        db = object.__new__(Database)
        db._connect_timeout, db._read_timeout = 10, 0
        self.assertEqual(db._driver_connect_args(MYSQL_URI), {"connect_timeout": 10})
        self.assertEqual(db._driver_connect_args(POSTGRES_URI), {"connect_timeout": 10} | PG_KEEPALIVES)


class TestEnvParsing(unittest.TestCase):
    def build(self, **env):
        with TemporaryDirectory() as tmp, patch.dict(environ, env):
            logger = MagicMock()
            db = Database(logger, f"sqlite:///{tmp}/db.sqlite3", log=False)
            db.sql_engine.dispose()
        return db, logger

    def test_defaults(self):
        db, _ = self.build()
        self.assertEqual((db._connect_timeout, db._read_timeout), (10, 300))

    def test_env_override_with_suffix(self):
        db, _ = self.build(DATABASE_CONNECT_TIMEOUT="3", DATABASE_READ_TIMEOUT="2m")
        self.assertEqual((db._connect_timeout, db._read_timeout), (3, 120))

    def test_zero_read_timeout_disables_it(self):
        db, logger = self.build(DATABASE_READ_TIMEOUT="0")
        self.assertEqual(db._read_timeout, 0)
        logger.warning.assert_not_called()

    def test_zero_connect_timeout_falls_back_with_warning(self):
        for value in ("0", "0s", "0ms"):
            db, logger = self.build(DATABASE_CONNECT_TIMEOUT=value)
            self.assertEqual(db._connect_timeout, 10, value)
            self.assertTrue(any("DATABASE_CONNECT_TIMEOUT" in str(call) for call in logger.warning.call_args_list), value)

    def test_bad_value_falls_back_with_warning(self):
        db, logger = self.build(DATABASE_READ_TIMEOUT="soon")
        self.assertEqual(db._read_timeout, 300)
        self.assertTrue(any("DATABASE_READ_TIMEOUT" in str(call) for call in logger.warning.call_args_list))


if __name__ == "__main__":
    unittest.main()
