"""`alembic/env.py`'s autogenerate hooks — the three that decide whether a *generated* revision is
correct rather than merely present.

Revisions are produced by `misc/migration/create.sh`, never by hand, so any knowledge the generator
lacks has to live in `env.py` or it is lost every time the heads are regenerated. Three pieces of it
are covered here, each of which produced a real broken revision on 2026-09-01 before it existed:

1. **A rename is not a drop and a create.** Autogenerate compares two schemas and has no notion of
   identity between them, so `bw_ui_user_columns_preferences` -> `bw_ui_user_preferences` came out
   as `drop_table` + `create_table`: a revision that runs cleanly, reports success, and throws away
   every operator's saved table layouts. `_rewrite_renamed_tables` turns the pair back into a real
   rename.
2. **`op.rename_table` has no autogenerate renderer.** Alembic can execute it but never generates
   one itself, so writing it into a revision raised `ValueError: no dispatch function for object`.
3. **A custom type renders a name the revision never imports.** `model.JSONText()` is rendered with
   its module prefix and no `import model`, so the generated revision died on
   `NameError: name 'model' is not defined` the first time it created a table with one.

`env.py` cannot simply be imported: it runs migrations at module scope and reads `context.config`,
which only exists inside an alembic invocation. `_load_env_namespace` execs the part above
`run_migrations_offline` with a stub `context`, which is the part these hooks live in.
"""

import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.autogenerate import render
from alembic.autogenerate.api import AutogenContext
from alembic.operations.ops import (
    AddColumnOp,
    AlterColumnOp,
    CreateTableOp,
    DowngradeOps,
    DropIndexOp,
    DropTableOp,
    ModifyTableOps,
    RenameTableOp,
    UpgradeOps,
)
from alembic.runtime.migration import MigrationContext

ENV_PY = Path(__file__).resolve().parents[3] / "src" / "common" / "db" / "alembic" / "env.py"

OLD_TABLE = "bw_ui_user_columns_preferences"
NEW_TABLE = "bw_ui_user_preferences"


def _load_env_namespace():
    """`env.py`'s module-level definitions, without running any migration.

    The file ends by calling `run_migrations_offline()`/`run_migrations_online()` at import time and
    opens with `context.config`, so it is executed here up to the first of those, with `context`
    stubbed. Everything this file tests is defined above that line.
    """

    class _Config:
        config_file_name = None
        config_ini_section = "alembic"

        def set_main_option(self, *_args):
            pass

        def get_main_option(self, *_args):
            return None

        def get_section(self, *_args, **_kwargs):
            return {}

    stub = ModuleType("alembic.context")
    stub.config = _Config()
    alembic = import_module("alembic")
    saved_module, saved_attr = sys.modules.get("alembic.context"), getattr(alembic, "context", None)
    sys.modules["alembic.context"] = stub
    alembic.context = stub
    try:
        source = ENV_PY.read_text().split("def run_migrations_offline")[0]
        namespace = {"__name__": "bw_alembic_env_under_test"}
        exec(compile(source, str(ENV_PY), "exec"), namespace)  # noqa: S102
        return namespace
    finally:
        if saved_module is None:
            sys.modules.pop("alembic.context", None)
        else:
            sys.modules["alembic.context"] = saved_module
        if saved_attr is not None:
            alembic.context = saved_attr


@pytest.fixture(scope="module")
def env():
    return _load_env_namespace()


def _columns(key_column, value_column):
    """The four columns the preferences table has under either name."""
    from model import JSONText  # type: ignore

    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_name", sa.String(256), nullable=False),
        sa.Column(key_column, sa.String(256), nullable=False),
        sa.Column(value_column, JSONText(), nullable=False),
    ]


def _drop_of(table_name, key_column, value_column):
    """A `DropTableOp` carrying the reflected table, the way autogenerate builds it.

    A bare `DropTableOp(name)` has no columns behind it, so the guard that compares the two tables
    would see an empty old table. `from_table` is what `_produce_net_changes` actually calls.
    """
    return DropTableOp.from_table(sa.Table(table_name, sa.MetaData(), *_columns(key_column, value_column)))


