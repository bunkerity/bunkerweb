"""`save_config` must never touch its session from a `ThreadPoolExecutor` thread.

The multisite branch fans the per-service pass out over a `ThreadPoolExecutor`. The
global-settings pass used to be submitted to that same executor **with the session** -- which is
the `scoped_session` registry, not a `Session`. Reading it from a pool thread hands that thread a
Session of its own; `_db_session`'s `finally` removes the *calling* thread's, and nothing ever
removes the worker's. The pool thread was left `idle in transaction` on

    SELECT bw_global_values.value, bw_global_values.file_name, bw_global_values.method ...

holding an ACCESS SHARE lock until the connection was recycled. In the unit matrix a later test's
`reset_schema` then blocked on `DROP TABLE bw_global_values` forever -- PostgreSQL and MariaDB
deadlocked, SQLite hid it (no server-side locks). In production the same leak parks that lock
inside a long-lived scheduler/API process.

**Why this is the cause and not the symptom.** The symptom is not reliably reachable from one
test: whether the orphaned Session survives long enough to block anything depends on when the
interpreter reclaims it after the worker thread is joined, which is why the matrix deadlocked on
the *18th* test of a file rather than the first. A single-shot "is anything idle in transaction"
probe passes on the broken code and would be worthless as a regression guard. The invariant
underneath is exact and always observable: a `Session` is not thread-safe, so `save_config` must
use its session only from the thread that opened it. That is what is asserted here, and it holds
for any future pass someone hands to that executor, not just the one that leaked.

End-to-end evidence lives in the lane report: `tests/unit/db/test_config_save_cleanup_methods.py`
on PostgreSQL went from a hang (killed after 18 of 30 tests) to `30 passed in 9.14s`.
"""

from threading import get_ident

import pytest

from sqlalchemy import select

from fixtures.seed import seed_multisite
from model import Global_values, Services_settings

pytestmark = pytest.mark.slow


class _ThreadWatchedSession:
    """Delegates to the real scoped session and records every access from a foreign thread.

    `_db_session` yields `self._session_factory` itself, so swapping in this wrapper puts it
    exactly where `save_config` reads from. Attribute *access* is what is recorded, not query
    execution: `session.execute(...)` resolves the attribute on the caller's thread, and a worker
    that only reads `session.no_autoflush` has still bound a Session to itself.
    """

    def __init__(self, inner):
        self._inner = inner
        self._owner = get_ident()
        self.foreign_accesses = []
        self.owner_accesses = 0

    def __getattr__(self, name):
        if get_ident() == self._owner:
            self.owner_accesses += 1
        else:
            self.foreign_accesses.append((name, get_ident()))
        return getattr(self._inner, name)


def _multisite_save(db):
    """A save that reaches the multisite branch, i.e. the fanned-out pass."""
    return db.save_config(
        {
            "MULTISITE": "yes",
            "SERVER_NAME": "app1.example.com app2.example.com",
            "SECURITY_MODE": "detect",
            "app1.example.com_SECURITY_MODE": "block",
            "app2.example.com_USE_REVERSE_PROXY": "yes",
        },
        "ui",
    )


def test_save_config_never_uses_its_session_from_a_worker_thread(db):
    seed_multisite(db)

    watched = _ThreadWatchedSession(db._session_factory)
    db._session_factory = watched
    try:
        _multisite_save(db)
    finally:
        db._session_factory = watched._inner

    # Liveness first: `_db_session` yields `self._session_factory` today, but a refactor that
    # cached the factory or yielded a real Session would route around the wrapper, and the
    # foreign-access assertion below would then pass while measuring nothing at all.
    assert watched.owner_accesses > 0, "the wrapper was never consulted -- this test no longer observes save_config's session"

    assert watched.foreign_accesses == [], (
        "save_config used its scoped session from a ThreadPoolExecutor thread; that thread gets a "
        f"Session nobody removes, left idle in transaction on bw_global_values: {watched.foreign_accesses}"
    )


def test_the_multisite_save_this_file_pins_really_reaches_the_fanned_out_pass(db):
    """RULE 13: the assertion above is vacuous if the save never enters the multisite branch.

    `_sc_process_global_settings` is what leaked, and it only runs when MULTISITE is "yes" and
    service management is on.

    Both rows below are asserted because the SAVE produces them, never because the fixture
    seeded them -- the first version of this test checked `MULTISITE=yes` and
    `SECURITY_MODE=detect`, which `seed_multisite` inserts itself, and it therefore still
    reported "passed" with `save_config` replaced by a no-op. The `method` column is the tell:
    the seeded rows are `scheduler`, anything this save wrote is `ui`.
    """
    seed_multisite(db)
    _multisite_save(db)

    with db._db_session() as session:
        global_rows = {
            (row.setting_id, row.suffix or 0): (row.value, row.method)
            for row in session.execute(select(Global_values.setting_id, Global_values.suffix, Global_values.value, Global_values.method))
        }
        service_rows = {
            (row.service_id, row.setting_id): (row.value, row.method)
            for row in session.execute(select(Services_settings.service_id, Services_settings.setting_id, Services_settings.value, Services_settings.method))
        }

    # written by the global-settings pass -- the one that leaked
    assert global_rows.get(("SERVER_NAME", 0)) == ("app1.example.com app2.example.com", "ui"), global_rows
    # written by the per-service pass -- still on the executor, and proof the fan-out ran
    assert service_rows.get(("app2.example.com", "USE_REVERSE_PROXY")) == ("yes", "ui"), service_rows
