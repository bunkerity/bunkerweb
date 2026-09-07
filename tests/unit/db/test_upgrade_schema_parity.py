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

**One exception, and it is the product's, not the test's: the `v1.5.0-beta` full-chain start cannot
run on PostgreSQL** (`START_ENGINES`, which carries the mechanism and the revision line numbers).
There it does not red, it deadlocks with itself and hangs for ever. The skip is explicit and says so;
it is never a silent engine skip.

That start DOES run on MariaDB, and has to: **the MariaDB chain produces drift the SQLite chain does
not**, so a run without it would report a clean upgrade that is not clean. `KNOWN_LEGACY_DRIFT`
records three of them — `bw_ui_users` loses its primary key outright, `bw_settings` keeps the
two-column one the 1.5.0-beta model declared, and `bw_template_custom_configs.step_id` stays
nullable. None of the three is reachable on SQLite, whose chain rebuilds those tables instead of
altering them in place. Every fix is a migration and the Alembic tree is frozen for 1.7, so they are
recorded with per-shape anti-rot assertions that red the day 1.8 closes any one of them — never
skipped, never widened, never silently tolerated.
"""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from db.alembic_baseline import ALEMBIC, BASELINE_TAG, BASELINE_VERSION, LEGACY_TAG, baseline_metadata, product_uri, revision_for, wipe
from model import Base  # type: ignore


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


# Two starting points, and they are not the same test. The 1.6.13 one is what an operator upgrading
# from the last stable 1.6 really runs, and it is cheap -- one stamp, then the handful of revisions
# above it. It is also the one L-G measured as GREEN while 33 columns of server-default drift were
# present (`report-L-G.md` follow-up 6): its starting schema was tagged `model.py`, a shape that
# never carried those defaults, so nothing on either side could disagree about them.
#
# The 1.5.0-beta one is the answer to that. It creates the schema the oldest supported release
# really shipped and then runs the WHOLE chain -- all 78 revisions, root included, no stamp -- so
# every column, default, index and constraint on the upgraded side is one a migration actually
# produced rather than one `create_all` handed it for free. It is the shape that would have caught
# that class in the first place, which is why it is here rather than in a comment.
STARTING_POINTS = {
    # tag -> the version to stamp before upgrading, or None to run the chain from its root.
    BASELINE_TAG: BASELINE_VERSION,
    LEGACY_TAG: None,
}

# The engines each start may run on. The 1.6.13 one runs everywhere. The 1.5.0-beta one runs
# everywhere EXCEPT PostgreSQL, where it cannot be run at all: it does not fail, it HANGS FOR EVER.
# `alembic/env.py:803-804` wraps the whole chain in ONE transaction, so by 1.6.0 that transaction
# holds `AccessExclusiveLock` on `bw_jobs` (`postgresql_versions/0b08c406d820:176`), and
# `postgresql_versions/8c096ca1beb8:22-38` then opens a SECOND connection to run
# `ALTER TABLE bw_jobs DROP CONSTRAINT` on that same table. The second waits for a lock the first
# will not release until `upgrade()` returns, and `upgrade()` cannot return until the second
# finishes -- a self-deadlock the server cannot detect, because the holder is waiting on its client
# socket rather than on a lock, so there is no cycle in the lock graph. Measured: the upgrade sat on
# `pg_blocking_pids` for as long as it was left running, with both backends on `bw_jobs`.
#
# `bw_jobs` is not even the only way in. `8c096ca1beb8:68` runs `UPDATE bw_metadata SET version …
# WHERE id = 1` on that same second connection, and every revision from 1.6.0-rc2 to 1.6.0
# (`b56eb8d8dbf2:50`, `c975711f7afa:24`, `7939f7165327:24`, `f85e36780e55:24`) updates that one row
# inside the outer transaction -- so a chain that touches `bw_jobs` nowhere still deadlocks on a
# single row. Only a database already stamped at `f85e36780e55` (1.6.0) escapes both.
#
# MariaDB runs, and it is the engine that pays for this variant: it is the only one that reports the
# three drifts recorded in KNOWN_LEGACY_DRIFT below, because its chain alters those tables in place
# where the SQLite chain rebuilds them.
START_ENGINES = {LEGACY_TAG: ("sqlite", "mariadb")}


@pytest.fixture(params=sorted(STARTING_POINTS), ids=lambda tag: f"from-{tag}")
def baseline_start(request):
    """The release an upgraded database starts from, and how the product would enter the chain."""
    return request.param, STARTING_POINTS[request.param]


# `(engine, tag)` -> the two descriptions, built once per session.
#
# The fixture below has to be function-scoped -- `tmp_path` and `monkeypatch` are -- so without this
# every one of the ten comparisons rebuilt the whole thing from scratch. That was already ten
# upgrades per engine before this file was parametrised; with the 1.5.0-beta start added it becomes
# ten more, and each of those runs all 78 revisions rather than stamping past 60 of them. Measured
# on this workstation the SQLite run of this whole file is 4.75s with the memo, against 53s without
# it (re-measured 2026-09-07; an earlier 8.65s and an independent 12.63s were taken on the same host
# under different load, so treat the order of magnitude as the claim, not the digits). The
# three-engine run that once "completed 3 of ~60 tests in fourteen minutes" was killed undiagnosed;
# it is CONSISTENT with the PostgreSQL deadlock described at START_ENGINES, but that was never
# confirmed, and the memo is a real speedup either way.
#
# Safe to share: both values are plain nested dicts of reflected names, built and never mutated
# afterwards, and every test below only reads them. What must NOT be cached is the database itself —
# and it is not: the entry is stored only after both descriptions are taken, so a later test never
# depends on the state the shared PostgreSQL/MariaDB database happens to be in.
_DESCRIPTIONS: dict = {}


@pytest.fixture
def upgraded_and_fresh(db_engine, tmp_path, monkeypatch, baseline_start):
    """The same engine described twice: upgraded from the baseline, then built fresh from the model.

    Sequential rather than two fixtures because PostgreSQL and MariaDB are one shared database — the
    two phases cannot coexist, so the first is described before the second wipes it.
    """
    tag, stamp_version = baseline_start
    allowed = START_ENGINES.get(tag)
    if allowed is not None and db_engine not in allowed:
        pytest.skip(
            f"the {tag} full-chain start cannot run on {db_engine} — it self-deadlocks and hangs there rather than failing "
            f"(alembic runs the whole chain in one transaction; 8c096ca1beb8 then opens a SECOND connection onto rows that "
            f"transaction already holds). It runs on {'/'.join(allowed)}. Mechanism: see START_ENGINES in this file."
        )
    if (db_engine, tag) in _DESCRIPTIONS:
        return _DESCRIPTIONS[(db_engine, tag)]
    uri = product_uri(db_engine, tmp_path)
    monkeypatch.setenv("DATABASE_URI", uri)
    monkeypatch.chdir(ALEMBIC)

    wipe(uri)
    engine = create_engine(uri)
    baseline_metadata(tag).create_all(engine)
    engine.dispose()

    # Set exactly as `entrypoint.sh:105` seds it into alembic.ini before invoking alembic, and for
    # the same reason: `alembic/env.py:36-38` also derives it from the URI scheme, but too late to
    # matter. `command.stamp` builds its `ScriptDirectory` from the config *before* running env.py
    # (alembic/command.py: `from_config` then `run_env`), so `version_locations` is already frozen
    # by the time env.py assigns it. Drop this line and every dialect fails to locate its own
    # baseline revision.
    config = Config("alembic.ini")
    config.set_main_option("version_locations", f"{db_engine}_versions")
    # No stamp for the 1.5.0-beta start, deliberately: an empty `alembic_version` is what makes
    # alembic run from the root, and the root revision has real work to do on that schema
    # (`bw_plugins.order` is dropped there). Stamping it would skip the only revision the older
    # baseline exists to exercise.
    if stamp_version is not None:
        command.stamp(config, revision_for(stamp_version, db_engine))
    command.upgrade(config, "head")

    engine = create_engine(uri)
    Base.metadata.create_all(engine, checkfirst=True)  # what initialization.py does next
    upgraded = _describe(engine)
    engine.dispose()

    wipe(uri)
    engine = create_engine(uri)
    Base.metadata.create_all(engine)
    fresh = _describe(engine)
    engine.dispose()

    _DESCRIPTIONS[(db_engine, tag)] = (upgraded, fresh)
    return upgraded, fresh


@pytest.mark.parametrize("tag", sorted(STARTING_POINTS))
def test_the_baseline_really_is_older_than_the_model(tag):
    """Anti-vacuity. If the baseline schema ever stops differing from the current one — a tag bump,
    a `git show` that silently returned the working tree — every assertion below passes for free.

    Takes no engine and no fixture: it is a property of the two `model.py` revisions, so paying for
    a database (and a 78-revision upgrade) to assert it would only make it slower.
    """
    baseline = baseline_metadata(tag)

    assert set(Base.metadata.tables) - set(baseline.tables), f"the {tag} baseline declares every table the model does; it is not an older schema"


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


def test_column_nullability_matches_between_an_upgraded_and_a_fresh_database(upgraded_and_fresh, baseline_start, db_engine):
    """A column that is NOT NULL on a fresh install and nullable on an upgraded one lets rows exist
    that the model says cannot, and the constraint only bites the operator who reinstalls.

    One of the two reasons the 1.5.0-beta start runs on MariaDB and not on SQLite alone:
    `bw_template_custom_configs.step_id` is recorded drift there (`KNOWN_LEGACY_DRIFT`) and does not
    exist on SQLite at all, whose chain rebuilds that table instead of altering it in place. SQLite
    reflects nullability perfectly well — it is the migration path that differs, not the reflection.
    """
    upgraded, fresh = upgraded_and_fresh
    tag, _ = baseline_start

    observed = {}
    for table, fresh_columns in sorted(fresh["columns"].items()):
        upgraded_columns = upgraded["columns"].get(table, {})
        for column, (_, fresh_nullable) in sorted(fresh_columns.items()):
            if column not in upgraded_columns:
                continue
            upgraded_nullable = upgraded_columns[column][1]
            if upgraded_nullable != fresh_nullable:
                observed.setdefault(table, set()).add((column, upgraded_nullable, fresh_nullable))

    residual = _forgive(observed, _recorded(db_engine, tag, "nullability"), "nullability", db_engine)
    drift = [
        f"{table}.{column}: upgraded nullable={upgraded_nullable} fresh nullable={fresh_nullable}"
        for table, columns in sorted(residual.items())
        for column, upgraded_nullable, fresh_nullable in sorted(columns)
    ]

    assert not drift, "columns whose nullability differs between an upgraded and a fresh database:\n  " + "\n  ".join(drift)


def _shared_tables(upgraded, fresh, dimension):
    """Tables described on both sides. A table missing entirely is the table test's job, and letting
    it also surface here would bury a real structural difference under a table's worth of noise."""
    return [table for table in sorted(fresh[dimension]) if table in upgraded[dimension]]