def _drop_and_create_pair():
    """What autogenerate really emits for the rename, in both directions."""
    upgrade = UpgradeOps(ops=[CreateTableOp(NEW_TABLE, _columns("key", "value")), _drop_of(OLD_TABLE, "table_name", "columns")])
    downgrade = DowngradeOps(ops=[CreateTableOp(OLD_TABLE, _columns("table_name", "columns")), _drop_of(NEW_TABLE, "key", "value")])
    return upgrade, downgrade


def _autogen_context(env):
    return AutogenContext(
        MigrationContext.configure(dialect_name="sqlite"),
        # `user_module_prefix=None` is alembic's own default and the branch that renders a type
        # defined outside SQLAlchemy as `<module>.<Type>()` -- the rendering this hook exists for.
        opts={
            "render_item": env["_render_item"],
            "sqlalchemy_module_prefix": "sa.",
            "alembic_module_prefix": "op.",
            "user_module_prefix": None,
        },
    )


class TestRenamedTableRewrite:
    def test_the_drop_and_create_pair_becomes_a_rename(self, env):
        upgrade, _ = _drop_and_create_pair()

        env["_rewrite_renamed_tables"](upgrade)

        assert not [op for op in upgrade.ops if isinstance(op, (CreateTableOp, DropTableOp))], "the destructive pair survived the rewrite"
        renames = [op for op in upgrade.ops if isinstance(op, RenameTableOp)]
        assert [(op.table_name, op.new_table_name) for op in renames] == [(OLD_TABLE, NEW_TABLE)]

    def test_both_columns_are_renamed_with_the_type_and_nullability_mysql_needs(self, env):
        """On MySQL/MariaDB a column rename is a `CHANGE` that restates the whole definition, so
        `existing_type` and `existing_nullable` are not decoration -- omitting them rewrites the
        column as a nullable something-else."""
        upgrade, _ = _drop_and_create_pair()

        env["_rewrite_renamed_tables"](upgrade)

        alters = {op.column_name: op for op in upgrade.ops if isinstance(op, AlterColumnOp)}
        assert {name: op.modify_name for name, op in alters.items()} == {"table_name": "key", "columns": "value"}
        for op in alters.values():
            assert op.table_name == NEW_TABLE
            assert op.existing_type is not None
            assert op.existing_nullable is False

    def test_the_downgrade_renames_back(self, env):
        _, downgrade = _drop_and_create_pair()

        env["_rewrite_renamed_tables"](downgrade, reverse=True)

        renames = [op for op in downgrade.ops if isinstance(op, RenameTableOp)]
        assert [(op.table_name, op.new_table_name) for op in renames] == [(NEW_TABLE, OLD_TABLE)]
        alters = {op.column_name: op.modify_name for op in downgrade.ops if isinstance(op, AlterColumnOp)}
        assert alters == {"key": "table_name", "value": "columns"}

    def test_leftover_index_ops_on_either_name_are_dropped(self, env):
        """MariaDB's version of the same diff also drops `uq_user_columns_preferences` from the old
        table and recreates it on the way down. Left in place those run against a table that has
        already been renamed (`Table 'db.bw_ui_user_columns_preferences' doesn't exist`), and
        retargeted they would delete the unique index the renamed table still carries."""
        upgrade = UpgradeOps(
            ops=[
                CreateTableOp(NEW_TABLE, _columns("key", "value")),
                DropIndexOp("uq_user_columns_preferences", table_name=OLD_TABLE),
                _drop_of(OLD_TABLE, "table_name", "columns"),
            ]
        )

        env["_rewrite_renamed_tables"](upgrade)

        assert not [op for op in upgrade.ops if isinstance(op, DropIndexOp)]
        assert [type(op).__name__ for op in upgrade.ops] == ["RenameTableOp", "AlterColumnOp", "AlterColumnOp"]

    def test_a_column_only_the_new_table_has_refuses_the_rewrite(self, env):
        """The rewrite keeps the rename and throws the `create_table` away, so a column the new
        table gained would reach a fresh install through the model and never reach an upgraded one.
        Silent, and permanent once the revision ships -- so it has to fail the generation instead."""
        upgrade = UpgradeOps(
            ops=[
                CreateTableOp(NEW_TABLE, _columns("key", "value") + [sa.Column("added_later", sa.String(16), nullable=True)]),
                _drop_of(OLD_TABLE, "table_name", "columns"),
            ]
        )

        with pytest.raises(RuntimeError, match="added_later"):
            env["_rewrite_renamed_tables"](upgrade)

    def test_a_column_only_the_old_table_has_refuses_the_rewrite(self, env):
        """The other direction is a real drop_column the rename would swallow."""
        upgrade = UpgradeOps(
            ops=[
                CreateTableOp(NEW_TABLE, _columns("key", "value")),
                DropTableOp.from_table(
                    sa.Table(OLD_TABLE, sa.MetaData(), *(_columns("table_name", "columns") + [sa.Column("dropped_here", sa.String(16), nullable=True)]))
                ),
            ]
        )

        with pytest.raises(RuntimeError, match="dropped_here"):
            env["_rewrite_renamed_tables"](upgrade)

    def test_a_named_constraint_in_the_create_is_not_mistaken_for_a_column(self, env):
        """`CreateTableOp.columns` mixes Columns and Constraints, and a named constraint has a
        `.name` too -- counting it would fail the guard on a pair that is perfectly fine."""
        upgrade = UpgradeOps(
            ops=[
                CreateTableOp(NEW_TABLE, _columns("key", "value") + [sa.UniqueConstraint("user_name", "key", name="uq_user_preferences")]),
                _drop_of(OLD_TABLE, "table_name", "columns"),
            ]
        )

        env["_rewrite_renamed_tables"](upgrade)

        assert [type(op).__name__ for op in upgrade.ops] == ["RenameTableOp", "AlterColumnOp", "AlterColumnOp"]

    def test_an_unrelated_diff_is_left_alone(self, env):
        """Once the rename has shipped, later regenerations see two schemas that already agree and
        emit neither op. The rewrite must be a no-op then, not a source of phantom renames."""
        upgrade = UpgradeOps(ops=[CreateTableOp("bw_something_else", _columns("key", "value"))])

        env["_rewrite_renamed_tables"](upgrade)

        assert len(upgrade.ops) == 1 and isinstance(upgrade.ops[0], CreateTableOp)

    def test_a_drop_with_no_matching_create_is_refused(self, env):
        """The dangerous half-pair: a drop of a table this map says was renamed, with nothing being
        created in its place, means the rows really are going away. Autogenerate cannot tell that
        from a rename, so the generator refuses rather than emitting the silent data loss."""
        upgrade = UpgradeOps(ops=[DropTableOp(OLD_TABLE)])

        with pytest.raises(RuntimeError, match=OLD_TABLE):
            env["_rewrite_renamed_tables"](upgrade)


