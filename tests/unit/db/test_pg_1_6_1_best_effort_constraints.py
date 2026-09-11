"""`postgresql_versions/8c096ca1beb8` adds three constraints a legacy database can legally refuse.

`bw_jobs_cache.job_name` can be orphaned, `bw_plugin_pages` can hold two rows for one plugin, and
`bw_settings.name` was not unique before 1.6.0 (`v1.5.6:model.py:67-72` -- `PRIMARY KEY (id, name)` +
`UNIQUE (id)`). Until 1.7 those three `ADD CONSTRAINT`s ran on a SECOND connection whose every error
was printed and dropped, which is also what made the whole chain self-deadlock on PostgreSQL.

Removing the second connection is the fix. Removing the tolerance with it is not: alembic runs the
entire chain in ONE transaction (`alembic/env.py:803-804`) and PostgreSQL poisons a transaction on any
error, so one orphan row would roll back the entire chain and the scheduler would never start.
Measured, on a throwaway `postgres:16` stamped `f85e36780e55` -- the population that upgrades fine
today: without the SAVEPOINT the chain aborts with `ForeignKeyViolation` / `UniqueViolation`
(`.cache/wave19-2026-09-10/red-ALB-data-abort.txt`); with it, it completes and warns
(`green-ALB-data-savepoints.txt`).

**Why this file asserts on the SAVEPOINT itself and not only on the outcome.** SQLite does NOT poison
a transaction on a statement error, so on SQLite the write after a refused constraint survives whether
or not a savepoint was ever opened -- an outcome-only test passes with `begin_nested()` deleted, which
is exactly the mutation that would restore the abort on every PostgreSQL upgrade. Measured, not
assumed: an earlier version of this file asserted only the outcome and passed on SQLite with
`begin_nested()` deleted. So the behavioural tests do two things: they run on every configured engine
(`db_engine`, so `--db-engines=postgresql` makes them load-bearing against the backend that actually
poisons), and they assert through SQLAlchemy's `savepoint` / `rollback_savepoint` events that the
SAVEPOINT was really emitted and really rolled back. That second half is what fails on ALL THREE
engines the moment the mutation lands -- measured, `red-ALB-savepoint-test.txt`: helper kept,
`with connection.begin_nested():` removed, 6 failed / 2 passed.

The structural tests are the other half: they stop a fourth constraint from being routed around the
helper, which no behavioural test would notice.
"""

import ast
from importlib.util import module_from_spec, spec_from_file_location

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError

from db.alembic_baseline import ALEMBIC
from fixtures.db_factory import resolve_uri
from fixtures.engines import _with_driver

REVISION = ALEMBIC / "postgresql_versions" / "8c096ca1beb8_upgrade_to_version_1_6_1_rc1.py"

# The helper's three call sites, and the two op spellings a fourth constraint would arrive as.
EXPECTED_HELPER_CALLS = 3
CONSTRAINT_OPS = ("create_unique_constraint", "create_foreign_key", "create_primary_key", "create_check_constraint")


@pytest.fixture(scope="module")
def revision_module():
    """The revision imported as a module. Import runs only the revision identifiers, never a migration."""
    spec = spec_from_file_location("bw_rev_8c096ca1beb8", REVISION)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def probe(db_engine, tmp_path):
    """A throwaway table on the engine under test, plus a log of every SAVEPOINT event seen."""
    engine = create_engine(_with_driver(resolve_uri(db_engine, tmp_path)))
    seen = []
    event.listen(engine, "savepoint", lambda connection, name: seen.append("savepoint"))
    event.listen(engine, "rollback_savepoint", lambda connection, name, context: seen.append("rollback"))

    metadata = MetaData()
    Table("bw_alb_probe", metadata, Column("id", Integer, primary_key=True), Column("name", String(16)))
    metadata.drop_all(engine)
    metadata.create_all(engine)
    try:
        yield engine, seen
    finally:
        metadata.drop_all(engine)
        engine.dispose()


