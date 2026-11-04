"""The 1.6.15~rc2 upgrade widens each ``method`` ENUM with ``api`` and keeps its labels, default and rows.

#4095 reported a crash on installations whose ``method`` columns are VARCHAR (pinned on SQLite in
``test_issue_4095_alembic_varchar_method_upgrade.py``). The ENUM branch is the one real MariaDB and MySQL
installations take: it reads the column back with the inspector and issues ``op.alter_column`` with a new
ENUM. The test builds pre-``api`` ENUM columns on a real server, runs the migration files and reads the
column definition back. On MariaDB both migration files run (the MySQL file's body is the same); on MySQL
only the MySQL file runs. Runs only with ``--db-engines mariadb`` and/or ``mysql``.

Refs: #4095.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.pool import NullPool

from fixtures.db_factory import resolve_uri
from fixtures.engines import _with_driver, reset_schema
from model import Base

ALEMBIC = Path(__file__).resolve().parents[3] / "src" / "common" / "db" / "alembic"
MIGRATIONS = {
    "mariadb": ALEMBIC / "mariadb_versions" / "d10f1615a003_upgrade_to_version_1_6_15_rc2.py",
    "mysql": ALEMBIC / "mysql_versions" / "d10f1615a002_upgrade_to_version_1_6_15_rc2.py",
}
METHOD_TABLES = ("bw_custom_configs", "bw_global_values", "bw_instances", "bw_plugins", "bw_services", "bw_services_settings", "bw_ui_users")
DEFAULT_TABLES = ("bw_plugins", "bw_ui_users")
OLD_LABELS = ["ui", "scheduler", "autoconf", "manual", "wizard"]


def _load(path):
    spec = spec_from_file_location(f"migration_{path.stem}", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def connection(db_engine, tmp_path):
    if db_engine not in ("mariadb", "mysql"):
        pytest.skip("the ENUM branch needs a real MariaDB or MySQL")
    uri = resolve_uri(db_engine, tmp_path)
    engine = sa.create_engine(_with_driver(uri), poolclass=NullPool)
    Base.metadata.drop_all(engine)
    labels = ", ".join(f"'{label}'" for label in OLD_LABELS)
    with engine.begin() as connection:
        for table in METHOD_TABLES:
            default = " DEFAULT 'manual'" if table in DEFAULT_TABLES else ""
            extra = ", totp_secret VARCHAR(64)" if table == "bw_ui_users" else ""
            connection.execute(sa.text(f"CREATE TABLE {table} (id INT PRIMARY KEY, method ENUM({labels}) NOT NULL{default}{extra})"))
            connection.execute(sa.text(f"INSERT INTO {table} (id, method) VALUES (1, 'scheduler')"))
        connection.execute(sa.text("CREATE TABLE bw_metadata (id INT PRIMARY KEY, version VARCHAR(32), last_pro_check TIMESTAMP NULL)"))
        connection.execute(sa.text("INSERT INTO bw_metadata (id, version, last_pro_check) VALUES (1, '1.6.15~rc1', '2026-01-01 00:00:00')"))
    try:
        with engine.begin() as connection:
            yield connection
    finally:
        engine.dispose()
        reset_schema(uri)


@pytest.mark.parametrize("engine", sorted(MIGRATIONS))
def test_enum_method_columns_gain_api_and_keep_labels_default_and_rows(connection, engine, db_engine):
    if db_engine == "mysql" and engine != "mysql":
        pytest.skip("the MariaDB migration file targets MariaDB servers")
    migration = _load(MIGRATIONS[engine])
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()

    inspector = sa.inspect(connection)
    for table in METHOD_TABLES:
        method = next(column for column in inspector.get_columns(table) if column["name"] == "method")
        assert isinstance(method["type"], sa.Enum), table
        assert list(method["type"].enums) == ["api", *OLD_LABELS], table
        assert method["nullable"] is False, table
        assert (method["default"] is not None) == (table in DEFAULT_TABLES), table
        assert connection.execute(sa.text(f"SELECT method FROM {table} WHERE id = 1")).scalar() == "scheduler", table
        connection.execute(sa.text(f"UPDATE {table} SET method = 'api' WHERE id = 1"))
        assert connection.execute(sa.text(f"SELECT method FROM {table} WHERE id = 1")).scalar() == "api", table
    assert connection.execute(sa.text("SELECT version FROM bw_metadata WHERE id = 1")).scalar() == "1.6.15~rc2"
