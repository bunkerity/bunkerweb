"""The saver must recognise a pre-migration database from the raw tables, not from the 1.7 ORM model.

Linux package upgrade: the old scheduler is still running while dpkg swaps the files, and its SIGHUP
handler launches the newly installed save_config.py against the database of the previous release. The
1.7 `Metadata` model has columns a 1.6.x `bw_metadata` table lacks, so `Database.get_metadata()` fails on
that table, swallows the error and reports a database that was never initialized. A guard keyed on it
never fires, the saver runs `init_tables` on the unmigrated schema and the migration that follows dies on
`table bw_bans already exists`.

The database below is built from the 1.6.17 `bw_metadata` columns (`git show v1.6.17:src/common/db/model.py`),
not from the current model: a test built from the current model cannot see this defect. The saver runs for
real in a child process, with VERSION faked the way the package swap changes it.
"""

import os
import runpy
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table, Text, inspect, insert, text
from sqlalchemy.exc import OperationalError

import common_utils
import Database
import logger
import save_config
from model import Base

REPO = Path(__file__).resolve().parents[3]
SCRIPT = Path(os.environ.get("SAVE_CONFIG_PY", REPO / "src" / "common" / "gen" / "save_config.py"))
INSTALLED = "1.7.0~alpha"
OLD_VERSION = "1.6.17"
GUARD_LINE = "migration has not run"

RUNNER = textwrap.dedent("""
    import runpy, sys
    repo, script, version, plugins, pro_plugins, variables, *flags = sys.argv[1:]
    for sub in ("db", "api", "utils", "gen"):
        sys.path.insert(0, f"{repo}/src/common/{sub}")
    import common_utils
    common_utils.get_version = lambda: version
    sys.argv = [
        script,
        "--settings", f"{repo}/src/common/settings.json",
        "--core", f"{repo}/src/common/core",
        "--plugins", plugins,
        "--pro-plugins", pro_plugins,
        "--variables", variables,
        *flags,
    ]
    runpy.run_path(script, run_name="__main__")
    """)


def _old_metadata_table(metadata: MetaData) -> Table:
    """bw_metadata exactly as 1.6.17 shipped it: no certificates_changed, no certificate keyring."""
    return Table(
        "bw_metadata",
        metadata,
        Column("id", Integer, primary_key=True, default=1),
        Column("is_initialized", Boolean, nullable=False),
        Column("is_pro", Boolean, default=False, nullable=False),
        Column("pro_license", String(128), default="", nullable=True),
        Column("pro_expire", DateTime(timezone=True), nullable=True),
        Column("pro_status", String(16), default="invalid", nullable=False),
        Column("pro_services", Integer, default=0, nullable=False),
        Column("non_draft_services", Integer, default=0, nullable=False),
        Column("pro_overlapped", Boolean, default=False, nullable=False),
        Column("last_pro_check", DateTime(timezone=True), nullable=True),
        Column("first_config_saved", Boolean, nullable=False),
        Column("autoconf_loaded", Boolean, default=False, nullable=True),
        Column("scheduler_first_start", Boolean, nullable=True),
        Column("custom_configs_changed", Boolean, default=False, nullable=True),
        Column("last_custom_configs_change", DateTime(timezone=True), nullable=True),
        Column("external_plugins_changed", Boolean, default=False, nullable=True),
        Column("last_external_plugins_change", DateTime(timezone=True), nullable=True),
        Column("pro_plugins_changed", Boolean, default=False, nullable=True),
        Column("last_pro_plugins_change", DateTime(timezone=True), nullable=True),
        Column("instances_changed", Boolean, default=False, nullable=True),
        Column("last_instances_change", DateTime(timezone=True), nullable=True),
        Column("reload_ui_plugins", Boolean, default=False, nullable=True),
        Column("force_pro_update", Boolean, default=False, nullable=True),
        Column("failover", Boolean, default=None, nullable=True),
        Column("failover_message", Text, nullable=True, default=""),
        Column("integration", String(32), default="Unknown", nullable=False),
        Column("version", String(32), default=OLD_VERSION, nullable=False),
    )


def _stand_in_table(metadata: MetaData) -> Table:
    """One more table that already holds data, so "a table was created" and "a row was written" are observable."""
    return Table("bw_plugins", metadata, Column("id", String(64), primary_key=True), Column("name", String(128), nullable=False))


def _build_old_database(db, *, initialized=True, version=OLD_VERSION):
    """Replace the 1.7 schema the `db` fixture built by a 1.6.17-shaped one holding a metadata row and a plugin."""
    engine = db.sql_engine
    Base.metadata.drop_all(engine)
    metadata = MetaData()
    old_metadata, plugins = _old_metadata_table(metadata), _stand_in_table(metadata)
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(insert(old_metadata).values(is_initialized=initialized, first_config_saved=True, integration="Linux", version=version))
        conn.execute(insert(plugins).values(id="seeded", name="Seeded plugin"))


def _snapshot(db):
    """Everything an unwanted write could change: table names, their columns and every row."""
    engine = db.sql_engine
    inspector = inspect(engine)
    state = {}
    for table in sorted(inspector.get_table_names()):
        columns = sorted(column["name"] for column in inspector.get_columns(table))
        with engine.connect() as conn:
            rows = sorted(map(tuple, conn.execute(text(f"SELECT * FROM {table}")).all()), key=repr)  # nosec B608: table names come from the inspector
        state[table] = (columns, rows)
    return state


