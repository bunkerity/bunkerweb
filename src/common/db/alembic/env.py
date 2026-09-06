import re
from logging.config import fileConfig
from os import environ
from sqlalchemy import Column
from sqlalchemy import DefaultClause
from sqlalchemy import Enum as SAEnum
from sqlalchemy import engine_from_config
from sqlalchemy import inspect
from sqlalchemy import pool
from sqlalchemy import text

from alembic import context
from alembic.autogenerate import renderers
from alembic.operations.ops import (
    AddColumnOp,
    AlterColumnOp,
    CreateIndexOp,
    CreateTableOp,
    CreateUniqueConstraintOp,
    DropConstraintOp,
    DropIndexOp,
    DropTableOp,
    ExecuteSQLOp,
    ModifyTableOps,
    OpContainer,
    RenameTableOp,
)
from alembic.script import ScriptDirectory

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
#
# `disable_existing_loggers=False` is deliberate. The default (True) disables every logger not
# named in alembic.ini -- harmless when alembic runs as its own process (entrypoint.sh, the linux
# scheduler script), but this module is also imported in-process by the migration unit tests, and
# there it silently kills BunkerWeb's already-created loggers for the rest of the interpreter.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

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


# Tables that were RENAMED between two releases, with the columns renamed along with them.
#
# Autogenerate compares two schemas and has no concept of identity between them, so a rename comes
# out as `drop_table(old)` + `create_table(new)`: structurally correct, and it silently discards
# every row on the way through. `bw_ui_user_columns_preferences` -> `bw_ui_user_preferences`
# (commit 720e54954) is one table of per-user column visibility, so the drop+create shape would
# reset every operator's saved table layouts on upgrade while reporting success.
#
# The knowledge that these two tables are the same table cannot be derived from either schema; it
# has to be written down. This is where, so that a regeneration through misc/migration/create.sh
# reproduces the correct revision instead of depending on someone remembering to hand-fix it.
_RENAMED_TABLES = {
    "bw_ui_user_columns_preferences": {
        "to": "bw_ui_user_preferences",
        # old column name -> new column name
        "columns": {"table_name": "key", "columns": "value"},
    },
}


