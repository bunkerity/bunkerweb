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
from json import dumps
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

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