class _FakeBind:
    """`migration_context.bind.execute(...)` returning whatever `pg_enum` is supposed to hold."""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, _statement):
        return self.rows


class _FakePostgresContext:
    def __init__(self, rows, dialect_name="postgresql"):
        self.bind = _FakeBind(rows)
        self.dialect = SimpleNamespace(name=dialect_name)


class TestPostgresqlEnums:
    """PostgreSQL is the one backend where an enum is a shared `TYPE`, and autogenerate is wrong
    about it in both directions -- it re-creates one that exists and never notices a new label."""

    def test_nothing_is_emitted_on_the_other_engines(self, env):
        upgrade = UpgradeOps(ops=[CreateTableOp("bw_bans", [sa.Column("method", sa.Enum("api", "ui", name="methods_enum"))])])

        assert env["_postgresql_enum_ops"](_FakePostgresContext([], dialect_name="mariadb"), upgrade) == []

    def test_an_enum_used_by_a_new_table_is_created_idempotently(self, env):
        """`methods_enum` already exists when `bw_bans` is created, and `create_table` emits
        `CREATE TYPE` regardless -- `type "methods_enum" already exists` killed the whole
        migration. The `DO $$ ... duplicate_object` block is correct whether it exists or not, so
        the same op covers a genuinely new type too."""
        upgrade = UpgradeOps(ops=[CreateTableOp("bw_bans", [sa.Column("method", sa.Enum("api", "ui", name="methods_enum"))])])

        ops = env["_postgresql_enum_ops"](_FakePostgresContext([("methods_enum", "api"), ("methods_enum", "ui")]), upgrade)

        creates = [op.sqltext for op in ops if "CREATE TYPE" in op.sqltext]
        assert creates == ["DO $$ BEGIN CREATE TYPE methods_enum AS ENUM ('api', 'ui'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;"]

    def test_an_enum_reached_through_add_column_is_created_too(self, env):
        """`bw_instances.tls_mode` arrives as an `add_column`, not inside a `create_table`, and its
        `instance_tls_mode_enum` does not exist yet."""
        upgrade = UpgradeOps(ops=[AddColumnOp("bw_instances", sa.Column("tls_mode", sa.Enum("off", "pinned", name="instance_tls_mode_enum")))])

        ops = env["_postgresql_enum_ops"](_FakePostgresContext([]), upgrade)

        assert any("CREATE TYPE instance_tls_mode_enum AS ENUM ('off', 'pinned')" in op.sqltext for op in ops)

    def test_a_label_the_model_added_to_an_existing_type_is_migrated_in(self, env):
        """The defect the replaced head shipped: on MySQL/SQLite the enum is a VARCHAR whose length
        changes so autogenerate sees it, on PostgreSQL it compares equal to itself by name and
        nothing is emitted. `settings_types_enum` lost `size` and `duration` exactly this way."""
        live = [("settings_types_enum", label) for label in ("password", "text", "number", "file", "check", "select", "multiselect", "multivalue")]

        ops = env["_postgresql_enum_ops"](_FakePostgresContext(live), UpgradeOps(ops=[]))

        added = [op.sqltext for op in ops if "ADD VALUE" in op.sqltext]
        assert "ALTER TYPE settings_types_enum ADD VALUE IF NOT EXISTS 'size'" in added
        assert "ALTER TYPE settings_types_enum ADD VALUE IF NOT EXISTS 'duration'" in added

    def test_a_type_already_holding_every_label_is_left_alone(self, env):
        """Anti-vacuity: keyed on the live labels, not on "this type is interesting"."""
        from model import SETTINGS_TYPES_ENUM  # type: ignore

        live = [("settings_types_enum", label) for label in SETTINGS_TYPES_ENUM.enums]

        ops = env["_postgresql_enum_ops"](_FakePostgresContext(live), UpgradeOps(ops=[]))

        assert not [op for op in ops if "settings_types_enum" in op.sqltext and "ADD VALUE" in op.sqltext]

    def test_a_type_absent_from_the_database_gets_no_add_value(self, env):
        """It does not exist yet, so the `DO` block creates it with every label; an `ALTER TYPE` on
        it would run before the type is there."""
        ops = env["_postgresql_enum_ops"](_FakePostgresContext([]), UpgradeOps(ops=[]))

        assert not [op for op in ops if "ADD VALUE" in op.sqltext]


