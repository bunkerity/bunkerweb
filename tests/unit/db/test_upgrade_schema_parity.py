"""An upgraded database must be indistinguishable from a fresh one.

`test_certificate_migrations.py::test_sqlite_upgrade_creates_resource_tables` cannot catch this
class and never could. It builds its starting point with `Base.metadata.create_all(engine)` — the
**current** model's schema — then drops five tables and runs alembic. Every column the 1.7 model
declares therefore exists *before* the first migration runs, so a migration that forgets an
`add_column` is invisible by construction. It is green today and would stay green for any amount of
column drift. It is left exactly as it is; it checks that the resource *tables* get created, which
is a real thing to check, and this file checks the other half.

What an operator actually upgrades is a database built by an **older release**. So that is what this
starts from: the real `model.py` from the `v1.6.13` tag, `create_all`'d into a fresh database, then
put through the product's own upgrade path —

    entrypoint.sh:105-120     alembic stamp <revision for the stored version> ; alembic upgrade head
    initialization.py:117     Base.metadata.create_all(engine, checkfirst=True)

`create_all(checkfirst=True)` is why a missing `add_column` is so quiet: it creates tables that do
not exist and never touches tables that do, so a forgotten column on an existing table survives both
mechanisms and shows up later as an `OperationalError` on a query nobody ran during the upgrade.

Each engine describes itself **twice** and is compared against itself: once upgraded from the
baseline, once built fresh from the model on a wiped database. Reflection against reflection, never
reflection against the model — the model renders differently per dialect, and guessing how is how a
parity test starts asserting its own assumptions instead of the schema. Comparing an engine to
itself also means a difference is real drift and never a dialect quirk.

`checkfirst=True` skips more than columns, so the comparison covers every structural dimension that
skip can silently drop: **tables, columns, types, nullability, server defaults, indexes, unique
constraints, foreign keys (with their `ON DELETE`/`ON UPDATE`), primary keys, and PostgreSQL ENUM
labels.** A specification that covered only some of those would read as complete and would not be.

Indexes, unique constraints and foreign keys are compared by **shape, never by name**: a migration
names its own objects, `create_all` names by convention, and each engine auto-names the objects
backing its constraints differently, so a name comparison would report drift on every engine and
mean nothing.

Multi-engine on purpose. SQLite has type *affinity* rather than types, so a SQLite-only run can
report "no type drift" without that meaning anything; PostgreSQL and MariaDB are where the type and
nullability halves of this become measurable. Run them with
`--db-engines sqlite,postgresql,mariadb` and the two URIs from `tests/unit/README.md`; an engine
that is unconfigured or unreachable skips rather than silently passing.
"""

from pathlib import Path
from subprocess import run
from types import ModuleType

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, create_engine, inspect, text

from fixtures.db_factory import resolve_uri
from fixtures.engines import _with_driver
from model import Base  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
ALEMBIC = ROOT / "src" / "common" / "db" / "alembic"

# The last stable 1.6 release, and the one the 1.7 head chains off. Hardcoded on purpose: deriving
# "the newest 1.6 tag" would quietly change what this test upgrades *from* the day a 1.6.15 lands,
# which is the opposite of what a regression test should do. The revision to stamp is not hardcoded
# — it is derived below exactly as the product derives it, so the two cannot drift apart.
BASELINE_TAG = "v1.6.13"
BASELINE_VERSION = BASELINE_TAG.lstrip("v")


