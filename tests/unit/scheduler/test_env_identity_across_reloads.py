"""``os.environ`` must keep its identity across reloads, or three readers freeze at start time.

``from os import environ`` binds the *object*, not the name ``os.environ``. Rebinding
``os.environ = base.copy()`` therefore leaves every such module pointing at the dict that
existed when it was first imported, and it keeps reading that stale dict forever. Three modules
in the scheduler process do exactly this and then read the binding at run time:

    src/scheduler/main.py:190                  handle_reload() builds the config-saver
                                               subprocess env from ``environ.items()``
    src/common/db/db_methods/metadata.py:73    returns ``environ`` as the keyring source
    src/common/utils/certificate_utils.py:29   ``values = values or environ``

The visible symptom is the nasty kind: a service or certificate key added after startup is
invisible to those three until the scheduler is restarted, while every other consumer sees it.

NOTE ON THE UPSTREAM RATIONALE. dev's ``a035b4369`` fixes the same root cause but argues it from
in-process job helpers and ``cleanup_modules``. **Neither exists here** -- 1.7 dispatches jobs to
Celery workers and ``JobScheduler`` has no ``cleanup_modules``. The defect is real in 1.7 for a
different reason, so the three readers above are the ones that matter, not dev's.
"""

import os
from logging import getLogger

import pytest

from JobScheduler import JobScheduler

LOGGER = getLogger("TEST.JOB_SCHEDULER")

# RULE 13 floor: the readers this exists for. `>=` -- another module binding `environ` is
# collaboration, and the guard below re-derives the list from source rather than trusting it.
KNOWN_READERS = (
    ("src/scheduler/main.py", "environ"),
    ("src/common/db/db_methods/metadata.py", "environ"),
    ("src/common/utils/certificate_utils.py", "environ"),
)
MINIMUM_READERS = 3


@pytest.fixture
def scheduler():
    """Restore the real ``os.environ`` afterwards: this test rebinds the process-wide object."""
    original = os.environ
    try:
        yield JobScheduler(LOGGER)
    finally:
        os.environ = original


class TracingDict(dict):
    """Records every size the dict is ever observed at, and refuses ``clear()``.

    ``clear()`` is not merely untidy here: ``handle_reload`` is the SIGHUP handler and runs in
    this thread between two arbitrary bytecodes, reading ``getenv("PATH")`` and
    ``environ.items()``. A momentarily empty ``os.environ`` hands the config-saver subprocess an
    empty PATH and DATABASE_URI. So the requirement is *update then prune*, never clear-then-fill.
    """

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.min_len = len(self)

    def _note(self):
        self.min_len = min(self.min_len, len(self))

    def clear(self):  # pragma: no cover - the assertion is that this is never reached
        raise AssertionError("os.environ was cleared; SIGHUP can observe it half-empty")

    def update(self, *a, **kw):
        super().update(*a, **kw)
        self._note()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._note()


def test_the_environ_object_is_never_rebound_after_the_first_set(scheduler):
    scheduler.env = {"SERVICE_A": "1"}
    published = os.environ
    scheduler.env = {"SERVICE_A": "1", "SERVICE_B": "2"}
    assert os.environ is published, "os.environ was rebound; every `from os import environ` binding is now stale"


def test_a_module_holding_the_binding_sees_later_changes(scheduler):
    scheduler.env = {"SERVICE_A": "1"}
    held = os.environ  # what `from os import environ` captured at import time
    scheduler.env = {"SERVICE_A": "1", "SERVICE_B": "2"}
    assert held.get("SERVICE_B") == "2", "a held binding did not see the new service -- this is the defect"


def test_a_removed_service_loses_its_keys(scheduler):
    scheduler.env = {"SERVICE_A": "1", "SERVICE_A_USE_ANTIBOT": "captcha"}
    held = os.environ
    scheduler.env = {"SERVICE_A": "1"}
    assert "SERVICE_A_USE_ANTIBOT" not in held, "a deleted service's keys survived; the prune loop is load-bearing"


def test_the_base_environment_survives_every_set(scheduler):
    """Anti-vacuity in the other direction: pruning must not eat the process's own environment."""
    scheduler.env = {"SERVICE_A": "1"}
    held = os.environ
    before = held.get("PATH")
    assert before, "PATH must be in base_env for this test to mean anything"
    scheduler.env = {"SERVICE_B": "2"}
    assert held.get("PATH") == before, "PATH was pruned -- base_env is no longer merged in"


def test_environ_is_never_observably_empty_between_two_configs(scheduler):
    """The SIGHUP window. Swaps in an instrumented dict and asserts the low-water mark."""
    scheduler.env = {"SERVICE_A": "1"}
    traced = TracingDict(os.environ)
    scheduler._JobScheduler__job_env = traced
    os.environ = traced
    floor = len(traced)

    scheduler.env = {"SERVICE_B": "2"}  # a completely disjoint service set

    assert traced.min_len > 0, "os.environ dropped to zero entries at some point"
    assert traced.min_len >= floor - 1, f"os.environ shrank to {traced.min_len} from {floor}; it is being rebuilt, not updated"


def test_the_readers_this_guard_exists_for_still_bind_the_object(scheduler):
    """RULE 13 floor, re-derived rather than trusted: if a reader stops doing
    ``from os import environ`` the argument weakens, and if one is added it should be listed."""
    root = __import__("pathlib").Path(__file__).resolve().parents[3]
    live = [
        (path, name)
        for path, name in KNOWN_READERS
        if any(
            line.startswith("from os import") and "environ" in line.replace(",", " ").split() for line in (root / path).read_text(encoding="utf-8").splitlines()
        )
    ]
    assert len(live) >= MINIMUM_READERS, f"only {len(live)} of {len(KNOWN_READERS)} readers still bind the object: {live}"