def test_a_constraint_the_data_refuses_does_not_poison_the_transaction(revision_module, probe):
    """The whole point: the failure rolls back to the savepoint, and the transaction survives it."""
    engine, seen = probe

    with engine.connect() as connection:
        with connection.begin():
            connection.execute(text("INSERT INTO bw_alb_probe (id, name) VALUES (1, 'dup'), (2, 'dup')"))

            revision_module.add_constraint_if_the_data_allows(
                connection, "bw_alb_probe", "bw_alb_probe_name_key", "CREATE UNIQUE INDEX bw_alb_probe_name_key ON bw_alb_probe (name)"
            )

            # Still usable. On PostgreSQL this is the statement that fails without the savepoint.
            connection.execute(text("INSERT INTO bw_alb_probe (id, name) VALUES (3, 'other')"))

        rows = connection.execute(text("SELECT id FROM bw_alb_probe ORDER BY id")).scalars().all()

    assert seen == ["savepoint", "rollback"], (
        "the refused constraint did not go through a SAVEPOINT that was then rolled back — "
        f"SQLAlchemy reported {seen or 'no savepoint events at all'}. Without it PostgreSQL aborts the "
        "whole migration chain on the first legacy row that refuses a constraint."
    )
    assert rows == [1, 2, 3], "the write after the refused constraint was lost — the failure was not contained"


def test_a_constraint_the_data_allows_is_actually_created(revision_module, probe):
    """The other direction, so the helper cannot pass by never doing anything."""
    engine, seen = probe

    with engine.connect() as connection:
        with connection.begin():
            connection.execute(text("INSERT INTO bw_alb_probe (id, name) VALUES (1, 'a'), (2, 'b')"))
            revision_module.add_constraint_if_the_data_allows(
                connection, "bw_alb_probe", "bw_alb_probe_name_key", "CREATE UNIQUE INDEX bw_alb_probe_name_key ON bw_alb_probe (name)"
            )
        # The constraint is really there: a duplicate is now refused by the database, not by us.
        with pytest.raises(SQLAlchemyError):
            with connection.begin():
                connection.execute(text("INSERT INTO bw_alb_probe (id, name) VALUES (3, 'a')"))

    assert seen == ["savepoint"], f"expected a committed savepoint and no rollback, got {seen}"


def test_every_constraint_the_revision_adds_goes_through_the_helper():
    """Structural: a fourth constraint added straight onto `connection.execute` or through alembic's
    own `op.create_*_constraint` would abort the chain on the first legacy database that refuses it,
    and no behavioural test here would see it."""
    tree = ast.parse(REVISION.read_text(encoding="utf-8"), filename=str(REVISION))
    upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")

    unguarded = []
    for node in ast.walk(upgrade):
        if not isinstance(node, ast.Call):
            continue
        called = ast.unparse(node.func)
        if called.endswith(".execute") and "ADD CONSTRAINT" in ast.unparse(node):
            unguarded.append(f"{node.lineno}: {called} with a raw ADD CONSTRAINT")
        elif called.rsplit(".", 1)[-1] in CONSTRAINT_OPS:
            unguarded.append(f"{node.lineno}: {called}")

    assert not unguarded, (
        "a constraint is added outside add_constraint_if_the_data_allows(), so a legacy database that "
        "refuses it would abort the whole migration chain:\n  " + "\n  ".join(unguarded)
    )


def test_the_helper_is_used_three_times():
    """Anti-rot for the test above: it passes vacuously the day the helper stops being called at all."""
    tree = ast.parse(REVISION.read_text(encoding="utf-8"), filename=str(REVISION))
    upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
    calls = [n for n in ast.walk(upgrade) if isinstance(n, ast.Call) and ast.unparse(n.func) == "add_constraint_if_the_data_allows"]

    assert len(calls) == EXPECTED_HELPER_CALLS, f"expected the revision's three best-effort constraints, found {len(calls)}"
