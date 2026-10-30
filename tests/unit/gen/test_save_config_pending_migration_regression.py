"""The covered saver CLI must refuse an installed revision ahead of the stored schema.

Refusal must precede table initialization, config saving and metadata stamping.
"""

import runpy
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

import common_utils
import Database
import logger
import save_config


def test_pending_migration_exits_before_any_database_write(db, tmp_path, monkeypatch):
    assert db.initialize_db("1.6.17", "Docker") == ""
    installed = "1.6.18~rc2"
    assert save_config.migration_pending("1.6.17", installed, "sqlite")
    monkeypatch.setattr(common_utils, "get_version", lambda: installed)
    monkeypatch.setattr(common_utils, "get_integration", lambda: "Docker")
    log = Mock()
    monkeypatch.setattr(logger, "getLogger", lambda *args: log)
    boundary = Mock(wraps=db)
    boundary.database_uri = db.database_uri
    monkeypatch.setattr(Database, "Database", Mock(return_value=boundary))
    root = Path(__file__).resolve().parents[3]
    argv = [save_config.__file__, "--settings", str(root / "src/common/settings.json"), "--core", str(root / "src/common/core")]
    for name in ("plugins", "pro-plugins"):
        path = tmp_path / name
        path.mkdir()
        argv.extend(["--" + name, str(path)])
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as error:
        runpy.run_path(save_config.__file__, run_name="__main__")

    assert db.get_metadata()["version"] == "1.6.17"
    boundary.init_tables.assert_not_called()
    boundary.initialize_db.assert_not_called()
    boundary.save_config.assert_not_called()
    assert error.value.code == 1
    assert "migration has not run" in str(log.error.call_args_list)
