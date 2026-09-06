from datetime import datetime, timezone
from logging import getLogger

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

# The baseline is defined once, in `db/alembic_baseline.py`, and imported rather than restated. A
# test module is not an API; this used to import it out of `test_upgrade_schema_parity`. `tests/unit`
# is on `sys.path` from conftest, so `db.` resolves whether the suite, the directory or this single
# file was named.
from db.alembic_baseline import ALEMBIC, BASELINE_VERSION, baseline_metadata, revision_for

FIXED_DT = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
HEADS = {
    "sqlite": "81ecf3d749d4",
    "mariadb": "6e94caf3f414",
    "mysql": "fdea53656bf5",
    "postgresql": "3d2c304bf84e",
}


def test_all_dialects_have_the_1_7_head():
    for dialect, expected in HEADS.items():
        config = Config(str(ALEMBIC / "alembic.ini"))
        config.set_main_option("script_location", str(ALEMBIC))
        config.set_main_option("version_locations", str(ALEMBIC / f"{dialect}_versions"))
        assert ScriptDirectory.from_config(config).get_current_head() == expected


def test_sqlite_upgrade_creates_resource_tables(tmp_path, monkeypatch):
    """The centralized-certificate tables have to be *created by the migration*, not by
    `create_all` on the way past.

    This used to build its starting point with `Base.metadata.create_all(engine)` -- the **current**
    model -- and then drop five tables. That is a schema no release ever shipped, and once the 1.7
    head grew `add_column`s (the regeneration of 2026-09-01) it stopped being merely weak and became
    impossible: every column already existed, so the upgrade died on `duplicate column name` rather
    than proving anything. It now starts from the schema `v1.6.13` really shipped, exactly as
    `test_upgrade_schema_parity` does, and stamps the revision the product would stamp for it.
    """
    uri = f"sqlite:///{tmp_path / 'migration.sqlite3'}"
    engine = create_engine(uri)
    baseline_metadata().create_all(engine)
    engine.dispose()

    monkeypatch.setenv("DATABASE_URI", uri)
    monkeypatch.chdir(ALEMBIC)
    config = Config("alembic.ini")
    config.set_main_option("version_locations", "sqlite_versions")
    command.stamp(config, revision_for(BASELINE_VERSION, "sqlite"))
    command.upgrade(config, "head")

    engine = create_engine(uri)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert {"bw_resources", "bw_certificates", "bw_resource_attachments", "bw_resource_groups", "bw_resource_group_entries"} <= tables


def test_the_user_preferences_table_is_renamed_and_not_recreated(tmp_path, monkeypatch):
    """A rename that autogenerate cannot see.

    `bw_ui_user_columns_preferences` became `bw_ui_user_preferences` (commit 720e54954). Alembic
    compares two schemas and has no notion of identity between them, so it emits `drop_table` +
    `create_table` -- a revision that runs cleanly, reports success, and silently discards every
    operator's saved table layouts. `alembic/env.py` rewrites that pair into a real rename; this
    checks the rows arrive on the other side, which is the only part an operator would notice.
    """
    uri = f"sqlite:///{tmp_path / 'rename.sqlite3'}"
    engine = create_engine(uri)
    baseline = baseline_metadata()
    baseline.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            baseline.tables["bw_ui_users"].insert().values(username="admin", password="x", method="manual", creation_date=FIXED_DT, update_date=FIXED_DT)
        )
        # `columns` is the 1.6.13 `JSONText` decorator, so it takes the dict and serialises it.
        conn.execute(baseline.tables["bw_ui_user_columns_preferences"].insert().values(user_name="admin", table_name="bans", columns={"2": True}))
    engine.dispose()

    monkeypatch.setenv("DATABASE_URI", uri)
    monkeypatch.chdir(ALEMBIC)
    config = Config("alembic.ini")
    config.set_main_option("version_locations", "sqlite_versions")
    command.stamp(config, revision_for(BASELINE_VERSION, "sqlite"))
    command.upgrade(config, "head")

    engine = create_engine(uri)
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as conn:
            rows = conn.exec_driver_sql("SELECT user_name, key, value FROM bw_ui_user_preferences").fetchall()
    finally:
        engine.dispose()

    assert "bw_ui_user_preferences" in tables
    assert "bw_ui_user_columns_preferences" not in tables, "the old table survived; the rename was a copy, not a rename"
    assert rows == [("admin", "bans", '{"2": true}')], "the saved preference did not survive the upgrade"


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