def _baseline_metadata():
    """`model.py` as it was at the baseline tag, loaded under its own `Base`.

    Read out of git rather than reconstructed: the point is to start from a schema some release
    really shipped, and any hand-written approximation of it would be the same mistake as
    `create_all`-ing the current model, just less obvious.
    """
    source = run(["git", "show", f"{BASELINE_TAG}:src/common/db/model.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    module = ModuleType(f"bw_model_{BASELINE_VERSION.replace('.', '_')}")
    exec(compile(source, f"<{BASELINE_TAG}:src/common/db/model.py>", "exec"), module.__dict__)  # noqa: S102
    return module.Base.metadata


def _revision_for(version, dialect):
    """The revision the product would stamp for a database recorded at `version`.

    `entrypoint.sh:107-110` finds it by filename — `*_upgrade_to_version_<version with _ for .>.py`
    — so this reads it the same way instead of naming a hash that would go stale silently.
    """
    normalised = version.replace(".", "_").replace("-", "_").replace("~", "_")
    matches = sorted((ALEMBIC / f"{dialect}_versions").glob(f"*_upgrade_to_version_{normalised}.py"))
    assert len(matches) == 1, f"expected one migration for {version} in {dialect}_versions, found {[m.name for m in matches]}"
    return matches[0].name.split("_", 1)[0]


def _product_uri(db_engine, tmp_path):
    """The URI the product would hand alembic, driver and all.

    `scheduler/entrypoint.sh:83-99` writes `db.database_uri` — the string *after*
    `Database.py:184-196` injected `+psycopg`/`+pymysql` — and re-exports that as `DATABASE_URI`
    before alembic runs. The operator's bare `postgresql://` or `mariadb://` never reaches alembic,
    which matters: SQLAlchemy defaults those to psycopg2 and MySQLdb, neither of which BunkerWeb
    ships. `_with_driver` is the same mapping, already mirrored for the fixtures.
    """
    return _with_driver(resolve_uri(db_engine, tmp_path)).render_as_string(hide_password=False)


def _wipe(uri):
    """Drop everything, not just what the current model declares.

    `fixtures.engines.reset_schema` uses `Base.metadata.drop_all`, which leaves behind anything the
    1.7 model does not name — `alembic_version` above all, whose leftover row would silently make
    the next `stamp` a no-op. PostgreSQL additionally needs its ENUM *types* gone, and those are not
    tables; `DROP SCHEMA public CASCADE` is the only wipe that takes both.
    """
    engine = create_engine(uri)
    try:
        with engine.begin() as conn:
            if engine.dialect.name == "postgresql":
                conn.execute(text("DROP SCHEMA public CASCADE"))
                conn.execute(text("CREATE SCHEMA public"))
            elif engine.dialect.name in ("mysql", "mariadb"):
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                for (table,) in conn.execute(text("SHOW TABLES")).fetchall():
                    conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            else:
                leftovers = MetaData()
                leftovers.reflect(bind=conn)
                leftovers.drop_all(bind=conn)
    finally:
        engine.dispose()


def _index_shape(index):
    """An index by what it does, not what it is called.

    Names are the one part of an index that legitimately differs between an upgraded and a fresh
    database — a migration names its own, `create_all` names by convention, and PostgreSQL and
    MariaDB each auto-name the indexes backing constraints differently. Comparing names would
    report drift on every engine and mean nothing. Columns and uniqueness are the behaviour.
    """
    return (tuple(str(column) for column in index.get("column_names") or ()), bool(index.get("unique")))


def _foreign_key_shape(fk):
    """A foreign key including its referential actions.

    `ON DELETE` is the reason this is worth reflecting at all: a FK that exists on both sides but
    cascades on one and restricts on the other deletes different rows, silently, and no column or
    type check would ever see it.
    """
    options = fk.get("options") or {}
    return (
        tuple(fk.get("constrained_columns") or ()),
        fk.get("referred_table"),
        tuple(fk.get("referred_columns") or ()),
        (options.get("ondelete") or "").upper() or None,
        (options.get("onupdate") or "").upper() or None,
    )


def _describe(engine):
    """Everything about the live schema this test compares: columns with their rendered types and
    nullability, server defaults, indexes, unique constraints, foreign keys, primary keys, and — on
    PostgreSQL — the labels of every ENUM type.

    All six structural dimensions come from one reflection pass per table rather than six, because
    `get_columns` and friends each re-query the catalog and 43 tables x 3 engines x 2 phases adds up.
    """
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    columns = {table: {c["name"]: (str(c["type"]), bool(c["nullable"])) for c in inspector.get_columns(table)} for table in tables}
    defaults = {table: {c["name"]: c.get("default") for c in inspector.get_columns(table)} for table in tables}
    indexes = {table: {_index_shape(index) for index in inspector.get_indexes(table)} for table in tables}
    unique = {table: {tuple(sorted(uc.get("column_names") or ())) for uc in inspector.get_unique_constraints(table)} for table in tables}
    foreign_keys = {table: {_foreign_key_shape(fk) for fk in inspector.get_foreign_keys(table)} for table in tables}
    primary_keys = {table: tuple(inspector.get_pk_constraint(table).get("constrained_columns") or ()) for table in tables}

    if engine.dialect.name in ("mysql", "mariadb"):
        # SQLAlchemy reflects a MariaDB ENUM column back as a bare `ENUM` with its labels dropped,
        # so label drift there would compare equal to itself and pass — the one blind spot the
        # PostgreSQL enum check below would not cover. `information_schema.column_type` is the
        # server's own rendering, `enum('a','b')` and all. Both sides read it from the same server,
        # so its extra verbosity (display widths, `unsigned`) cancels instead of becoming noise.
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT table_name, column_name, column_type FROM information_schema.columns WHERE table_schema = DATABASE()"))
            for table, column, column_type in rows:
                if column in columns.get(table, {}):
                    columns[table][column] = (column_type, columns[table][column][1])

    enums = {}
    if engine.dialect.name == "postgresql":
        with engine.connect() as conn:
            for typname, label in conn.execute(text("SELECT t.typname, e.enumlabel FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid")):
                enums.setdefault(typname, set()).add(label)
    return {
        "columns": columns,
        "defaults": defaults,
        "indexes": indexes,
        "unique": unique,
        "foreign_keys": foreign_keys,
        "primary_keys": primary_keys,
        "enums": enums,
    }


@pytest.fixture
def upgraded_and_fresh(db_engine, tmp_path, monkeypatch):
    """The same engine described twice: upgraded from the baseline, then built fresh from the model.

    Sequential rather than two fixtures because PostgreSQL and MariaDB are one shared database — the
    two phases cannot coexist, so the first is described before the second wipes it.
    """
    uri = _product_uri(db_engine, tmp_path)
    monkeypatch.setenv("DATABASE_URI", uri)
    monkeypatch.chdir(ALEMBIC)

    _wipe(uri)
    engine = create_engine(uri)
    _baseline_metadata().create_all(engine)
    engine.dispose()

    # Set exactly as `entrypoint.sh:105` seds it into alembic.ini before invoking alembic, and for
    # the same reason: `alembic/env.py:36-38` also derives it from the URI scheme, but too late to
    # matter. `command.stamp` builds its `ScriptDirectory` from the config *before* running env.py
    # (alembic/command.py: `from_config` then `run_env`), so `version_locations` is already frozen
    # by the time env.py assigns it. Drop this line and every dialect fails to locate its own
    # baseline revision.
    config = Config("alembic.ini")
    config.set_main_option("version_locations", f"{db_engine}_versions")
    command.stamp(config, _revision_for(BASELINE_VERSION, db_engine))
    command.upgrade(config, "head")

    engine = create_engine(uri)
    Base.metadata.create_all(engine, checkfirst=True)  # what initialization.py does next
    upgraded = _describe(engine)
    engine.dispose()

    _wipe(uri)
    engine = create_engine(uri)
    Base.metadata.create_all(engine)
    fresh = _describe(engine)
    engine.dispose()

    return upgraded, fresh


def test_the_baseline_really_is_older_than_the_model(upgraded_and_fresh):
    """Anti-vacuity. If the baseline schema ever stops differing from the current one — a tag bump,
    a `git show` that silently returned the working tree — every assertion below passes for free."""
    baseline = _baseline_metadata()

    assert set(Base.metadata.tables) - set(baseline.tables), "the baseline declares every table the model does; it is not an older schema"


def test_every_table_the_model_declares_survives_the_upgrade(upgraded_and_fresh):
    upgraded, _ = upgraded_and_fresh
    missing = sorted(set(Base.metadata.tables) - set(upgraded["columns"]))

    assert not missing, f"tables absent after upgrade + create_all: {missing}"


def test_every_column_the_model_declares_exists_after_the_upgrade(upgraded_and_fresh):
    """The one that fails today.

    `create_all(checkfirst=True)` skips a table that already exists, so a column added to the model
    without a matching `add_column` never reaches an upgraded database — only a fresh one. The two
    installs then run the same code against different schemas.
    """
    upgraded, _ = upgraded_and_fresh

    missing = []
    for name, table in sorted(Base.metadata.tables.items()):
        present = upgraded["columns"].get(name)
        if present is None:
            continue  # a missing table is the test above; do not report it twice as N columns
        missing += [f"{name}.{column.name}" for column in table.columns if column.name not in present]

    assert not missing, "columns the model declares that an upgraded database never gets:\n  " + "\n  ".join(missing)


def test_column_types_match_between_an_upgraded_and_a_fresh_database(upgraded_and_fresh):
    """Only columns present on both sides — an absent one is the test above, and reporting it here
    too would bury a type mismatch under a list of things that are simply missing.

    A migration is free to `add_column` with a type that is not the one the model declares, and
    nothing else in the suite would notice: both databases have the column, queries against both
    succeed, and the difference only surfaces as a truncated value or a rejected insert in
    production.
    """
    upgraded, fresh = upgraded_and_fresh

    drift = []
    for table, fresh_columns in sorted(fresh["columns"].items()):
        upgraded_columns = upgraded["columns"].get(table, {})
        for column, (fresh_type, _) in sorted(fresh_columns.items()):
            upgraded_type = upgraded_columns.get(column, (None, None))[0]
            if upgraded_type is not None and upgraded_type != fresh_type:
                drift.append(f"{table}.{column}: upgraded={upgraded_type} fresh={fresh_type}")

    assert not drift, "columns whose type differs between an upgraded and a fresh database:\n  " + "\n  ".join(drift)


def test_column_nullability_matches_between_an_upgraded_and_a_fresh_database(upgraded_and_fresh):
    """A column that is NOT NULL on a fresh install and nullable on an upgraded one lets rows exist
    that the model says cannot, and the constraint only bites the operator who reinstalls."""
    upgraded, fresh = upgraded_and_fresh

    drift = []
    for table, fresh_columns in sorted(fresh["columns"].items()):
        upgraded_columns = upgraded["columns"].get(table, {})
        for column, (_, fresh_nullable) in sorted(fresh_columns.items()):
            if column not in upgraded_columns:
                continue
            upgraded_nullable = upgraded_columns[column][1]
            if upgraded_nullable != fresh_nullable:
                drift.append(f"{table}.{column}: upgraded nullable={upgraded_nullable} fresh nullable={fresh_nullable}")

    assert not drift, "columns whose nullability differs between an upgraded and a fresh database:\n  " + "\n  ".join(drift)


def _shared_tables(upgraded, fresh, dimension):
    """Tables described on both sides. A table missing entirely is the table test's job, and letting
    it also surface here would bury a real structural difference under a table's worth of noise."""
    return [table for table in sorted(fresh[dimension]) if table in upgraded[dimension]]


def _compare_sets(upgraded, fresh, dimension, render):
    """Per-table set difference in both directions.

    `missing` is the defect `create_all(checkfirst=True)` produces — the model declares it, the
    upgraded database never got it. `extra` is the opposite and usually a leftover the migrations
    built and the model later dropped; it is reported separately rather than merged, because the two
    need different fixes.
    """
    missing, extra = [], []
    for table in _shared_tables(upgraded, fresh, dimension):
        for item in sorted(fresh[dimension][table] - upgraded[dimension][table]):
            missing.append(f"{table}: {render(item)}")
        for item in sorted(upgraded[dimension][table] - fresh[dimension][table]):
            extra.append(f"{table}: {render(item)}")
    return missing, extra


def _report(missing, extra, what):
    lines = [f"MISSING after upgrade — {what} the model declares that an upgraded database never gets:"] + [f"  {m}" for m in missing] if missing else []
    if extra:
        lines += [f"EXTRA after upgrade — {what} an upgraded database has and a fresh one does not:"] + [f"  {e}" for e in extra]
    return "\n" + "\n".join(lines)


def test_indexes_match_between_an_upgraded_and_a_fresh_database(upgraded_and_fresh):
    """`create_all(checkfirst=True)` skips an existing table, and it skips that table's indexes with
    it. An index added to the model against an existing table therefore only ever exists on a fresh
    install; the upgraded one keeps doing sequential scans and nothing fails, it is just slower on
    the databases that have grown large enough to care.

    Compared by columns and uniqueness, never by name — see `_index_shape`.

    **Partially blind on SQLite, on purpose rather than by accident.** SQLAlchemy's SQLite reflection
    excludes `sqlite_autoindex_*`, the index it creates automatically behind a UNIQUE constraint —
    `PRAGMA index_list` reports three on a fresh `bw_resource_attachments` and `get_indexes` returns
    two. So index drift whose origin is a unique constraint cannot be seen here on SQLite. It is seen
    by `test_unique_constraints_match_...` instead, which is why this is a documented limitation and
    not a skip: the check still covers every index that is not backing a constraint, and skipping it
    outright would trade real coverage for tidiness.
    """
    upgraded, fresh = upgraded_and_fresh

    assert sum(len(shapes) for shapes in fresh["indexes"].values()), "no indexes reflected on a fresh install; this comparison would pass vacuously"

    missing, extra = _compare_sets(upgraded, fresh, "indexes", lambda i: f"columns={list(i[0])} unique={i[1]}")

    assert not (missing or extra), _report(missing, extra, "indexes")


def test_unique_constraints_match_between_an_upgraded_and_a_fresh_database(upgraded_and_fresh):
    """The correctness half of the index check. A UNIQUE the model declares and an upgraded database
    never gets means that database will happily accept duplicate rows a fresh install rejects — and
    the divergence is invisible until someone tries to add the constraint later and finds they
    cannot, because the duplicates are already there.
    """
    upgraded, fresh = upgraded_and_fresh

    assert sum(len(c) for c in fresh["unique"].values()), "no unique constraints reflected on a fresh install; this comparison would pass vacuously"

    missing, extra = _compare_sets(upgraded, fresh, "unique", lambda u: f"unique{list(u)}")

    assert not (missing or extra), _report(missing, extra, "unique constraints")


def test_foreign_keys_match_between_an_upgraded_and_a_fresh_database(upgraded_and_fresh):
    """Including `ON DELETE`/`ON UPDATE`, which is the part worth the reflection: a foreign key that
    exists on both sides but cascades on one and restricts on the other deletes different rows, and
    no column, type or nullability check would ever see it."""
    upgraded, fresh = upgraded_and_fresh

    assert sum(len(f) for f in fresh["foreign_keys"].values()), "no foreign keys reflected on a fresh install; this comparison would pass vacuously"

    missing, extra = _compare_sets(upgraded, fresh, "foreign_keys", lambda f: f"{list(f[0])} -> {f[1]}{list(f[2])} ondelete={f[3]} onupdate={f[4]}")

    assert not (missing or extra), _report(missing, extra, "foreign keys")


def test_server_defaults_match_between_an_upgraded_and_a_fresh_database(upgraded_and_fresh):
    """A column that exists on both sides but defaults differently.

    Only columns present on both are compared: an absent column is the column test, and a default is
    not a meaningful thing to say about a column that does not exist.
    """
    upgraded, fresh = upgraded_and_fresh

    declared = [default for table in fresh["defaults"].values() for default in table.values() if default is not None]
    assert declared, "no server defaults reflected on a fresh install; this comparison would pass vacuously"

    drift = []
    for table in _shared_tables(upgraded, fresh, "defaults"):
        for column, fresh_default in sorted(fresh["defaults"][table].items()):
            if column not in upgraded["defaults"][table]:
                continue
            upgraded_default = upgraded["defaults"][table][column]
            if upgraded_default != fresh_default:
                drift.append(f"{table}.{column}: upgraded={upgraded_default!r} fresh={fresh_default!r}")

    assert not drift, "columns whose server default differs between an upgraded and a fresh database:\n  " + "\n  ".join(drift)


def test_primary_keys_match_between_an_upgraded_and_a_fresh_database(upgraded_and_fresh):
    """Primary key shape, composite keys included. Cheap to reach from the same reflection, and a
    key whose column order or membership differs is a different table however similar it looks."""
    upgraded, fresh = upgraded_and_fresh

    assert any(fresh["primary_keys"].values()), "no primary keys reflected on a fresh install; this comparison would pass vacuously"

    drift = []
    for table in _shared_tables(upgraded, fresh, "primary_keys"):
        if upgraded["primary_keys"][table] != fresh["primary_keys"][table]:
            drift.append(f"{table}: upgraded={list(upgraded['primary_keys'][table])} fresh={list(fresh['primary_keys'][table])}")

    assert not drift, "tables whose primary key differs between an upgraded and a fresh database:\n  " + "\n  ".join(drift)


def test_enum_labels_match_between_an_upgraded_and_a_fresh_database(upgraded_and_fresh, db_engine):
    """PostgreSQL only — it is the one backend where an enum is a *type* rather than a check
    constraint or a VARCHAR, so a value the model added has to be migrated in with
    `ALTER TYPE ... ADD VALUE` and can be forgotten.

    `postgresql_versions/b745cae3a655_..._1_7_0_beta.py` does exactly that for `web_cache`,
    `resource_groups` and `certificates`. The migration *not raising* is only half the answer; this
    is the other half. Note the label check passing here says nothing about PostgreSQL 11 or older,
    where `ADD VALUE` cannot run inside a transaction at all — the compose pins `postgres:16`.
    """
    if db_engine != "postgresql":
        pytest.skip(f"enum types are a PostgreSQL concept; {db_engine} stores these as plain values")

    upgraded, fresh = upgraded_and_fresh

    drift = []
    for name, fresh_labels in sorted(fresh["enums"].items()):
        upgraded_labels = upgraded["enums"].get(name)
        if upgraded_labels is None:
            drift.append(f"{name}: absent after upgrade, {len(fresh_labels)} labels when fresh")
        elif upgraded_labels != fresh_labels:
            drift.append(f"{name}: missing after upgrade {sorted(fresh_labels - upgraded_labels)}, extra {sorted(upgraded_labels - fresh_labels)}")

    assert fresh["enums"], "no ENUM types found on a fresh PostgreSQL install; this test would pass vacuously"
    assert not drift, "ENUM types whose labels differ between an upgraded and a fresh database:\n  " + "\n  ".join(drift)


def test_no_engine_directory_has_two_migrations_for_the_same_version():
    """`entrypoint.sh:109` resolves a version to a revision by globbing the filename.

    It takes `*_upgrade_to_version_<version>.py` and pipes the result through `awk -F_ '{print $1}'`,
    so two files matching one version give it a two-line REVISION and `alembic stamp` fails on a
    database that is otherwise perfectly upgradable. `_revision_for` above asserts this for the one
    version it is asked about; nothing asserted it for the set, which is what porting dev's
    revisions into these directories puts at risk -- a version that exists on both branches under
    two different revision ids leaves two files behind and breaks the upgrade for that version only.
    """
    collisions, total = [], 0
    for directory in sorted(ALEMBIC.glob("*_versions")):
        seen = {}
        for path in sorted(directory.glob("*_upgrade_to_version_*.py")):
            version = path.name.split("_upgrade_to_version_", 1)[1]
            seen.setdefault(version, []).append(path.name)
            total += 1
        collisions += [f"{directory.name}: {version} -> {names}" for version, names in sorted(seen.items()) if len(names) > 1]

    assert total > 100, f"only {total} migration files found across all engines; this test would pass near-vacuously"
    assert not collisions, "versions with more than one migration file, which entrypoint.sh cannot resolve:\n  " + "\n  ".join(collisions)