def _compare_sets(upgraded, fresh, dimension, render, db_engine=None, tag=None):
    """Per-table set difference in both directions.

    `missing` is the defect `create_all(checkfirst=True)` produces — the model declares it, the
    upgraded database never got it. `extra` is the opposite and usually a leftover the migrations
    built and the model later dropped; it is reported separately rather than merged, because the two
    need different fixes.

    Only EXTRA passes through `KNOWN_LEGACY_DRIFT`, and a MISSING never does: a column, index or
    constraint the model declares and an upgraded database never got is the defect this whole file
    exists for, and nothing here may wave one through.
    """
    missing, observed = [], {}
    for table in _shared_tables(upgraded, fresh, dimension):
        for item in sorted(fresh[dimension][table] - upgraded[dimension][table]):
            missing.append(f"{table}: {render(item)}")
        observed[table] = upgraded[dimension][table] - fresh[dimension][table]

    residual = _forgive(observed, _recorded(db_engine, tag, dimension), dimension, db_engine)
    extra = [f"{table}: {render(item)}" for table, shapes in residual.items() for item in sorted(shapes)]
    return missing, extra


def _report(missing, extra, what):
    lines = [f"MISSING after upgrade — {what} the model declares that an upgraded database never gets:"] + [f"  {m}" for m in missing] if missing else []
    if extra:
        lines += [f"EXTRA after upgrade — {what} an upgraded database has and a fresh one does not:"] + [f"  {e}" for e in extra]
    return "\n" + "\n".join(lines)


