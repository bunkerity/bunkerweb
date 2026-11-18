"""Manual source deletion, incomplete scans and inactive CRS files use the real SQLite DB."""

import json
import logging
import os
from functools import partial
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader

from fixtures.seed import add_custom_config_row, add_global_value, add_setting, seed_minimal

MARKER = ".bw-managed"


@pytest.fixture
def manual_source(sched_main, sandbox, db, monkeypatch, sched_logger):
    seed_minimal(db)
    monkeypatch.setattr(sched_main, "SCHEDULER", SimpleNamespace(db=db, apis=[]))
    monkeypatch.setattr(sched_main, "LOGGER", sched_logger)
    monkeypatch.setattr(
        sched_main, "generate_custom_configs", partial(sched_main.generate_custom_configs, original_path=sandbox.CUSTOM_CONFIGS_PATH, send=False)
    )
    return sandbox.CUSTOM_CONFIGS_PATH


def put(source, relative, content="# manual"):
    path = source / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


@pytest.mark.parametrize("linked", [False, True], ids=["linux", "data-volume"])
def test_last_manual_deletion_survives_restart(sched_main, manual_source, db, linked, tmp_path):
    if linked:
        manual_source.rmdir()
        target = tmp_path / "data" / "configs"
        target.mkdir(parents=True)
        manual_source.symlink_to(target, target_is_directory=True)
    original = put(manual_source, "http/only.conf")
    assert sched_main.check_configs_changes(generate=False) is True
    assert (manual_source / MARKER).is_file()
    assert db.get_custom_config("http", "only")["method"] == "manual"
    original.unlink()
    # No process-local state: the next call sees only the on-disk marker and persisted DB.
    assert sched_main.check_configs_changes() is True
    assert db.get_custom_configs() == []
    assert not original.exists()
    assert (manual_source / MARKER).is_file()
    assert sched_main.check_configs_changes() is False


@pytest.mark.parametrize("missing", [False, True], ids=["fresh-empty", "missing-volume"])
def test_unmarked_empty_source_restores_database_without_retry(sched_main, manual_source, db, missing, caplog):
    add_custom_config_row(db, name="only", data=b"# retained")
    if missing:
        manual_source.rmdir()
    with caplog.at_level(logging.WARNING):
        assert sched_main.check_configs_changes(generate=False) is False
    assert db.get_custom_config("http", "only")["data"] == b"# retained"
    assert (manual_source / "http/only.conf").read_bytes() == b"# retained"
    assert (manual_source / MARKER).is_file()
    assert len([r for r in caplog.records if r.levelno >= logging.WARNING]) == 1
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    caplog.clear()
    assert sched_main.check_configs_changes() is True
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_unreadable_subfolder_does_not_commit_partial_scan(sched_main, manual_source, db, monkeypatch, caplog):
    add_custom_config_row(db, name="keep", data=b"# keep")
    add_custom_config_row(db, type="server_http", service_id="app1.example.com", name="hidden", data=b"# hidden")
    put(manual_source, "http/keep.conf", "# keep")
    hidden = put(manual_source, "server-http/app1.example.com/hidden.conf", "# hidden")
    (manual_source / MARKER).touch()
    scandir = os.scandir

    def deny(path):
        if not isinstance(path, int) and os.fspath(path) == str(hidden.parent):
            raise PermissionError(13, "unreadable subfolder", str(path))
        return scandir(path)

    monkeypatch.setattr(os, "scandir", deny)
    with caplog.at_level(logging.WARNING):
        assert sched_main.check_configs_changes() is False
    assert {c["name"] for c in db.get_custom_configs()} == {"keep", "hidden"}
    assert hidden.read_bytes() == b"# hidden"
    assert "unreadable subfolder" in caplog.text


def test_read_error_does_not_overwrite_edits_or_delete_rows(sched_main, manual_source, db, monkeypatch, caplog):
    add_custom_config_row(db, name="only", data=b"# retained")
    path = put(manual_source, "http/only.conf", "# unsaved edit")
    (manual_source / MARKER).touch()
    read = type(path).read_text

    def deny(file, *args, **kwargs):
        if file == path:
            raise PermissionError(13, "read denied", str(file))
        return read(file, *args, **kwargs)

    monkeypatch.setattr(type(path), "read_text", deny)
    with caplog.at_level(logging.WARNING):
        assert sched_main.check_configs_changes() is False
    assert db.get_custom_config("http", "only")["data"] == b"# retained"
    assert path.read_bytes() == b"# unsaved edit"
    assert "read denied" in caplog.text


