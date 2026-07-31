from logging import getLogger
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from model import Base  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
ALEMBIC = ROOT / "src" / "common" / "db" / "alembic"
HEADS = {
    "sqlite": "72d9f6a4c301",
    "mariadb": "c41a6e9d2b70",
    "mysql": "5e37a98b120c",
    "postgresql": "e8b4d91f6a20",
}


def test_all_dialects_have_the_1_7_head():
    for dialect, expected in HEADS.items():
        config = Config(str(ALEMBIC / "alembic.ini"))
        config.set_main_option("script_location", str(ALEMBIC))
        config.set_main_option("version_locations", str(ALEMBIC / f"{dialect}_versions"))
        assert ScriptDirectory.from_config(config).get_current_head() == expected


def test_sqlite_upgrade_creates_resource_tables(tmp_path, monkeypatch):
    uri = f"sqlite:///{tmp_path / 'migration.sqlite3'}"
    engine = create_engine(uri)
    Base.metadata.create_all(engine)
    for table in ("bw_resource_attachments", "bw_certificates", "bw_resources", "bw_resource_group_entries", "bw_resource_groups"):
        Base.metadata.tables[table].drop(engine, checkfirst=True)
    engine.dispose()

    monkeypatch.setenv("DATABASE_URI", uri)
    monkeypatch.chdir(ALEMBIC)
    config = Config("alembic.ini")
    config.set_main_option("version_locations", "sqlite_versions")
    command.stamp(config, "f9c3d7b2dba8")
    command.upgrade(config, "head")

    engine = create_engine(uri)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert {"bw_resources", "bw_certificates", "bw_resource_attachments", "bw_resource_groups", "bw_resource_group_entries"} <= tables


def test_loading_the_alembic_env_in_process_does_not_disable_existing_loggers(tmp_path, monkeypatch):
    """`env.py` calls `logging.config.fileConfig`, whose default `disable_existing_loggers=True`
    disables every logger not named in `alembic.ini`. That is harmless when alembic owns its own
    process (`entrypoint.sh`, `bunkerweb-scheduler.sh`), but this file loads `env.py` *in-process*,
    and the default silently killed the UI's module-level `LOGGER` for the rest of the pytest
    session -- `test_plugins_marketplace.py::test_rejected_toggle_flashes_error_and_clears_reloading`
    failed in a full-suite run and passed standalone. Ordering is not a guard, so this is."""
    victim = getLogger("bw_test_logger_created_before_alembic_runs")
    assert victim.disabled is False

    monkeypatch.setenv("DATABASE_URI", f"sqlite:///{tmp_path / 'logging.sqlite3'}")
    monkeypatch.chdir(ALEMBIC)
    config = Config("alembic.ini")
    config.set_main_option("version_locations", "sqlite_versions")
    command.stamp(config, "base")

    assert victim.disabled is False