def test_indexes_match_between_an_upgraded_and_a_fresh_database(upgraded_and_fresh, baseline_start, db_engine):
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
    tag, _ = baseline_start

    assert sum(len(shapes) for shapes in fresh["indexes"].values()), "no indexes reflected on a fresh install; this comparison would pass vacuously"

    missing, extra = _compare_sets(upgraded, fresh, "indexes", lambda i: f"columns={list(i[0])} unique={i[1]}", db_engine, tag)

    assert not (missing or extra), _report(missing, extra, "indexes")


# What an upgrade from the 1.5.0-beta chain really leaves behind, and the ONLY drift this file
# forgives. One entry per `(engine, table)` root cause, because that is the unit the drift comes in:
# MariaDB has no constraint object of its own, so a single lost primary key surfaces at once as a
# primary-key difference, an extra unique constraint AND an extra index. Splitting that into three
# unrelated exemptions would hide the fact that they are one bug.
#
# Every entry spells out its EXACT shapes per dimension. No wildcard, no dimension-wide forgiveness,
# no "this table is exempt": a shape not listed here is still a failure, in every dimension, on every
# engine. `_forgive` asserts both halves of that on every run -- see its docstring.
#
# Engine-keyed because the same schema history materialises differently per dialect, and a record
# calibrated on one engine asserts something false on the next:
#
#   sqlite / bw_jobs                        the 1.5.0-beta model declared
#                                           `UniqueConstraint("name", "plugin_id")`, the current
#                                           model does not, and the sqlite chain never drops it.
#                                           INERT: `bw_jobs.name` is the primary key on both sides,
#                                           so a pair this rejects is one the primary key already
#                                           rejected. Absent on MariaDB, whose 1.5.6 revision DROPS
#                                           the key in `upgrade()` (`18e9d2191dcc:60`; the
#                                           `create_index` at `:82` is in `downgrade()`, which
#                                           starts at `:76`), and not reachable on PostgreSQL.
#   mariadb / bw_ui_users                   the upgrade LOSES THE PRIMARY KEY. `bfa7869e34c3` drops
#                                           the old `id` PK column and passes `primary_key=True` to
#                                           `batch_op.alter_column`, which alembic swallows into
#                                           `**kw` on a non-recreating MySQL batch, so `username`
#                                           ends up a bare UNIQUE KEY. The sqlite chain rebuilds the
#                                           table properly, which is why only MariaDB shows it.
#   mariadb / bw_settings                   a DIFFERENT class, despite looking alike: nothing in the
#                                           MariaDB `upgrade()` path narrows this key at all. The
#                                           1.5.0-beta model declared `PrimaryKeyConstraint("id",
#                                           "name")` + `UniqueConstraint("id")`, the current model
#                                           declares `id` alone, and the only PK operations on this
#                                           table anywhere in the MariaDB chain are in
#                                           `bfa7869e34c3`'s `downgrade()` (`:391-398`, past the
#                                           `def downgrade` at `:284`). A missing migration, not a
#                                           mis-emitted one.
#   mariadb / bw_template_custom_configs    `step_id` stays nullable where the model says NOT NULL.
#                                           Invisible on SQLite because that chain rebuilds the
#                                           table rather than altering it -- not because SQLite
#                                           cannot reflect nullability, which it does exactly.
#
# All four are deferred to 1.8: every fix is a migration and the Alembic tree is FROZEN for 1.7. The
# anti-rot assertions below are what make that deferral safe: the day 1.8 fixes any listed shape, the
# record stops matching, this file REDS naming the shape, and whoever fixed it deletes the entry. A
# forgiveness with no such trigger would just be coverage quietly switched off.
#
# Two of these forgive a constraint the MODEL DECLARES and an upgraded database never gets -- the
# `bw_ui_users` primary key and the `step_id` NOT NULL. That is normally the exact defect this file
# exists to catch, and they are here only because no 1.7-legal change can fix them; they are the
# reason the anti-rot above is an assertion rather than a comment.
KNOWN_LEGACY_DRIFT = {
    # 1.8: drop the residual UNIQUE(name, plugin_id) from bw_jobs -- one migration per dialect.
    ("sqlite", "bw_jobs"): {"unique": {("name", "plugin_id")}},
    # 1.8: give an upgraded MariaDB bw_ui_users its PRIMARY KEY(username) back.
    ("mariadb", "bw_ui_users"): {
        "indexes": {(("username",), True)},
        "unique": {("username",)},
        "primary_keys": {((), ("username",))},
    },
    # 1.8: narrow the upgraded MariaDB bw_settings key from (id, name) to (id), as the model declares.
    ("mariadb", "bw_settings"): {
        "indexes": {(("id",), True)},
        "unique": {("id",)},
        "primary_keys": {(("id", "name"), ("id",))},
    },
    # 1.8: re-apply NOT NULL to bw_template_custom_configs.step_id on an upgraded MariaDB.
    ("mariadb", "bw_template_custom_configs"): {"nullability": {("step_id", True, False)}},
}


