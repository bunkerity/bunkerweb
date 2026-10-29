"""No revision may open a second database connection of its own.

`alembic/env.py:803-804` wraps the whole chain in ONE transaction, so a revision that reaches past
`op.get_bind()` for a connection of its own is asking the server for locks its own outer
transaction already holds. On PostgreSQL that is not an error, it is a hang the server cannot
detect: the holder is blocked on its client socket rather than on a lock, so there is no cycle in
the lock graph and no deadlock detector fires. `postgresql_versions/8c096ca1beb8` did exactly this
(`execute_with_new_transaction`, `engine.begin()`) and every database stamped below 1.6.0 hung
forever on the way to 1.7 -- `alembic upgrade head` in `scheduler/entrypoint.sh:120` has no timeout,
so the scheduler never started and never logged. Measured before the fix: `pg_blocking_pids` showed
`ALTER TABLE bw_jobs DROP CONSTRAINT ...` blocked by the outer transaction, for as long as it was
left running (`.cache/wave19-2026-09-10/red-ALB-pg-deadlock.txt`).

Static rather than live on purpose. Reproducing the hang costs a PostgreSQL container and a
timeout, and it can only ever prove the revisions that exist today; this reads every revision in
every dialect and is what a *new* one trips over. It is deliberately not a grep: `.engine` in a
comment or a docstring is not a second connection, and a regression test that cries wolf gets
deleted.
"""

import ast

import pytest

from db.alembic_baseline import ALEMBIC

DIALECTS = ("sqlite", "postgresql", "mariadb", "mysql")

# The two ways a revision can get a connection that is not the migration's own.
#   `op.get_bind().engine` / `connection.engine` -> the Engine behind the bind, whose `begin()` and
#   `connect()` both hand out a NEW connection. This is the shape `8c096ca1beb8` had.
#   `create_engine(...)` / `engine_from_config(...)` -> a whole new pool, same problem with an extra
#   password to find. Both are matched bare AND qualified: every revision in this tree does
#   `import sqlalchemy as sa`, so `sa.create_engine(...)` is the spelling a new one would reach for,
#   and matching only the bare `ast.Name` form would leave the guard blind to exactly that.
FORBIDDEN_ATTRIBUTE = "engine"
FORBIDDEN_CALLS = ("create_engine", "engine_from_config")


def second_connections(source, filename):
    """Every `<expr>.engine` and engine-constructing call in `source`, as `"line: snippet"` strings."""
    tree = ast.parse(source, filename=filename)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == FORBIDDEN_ATTRIBUTE:
            found.append(f"{node.lineno}: ...{FORBIDDEN_ATTRIBUTE} on {ast.unparse(node.value)}")
        elif isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) in FORBIDDEN_CALLS:
            found.append(f"{node.lineno}: {ast.unparse(node.func)}(...)")
    return found


@pytest.mark.parametrize("dialect", DIALECTS)
def test_no_revision_reaches_for_a_connection_of_its_own(dialect):
    versions = sorted((ALEMBIC / f"{dialect}_versions").glob("*.py"))
    assert versions, f"no revisions found for {dialect}; this guard would pass vacuously"

    offenders = {path.name: hits for path in versions if (hits := second_connections(path.read_text(encoding="utf-8"), str(path)))}

    assert not offenders, (
        f"{dialect} revisions opening a second database connection -- the whole chain runs in one "
        f"transaction, so this deadlocks (PostgreSQL) or blocks (MariaDB/MySQL) against locks the "
        f"outer transaction already holds. Use `op.get_bind()` and nothing beyond it:\n  "
        + "\n  ".join(f"{name}: {', '.join(hits)}" for name, hits in sorted(offenders.items()))
    )