class TestServerDefaults:
    """An upgraded database must not keep a server default a fresh one never gets."""

    def test_a_default_only_the_database_has_is_dropped(self, env):
        """`bw_ui_users.method` was created with `server_default="manual"` in 1.5.5 and every
        `alter_column` since restated it, while the model declares only a Python-side default. The
        two installs have differed there ever since."""
        upgrade = UpgradeOps(
            ops=[
                AlterColumnOp(
                    "bw_ui_users",
                    "method",
                    existing_type=sa.Enum("ui", "manual", name="methods_enum"),
                    existing_nullable=False,
                    existing_server_default=sa.text("'manual'"),
                )
            ]
        )

        env["_drop_server_defaults_the_model_does_not_declare"](upgrade)

        assert upgrade.ops[0].modify_server_default is None

    def test_a_default_the_model_declares_is_left_alone(self, env):
        """Anti-vacuity: `bw_metrics_requests.protocol` really does declare `server_default="http"`,
        and dropping it would be the same defect in the other direction."""
        upgrade = UpgradeOps(
            ops=[
                AlterColumnOp(
                    "bw_metrics_requests",
                    "protocol",
                    existing_type=sa.String(8),
                    existing_nullable=False,
                    existing_server_default=sa.text("'http'"),
                )
            ]
        )

        env["_drop_server_defaults_the_model_does_not_declare"](upgrade)

        assert upgrade.ops[0].modify_server_default is False, "False is alembic's 'leave it alone' sentinel"

    def test_an_op_that_carries_no_default_is_left_alone(self, env):
        """`existing_server_default` is `False` when unspecified, not `None`, and `False is not
        None` is true -- so the naive guard fired on every alter_column and sprinkled an explicit
        `server_default=None` across columns that never had one."""
        upgrade = UpgradeOps(ops=[AlterColumnOp("bw_ui_users", "method", existing_type=sa.String(16), existing_nullable=False)])

        env["_drop_server_defaults_the_model_does_not_declare"](upgrade)

        assert upgrade.ops[0].modify_server_default is False

    def test_a_column_the_model_no_longer_declares_is_left_alone(self, env):
        """A table or column being dropped has no model entry to converge on; guessing would turn a
        missing key into a DROP DEFAULT on something that is going away anyway."""
        upgrade = UpgradeOps(ops=[AlterColumnOp("bw_gone", "method", existing_type=sa.String(16), existing_server_default=sa.text("'manual'"))])

        env["_drop_server_defaults_the_model_does_not_declare"](upgrade)

        assert upgrade.ops[0].modify_server_default is False