def _recorded(db_engine, tag, dimension):
    """`{table: {shape, ...}}` recorded for this engine and this starting point, in this dimension.

    Empty for any start but the 1.5.0-beta one: the 1.6.13 start begins from a tagged model that had
    already been through these migrations, so it produces none of this drift and forgiving anything
    there would be a hole rather than a record.
    """
    if tag != LEGACY_TAG:
        return {}
    return {table: record[dimension] for (engine, table), record in KNOWN_LEGACY_DRIFT.items() if engine == db_engine and dimension in record}


def _forgive(observed, recorded, dimension, db_engine):
    """`observed` (`{table: {shape, ...}}`) minus EXACTLY the recorded shapes, asserting the record.

    Two properties, and the exemption is only safe while both hold:

    * **The record is still true.** Every recorded shape must still be observed. The day a 1.8
      migration fixes one, this reds and names it, and whoever fixed it deletes the entry — which is
      the only thing that stops a deferred fix from turning into permanently disabled coverage.
    * **Nothing else rides along.** The residual for a recorded table is its drift minus the listed
      shapes, never the whole table: new drift on `bw_ui_users` still fails, exactly like new drift
      on any other table.
    """
    stale = {table: sorted(shapes - observed.get(table, frozenset())) for table, shapes in recorded.items()}
    stale = {table: gone for table, gone in stale.items() if gone}
    assert not stale, (
        f"recorded 1.5.0-beta {dimension} drift is GONE from {db_engine}: {stale}. A migration fixed it — "
        f"delete those shapes from KNOWN_LEGACY_DRIFT and close the matching 1.8 note."
    )
    return {table: shapes - recorded.get(table, frozenset()) for table, shapes in observed.items()}