@pytest.fixture
def run_saver(db, tmp_path):
    (tmp_path / "plugins").mkdir()
    (tmp_path / "pro").mkdir()
    runner = tmp_path / "runner.py"
    runner.write_text(RUNNER, encoding="utf-8")
    variables = tmp_path / "variables.env"
    variables.write_text("", encoding="utf-8")
    child_env = {"PATH": os.environ["PATH"], "DATABASE_URI": db.database_uri, "LOG_LEVEL": "info", "HOME": str(tmp_path)}

    def run(*flags, version=INSTALLED):
        return subprocess.run(
            [sys.executable, "-I", str(runner), str(REPO), str(SCRIPT), version, str(tmp_path / "plugins"), str(tmp_path / "pro"), str(variables), *flags],
            env=child_env,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=300,
        )

    return run


# --- the defect: an initialized database of the previous release ------------------------------------------------


@pytest.mark.parametrize("flags", [(), ("--init",)], ids=["sighup-save", "pre-init"])
def test_initialized_old_schema_is_refused_and_left_untouched(db, run_saver, flags):
    _build_old_database(db)
    before = _snapshot(db)

    result = run_saver(*flags)

    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert GUARD_LINE in output, output
    assert _snapshot(db) == before, "the saver wrote to a database whose migration has not run"


# --- fresh install, uninitialized and migrated databases keep their behaviour ------------------------------------


def test_database_without_a_metadata_table_is_initialized(db, run_saver):
    Base.metadata.drop_all(db.sql_engine)
    assert inspect(db.sql_engine).get_table_names() == []

    result = run_saver("--init")

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "Database not initialized, initializing" in output, output
    assert GUARD_LINE not in output
    with db.sql_engine.connect() as conn:
        assert conn.execute(text("SELECT version FROM bw_metadata WHERE id = 1")).scalar_one() == INSTALLED


def test_old_schema_not_yet_marked_initialized_is_not_refused(db, run_saver):
    # An old database whose first save never completed has nothing to protect and no pending state to wait for.
    _build_old_database(db, initialized=False)

    result = run_saver("--init")

    assert GUARD_LINE not in result.stdout + result.stderr


def test_migrated_database_saves_as_before(db, run_saver):
    assert db.initialize_db(INSTALLED, "Linux") == ""

    result = run_saver("--init")

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "Database is already initialized, checking for changes" in output, output
    assert GUARD_LINE not in output


# --- a read error must never look like an empty database ---------------------------------------------------------


def test_unreadable_metadata_table_fails_closed(db, run_saver):
    # bw_metadata exists but cannot be read the way the saver needs: this is not "table missing".
    engine = db.sql_engine
    Base.metadata.drop_all(engine)
    metadata = MetaData()
    Table("bw_metadata", metadata, Column("id", Integer, primary_key=True), Column("version", String(32), nullable=False))
    _stand_in_table(metadata)
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO bw_metadata (id, version) VALUES (1, :version)"), {"version": OLD_VERSION})
        conn.execute(text("INSERT INTO bw_plugins (id, name) VALUES ('seeded', 'Seeded plugin')"))
    before = _snapshot(db)

    result = run_saver()

    assert result.returncode != 0, result.stdout + result.stderr
    assert _snapshot(db) == before, "an unreadable metadata table fell through to table creation"


def test_lost_connection_during_the_state_read_never_reaches_init_tables(db, tmp_path, monkeypatch):
    assert db.initialize_db(OLD_VERSION, "Linux") == ""
    monkeypatch.setattr(common_utils, "get_version", lambda: INSTALLED)
    monkeypatch.setattr(common_utils, "get_integration", lambda: "Linux")
    monkeypatch.setattr(logger, "getLogger", lambda *args: Mock())
    broken_engine = Mock()
    broken_engine.connect.side_effect = OperationalError("SELECT 1", {}, Exception("server has gone away"))
    boundary = Mock(wraps=db)
    boundary.database_uri = db.database_uri
    boundary.sql_engine = broken_engine
    # what get_metadata() answers when its own read fails: the error is swallowed and the defaults come back
    boundary.get_metadata.return_value = {"is_initialized": False, "default": True, "version": INSTALLED}
    monkeypatch.setattr(Database, "Database", Mock(return_value=boundary))
    argv = [save_config.__file__, "--settings", str(REPO / "src/common/settings.json"), "--core", str(REPO / "src/common/core")]
    for name in ("plugins", "pro-plugins"):
        (tmp_path / name).mkdir()
        argv.extend(["--" + name, str(tmp_path / name)])
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as error:
        runpy.run_path(save_config.__file__, run_name="__main__")

    assert error.value.code not in (0, None)
    boundary.init_tables.assert_not_called()
    boundary.initialize_db.assert_not_called()
    boundary.save_config.assert_not_called()


def test_get_metadata_still_reports_defaults_on_the_old_schema(db):
    # Pinned on purpose: the scheduler loop, the API start-up wait and the worker rely on this, the saver must not.
    _build_old_database(db)

    metadata = db.get_metadata()

    assert metadata["default"] is True
    assert metadata["is_initialized"] is False