# (table, column) pairs whose server default exists only in an *upgraded* database: some revision
# wrote it, `model.py` never declared it, so a freshly installed database has no default there and
# the two shapes have differed ever since. `bw_ui_users.method` and `bw_plugins.method` were the
# first two found (`mariadb_versions/d4d8df48d14d`, 1.5.5); the rest of the class came out of the
# survey below. The stored value is unaffected either way -- SQLAlchemy always sends the column,
# which is why nothing noticed.
#
# `_drop_server_defaults_the_model_does_not_declare` converges this class wherever autogenerate
# produced an `alter_column` to hang the drop on, which is a minority of it: SQLite mostly sees no
# change at all and PostgreSQL runs with `compare_server_default` off, so on those two engines
# autogenerate emits nothing to modify and the drift survives every regeneration. These pairs are
# therefore emitted outright, and *only* these -- a blanket "every column whose reflected default the
# model does not declare" sweep would also strip PostgreSQL's `nextval('..._id_seq')` off every
# serial primary key, so the class is written down rather than computed.
#
# The list is the output of `.cache/results-2026-09-02-wave12/survey-server-defaults-L-G.py`: every
# revision's `upgrade()` AST-folded in chain order, per engine, intersected with the columns
# `model.py` still declares without a `server_default` of its own. It has to be derived that way and
# not from `test_upgrade_schema_parity`, which cannot see this class at all: that test builds its
# "upgraded" side from `model.py` at the v1.6.13 *tag*, so a default only an older revision ever
# wrote is absent from both of its sides and the comparison is green while the drift is real.
#
# Not every engine carries every pair -- `bw_selects.value` is SQLite-only, `bw_instances.https_port`
# is on the other three -- and nothing here says which. The live database decides, per engine,
# through `_reflected_server_default`; that gate is also what stops the op being re-emitted forever
# once the drop has shipped and the next generation baseline no longer has the default.
#
# The downgrade restores the default the database really had, read back off it rather than named
# here. The spelling is engine-specific and not interchangeable: `sa.false()` compiles to `0` on
# MySQL and `false` on PostgreSQL, where `SET DEFAULT 0` on a boolean column is a type error, and
# `bw_templates.creation_date` is `CURRENT_TIMESTAMP` on MySQL against `timezone('utc', now())` on
# PostgreSQL, which are different instants for a column with no timezone. One literal per pair could
# not be right on all four, and a per-engine table of 35 literals would be 105 unverifiable strings.
#
# Sorted on use, not merely written sorted: this is a set, and the op order it produces has to be
# stable or two regenerations of the same schema differ.
#
# Adding a pair that is also in `_IGNORED_ALTER_COLUMNS` makes the two filters contradict each other
# -- the strip runs first and removes autogenerate's op, then this pass sees none and appends a fresh
# one. The assertion below is that check, so it cannot rot silently.
_UNDECLARED_SERVER_DEFAULTS = frozenset(
    {
        ("bw_global_values", "suffix"),
        ("bw_global_values", "value"),
        ("bw_instances", "creation_date"),
        ("bw_instances", "https_port"),
        ("bw_instances", "last_seen"),
        ("bw_instances", "listen_https"),
        ("bw_jobs", "run_async"),
        ("bw_jobs_runs", "end_date"),
        ("bw_jobs_runs", "start_date"),
        ("bw_jobs_runs", "success"),
        ("bw_metadata", "is_pro"),
        ("bw_metadata", "non_draft_services"),
        ("bw_metadata", "pro_overlapped"),
        ("bw_metadata", "pro_services"),
        ("bw_metadata", "pro_status"),
        ("bw_plugins", "method"),
        ("bw_plugins", "type"),
        ("bw_selects", "order"),
        ("bw_selects", "value"),
        ("bw_services", "is_draft"),
        ("bw_services_settings", "suffix"),
        ("bw_services_settings", "value"),
        ("bw_template_settings", "default"),
        ("bw_template_settings", "order"),
        ("bw_template_settings", "suffix"),
        ("bw_templates", "creation_date"),
        ("bw_templates", "last_update"),
        ("bw_templates", "method"),
        ("bw_ui_user_sessions", "user_agent"),
        ("bw_ui_users", "admin"),
        ("bw_ui_users", "creation_date"),
        ("bw_ui_users", "language"),
        ("bw_ui_users", "method"),
        ("bw_ui_users", "theme"),
        ("bw_ui_users", "update_date"),
    }
)

_CONTRADICTORY = _UNDECLARED_SERVER_DEFAULTS & _IGNORED_ALTER_COLUMNS
assert not _CONTRADICTORY, f"a column cannot be both stripped and converged: {sorted(_CONTRADICTORY)}"


class _VersionUpdateOp(ExecuteSQLOp):
    """ExecuteSQLOp variant that renders with a leading explanatory comment."""

    def __init__(self, sqltext: str, comment: str) -> None:
        super().__init__(sqltext)
        self.comment = comment


@renderers.dispatch_for(_VersionUpdateOp)
def _render_version_update(_autogen_context, op: _VersionUpdateOp):
    return [op.comment, f"op.execute({op.sqltext!r})"]


# `replace=True` because the dispatch registry is global and this module is imported once per
# alembic invocation -- fine in `entrypoint.sh`, where each invocation is its own process, but the
# migration tests load it repeatedly in one interpreter and the second registration would raise
# `key already exists`. The `_VersionUpdateOp` renderer above escapes this only because its target
# class is rebuilt on every import; `RenameTableOp` is alembic's own and is not.
@renderers.dispatch_for(RenameTableOp, replace=True)
def _render_rename_table(_autogen_context, op: RenameTableOp):
    """Alembic can *run* `op.rename_table` but ships no autogenerate renderer for it -- nothing it
    generates on its own ever produces one, so writing the op into a revision raises
    `ValueError: no dispatch function for object`. `_rewrite_renamed_tables` produces exactly this
    op, so this is the other half of that."""
    return f"op.rename_table({op.table_name!r}, {op.new_table_name!r})"


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


def _find_op(container, op_type, table_name):
    for index, op in enumerate(container.ops):
        if isinstance(op, op_type) and op.table_name == table_name:
            return index, op
    return None, None


