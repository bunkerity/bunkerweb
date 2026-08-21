"""The write probes must create a table a primary-key-enforcing server will accept.

`Database` proves it can write by creating and dropping a throwaway `test_<uuid>` table, at two
sites: the constructor's connection loop (`Database.py:376`) and `retry_connection`
(`Database.py:586`). Both used to emit `CREATE TABLE ... (id INT)`.

A table with no primary key is refused outright by several production-grade MySQL-compatible
servers -- Percona XtraDB Cluster / Galera under `pxc_strict_mode=ENFORCING`, and TiDB with
`sql_require_primary_key=ON`. On those, the probe fails for a reason that has nothing to do with
write access: the constructor logs "Can't connect to database ..." and `_exit(1)`s, and
`retry_connection` raises. The database is writable; the probe just asked for something the server
does not allow.

Ported from `dev` (`7dc8ba5ab`, "fix(db): require primary keys in write probes"). `dev` patched
three sites; 1.7 has two -- it carries no `test_write()` method.

The two tests below attack the two sites differently on purpose:

  * `retry_connection` has no `except` clause, so a rejecting server surfaces as a raised
    exception and the test can assert the real end-to-end behaviour (the probe survives).
  * the constructor swallows `OperationalError`/`DatabaseError` and `_exit(1)`s once
    `DATABASE_RETRY_TIMEOUT` expires. `os._exit` would take the pytest process down with it, so
    that site is covered by recording the DDL it actually emits rather than by rejecting it.

Both assert a `>= 1` floor on the number of probes observed: `all(...)` over an empty list is
vacuously true, and a probe that stopped running would otherwise read as a pass.
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

_UNIT = Path(__file__).resolve().parents[1]
if str(_UNIT) not in sys.path:
    sys.path.insert(0, str(_UNIT))

from fixtures.db_factory import resolve_uri  # noqa: E402
from fixtures.engines import reset_schema  # noqa: E402

PROBE_MARKER = "CREATE TABLE IF NOT EXISTS test_"


class StrictServerRejection(Exception):
    """Stand-in for what Galera/TiDB return for a table with no primary key."""


@pytest.fixture
def recorded_probes():
    """Every write-probe DDL emitted while this fixture is active, on any Engine.

    Class-level, because `retry_connection` disposes `self.sql_engine` and builds a new one:
    a listener bound to the instance we start from would not see the statement under test.
    """
    seen = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        if PROBE_MARKER in statement:
            seen.append(statement)

    event.listen(Engine, "before_cursor_execute", _record)
    try:
        yield seen
    finally:
        event.remove(Engine, "before_cursor_execute", _record)


@pytest.fixture
def primary_key_enforcing_server():
    """Reject any write probe that omits a primary key, the way `pxc_strict_mode` does."""
    seen = []

    def _enforce(conn, cursor, statement, parameters, context, executemany):
        if PROBE_MARKER in statement:
            seen.append(statement)
            if "PRIMARY KEY" not in statement.upper():
                raise StrictServerRejection(f"Percona-XtraDB-Cluster prohibits use of DDL command on a table ({statement})")

    event.listen(Engine, "before_cursor_execute", _enforce)
    try:
        yield seen
    finally:
        event.remove(Engine, "before_cursor_execute", _enforce)


def test_retry_connection_probes_a_server_that_requires_primary_keys(db, primary_key_enforcing_server):
    """The reconnect probe must go through on a server that refuses PK-less tables."""
    db.retry_connection()

    assert len(primary_key_enforcing_server) >= 1, "retry_connection emitted no write probe at all -- the test proves nothing"
    assert all("PRIMARY KEY" in statement.upper() for statement in primary_key_enforcing_server), primary_key_enforcing_server


def test_the_constructor_write_probe_declares_a_primary_key(db_engine, tmp_path, quiet_logger, _clean_env, recorded_probes):
    """The constructor's probe emits the same PK-carrying DDL.

    Asserted on the emitted statement, not on the source: `os._exit(1)` on the failure path makes
    the reject-and-watch-it-survive shape of the sibling test unsafe here.
    """
    uri = resolve_uri(db_engine, tmp_path)
    reset_schema(uri)

    from Database import Database  # noqa: E402 -- after conftest's sys.path injection

    database = Database(quiet_logger, sqlalchemy_string=uri, log=False)
    try:
        assert len(recorded_probes) >= 1, "the constructor emitted no write probe -- the test proves nothing"
        assert all("PRIMARY KEY" in statement.upper() for statement in recorded_probes), recorded_probes
    finally:
        database.close()
