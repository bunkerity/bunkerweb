"""A change flag may only be cleared once its material reached the instances.

`deploy-certificates` writes certificate material and exits 1; the /cache push and the reload
happen afterwards, here in the worker. Clearing the `certificates` flag inside the job therefore
recorded a delivery that could still fail — and nothing re-dispatches a job whose flag is already
clear, so every instance kept serving the previous certificate with a successful job run as the
only evidence.

Same class as the push-configs bug: acknowledging work that was not delivered.
"""

import importlib.util
import sys
from json import dumps, loads
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

import jobs  # noqa: E402 -- must be in sys.modules before _load_tasks patches it

ROOT = Path(__file__).resolve().parents[3]


class _StubApp:
    def task(self, *_args, **_kwargs):
        def decorator(function):
            return function

        return decorator


def _load_tasks(db=None):
    worker_pkg = ModuleType("worker")
    worker_app = ModuleType("worker.app")
    worker_executor = ModuleType("worker.executor")
    worker_app.app = _StubApp()
    worker_app.get_worker_db = lambda: db
    worker_executor.JobExecutor = Mock()
    modules = {"worker": worker_pkg, "worker.app": worker_app, "worker.executor": worker_executor}
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location("bw_worker_tasks_acks", ROOT / "src" / "worker" / "tasks.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ENTRY = dumps({"keys": ["certificates"], "snapshot": {"certificates_changed": True, "last_certificates_change": "2026-08-18T08:00:00"}})


def test_a_delivered_change_is_acknowledged_and_dequeued():
    db = Mock()
    db.clear_applied_changes.return_value = ""
    tasks = _load_tasks(db)
    client = Mock()

    tasks._apply_deferred_acks(client, [ENTRY], Mock())

    db.clear_applied_changes.assert_called_once()
    snapshot, keys = db.clear_applied_changes.call_args[0]
    assert keys == ("certificates",)
    assert snapshot["certificates_changed"] is True
    # The watermark is what makes the clear a compare-and-set; it has to survive the JSON trip as a
    # datetime, not the string Redis handed back.
    from datetime import datetime

    assert snapshot["last_certificates_change"] == datetime.fromisoformat("2026-08-18T08:00:00")
    client.srem.assert_called_once_with(tasks.ACK_PENDING_KEY, ENTRY)


def test_a_failed_acknowledgement_stays_queued():
    """The regression, inverted: dropping it here is exactly the bug being fixed."""
    db = Mock()
    db.clear_applied_changes.return_value = "database is read-only"
    tasks = _load_tasks(db)
    client = Mock()

    tasks._apply_deferred_acks(client, [ENTRY], Mock())

    client.srem.assert_not_called()


def test_nothing_is_acknowledged_without_a_database():
    tasks = _load_tasks(None)
    client = Mock()

    tasks._apply_deferred_acks(client, [ENTRY], Mock())

    client.srem.assert_not_called()


def test_a_corrupt_entry_does_not_block_the_others():
    db = Mock()
    db.clear_applied_changes.return_value = ""
    tasks = _load_tasks(db)
    client = Mock()

    tasks._apply_deferred_acks(client, ["not json", ENTRY], Mock())

    assert db.clear_applied_changes.call_count == 1
    client.srem.assert_called_once_with(tasks.ACK_PENDING_KEY, ENTRY)


@pytest.mark.parametrize("claimed", ([], None))
def test_no_pending_acknowledgements_touches_nothing(claimed):
    db = Mock()
    tasks = _load_tasks(db)
    client = Mock()

    tasks._apply_deferred_acks(client, claimed, Mock())

    db.clear_applied_changes.assert_not_called()
    client.srem.assert_not_called()


def test_the_job_no_longer_clears_its_own_flag_on_the_reload_path():
    """`status == 1` means a reload will follow, so the job must defer rather than clear.

    Pinned at source level: the clear and the defer are one line apart and the difference between
    them is the entire bug.
    """
    source = (ROOT / "src" / "common" / "core" / "certificates" / "jobs" / "deploy-certificates.py").read_text(encoding="utf-8")

    assert "defer_change_acknowledgement" in source, "the job stopped deferring its acknowledgement"
    assert "if status in (0, 1):" not in source, "the job acknowledges again on the path where the push has not happened yet"


def test_the_worker_queues_what_the_job_deferred():
    """The publish that the job cannot do itself, because it has no broker credential.

    An end-to-end run caught this: `defer_change_acknowledgement` built its own client from a
    CELERY_BROKER_URL the worker deliberately strips from every job environment, so it fell back to
    localhost and was refused every single time. The job leaves the payload in the jobs module now
    and the worker ships it from here.
    """
    tasks = _load_tasks()
    client = Mock()
    logger = Mock()

    with patch.object(tasks, "drain_pending_acks", return_value=[ENTRY]), patch.object(tasks, "_broker_client", return_value=client):
        tasks._publish_deferred_acks("redis://broker:6379/0", logger)

    client.sadd.assert_called_once_with(tasks.ACK_PENDING_KEY, ENTRY)
    logger.error.assert_not_called()


def test_a_broker_that_refuses_the_publish_leaves_the_change_pending():
    """Reported, never raised: this runs in the job's `finally`, and an exception here would
    replace the job's own outcome. The flag stays raised, so the scheduler re-dispatches."""
    tasks = _load_tasks()
    logger = Mock()

    with patch.object(tasks, "drain_pending_acks", return_value=[ENTRY]), patch.object(tasks, "_broker_client", side_effect=OSError("broker unreachable")):
        tasks._publish_deferred_acks("redis://broker:6379/0", logger)

    assert "broker unreachable" in logger.error.call_args[0][0]


def test_a_job_that_deferred_nothing_does_not_dial_the_broker():
    """Every job passes through here; only a handful ever defer anything."""
    tasks = _load_tasks()
    broker = Mock()

    with patch.object(tasks, "drain_pending_acks", return_value=[]), patch.object(tasks, "_broker_client", broker):
        tasks._publish_deferred_acks("redis://broker:6379/0", Mock())

    broker.assert_not_called()


def test_the_publish_happens_before_the_reload_is_requested():
    """Ordering, pinned at source level: the reload holder claims the pending set at the top of
    each round, so an entry published after the request would miss the very push it belongs to."""
    source = (ROOT / "src" / "worker" / "tasks.py").read_text(encoding="utf-8")

    assert source.index("_publish_deferred_acks(broker_url, logger)") < source.index("_request_reload_debounced(apis, broker_url, logger)")


def test_the_payload_survives_the_handoff_from_the_job_to_the_worker():
    """The seam the whole fix rests on, with nothing stubbed in between.

    A job cannot reach the broker, so it leaves the payload in the `jobs` module and the worker
    publishes it from there. That only works while both sides hold the SAME module object: if
    anything ever gives them separate copies -- a second `jobs.py` on the path, a stale
    `sys.modules` entry -- the drain returns empty, `_publish_deferred_acks` returns without a
    word, and the acknowledgement is lost exactly as silently as the bug this replaced. Every
    other test here patches `drain_pending_acks` and would pass straight through that.
    """
    tasks = _load_tasks()
    assert tasks.drain_pending_acks is jobs.drain_pending_acks, "the worker bound a different jobs module"

    jobs.drain_pending_acks()  # anything a previous test left behind
    jobs.defer_change_acknowledgement(("certificates",), {"certificates_changed": True}, Mock())

    client = Mock()
    with patch.object(tasks, "_broker_client", return_value=client):
        tasks._publish_deferred_acks("redis://broker:6379/0", Mock())

    client.sadd.assert_called_once()
    key, raw = client.sadd.call_args[0]
    assert key == tasks.ACK_PENDING_KEY
    assert loads(raw)["keys"] == ["certificates"]
    assert jobs.drain_pending_acks() == [], "the payload must not be handed out twice"