def _column_spec(create_op, column_name):
    """The type and nullability of one column of a CreateTableOp.

    `alter_column(new_column_name=...)` needs both on MySQL/MariaDB, where a rename is a `CHANGE`
    that restates the whole column definition -- omitting them there rewrites the column as a
    nullable something-else.
    """
    for column in create_op.columns:
        if getattr(column, "name", None) == column_name:
            return column.type, column.nullable
    raise RuntimeError(f"{create_op.table_name}.{column_name} is not in the generated create_table; _RENAMED_TABLES is stale")


def _assert_only_the_listed_columns_differ(drop_op, create_op, columns):
    """Refuse the rewrite unless the two tables really are the same table under two names.

    The rewrite below throws the `create_table` away and keeps only `rename_table` plus the renames
    in `_RENAMED_TABLES`, so anything the create carried that the rename does not reproduce is
    silently lost -- it reaches a fresh install through the model and never reaches an upgraded one.
    That is safe exactly while the column sets match once the listed renames are applied, and
    nothing else makes it so: add a column to the new table, regenerate, and the loss is silent.
    So check it here instead, and fail the generation the way `_column_spec` already does.
    """
    old_columns = {column.name for column in drop_op.to_table().columns}
    # `create_op.columns` mixes Columns and Constraints, and a named constraint has a `.name` too.
    new_columns = {column.name for column in create_op.columns if isinstance(column, Column)}

    renamed = old_columns - set(columns) | {columns[name] for name in old_columns & set(columns)}
    if renamed != new_columns:
        raise RuntimeError(
            f"{drop_op.table_name} and {create_op.table_name} differ by more than the renames in _RENAMED_TABLES: "
            f"only in the new table {sorted(new_columns - renamed)}, only in the old one {sorted(renamed - new_columns)}"
        )


def _rewrite_renamed_tables(container, reverse=False):
    """Turn each drop_table+create_table pair named in `_RENAMED_TABLES` into a real rename.

    `reverse` describes the downgrade direction, where the same pair appears the other way round.
    Nothing happens when the pair is absent -- once the rename has shipped in a revision, later
    autogenerate runs see two schemas that already agree and emit neither op.
    """
    if container is None:
        return
    for old_name, spec in _RENAMED_TABLES.items():
        new_name = spec["to"]
        created_name, dropped_name = (old_name, new_name) if reverse else (new_name, old_name)
        columns = {new: old for old, new in spec["columns"].items()} if reverse else dict(spec["columns"])

        _, create_op = _find_op(container, CreateTableOp, created_name)
        drop_index, drop_op = _find_op(container, DropTableOp, dropped_name)

        if create_op is None or drop_index is None:
            # Half a pair is the dangerous shape: a drop with no matching create means the rows are
            # going away for real. Autogenerate cannot tell that from a rename, so refuse rather
            # than emit a revision that quietly deletes a table this map says still exists.
            if drop_index is not None:
                raise RuntimeError(f"autogenerate wants to drop {dropped_name} with no matching create of {created_name}; _RENAMED_TABLES is stale")
            continue

        _assert_only_the_listed_columns_differ(drop_op, create_op, columns)

        replacement = [RenameTableOp(dropped_name, created_name)]
        for from_column, to_column in columns.items():
            column_type, nullable = _column_spec(create_op, to_column)
            replacement.append(AlterColumnOp(created_name, from_column, modify_name=to_column, existing_type=column_type, existing_nullable=nullable))

        # Every *other* op autogenerate emitted about either name is an artefact of believing one
        # table disappears and another appears: on MariaDB it drops `uq_user_columns_preferences`
        # from the old table on the way up and recreates it on the way down. A rename carries the
        # table's indexes and constraints across unchanged, so those are dropped rather than
        # retargeted -- retargeting the drop would delete the unique index the renamed table still
        # has, and replaying the create would collide with it. The two tables differ only by the
        # column names in `_RENAMED_TABLES`, which is what makes that safe.
        rewritten, inserted = [], False
        for op in container.ops:
            if getattr(op, "table_name", None) in (created_name, dropped_name):
                if not inserted:
                    rewritten.extend(replacement)
                    inserted = True
                continue
            rewritten.append(op)
        container.ops = rewritten