class TestNameFilter:
    """The generation database is a scratch container, and whatever else lives in it must not end
    up described in a shipped revision."""

    def test_a_stray_table_in_the_generation_database_is_ignored(self, env):
        """MariaDB's run came back with a table called `test` and autogenerate emitted
        `op.drop_table("test")` into the head -- an op that fails on every real database."""
        assert env["_include_name"]("test", "table", {}) is False

    def test_the_products_own_tables_are_kept(self, env):
        assert env["_include_name"]("bw_jobs_runs", "table", {}) is True

    def test_everything_that_is_not_a_table_is_kept(self, env):
        """The filter is keyed on `bw_`, which is a table-naming rule and nothing else; applying it
        to columns would silently drop every column whose name does not start with `bw_`."""
        assert env["_include_name"]("error", "column", {"table_name": "bw_jobs_runs"}) is True
        assert env["_include_name"](None, "schema", {}) is True

    def test_every_table_the_model_declares_survives_the_filter(self, env):
        """Anti-vacuity, and the assumption the filter rests on: all 43 are `bw_`-prefixed. A table
        added without that prefix would be invisible to autogenerate, so this fails loudly."""
        from model import Base  # type: ignore

        assert Base.metadata.tables
        excluded = sorted(name for name in Base.metadata.tables if not env["_include_name"](name, "table", {}))
        assert not excluded, f"the model declares tables the generator would ignore: {excluded}"


