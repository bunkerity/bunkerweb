"""Backups exclude only UUID write probes, preserving the live database and user objects."""

import sys
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

import pytest
from sqlalchemy import inspect, text

from fixtures.db_clients import clients_present, missing_clients_message

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src/common/core/backup"))
import backup  # noqa: E402

PROBE = "test_" + "ab12" * 8


def test_dump_omits_probe_and_keeps_user_tables_views_and_data(db, db_engine, tmp_path):
    # `db` has already skipped an unconfigured or unreachable engine, so reaching here means the engine is
    # there; one without its dump client is a broken environment and fails, as in test_downgrade_round_trip.
    if not clients_present(db_engine):
        pytest.fail(missing_clients_message(db_engine))
    with db.sql_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {PROBE} (id INT PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE test_customer (id INT PRIMARY KEY)"))
        conn.execute(text("INSERT INTO test_customer VALUES (42)"))
        conn.execute(text("CREATE VIEW test_customer_view AS SELECT id FROM test_customer"))
    try:
        _, archive = backup.backup_database(datetime.now().astimezone(), db, tmp_path)
        with ZipFile(archive) as zipf:
            sql = zipf.read(archive.with_suffix(".sql").name).decode()
        assert PROBE not in sql
        assert "test_customer" in sql
        assert "test_customer_view" in sql
        assert "42" in sql
        assert PROBE in inspect(db.sql_engine).get_table_names()
    finally:
        with db.sql_engine.begin() as conn:
            conn.execute(text("DROP VIEW IF EXISTS test_customer_view"))
            conn.execute(text("DROP TABLE IF EXISTS test_customer"))
            conn.execute(text(f"DROP TABLE IF EXISTS {PROBE}"))