def _named_enums(container, into):
    """Every named `Enum` an op container would put in the database, as {type name: [labels]}.

    `alter_column` counts, and used not to. `_render_item` stamps `create_type=False` on *every*
    PostgreSQL enum it renders, including one reached through `modify_type` -- so a
    varchar-to-named-enum `alter_column`, which is what widening a plain string column into an enum
    generates, would render a type with nothing anywhere creating it and the revision would die on
    `type "..." does not exist`. Nothing generates that shape today; the next model change that turns
    a `String` column into an `Enum` does, and it would fail at the operator rather than here.

    `existing_type` is deliberately not read: a type reached only through it is what autogenerate
    reflected off the column, so it is already in the database. The `DO $$ ... duplicate_object`
    block would be a no-op for it, but including it would also resurrect a type on a downgrade path
    that dropped it, and there is no reason to.
    """
    for op in container.ops:
        if isinstance(op, CreateTableOp):
            types = [getattr(column, "type", None) for column in op.columns]
        elif isinstance(op, AddColumnOp):
            types = [getattr(op.column, "type", None)]
        elif isinstance(op, AlterColumnOp):
            types = [op.modify_type]
        else:
            types = []
        for column_type in types:
            if isinstance(column_type, SAEnum) and column_type.name:
                into[column_type.name] = list(column_type.enums)
        if isinstance(op, OpContainer):
            _named_enums(op, into)
    return into


def _postgresql_enum_ops(migration_context, upgrade_ops):
    """The two things PostgreSQL needs that autogenerate does not emit.

    On PostgreSQL an enum is a real `TYPE`, shared by every column that uses it, and that breaks
    autogenerate in both directions:

    1. **`CREATE TYPE` fires again for a type that already exists.** `create_table` renders the
       enum column, and SQLAlchemy emits `CREATE TYPE` before the table -- so the first new table
       carrying an existing enum (`bw_bans.method`, `methods_enum`) kills the whole migration with
       `type "methods_enum" already exists`. `_render_item` renders these with `create_type=False`
       so the table stops trying, and the `DO $$ ... duplicate_object` block below creates the type
       when it is genuinely new. Idempotent either way, so it needs no knowledge of the live DB.
    2. **A label added to an existing enum is invisible.** On MySQL/SQLite an enum renders as a
       VARCHAR whose length changes, so autogenerate sees an `alter_column`; on PostgreSQL the
       reflected type compares equal to itself by name and nothing is emitted. That is exactly how
       `settings_types_enum` lost `size`/`duration` and `api_resource_enum` lost `redirects`,
       `upstreams` and `workflows` in the 1.7.0~beta head that this one replaces. Read out of
       `pg_enum` and emitted as `ALTER TYPE ... ADD VALUE IF NOT EXISTS`, which needs PostgreSQL 12
       or newer to run inside a transaction (the compose pins 18).

    No downgrade counterpart: PostgreSQL cannot remove a value from an enum type at all.
    """
    if migration_context is None or migration_context.dialect.name != "postgresql":
        return []

    used = _named_enums(upgrade_ops, {})
    ops = [
        ExecuteSQLOp(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({', '.join(_sql_literal(label) for label in labels)}); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        )
        for name, labels in sorted(used.items())
    ]

    live = {}
    for typname, label in migration_context.bind.execute(text("SELECT t.typname, e.enumlabel FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid")):
        live.setdefault(typname, set()).add(label)

    declared = {}
    for table in target_metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, SAEnum) and column.type.name:
                declared[column.type.name] = list(column.type.enums)

    for name, labels in sorted(declared.items()):
        if name not in live:
            continue  # not in the database yet; the DO block above creates it with every label
        ops += [ExecuteSQLOp(f"ALTER TYPE {name} ADD VALUE IF NOT EXISTS {_sql_literal(label)}") for label in labels if label not in live[name]]
    return ops


def _sql_literal(value):
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _server_default_text(existing):
    """The SQL text of a reflected server default, whatever wrapper it arrived in.

    Autogenerate hands `existing_server_default` over as a `DefaultClause` on some paths and as the
    bare `TextClause` inside it on others, and `str()` on a `DefaultClause` renders the object, not
    the SQL. Unwrap both, then stringify.
    """
    arg = getattr(existing, "arg", existing)
    return str(getattr(arg, "text", arg))


