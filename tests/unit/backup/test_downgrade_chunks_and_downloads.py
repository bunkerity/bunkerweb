"""D11: an in-place downgrade is refused while `download` plugins or `bw_blob_chunks` rows exist.

A 1.6.x reader cannot represent either: SQLAlchemy raises `LookupError` on the unknown `download`
label, and the rc3 revision's `downgrade()` drops `bw_blob_chunks` while the owner rows still hold
an 80-byte marker instead of the blob, so the data is silently gone. The only supported way back
is a restore from a backup, which is what `restore_only` says.
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

_BACKUP = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

import downgrade  # noqa: E402
from downgrade import IN_PLACE, RESTORE_ONLY, check_download_plugins, check_irrepresentable, count_download_plugins, count_irrepresentable  # noqa: E402

NOW = datetime(2026, 10, 5, 12, 0, 0).astimezone()


def _plugin(plugin_id: str, method: str):
    from model import Plugins  # noqa: PLC0415 - conftest puts src/common/db on the path

    return Plugins(id=plugin_id, name=plugin_id, description="d", version="1.0", type="external", method=method)


class TestPureChecks:
    def test_the_chunk_table_is_one_of_the_tables_the_preflight_counts(self):
        assert "bw_blob_chunks" in downgrade.IRREPRESENTABLE_TABLES

    def test_chunk_rows_force_a_restore(self):
        assert check_irrepresentable({"bw_blob_chunks": 1}).verdict == RESTORE_ONLY

    def test_no_download_plugin_passes(self):
        assert check_download_plugins(0).verdict == IN_PLACE

    def test_a_download_plugin_forces_a_restore(self):
        check = check_download_plugins(2)
        assert check.verdict == RESTORE_ONLY
        assert "download" in check.detail and "backup" in check.detail

    def test_an_uncountable_plugin_table_is_not_assumed_empty(self):
        assert check_download_plugins(None).verdict == RESTORE_ONLY


class TestAgainstARealDatabase:
    """Every engine the suite runs (`--db-engines`): the counting SQL is the part that differs."""

    def test_a_fresh_schema_counts_zero(self, db):
        assert count_download_plugins(db) == 0
        assert count_irrepresentable(db)["bw_blob_chunks"] == 0

    def test_a_download_plugin_is_counted_and_refused(self, db, tmp_path, monkeypatch):
        with db._db_session() as session:
            session.add(_plugin("from-url", "download"))
            session.add(_plugin("by-hand", "manual"))
            session.add(_plugin("legacy", "scheduler"))
            session.commit()

        assert count_download_plugins(db) == 1, "only the `download` method is counted"

        monkeypatch.setenv("CELERY_BROKER_URL", "")
        report = downgrade.preflight("1.6.15", db=db, backup_dir=tmp_path, now=NOW)
        check = next(c for c in report["checks"] if c["name"] == "download_plugins")
        assert check["verdict"] == RESTORE_ONLY
        assert report["verdict"] != IN_PLACE

    def test_manual_ui_and_legacy_plugins_alone_do_not_refuse(self, db):
        with db._db_session() as session:
            for plugin_id, method in (("by-hand", "manual"), ("by-ui", "ui"), ("legacy", "scheduler")):
                session.add(_plugin(plugin_id, method))
            session.commit()
        assert count_download_plugins(db) == 0
        assert check_download_plugins(count_download_plugins(db)).verdict == IN_PLACE

    def test_a_chunk_row_is_counted_and_refused(self, db, tmp_path, monkeypatch):
        from model import Blob_chunks  # noqa: PLC0415

        with db._db_session() as session:
            session.add(Blob_chunks(owner="bw_jobs_cache:1", checksum="0" * 64, idx=0, data=b"x"))
            session.commit()

        counts = count_irrepresentable(db)
        assert counts["bw_blob_chunks"] == 1
        assert check_irrepresentable(counts).verdict == RESTORE_ONLY

        monkeypatch.setenv("CELERY_BROKER_URL", "")
        report = downgrade.preflight("1.6.15", db=db, backup_dir=tmp_path, now=NOW)
        check = next(c for c in report["checks"] if c["name"] == "irrepresentable_data")
        assert check["verdict"] == RESTORE_ONLY
        assert "bw_blob_chunks" in check["detail"]

    def test_the_new_checks_issue_no_write_statement(self, db):
        from sqlalchemy import event  # noqa: PLC0415

        seen = []

        @event.listens_for(db.sql_engine, "before_cursor_execute")
        def _record(_conn, _cursor, statement, *_args):
            seen.append(statement)

        try:
            count_download_plugins(db)
        finally:
            event.remove(db.sql_engine, "before_cursor_execute", _record)

        assert seen, "no statement recorded: the listener never fired"
        assert all(s.strip().split()[0].upper() == "SELECT" for s in seen), seen


@pytest.mark.parametrize("target", ["1.6.14", "1.6.15"])
def test_the_report_names_the_check_for_both_manifest_targets(db, tmp_path, monkeypatch, target):
    monkeypatch.setenv("CELERY_BROKER_URL", "")
    names = [c["name"] for c in downgrade.preflight(target, db=db, backup_dir=tmp_path, now=NOW)["checks"]]
    assert "download_plugins" in names
