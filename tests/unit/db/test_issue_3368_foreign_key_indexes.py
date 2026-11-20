"""Hot foreign-key and status columns had no index, so common lookups scanned whole tables.

On MySQL and MariaDB the slow log filled with full table scans on the jobs, settings and sessions tables. 1.6.10
added a single-column index on each of 18 columns, in the model for fresh installs and in a migration for
upgraded ones. The expected list is written out here rather than read from the model, so dropping an index
from the model (and its migration) is caught; the existing schema-parity tests only compare the two against
each other.

Refs: #3368.
"""

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

INDEXED_COLUMNS = [
    ("bw_plugins", "config_changed"),
    ("bw_settings", "plugin_id"),
    ("bw_selects", "setting_id"),
    ("bw_multiselects", "setting_id"),
    ("bw_services", "is_draft"),
    ("bw_services_settings", "setting_id"),
    ("bw_jobs", "plugin_id"),
    ("bw_jobs_cache", "job_name"),
    ("bw_jobs_cache", "service_id"),
    ("bw_jobs_runs", "job_name"),
    ("bw_templates", "plugin_id"),
    ("bw_template_settings", "setting_id"),
    ("bw_ui_users", "admin"),
    ("bw_ui_user_sessions", "user_name"),
    ("bw_ui_user_recovery_codes", "user_name"),
    ("bw_ui_roles_users", "role_name"),
    ("bw_ui_roles_permissions", "permission_name"),
    ("bw_api_user_permissions", "api_user"),
]

SQLITE_MIGRATION = Path(__file__).resolve().parents[3] / "src/common/db/alembic/sqlite_versions/4d48b391ee8c_upgrade_to_version_1_6_10_rc6.py"


def _leading_columns(connection, table):
    return {index["column_names"][0] for index in sa.inspect(connection).get_indexes(table) if index["column_names"]}


def test_a_fresh_database_indexes_every_hot_column(db):
    with db.sql_engine.connect() as connection:
        missing = [(table, column) for table, column in INDEXED_COLUMNS if column not in _leading_columns(connection, table)]

    assert missing == []


def test_the_sqlite_upgrade_adds_every_missing_index_and_can_run_twice(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'upgrade.sqlite3'}")
    spec = spec_from_file_location("sqlite_rc6_upgrade", SQLITE_MIGRATION)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    with engine.begin() as connection:
        for table in sorted({table for table, _ in INDEXED_COLUMNS}):
            columns = ", ".join(f'"{column}" TEXT' for t, column in INDEXED_COLUMNS if t == table)
            connection.execute(sa.text(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY, {columns})'))
        connection.execute(sa.text("CREATE TABLE bw_metadata (id INTEGER PRIMARY KEY, version VARCHAR(32))"))
        connection.execute(sa.text("INSERT INTO bw_metadata (id, version) VALUES (1, '1.6.9')"))

        for _ in range(2):
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()

        missing = [(table, column) for table, column in INDEXED_COLUMNS if column not in _leading_columns(connection, table)]
        version = connection.execute(sa.text("SELECT version FROM bw_metadata WHERE id = 1")).scalar()

    engine.dispose()
    assert missing == []
    assert version == "1.6.10~rc6"