def _is_a_sequence_default(existing):
    """Whether a reflected server default is a sequence hook rather than drift to converge.

    PostgreSQL renders a serial primary key's generator as `nextval('..._id_seq'::regclass)`, and
    `model.py` declares no `server_default` for those columns -- the sequence is the dialect's own
    doing, not something a revision wrote. The sweep below would therefore read every serial PK as
    undeclared drift and drop its default, leaving a NOT NULL column with no generator: the next
    INSERT that omits the id fails. `_UNDECLARED_SERVER_DEFAULTS` is written down by hand partly to
    avoid exactly this (see its comment), but this pass is not gated on that list, so it needs the
    check itself.
    """
    return "nextval(" in _server_default_text(existing).lower()


def _drop_server_defaults_the_model_does_not_declare(container):
    """Stop an `alter_column` carrying forward a server default that only the database has.

    `bw_ui_users.method` and `bw_plugins.method` were created with `server_default="manual"` back in
    1.5.5 (`mariadb_versions/d4d8df48d14d`), and every `alter_column` since has restated it through
    `existing_server_default`. The model declares only a Python-side `default="manual"`, so a fresh
    install has no server default at all -- an upgraded MySQL/MariaDB database and a freshly
    installed one have differed on those two columns since 1.5.5, and `test_upgrade_schema_parity`
    is the first thing to look. The value is unaffected either way: SQLAlchemy always sends
    `method`, which is why nothing noticed.

    Converging on the model rather than on the database, because the model is what a fresh install
    builds from and what the parity contract compares against. Upgrade direction only -- a downgrade
    is supposed to put the old shape back, server default included.

    Unlike `_drop_undeclared_server_defaults_autogenerate_missed`, this pass is not restricted to
    `_UNDECLARED_SERVER_DEFAULTS`: it fires on *any* `alter_column` autogenerate emitted. That is
    what `_is_a_sequence_default` is for -- see its docstring.
    """
    if container is None:
        return
    declared = {(table.name, column.name): column.server_default for table in target_metadata.tables.values() for column in table.columns}
    for op in container.ops:
        if isinstance(op, OpContainer):
            _drop_server_defaults_the_model_does_not_declare(op)
        elif isinstance(op, AlterColumnOp) and _has_reflected_default(op):
            if declared.get((op.table_name, op.column_name), False) is None and not _is_a_sequence_default(op.existing_server_default):
                op.modify_server_default = None


def _find_alter_column(container, table_name, column_name):
    """The `AlterColumnOp` autogenerate produced for one column, or None.

    Autogenerate nests them one `ModifyTableOps` deep, and `_rewrite_renamed_tables` adds bare ones
    at the top level, so both shapes have to be searched.
    """
    for op in container.ops:
        if isinstance(op, OpContainer):
            found = _find_alter_column(op, table_name, column_name)
            if found is not None:
                return found
        elif isinstance(op, AlterColumnOp) and (op.table_name, op.column_name) == (table_name, column_name):
            return op
    return None


def _reflected_server_default(migration_context, table_name, column_name):
    """The server default the database being generated against still carries there, as SQL text.

    `None` when there is none, when the table does not exist yet, or when there is no bind to ask --
    all three mean "nothing to converge here", which is also what makes the op stop being emitted
    once the drop has shipped and the next generation baseline no longer has the default. Otherwise
    every future head would carry a `DROP DEFAULT` for something already gone.

    The text is what the downgrade restores, so it is read rather than named: the spelling is
    per-engine (`'manual'` on SQLite against `'manual'::methods_enum` on PostgreSQL) and, for the
    boolean and timestamp columns in `_UNDECLARED_SERVER_DEFAULTS`, per-engine in a way that is not
    interchangeable. This is the same round-trip alembic itself does through
    `existing_server_default`, which is reflected text fed back as SQL.
    """
    bind = getattr(migration_context, "bind", None)
    if bind is None:
        return None
    inspector = inspect(bind)
    if not inspector.has_table(table_name):
        return None
    for column in inspector.get_columns(table_name):
        if column["name"] == column_name:
            return column.get("default")
    return None


