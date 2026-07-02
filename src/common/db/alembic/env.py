import re
from logging.config import fileConfig
from os import environ
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from alembic.autogenerate import renderers
from alembic.operations.ops import AlterColumnOp, CreateIndexOp, CreateUniqueConstraintOp, DropConstraintOp, DropIndexOp, ExecuteSQLOp, OpContainer
from alembic.script import ScriptDirectory

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from model import Base

target_metadata = Base.metadata

# Override sqlalchemy.url with DATABASE_URI environment variable if present
if "DATABASE_URI" in environ:
    config.set_main_option("sqlalchemy.url", environ["DATABASE_URI"].replace("%", "%%"))

    # Extract the database type from the URI and set version_locations accordingly
    database_type = environ["DATABASE_URI"].split(":")[0].split("+")[0]
    config.set_main_option("version_locations", f"{database_type}_versions")


# Pattern matching the canonical "Upgrade to version X.Y.Z" message used by
# misc/migration/entrypoint.sh so the version-bump SQL gets auto-injected.
_VERSION_MESSAGE_RE = re.compile(r"Upgrade to version (\S+)")

# (table, column) pairs whose alter_column ops are spurious autogenerate noise:
# - MySQL/MariaDB: LONGBLOB <-> LargeBinary(2**32-1) round-trip, INT(11)
#   display-width, pre-applied nullability
# - PostgreSQL: TIMESTAMP <-> DateTime(timezone=True) on columns created
#   pre-v1.6 as sa.DateTime(); MariaDB/MySQL/SQLite cannot store timezones so
#   leaving PG as TIMESTAMP keeps schemas symmetric across backends
_IGNORED_ALTER_COLUMNS = frozenset(
    {
        ("bw_custom_configs", "data"),
        ("bw_jobs_cache", "data"),
        ("bw_plugin_pages", "data"),
        ("bw_plugins", "data"),
        ("bw_template_custom_configs", "step_id"),
        ("bw_template_custom_configs", "data"),
        ("bw_metadata", "pro_expire"),
        ("bw_metadata", "last_pro_check"),
        ("bw_metadata", "last_custom_configs_change"),
        ("bw_metadata", "last_external_plugins_change"),
        ("bw_metadata", "last_pro_plugins_change"),
        ("bw_metadata", "last_instances_change"),
        ("bw_plugins", "last_config_change"),
    }
)

# (table, index_name) pairs whose create/drop_index ops are spurious. Each
# entry is a redundant named index that mirrors the PK and is bound to FKs
# from child tables on MySQL/MariaDB — dropping it triggers errno 150.
_IGNORED_INDEXES = frozenset(
    {
        ("bw_ui_users", "username"),
        ("bw_settings", "id"),
    }
)

# (table, constraint_name) pairs whose create_unique_constraint/drop_constraint
# ops are spurious. PostgreSQL emits a separate `<table>_<col>_key` unique
# constraint for each column that was promoted to PK or already had a unique
# index — the equivalent redundancy on MySQL/MariaDB is filtered via
# _IGNORED_INDEXES.
_IGNORED_CONSTRAINTS = frozenset(
    {
        ("bw_settings", "bw_settings_id_key"),
        ("bw_ui_users", "bw_ui_users_username_key"),
    }
)


class _VersionUpdateOp(ExecuteSQLOp):
    """ExecuteSQLOp variant that renders with a leading explanatory comment."""

    def __init__(self, sqltext: str, comment: str) -> None:
        super().__init__(sqltext)
        self.comment = comment


@renderers.dispatch_for(_VersionUpdateOp)
def _render_version_update(_autogen_context, op: _VersionUpdateOp):
    return [op.comment, f"op.execute({op.sqltext!r})"]


def _extract_version(text):
    if not text:
        return None
    match = _VERSION_MESSAGE_RE.search(text)
    return match.group(1) if match else None


def _strip_ignored_ops(container):
    if container is None:
        return
    kept = []
    for op in container.ops:
        if isinstance(op, AlterColumnOp) and (op.table_name, op.column_name) in _IGNORED_ALTER_COLUMNS:
            continue
        if isinstance(op, (DropIndexOp, CreateIndexOp)) and (op.table_name, op.index_name) in _IGNORED_INDEXES:
            continue
        if isinstance(op, (DropConstraintOp, CreateUniqueConstraintOp)) and (op.table_name, op.constraint_name) in _IGNORED_CONSTRAINTS:
            continue
        if isinstance(op, OpContainer):
            _strip_ignored_ops(op)
            if not op.ops:
                continue
        kept.append(op)
    container.ops = kept


def _previous_version():
    # Read the current head revision's docstring and recover its version label so
    # the generated downgrade() can roll bw_metadata.version back to it.
    try:
        script_directory = ScriptDirectory.from_config(config)
        head = script_directory.get_current_head()
        if not head:
            return None
        revision = script_directory.get_revision(head)
        return _extract_version(revision.doc) or _extract_version(revision.longdoc)
    except Exception:
        return None


def process_revision_directives(context_, revision, directives):
    if not directives:
        return
    for script in directives:
        _strip_ignored_ops(script.upgrade_ops)
        _strip_ignored_ops(script.downgrade_ops)
        new_version = _extract_version(getattr(script, "message", None))
        if not new_version:
            continue
        upgrade_sql = f"UPDATE bw_metadata SET version = '{new_version}' WHERE id = 1"
        if script.upgrade_ops is not None:
            script.upgrade_ops.ops.insert(0, _VersionUpdateOp(upgrade_sql, "# Update the version in bw_metadata"))
            # Clear last_pro_check so the next scheduler run re-fetches version-specific Pro plugins.
            # Upgrade only (not downgrade).
            pro_recheck_sql = "UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1"
            script.upgrade_ops.ops.insert(1, _VersionUpdateOp(pro_recheck_sql, "# Force a Pro plugins re-check after the version change"))
        old_version = _previous_version()
        if old_version and script.downgrade_ops is not None:
            downgrade_sql = f"UPDATE bw_metadata SET version = '{old_version}' WHERE id = 1"
            script.downgrade_ops.ops.insert(0, _VersionUpdateOp(downgrade_sql, "# Revert the version in bw_metadata"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
