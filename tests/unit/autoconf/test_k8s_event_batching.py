"""#4107: a change the backend-retry worker could not apply because the scheduler was busy must not wait for an unrelated event.

The worker applies from outside the watch loops. When the scheduler is still applying the previous
configuration it used to leave the apply pending and return, but only a watch thread that receives an
event consumes that flag, so the new Ingress stayed undeployed until the next event.
AUTOCONF_SRC points the test at another copy of src/autoconf (the unfixed one, to watch it fail).
"""

import logging
import os
import sys
from contextlib import suppress
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic, sleep
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[3]
for rel in (os.getenv("AUTOCONF_SRC", "src/autoconf"), "src/common/db", "src/common/utils", "src/common/api"):
    sys.path.insert(0, rel if rel.startswith("/") else str(ROOT / rel))

from controllers import KubernetesController as module  # noqa: E402
from controllers.KubernetesController import KubernetesController  # noqa: E402


class WorkerStopped(BaseException):
    pass


def build_controller(busy_checks):
    """A controller with only what the retry worker touches; the first `busy_checks` have_to_wait() calls answer True."""
    ctrl = KubernetesController.__new__(KubernetesController)
    ctrl._logger = logging.getLogger("k8s-batching-test")
    ctrl._internal_lock = Lock()
    ctrl._pending_apply = False
    ctrl._last_event_time = 0.0
    ctrl._debounce_delay = 2
    ctrl._apply_retry_at = None
    ctrl._event_summary = {}
    ctrl._event_summary_max = 8
    ctrl._event_loggable_kinds = {"Ingress"}
    ctrl._pending_backends_lock = Lock()
    ctrl._pending_backends = {("tenant", "backend"): {"attempts": 0.0, "next_retry_at": 0.0}}
    ctrl._pending_backends_max_attempts = 5
    ctrl._pending_backends_base_delay = 1.0
    ctrl._corev1 = MagicMock()
    ctrl._corev1.list_namespaced_service.return_value.items = [object()]
    ctrl._record_event("Ingress", "tenant", "new-host", "ADDED")

    answers = iter([True] * busy_checks)
    ctrl.have_to_wait = MagicMock(side_effect=lambda: next(answers, False))
    ctrl._update_settings = MagicMock()
    ctrl.get_instances = MagicMock(return_value=[])
    ctrl.get_services = MagicMock(return_value=[{"SERVER_NAME": "new-host"}])
    ctrl.get_configs = MagicMock(return_value=({}, {}))
    ctrl.update_needed = MagicMock(return_value=True)
    ctrl._sync_status = MagicMock()
    ctrl._set_autoconf_load_db = MagicMock()
    ctrl.apply_config = MagicMock(return_value=True)
    return ctrl


def run_worker(ctrl):
    with suppress(WorkerStopped):
        ctrl._pending_backends_worker()


def run_worker_until_applied(ctrl, timeout=8.0):
    stop = Event()

    def stoppable_sleep(seconds):
        if stop.is_set():
            raise WorkerStopped
        sleep(min(seconds, 0.05))

    with patch.object(module, "sleep", stoppable_sleep):
        thread = Thread(target=run_worker, args=(ctrl,), daemon=True)
        thread.start()
        deadline = monotonic() + timeout
        while monotonic() < deadline and not ctrl.apply_config.called:
            sleep(0.05)
        stop.set()
        thread.join(5)
    assert not thread.is_alive(), "the worker did not stop"


def test_apply_deferred_while_the_scheduler_is_busy_is_retried_without_a_new_event():
    ctrl = build_controller(busy_checks=2)
    run_worker_until_applied(ctrl)
    assert ctrl.apply_config.called, "the change recovered by the worker stayed undeployed after the scheduler was done"
    assert ctrl._pending_apply is False


def test_an_idle_scheduler_still_applies_straight_away():
    ctrl = build_controller(busy_checks=0)
    run_worker_until_applied(ctrl)
    assert ctrl.apply_config.call_count == 1