def _drop_undeclared_server_defaults_autogenerate_missed(migration_context, upgrade_ops, downgrade_ops):
    """The same convergence as above, on the engines where autogenerate emits no op to carry it.

    `_drop_server_defaults_the_model_does_not_declare` can only edit an op that exists. For the pairs
    in `_UNDECLARED_SERVER_DEFAULTS` the op is emitted outright when there is none, so that all four
    engines' upgraded databases agree with a fresh install *on those columns* -- not on every column
    they carry an undeclared default for; see the list's comment for how the class was derived.

    The downgrade puts the default back explicitly, except where autogenerate's own reverse op
    already does -- see `_the_reverse_op_restates_the_whole_column`.

    `existing_type` and `existing_nullable` are taken from the *model*, not from the database. They
    are unused on PostgreSQL and overridden by reflection inside a SQLite batch block, but on
    MySQL/MariaDB a DateTime downgrade compiles to `MySQLChangeColumn`, which rewrites the whole
    column definition from exactly those two. They agree with every upgraded database today; the day
    a listed column's type or nullability differs between the model and an upgraded database, the
    downgrade would silently retype it.
    """
    if upgrade_ops is None:
        return
    # Sorted because the container is a set: unsorted iteration would order the emitted ops by hash
    # and two regenerations of the same schema would produce two different revisions.
    #
    # Grouped by table rather than one container per column: on SQLite every `ModifyTableOps` is a
    # `batch_alter_table`, and a batch block is a full table copy (`CREATE TABLE _alembic_tmp_x` +
    # `INSERT .. SELECT` + `DROP` + `RENAME`). Ungrouped, `bw_ui_users` was copied five times and
    # `bw_metadata` four, on the engine with the least atomic DDL and for no gain.
    grouped = {}
    for table_name, column_name in sorted(_UNDECLARED_SERVER_DEFAULTS):
        # A KeyError here means the list is stale -- fail the generation rather than silently skip.
        column = target_metadata.tables[table_name].columns[column_name]
        if column.server_default is not None:
            continue  # the model declares one now; a fresh install gets it too, nothing to converge
        default = _reflected_server_default(migration_context, table_name, column_name)
        if default is None:
            continue  # already converged, this engine never had it, or the table is not there yet

        existing = _find_alter_column(upgrade_ops, table_name, column_name)
        if existing is not None:
            # Autogenerate already emitted an op for this column and
            # `_drop_server_defaults_the_model_does_not_declare` already dropped the default on it,
            # so the upgrade side is covered. Setting it again is a no-op; setting it on an op that
            # reached here another way (a type change with no reflected default) is the fix.
            existing.modify_server_default = None
        else:
            grouped.setdefault(table_name, []).append(
                AlterColumnOp(
                    table_name,
                    column_name,
                    modify_server_default=None,
                    existing_type=column.type,
                    existing_nullable=column.nullable,
                    existing_server_default=DefaultClause(text(default)),
                )
            )

        if downgrade_ops is None or (existing is not None and _the_reverse_op_restates_the_whole_column(migration_context)):
            continue
        downgrade_ops.ops.insert(
            0,
            ModifyTableOps(
                table_name,
                ops=[
                    AlterColumnOp(
                        table_name,
                        column_name,
                        modify_server_default=DefaultClause(text(default)),
                        existing_type=column.type,
                        existing_nullable=column.nullable,
                    )
                ],
            ),
        )

    for table_name, ops in grouped.items():
        upgrade_ops.ops.append(ModifyTableOps(table_name, ops=ops))


def _the_reverse_op_restates_the_whole_column(migration_context):
    """Whether an `alter_column` autogenerate emitted brings its `existing_server_default` back down.

    Only on MySQL and MariaDB, where a downgrade compiles to `MODIFY`/`CHANGE` -- one statement
    restating the entire column definition, default included -- so restoring it a second time would
    be a redundant whole-table rewrite.

    Everywhere else the reused op does *not* carry its own downgrade, and this is the difference
    between converging a default and losing it: `ALTER COLUMN ... TYPE` on PostgreSQL changes only
    the type, and a SQLite batch block rebuilds the table by reflecting the *already-converged*
    one, so neither puts the default back. Nothing reaches that branch today -- the reuse case is
    MySQL/MariaDB-only in the current heads -- but adding one label to `methods_enum`, `themes_enum`,
    `plugin_types_enum` or `pro_status_enum` renders as a VARCHAR-length `alter_column` on SQLite,
    and five listed columns sit on those types.

    The restore is inserted at the *front* of the downgrade, so it runs before autogenerate's own
    reverse op for the same column. Measured rather than assumed: a SQLite batch rebuild reflects the
    table it is rebuilding, so a default set by an earlier op survives it (`VARCHAR(16) DEFAULT
    'manual'` -> `VARCHAR(8) DEFAULT 'manual'`). On PostgreSQL the ordering cannot bite either, for a
    different reason -- the only reuse shape an enum produces there would be a *narrowing*, and
    PostgreSQL cannot remove a value from an enum type at all, so no downgrade ever changes one back.
    """
    dialect = getattr(migration_context, "dialect", None)
    if dialect is None:
        bind = getattr(migration_context, "bind", None)
        dialect = bind.dialect if bind is not None else None
    return dialect is not None and dialect.name in ("mysql", "mariadb")


