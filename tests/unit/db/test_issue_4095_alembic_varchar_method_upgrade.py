"""The 1.6.15~rc2 upgrade crashed on installations whose ``method`` columns are plain VARCHAR.

The migration widened each ``method`` enum with ``column["type"].enums`` and raised ``AttributeError`` when
a database had stored the column as a string (older installations and some MariaDB/MySQL setups), which
stopped the scheduler from starting after the upgrade. The test runs the real migration files for MariaDB
and MySQL on a database whose ``method`` columns are VARCHAR: a column wide enough for every method value is
left alone with a warning and the rest of the upgrade completes, a column too narrow stops the upgrade with an
explicit message.

Refs: #4095.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

ALEMBIC = Path(__file__).resolve().parents[3] / "src" / "common" / "db" / "alembic"
MIGRATIONS = {
    "mariadb": ALEMBIC / "mariadb_versions" / "d10f1615a003_upgrade_to_version_1_6_15_rc2.py",
    "mysql": ALEMBIC / "mysql_versions" / "d10f1615a002_upgrade_to_version_1_6_15_rc2.py",
}
METHOD_TABLES = ("bw_custom_configs", "bw_global_values", "bw_instances", "bw_plugins", "bw_services", "bw_services_settings", "bw_ui_users")


def _load(path):
    spec = spec_from_file_location(f"migration_{path.stem}", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_schema(connection, method_type):
    for table in METHOD_TABLES:
        extra = ", totp_secret VARCHAR(64)" if table == "bw_ui_users" else ""
        connection.execute(sa.text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, method {method_type} NOT NULL DEFAULT 'manual'{extra})"))
    connection.execute(sa.text("CREATE TABLE bw_metadata (id INTEGER PRIMARY KEY, version VARCHAR(32), last_pro_check TIMESTAMP)"))
    connection.execute(sa.text("INSERT INTO bw_metadata (id, version, last_pro_check) VALUES (1, '1.6.15~rc1', '2026-01-01 00:00:00')"))
    connection.execute(sa.text("INSERT INTO bw_ui_users (id, method, totp_secret) VALUES (1, 'ui', 'SECRET')"))


def _upgrade(connection, path):
    migration = _load(path)
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()


@pytest.fixture
def connection(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'upgrade.sqlite3'}")
    with engine.begin() as connection:
        yield connection
    engine.dispose()


@pytest.mark.parametrize("engine", sorted(MIGRATIONS))
def test_varchar_method_columns_wide_enough_are_kept_and_the_upgrade_completes(connection, capsys, engine):
    _create_schema(connection, "VARCHAR(20)")

    _upgrade(connection, MIGRATIONS[engine])

    inspector = sa.inspect(connection)
    for table in METHOD_TABLES:
        method = next(column for column in inspector.get_columns(table) if column["name"] == "method")
        assert str(method["type"]) == "VARCHAR(20)"
    assert "totp_last_counter" in {column["name"] for column in inspector.get_columns("bw_ui_users")}
    assert connection.execute(sa.text("SELECT version FROM bw_metadata WHERE id = 1")).scalar() == "1.6.15~rc2"
    assert connection.execute(sa.text("SELECT totp_last_counter FROM bw_ui_users WHERE id = 1")).scalar() > 0
    assert capsys.readouterr().err.count("it already supports all method values") == len(METHOD_TABLES)


@pytest.mark.parametrize("engine", sorted(MIGRATIONS))
def test_varchar_method_column_too_narrow_stops_the_upgrade_with_an_explicit_error(connection, engine):
    _create_schema(connection, "VARCHAR(5)")

    with pytest.raises(RuntimeError, match=r"Cannot upgrade bw_custom_configs\.method: unsupported type VARCHAR\(5\)"):
        _upgrade(connection, MIGRATIONS[engine])