def test_incompatible_manual_source_survives_generation_and_scan(sched_main, manual_source, db):
    add_setting(db, "USE_MODSECURITY_GLOBAL_CRS", default="no")
    add_custom_config_row(db, name="keep", data=b"# keep")
    add_custom_config_row(db, type="modsec_crs", service_id="app1.example.com", name="rules", data=b"# original")
    sched_main.generate_custom_configs()
    path = manual_source / "modsec-crs/app1.example.com/rules.conf"
    path.write_bytes(b"# unsaved manual edit")
    before = path.stat()
    stale = put(manual_source, "modsec-crs/app1.example.com/stale.conf")
    add_global_value(db, setting_id="USE_MODSECURITY_GLOBAL_CRS", value="yes", method="ui")
    assert db.get_custom_config_compatibility_error("modsec-crs", service_id="app1.example.com")
    sched_main.generate_custom_configs()
    assert path.read_bytes() == b"# unsaved manual edit"
    assert path.stat().st_ino == before.st_ino
    assert not stale.exists()
    assert sched_main.check_configs_changes(generate=False) is True
    assert db.get_custom_config("modsec_crs", "rules", service_id="app1.example.com")["data"] == b"# unsaved manual edit"

    # The real global-CRS templates include only top-level modsec-crs files; preserved service files stay inactive.
    root = Path(__file__).resolve().parents[3]
    env = Environment(loader=FileSystemLoader(root / "src/common/core/modsecurity/confs"))
    env.globals.update({"import": import_module}, is_custom_conf=lambda path: True, has_variable=lambda *args: False)
    settings = json.loads((root / "src/common/core/modsecurity/plugin.json").read_text())["settings"]
    variables = {name: setting["default"] for name, setting in settings.items()}
    variables.update(db.get_config(), MAX_CLIENT_SIZE="10m", ALLOWED_METHODS="GET|HEAD", all={"app1.example.com_ALLOWED_METHODS": "GET|HEAD"})
    variables.update(USE_MODSECURITY="yes", USE_MODSECURITY_CRS="yes", USE_MODSECURITY_GLOBAL_CRS="yes", MULTISITE="yes", SERVER_NAME="app1.example.com")
    for name in ("http/modsecurity-rules-global-crs.conf.modsec", "server-http/modsecurity-rules-global-crs.conf.modsec"):
        rendered = env.get_template(name).render(**variables)
        assert "modsec-crs/app1.example.com/" not in rendered


def test_marked_empty_source_deletes_last_manual_row(sched_main, manual_source, db, caplog):
    add_custom_config_row(db, name="only", data=b"# deleted by operator")
    (manual_source / MARKER).touch()
    with caplog.at_level(logging.INFO):
        assert sched_main.check_configs_changes(generate=False) is True
    assert db.get_custom_configs() == []
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    sched_main.generate_custom_configs()
    assert not (manual_source / "http/only.conf").exists()
    assert (manual_source / MARKER).is_file()


def test_failed_restore_does_not_authorize_empty_scan(sched_main, manual_source, db, monkeypatch):
    add_custom_config_row(db, name="only", data=b"# retained")

    def fail(path, data):
        raise OSError("disk full")

    monkeypatch.setattr(sched_main, "_write_atomic", fail)
    assert sched_main.check_configs_changes(generate=False) is False
    assert not (manual_source / MARKER).exists()
    assert db.get_custom_config("http", "only")["data"] == b"# retained"


def test_unmarked_volume_restores_inactive_manual_rules(sched_main, manual_source, db):
    add_setting(db, "USE_MODSECURITY_GLOBAL_CRS", default="yes")
    add_custom_config_row(db, name="keep", data=b"# keep")
    add_custom_config_row(db, type="modsec_crs", service_id="app1.example.com", name="rules", data=b"# inactive")
    assert sched_main.check_configs_changes(generate=False) is False
    assert (manual_source / "modsec-crs/app1.example.com/rules.conf").read_bytes() == b"# inactive"
    assert (manual_source / MARKER).is_file()
    assert sched_main.check_configs_changes(generate=False) is True
    assert {c["name"] for c in db.get_custom_configs()} == {"keep", "rules"}


def test_empty_manual_source_survives_generation(sched_main, manual_source, db):
    add_custom_config_row(db, name="empty", data=b"")
    path = put(manual_source, "http/empty.conf", "")
    (manual_source / MARKER).touch()
    sched_main.generate_custom_configs()
    assert path.is_file()
    assert path.read_bytes() == b""
    sched_main.check_configs_changes(generate=False)
    assert db.get_custom_config("http", "empty")["data"] == b""


def test_failed_generation_preserves_manual_source_for_next_scan(sched_main, manual_source, db, monkeypatch):
    add_custom_config_row(db, name="only", data=b"# retained")
    path = put(manual_source, "http/only.conf", "# retained")
    (manual_source / MARKER).touch()

    def fail(path, data):
        raise OSError("disk full")

    monkeypatch.setattr(sched_main, "_write_atomic", fail)
    sched_main.generate_custom_configs()
    assert path.read_bytes() == b"# retained"
    sched_main.check_configs_changes(generate=False)
    assert db.get_custom_config("http", "only")["data"] == b"# retained"