def _has_reflected_default(op):
    """Whether the op actually carries a server default read off the database.

    `AlterColumnOp.existing_server_default` is `False` when unspecified, not `None`, and the value
    when specified is a `TextClause` whose `==` builds SQL rather than returning a bool -- so this
    is identity comparison against both sentinels and nothing else.
    """
    existing = op.existing_server_default
    return existing is not None and existing is not False


def _include_name(name, type_, _parent_names):
    """Keep autogenerate's attention on BunkerWeb's own tables.

    Every table the model declares is `bw_`-prefixed (43 of 43), and the generation database is a
    scratch container that other things write to: MariaDB's run came back with a stray `test` table
    and autogenerate duly emitted `op.drop_table("test")` into the shipped revision -- an op that
    fails on every real database, because no release ever created that table. A revision must
    describe the product's schema, not the machine it was generated on.

    Only the reflected side is filtered, so a `bw_` table the model drops is still detected.
    """
    if type_ == "table" and name is not None and not name.startswith("bw_"):
        return False
    return True


def _render_item(item_type, obj, autogen_context):
    """Make a custom type from `model.py` render into a revision that can actually run.

    Autogenerate renders a `TypeDecorator` defined outside SQLAlchemy with its module prefix --
    `model.JSONText()` -- but never adds the import that makes the name resolve, and
    `script.py.mako` only emits the imports it is given. The result is a revision that raises
    `NameError: name 'model' is not defined` the first time it creates a table with one, which is
    exactly what happened to `bw_ui_user_preferences`. `env.py` has already imported `model` above,
    so by the time a revision runs the module is in `sys.modules`; the import only has to be in the
    file. Returning False leaves alembic's own rendering alone.
    """
    if item_type == "type" and type(obj).__module__ == "model":
        autogen_context.imports.add("import model")
        return False
    if item_type == "type" and autogen_context.dialect.name == "postgresql" and isinstance(obj, SAEnum) and obj.name:
        # `create_type=False` stops `create_table` emitting `CREATE TYPE` for a type that is shared
        # with tables it is not creating -- see `_postgresql_enum_ops`, which creates it separately
        # and idempotently.
        autogen_context.imports.add("from sqlalchemy.dialects import postgresql")
        labels = ", ".join(_sql_literal(label) for label in obj.enums)
        return f"postgresql.ENUM({labels}, name={obj.name!r}, create_type=False)"
    return False


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
        _rewrite_renamed_tables(script.upgrade_ops)
        _rewrite_renamed_tables(script.downgrade_ops, reverse=True)
        _drop_server_defaults_the_model_does_not_declare(script.upgrade_ops)
        _drop_undeclared_server_defaults_autogenerate_missed(context_, script.upgrade_ops, script.downgrade_ops)
        if script.upgrade_ops is not None:
            script.upgrade_ops.ops[:0] = _postgresql_enum_ops(context_, script.upgrade_ops)
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


def _render_as_batch(dialect_name) -> bool:
    """SQLite gets `with op.batch_alter_table(...)`, the other three do not.

    SQLite has no `ALTER TABLE ... ALTER COLUMN`, so a plain `alter_column` renders SQL it rejects
    with `near "TYPE": syntax error` -- which is what a widened enum (`settings_types_enum` gaining
    `size`/`duration`, `api_resource_enum` gaining three resources) generates. Batch mode copies the
    table through a new definition instead, preserving the rows. Restricted to SQLite because on the
    other engines a batch block is a table rebuild where a one-line ALTER would do.
    """
    return dialect_name == "sqlite"


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
        render_item=_render_item,
        include_name=_include_name,
        render_as_batch=_render_as_batch(url.split(":")[0].split("+")[0] if url else None),
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
            render_item=_render_item,
            include_name=_include_name,
            render_as_batch=_render_as_batch(connection.dialect.name),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
