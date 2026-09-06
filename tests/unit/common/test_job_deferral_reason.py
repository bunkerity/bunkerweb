"""The job side of a deferral reason: hand it to the worker, do not persist it here.

push-configs (and any future job) exits 0 having deliberately done nothing, because a
precondition -- not an error -- was not met yet (every registered instance is down). That run is
still `success=True`: nothing broke, and the change flags stay raised for the next dispatch to
retry. Without a reason attached to it, the run row is indistinguishable from "ran, changed
nothing", so `note_deferral`/`drain_deferral_reason` hand the reason to `src/worker/tasks.py`
through the same in-process relay `defer_change_acknowledgement`/`drain_pending_acks` and
`request_requeue`/`drain_requeue_request` already use for the identical job -> worker direction.
"""

import pytest

from jobs import JOB_DEFERRAL_PREFIX, drain_deferral_reason, note_deferral


@pytest.fixture(autouse=True)
def _empty_queue():
    """The handoff is module state: a leftover from one test would arrive in the next."""
    drain_deferral_reason()
    yield
    drain_deferral_reason()


def test_a_noted_reason_is_handed_to_the_drain():
    note_deferral("All 1 registered BunkerWeb instance(s) are down; leaving the changes pending for a later run")

    assert drain_deferral_reason() == "All 1 registered BunkerWeb instance(s) are down; leaving the changes pending for a later run"


def test_nothing_noted_drains_to_none():
    """Anti-vacuity: an ordinary run that never defers must not manufacture a reason."""
    assert drain_deferral_reason() is None


def test_a_drained_reason_is_not_handed_out_twice():
    """Mutation: delete the `.clear()` in `drain_deferral_reason` and this goes red -- the second
    drain would still return the first reason, and the same leak would let a deferral reason from
    one run attach itself to the next, unrelated run in the same worker child."""
    note_deferral("every instance down")

    assert drain_deferral_reason() == "every instance down"
    assert drain_deferral_reason() is None


def test_the_prefix_is_not_glued_on_by_this_module():
    """`note_deferral` records the bare reason; prefixing with `JOB_DEFERRAL_PREFIX` is
    `src/worker/tasks.py`'s job, done once it also knows the run is otherwise a success. Gluing it
    on here would double it up if tasks.py ever changed to prefix defensively."""
    note_deferral("every instance down")

    reason = drain_deferral_reason()

    assert not reason.startswith(JOB_DEFERRAL_PREFIX)
