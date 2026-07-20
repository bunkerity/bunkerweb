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