class TestRendering:
    def test_a_rename_renders_as_a_call_alembic_can_run(self, env):
        """Alembic ships no renderer for `RenameTableOp`; without the one in env.py, generating a
        revision containing it raises `ValueError: no dispatch function for object`."""
        rendered = render.render_op_text(_autogen_context(env), RenameTableOp(OLD_TABLE, NEW_TABLE))

        assert rendered == f"op.rename_table({OLD_TABLE!r}, {NEW_TABLE!r})"

    def test_a_custom_type_pulls_its_import_into_the_revision(self, env):
        """`model.JSONText()` is what alembic renders; `import model` is what makes it resolve, and
        alembic never adds it. `script.py.mako` emits `${imports}`, so it only has to be registered.
        """
        context = _autogen_context(env)
        rendered = render.render_op_text(context, CreateTableOp(NEW_TABLE, _columns("key", "value")))

        assert "model.JSONText()" in rendered
        assert "import model" in context.imports

    def test_a_postgresql_enum_renders_without_its_create_type(self, env):
        """The column must stop emitting `CREATE TYPE`; `_postgresql_enum_ops` creates the type
        separately and idempotently. Without this, the first new table carrying an enum that
        already exists dies on `type "methods_enum" already exists`."""
        context = AutogenContext(
            MigrationContext.configure(dialect_name="postgresql"),
            opts={
                "render_item": env["_render_item"],
                "sqlalchemy_module_prefix": "sa.",
                "alembic_module_prefix": "op.",
                "user_module_prefix": None,
            },
        )

        rendered = render.render_op_text(context, CreateTableOp("bw_bans", [sa.Column("method", sa.Enum("api", "ui", name="methods_enum"))]))

        assert "postgresql.ENUM('api', 'ui', name='methods_enum', create_type=False)" in rendered
        assert "from sqlalchemy.dialects import postgresql" in context.imports

    def test_the_other_engines_keep_alembics_own_enum_rendering(self, env):
        """Anti-vacuity: `create_type` is a PostgreSQL concept and `postgresql.ENUM` would be the
        wrong type object anywhere else."""
        context = _autogen_context(env)  # sqlite

        rendered = render.render_op_text(context, CreateTableOp("bw_bans", [sa.Column("method", sa.Enum("api", "ui", name="methods_enum"))]))

        assert "create_type" not in rendered
        assert "sa.Enum('api', 'ui', name='methods_enum')" in rendered

    def test_a_plain_sqlalchemy_type_pulls_in_no_such_import(self, env):
        """Anti-vacuity: the hook must key on the type's own module, not add `import model` to every
        revision that renders any type at all."""
        context = _autogen_context(env)
        render.render_op_text(context, CreateTableOp("bw_plain", [sa.Column("id", sa.Integer(), primary_key=True)]))

        assert "import model" not in context.imports


def _sqlite_context(with_default=True):
    """A migration context bound to a database shaped like the two columns that carry the default.

    `_database_has_a_server_default` reflects the live database, so this is a real connection rather
    than a stub: the point of the check is that reflection sees the `DEFAULT 'manual'` an upgraded
    database has and does not see one a converged database no longer has.
    """
    default = " DEFAULT 'manual'" if with_default else ""
    engine = sa.create_engine("sqlite://")
    connection = engine.connect()
    connection.exec_driver_sql(f"CREATE TABLE bw_plugins (id VARCHAR(64) PRIMARY KEY, method VARCHAR(16) NOT NULL{default})")
    connection.exec_driver_sql(f"CREATE TABLE bw_ui_users (username VARCHAR(256) PRIMARY KEY, method VARCHAR(16) NOT NULL{default})")
    return SimpleNamespace(bind=connection)


def _batch_autogen_context(env):
    """A SQLite autogenerate context with batch rendering on, the way `env.py` configures it."""
    return AutogenContext(
        MigrationContext.configure(dialect_name="sqlite"),
        opts={
            "render_item": env["_render_item"],
            "sqlalchemy_module_prefix": "sa.",
            "alembic_module_prefix": "op.",
            "user_module_prefix": None,
            "render_as_batch": True,
        },
    )


