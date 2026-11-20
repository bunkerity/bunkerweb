"""Backup list reports sorted archive metadata and fails visibly on malformed names."""

import logging
from pathlib import Path
import runpy
import sys
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "src/common/core/backup/bwcli/list.py"


@pytest.fixture
def list_backups(tmp_path, caplog, monkeypatch):
    module = ModuleType("backup")
    module.BACKUP_DIR = tmp_path
    module.LOGGER = logging.getLogger("backup-list-outcomes")
    monkeypatch.setitem(sys.modules, "backup", module)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    caplog.set_level(logging.INFO, logger=module.LOGGER.name)

    def run():
        try:
            runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as exc:
            return exc.code
        return 0

    return run


@pytest.mark.parametrize("count", [0, 1, 2])
def test_archive_count_sorting_and_database_column(list_backups, tmp_path, caplog, count):
    names = ["backup-sqlite-2026-01-01_01-02-03.zip", "backup-postgresql-2026-02-02_04-05-06.zip"]
    for name in names[:count]:
        (tmp_path / name).write_bytes(b"archive")
    (tmp_path / "ignore.txt").write_text("not an archive")
    assert list_backups() == 0
    if count == 0:
        assert f"No backup found in {tmp_path}" in caplog.text
        assert "Database" not in caplog.text
    else:
        assert f"Found {count} backup{'s' if count > 1 else ''} in {tmp_path}" in caplog.text
        assert "Database" in caplog.text and "Date" in caplog.text
        assert "sqlite" in caplog.text and "2026/01/01 01:02:03" in caplog.text
        if count == 2:
            assert caplog.text.index("sqlite") < caplog.text.index("postgresql")
            assert "2026/02/02 04:05:06" in caplog.text
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(names[:count] + ["ignore.txt"])


@pytest.mark.parametrize("name", ["malformed.zip", "backup-sqlite-invalid-date.zip"])
def test_malformed_archive_name_exits_one_and_logs_error(list_backups, tmp_path, caplog, name):
    (tmp_path / name).write_bytes(b"preserve")
    assert list_backups() == 1
    assert "Error while executing backup list command" in caplog.text
    assert (tmp_path / name).read_bytes() == b"preserve"
