"""The worker half of a job deferral reason: fold it into the run row, only on a success.

A job that leaves its change flags pending on purpose (`jobs.note_deferral`, e.g. push-configs
finding every instance down) still exits 0 -- `Jobs_runs.success` stays True, nothing broke. Left
alone, that row is indistinguishable from "ran, changed nothing": no `error`, same as a plain
success. `execute_job` folds the drained reason into `error`, prefixed with `JOB_DEFERRAL_PREFIX`,
so the UI can tell "waiting for a precondition" apart from both a plain success (no error) and a
real failure (`success=False`).

Same loading technique as ``test_delivery_guarantees.py``: celery/redis are not in the unit venv,
so ``src/worker/tasks.py`` is loaded for real with its ``worker.*`` imports stubbed. ``jobs`` is
real -- the relay under test.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from jobs import JOB_DEFERRAL_PREFIX, drain_deferral_reason, note_deferral

ROOT = Path(__file__).resolve().parents[3]


class _StubApp:
    def task(self, **options):
        def decorator(function):
            function.task_options = options
            return function

        return decorator


def _load_tasks():
    worker_pkg = ModuleType("worker")
    worker_app = ModuleType("worker.app")
    worker_executor = ModuleType("worker.executor")
    worker_app.app = _StubApp()
    worker_app.get_worker_db = lambda: None
    worker_executor.JobExecutor = Mock()
    modules = {"worker": worker_pkg, "worker.app": worker_app, "worker.executor": worker_executor}
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location("bw_worker_tasks_deferral", ROOT / "src" / "worker" / "tasks.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


TASKS = _load_tasks()

LOGGER = Mock()
BROKER = "redis://broker:6379/0"


class _Request:
    def __init__(self, task_id):
        self.id = task_id


class _Self:
    def __init__(self, task_id="run-1"):
        self.request = _Request(task_id)


JOB = {"name": "push-configs", "plugin_id": "jobs", "run_id": "run-1", "file": "push-configs.py", "path": "/x"}


@pytest.fixture(autouse=True)
def _clean():
    """Module state, same reason `test_job_requeue.py` drains it: a leftover reason must not
    attach itself to an unrelated test's run."""
    drain_deferral_reason()
    yield
    drain_deferral_reason()


@pytest.fixture
def stub_runtime(monkeypatch):
    logger_module = ModuleType("logger")
    logger_module.setup_logger = Mock(return_value=LOGGER)
    monkeypatch.setitem(sys.modules, "logger", logger_module)
    monkeypatch.setattr(TASKS, "_get_apis", lambda *_args: None)
    monkeypatch.setattr(TASKS, "_load_job_config_env", lambda db, logger: {})
    monkeypatch.setenv("CELERY_BROKER_URL", BROKER)
    executor = Mock()
    executor.run = Mock(return_value=0)
    monkeypatch.setattr(TASKS, "JobExecutor", Mock(return_value=executor))

    redis_module = ModuleType("redis")
    redis_module.Redis = Mock()
    redis_module.Redis.from_url = Mock(side_effect=RuntimeError("no broker in this test"))
    monkeypatch.setitem(sys.modules, "redis", redis_module)
    return executor


def _run(monkeypatch, db=None):
    db = db if db is not None else Mock(add_job_run=Mock(return_value=None))
    monkeypatch.setattr(TASKS, "get_worker_db", lambda: db)
    TASKS.execute_job(_Self(), dict(JOB))
    return db.add_job_run.call_args


class TestADeferredRunIsRecorded:
    def test_a_job_that_deferred_records_the_reason_prefixed(self, stub_runtime, monkeypatch):
        stub_runtime.run = Mock(side_effect=lambda _data: note_deferral("All 1 registered BunkerWeb instance(s) are down") or 0)

        call = _run(monkeypatch)

        assert call.args[1] is True  # success
        assert call.kwargs["error"] == f"{JOB_DEFERRAL_PREFIX}All 1 registered BunkerWeb instance(s) are down"

    def test_a_job_that_did_not_defer_records_no_reason(self, stub_runtime, monkeypatch):
        """Anti-vacuity, mirrors `TestFailureReason.test_a_successful_run_records_no_reason`: a
        message on every success row would make the UI show a cause for jobs that changed
        nothing and ran cleanly."""
        stub_runtime.run = Mock(return_value=0)

        call = _run(monkeypatch)

        assert call.args[1] is True
        assert call.kwargs["error"] is None

    def test_a_deferral_reason_left_by_a_crashed_job_does_not_attach_to_this_runs_row(self, stub_runtime, monkeypatch):
        """`note_deferral` is drained unconditionally in `execute_job`'s `finally`, same as the
        other two job -> worker relays, so a reason noted just before a crash cannot leak."""

        def _blow_up(_data):
            note_deferral("half-noted before the crash")
            raise RuntimeError("boom")

        stub_runtime.run = Mock(side_effect=_blow_up)

        call = _run(monkeypatch)

        assert call.args[1] is False  # a crash is a real failure, not a deferral
        assert call.kwargs["error"] == "Job crashed: boom"

    def test_mutation_dropping_the_fold_loses_the_reason(self, stub_runtime, monkeypatch):
        """Pins the fold in `execute_job` itself: if the `elif success and deferral_reason:`
        branch is ever deleted, this goes red because `error` reverts to `None`.
        """
        stub_runtime.run = Mock(side_effect=lambda _data: note_deferral("every instance down") or 0)

        call = _run(monkeypatch)

        assert call.kwargs["error"] is not None, "the deferral reason was dropped on its way to Jobs_runs.error"


def test_the_prefix_is_reserved_for_this_purpose():
    """The UI switches on this exact string (see src/ui/app/templates/jobs.html). Changing it here
    without updating the template silently breaks the "Deferred" status pill."""
    assert JOB_DEFERRAL_PREFIX == "deferred: "