def test_unique_constraints_match_between_an_upgraded_and_a_fresh_database(upgraded_and_fresh, baseline_start, db_engine):
    """The correctness half of the index check. A UNIQUE the model declares and an upgraded database
    never gets means that database will happily accept duplicate rows a fresh install rejects — and
    the divergence is invisible until someone tries to add the constraint later and finds they
    cannot, because the duplicates are already there.
    """
    upgraded, fresh = upgraded_and_fresh
    tag, _ = baseline_start

    assert sum(len(c) for c in fresh["unique"].values()), "no unique constraints reflected on a fresh install; this comparison would pass vacuously"

    missing, extra = _compare_sets(upgraded, fresh, "unique", lambda u: f"unique{list(u)}", db_engine, tag)

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


def test_primary_keys_match_between_an_upgraded_and_a_fresh_database(upgraded_and_fresh, baseline_start, db_engine):
    """Primary key shape, composite keys included. Cheap to reach from the same reflection, and a
    key whose column order or membership differs is a different table however similar it looks.

    This is the comparison that catches the worst of the recorded 1.5.x drift: on MariaDB an upgraded
    `bw_ui_users` has NO primary key at all (`KNOWN_LEGACY_DRIFT`), which no column, type or index
    check would have reported.
    """
    upgraded, fresh = upgraded_and_fresh
    tag, _ = baseline_start

    assert any(fresh["primary_keys"].values()), "no primary keys reflected on a fresh install; this comparison would pass vacuously"

    observed = {
        table: {(upgraded["primary_keys"][table], fresh["primary_keys"][table])}
        for table in _shared_tables(upgraded, fresh, "primary_keys")
        if upgraded["primary_keys"][table] != fresh["primary_keys"][table]
    }
    residual = _forgive(observed, _recorded(db_engine, tag, "primary_keys"), "primary_keys", db_engine)
    drift = [f"{table}: upgraded={list(u)} fresh={list(f)}" for table, pairs in sorted(residual.items()) for u, f in sorted(pairs)]

    assert not drift, "tables whose primary key differs between an upgraded and a fresh database:\n  " + "\n  ".join(drift)


def test_enum_labels_match_between_an_upgraded_and_a_fresh_database(upgraded_and_fresh, db_engine):
    """PostgreSQL only — it is the one backend where an enum is a *type* rather than a check
    constraint or a VARCHAR, so a value the model added has to be migrated in with
    `ALTER TYPE ... ADD VALUE` and can be forgotten.

    `postgresql_versions/404a6ed42a31_..._1_7_0_beta.py` does exactly that for `web_cache`,
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
    database that is otherwise perfectly upgradable. `revision_for` asserts this for the one
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