class TestServerDefaultsAutogenerateMissed:
    """The other half of `TestServerDefaults`: the engines where there is no op to edit.

    `bw_ui_users.method` has carried `server_default='manual'` since 1.5.5 on all four engines, and
    `bw_plugins.method` on MySQL and MariaDB only -- the SQLite and PostgreSQL 1.5.5 revisions add it
    to `bw_ui_users` alone (measured against real chain-built databases on 2026-09-01). The model
    declares only a Python-side default in every case. Autogenerate produces an `alter_column` to
    hang the drop on only on MySQL and MariaDB -- SQLite sees the old and the new `methods_enum` as
    the same VARCHAR length, and PostgreSQL runs with `compare_server_default` off -- so without this
    pass two engines converge with a fresh install and two do not.
    """

    def test_the_op_autogenerate_never_produced_is_emitted(self, env):
        upgrade, downgrade = UpgradeOps(ops=[]), DowngradeOps(ops=[])

        env["_drop_undeclared_server_defaults_autogenerate_missed"](_sqlite_context(), upgrade, downgrade)

        emitted = {op.table_name: op for op in upgrade.ops if isinstance(op, ModifyTableOps)}
        assert sorted(emitted) == ["bw_plugins", "bw_ui_users"]
        for table_name, container in emitted.items():
            (alter,) = container.ops
            assert (alter.table_name, alter.column_name) == (table_name, "method")
            assert alter.modify_server_default is None
            assert alter.existing_type is not None, "SQLite rebuilds the column in batch mode and needs the type"
            assert alter.existing_nullable is False

    def test_the_downgrade_puts_the_default_back_explicitly(self, env):
        """`ALTER COLUMN` on SQLite and PostgreSQL changes only what it is told to change, so the
        `existing_server_default=` that restores it on MySQL's whole-definition `MODIFY` is not
        enough here -- the downgrade has to set it."""
        upgrade, downgrade = UpgradeOps(ops=[]), DowngradeOps(ops=[])

        env["_drop_undeclared_server_defaults_autogenerate_missed"](_sqlite_context(), upgrade, downgrade)

        restored = {op.table_name: op.ops[0] for op in downgrade.ops if isinstance(op, ModifyTableOps)}
        assert sorted(restored) == ["bw_plugins", "bw_ui_users"]
        for alter in restored.values():
            assert str(alter.modify_server_default.arg) == "'manual'"

    def test_a_database_without_the_default_gets_no_op(self, env):
        """Anti-vacuity, and what stops every future head carrying a `DROP DEFAULT` for something
        this revision already removed: the emission is keyed on the live database, not on the map."""
        upgrade, downgrade = UpgradeOps(ops=[]), DowngradeOps(ops=[])

        env["_drop_undeclared_server_defaults_autogenerate_missed"](_sqlite_context(with_default=False), upgrade, downgrade)

        assert upgrade.ops == [] and downgrade.ops == []

    def test_a_default_the_model_declares_is_left_alone(self, env):
        """Anti-vacuity in the other direction: the model is what a fresh install builds from, so a
        default it declares is one an upgraded database is supposed to keep."""
        column = env["target_metadata"].tables["bw_plugins"].columns["method"]
        upgrade, downgrade = UpgradeOps(ops=[]), DowngradeOps(ops=[])

        column.server_default = sa.DefaultClause(sa.text("'manual'"))
        try:
            env["_drop_undeclared_server_defaults_autogenerate_missed"](_sqlite_context(), upgrade, downgrade)
        finally:
            column.server_default = None

        assert [op.table_name for op in upgrade.ops] == ["bw_ui_users"], "only the column the model still leaves undeclared"

    def test_an_op_autogenerate_did_produce_is_reused_rather_than_duplicated(self, env):
        """MySQL and MariaDB: the pass before this one already dropped the default on the op
        autogenerate emitted. Emitting a second `alter_column` for the same column would be a
        redundant table rebuild on SQLite and a contradictory pair of statements everywhere."""
        existing = AlterColumnOp(
            "bw_plugins",
            "method",
            existing_type=sa.Enum("ui", "manual", name="methods_enum"),
            existing_nullable=False,
            existing_server_default=sa.text("'manual'"),
        )
        upgrade, downgrade = UpgradeOps(ops=[ModifyTableOps("bw_plugins", ops=[existing])]), DowngradeOps(ops=[])

        env["_drop_undeclared_server_defaults_autogenerate_missed"](_sqlite_context(), upgrade, downgrade)

        assert [op.table_name for op in upgrade.ops] == ["bw_plugins", "bw_ui_users"], "bw_plugins got no second container"
        assert existing.modify_server_default is None
        assert [op.table_name for op in downgrade.ops] == ["bw_ui_users"], "the reused op carries its own downgrade"

    def test_a_stale_map_fails_the_generation(self, env):
        """A renamed or dropped column must not turn into a silently skipped convergence: the map is
        knowledge that cannot be re-derived, so it fails loudly when it stops matching the model."""
        saved = dict(env["_UNDECLARED_SERVER_DEFAULTS"])
        env["_UNDECLARED_SERVER_DEFAULTS"].clear()
        env["_UNDECLARED_SERVER_DEFAULTS"][("bw_plugins", "gone")] = "'manual'"
        try:
            with pytest.raises(KeyError, match="gone"):
                env["_drop_undeclared_server_defaults_autogenerate_missed"](_sqlite_context(), UpgradeOps(ops=[]), DowngradeOps(ops=[]))
        finally:
            env["_UNDECLARED_SERVER_DEFAULTS"].clear()
            env["_UNDECLARED_SERVER_DEFAULTS"].update(saved)

    def test_offline_generation_emits_nothing(self, env):
        """No connection means no way to know whether the default is still there, and guessing would
        write a `DROP DEFAULT` into a revision on the strength of a hardcoded map alone."""
        upgrade, downgrade = UpgradeOps(ops=[]), DowngradeOps(ops=[])

        env["_drop_undeclared_server_defaults_autogenerate_missed"](SimpleNamespace(bind=None), upgrade, downgrade)

        assert upgrade.ops == [] and downgrade.ops == []

    def test_it_renders_inside_a_batch_block_on_sqlite(self, env):
        """SQLite has no `ALTER TABLE ... ALTER COLUMN`. A bare `AlterColumnOp` at the top of
        `upgrade_ops` renders as `op.alter_column(...)` with no `batch_alter_table` around it --
        `_render_modify_table` is what produces the wrapper -- and the revision dies on
        `near "ALTER": syntax error`."""
        upgrade, downgrade = UpgradeOps(ops=[]), DowngradeOps(ops=[])
        env["_drop_undeclared_server_defaults_autogenerate_missed"](_sqlite_context(), upgrade, downgrade)

        container = next(op for op in upgrade.ops if op.table_name == "bw_plugins")
        rendered = render.render_op_text(_batch_autogen_context(env), container)

        assert rendered.startswith("with op.batch_alter_table('bw_plugins', schema=None) as batch_op:")
        assert "batch_op.alter_column('method'" in rendered
        assert "server_default=None" in rendered

    def test_the_downgrade_renders_the_literal_the_other_heads_use(self, env):
        upgrade, downgrade = UpgradeOps(ops=[]), DowngradeOps(ops=[])
        env["_drop_undeclared_server_defaults_autogenerate_missed"](_sqlite_context(), upgrade, downgrade)

        container = next(op for op in downgrade.ops if op.table_name == "bw_ui_users")
        rendered = render.render_op_text(_batch_autogen_context(env), container)

        assert "server_default=sa.text(\"'manual'\")" in rendered

    def test_a_table_the_database_does_not_have_yet_is_skipped(self, env):
        """`has_table` is not decoration: `get_columns` raises `NoSuchTableError` on a missing table,
        and a revision command runs this pass against whatever database it is pointed at."""
        engine = sa.create_engine("sqlite://")
        upgrade, downgrade = UpgradeOps(ops=[]), DowngradeOps(ops=[])

        env["_drop_undeclared_server_defaults_autogenerate_missed"](SimpleNamespace(bind=engine.connect()), upgrade, downgrade)

        assert upgrade.ops == [] and downgrade.ops == []

    def test_it_renders_flat_on_postgresql(self, env):
        """The other engine this pass exists for. PostgreSQL takes a plain `ALTER COLUMN`, so the op
        must render without the batch wrapper -- and with the enum carrying `create_type=False`, or
        the revision would try to create a type that already exists."""
        upgrade, downgrade = UpgradeOps(ops=[]), DowngradeOps(ops=[])
        env["_drop_undeclared_server_defaults_autogenerate_missed"](_sqlite_context(), upgrade, downgrade)
        context = AutogenContext(
            MigrationContext.configure(dialect_name="postgresql"),
            opts={
                "render_item": env["_render_item"],
                "sqlalchemy_module_prefix": "sa.",
                "alembic_module_prefix": "op.",
                "user_module_prefix": None,
                "render_as_batch": False,
            },
        )

        container = next(op for op in upgrade.ops if op.table_name == "bw_ui_users")
        rendered = render.render_op_text(context, container)

        assert rendered.startswith("op.alter_column('bw_ui_users', 'method'")
        assert "batch_alter_table" not in rendered
        assert "create_type=False" in rendered
        assert "server_default=None" in rendered
