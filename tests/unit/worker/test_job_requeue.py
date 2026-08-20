"""The worker half of a job deferral (F-SCHED-3): re-dispatch it, do not hold a child for it.

A job whose precondition is not met yet (`certbot-new` waiting for `push-configs` to reach the
instances) must return immediately and be run again later. It cannot arrange that itself: the
worker strips `CELERY_BROKER_URL` from every job environment, so the job leaves the request in the
`jobs` module -- the same handoff `defer_change_acknowledgement` already uses -- and the worker,
which still holds the credential, queues it.

`src/worker/tasks.py` imports celery, which is not in the unit venv, so only its definitions are
loaded. `jobs` is real: the handoff is what is being tested.
"""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, Mock, patch

import pytest

from jobs import MAX_JOB_REQUEUES, drain_requeue_request, request_requeue

ROOT = Path(__file__).resolve().parents[3]
TASKS = ROOT / "src" / "worker" / "tasks.py"


def _load_definitions():
    tree = ast.parse(TASKS.read_text(encoding="utf-8"), filename=str(TASKS))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    stubs = {name: MagicMock() for name in ("worker", "worker.app", "worker.executor", "redis")}
    module = ModuleType("bw_worker_tasks")
    module.__dict__["__file__"] = str(TASKS)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(TASKS), "exec"), module.__dict__)  # noqa: S102
    return module


MODULE = _load_definitions()

JOB = {"name": "certbot-new", "plugin_id": "letsencrypt", "file": "certbot-new.py", "path": "/x", "run_id": "run-1"}


@pytest.fixture(autouse=True)
def _clean():
    drain_requeue_request()
    MODULE.execute_job = Mock()
    MODULE.queue_for = Mock(return_value="heavy")
    yield
    drain_requeue_request()


def _sent():
    assert MODULE.execute_job.apply_async.call_count == 1
    return MODULE.execute_job.apply_async.call_args


class TestNothingAsked:
    def test_a_job_that_did_not_defer_is_not_re_dispatched(self):
        MODULE._requeue_if_asked(dict(JOB), Mock())
        MODULE.execute_job.apply_async.assert_not_called()

    def test_the_request_is_consumed_so_it_cannot_leak_into_the_next_run(self):
        request_requeue(10, "waiting", Mock())
        MODULE._requeue_if_asked(dict(JOB), Mock())
        MODULE.execute_job.apply_async.reset_mock()

        MODULE._requeue_if_asked(dict(JOB), Mock())
        MODULE.execute_job.apply_async.assert_not_called()


class TestTheReDispatch:
    def test_it_is_queued_for_later_rather_than_waited_on(self):
        """The countdown is served by the broker. Sleeping here instead would occupy one of the
        two heavy prefork children for the whole wait."""
        request_requeue(10, "waiting", Mock())
        MODULE._requeue_if_asked(dict(JOB), Mock())
        assert _sent().kwargs["countdown"] == 10

    def test_it_stays_on_the_lane_the_job_belongs_to(self):
        request_requeue(10, "waiting", Mock())
        MODULE._requeue_if_asked(dict(JOB), Mock())
        MODULE.queue_for.assert_called_once_with("certbot-new")
        assert _sent().kwargs["queue"] == "heavy"

    def test_it_mints_a_new_task_id_instead_of_retrying_the_old_one(self):
        """`_delivery_attempt` counts deliveries per task id to bound a job that keeps killing its
        worker, and a celery `retry()` preserves the id. A deferral chain on the same id would be
        abandoned as "it keeps killing its worker" -- a diagnosis it never earned."""
        request_requeue(10, "waiting", Mock())
        MODULE._requeue_if_asked(dict(JOB), Mock())
        call = _sent()
        assert call.kwargs["task_id"] != JOB["run_id"]
        assert call.kwargs["args"][0]["run_id"] == call.kwargs["task_id"]

    def test_the_deferral_count_travels_with_it(self):
        """The next run reads this back out of its environment to know what budget is left."""
        request_requeue(10, "waiting", Mock())
        MODULE._requeue_if_asked(dict(JOB) | {"requeue_count": 3}, Mock())
        assert _sent().kwargs["args"][0]["requeue_count"] == 4

    def test_it_is_reported(self):
        logger = Mock()
        request_requeue(10, "the configuration has not reached the instances yet", logger)
        MODULE._requeue_if_asked(dict(JOB), logger)
        assert any("certbot-new" in str(call) for call in logger.warning.call_args_list)


class TestTheBound:
    def test_a_job_cannot_defer_itself_forever(self):
        """Jobs include third-party plugin code, so the bound is enforced on this side whatever
        the job asks for."""
        request_requeue(10, "waiting", Mock())
        logger = Mock()
        MODULE._requeue_if_asked(dict(JOB) | {"requeue_count": MAX_JOB_REQUEUES}, logger)
        MODULE.execute_job.apply_async.assert_not_called()
        assert logger.error.called

    def test_the_last_allowed_deferral_still_goes_out(self):
        request_requeue(10, "waiting", Mock())
        MODULE._requeue_if_asked(dict(JOB) | {"requeue_count": MAX_JOB_REQUEUES - 1}, Mock())
        assert _sent().kwargs["args"][0]["requeue_count"] == MAX_JOB_REQUEUES

    def test_a_broker_that_refuses_the_dispatch_is_reported_not_swallowed(self):
        """Nothing is lost that was not already lost -- the job did no work -- but a deferral that
        vanished silently would look exactly like a job with nothing to do."""
        request_requeue(10, "waiting", Mock())
        MODULE.execute_job.apply_async.side_effect = RuntimeError("broker down")
        logger = Mock()
        MODULE._requeue_if_asked(dict(JOB), logger)
        assert logger.error.called
