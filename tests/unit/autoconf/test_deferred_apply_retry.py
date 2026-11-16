"""A scheduler-busy apply must retry even with no backend entries and no new events."""

from threading import Lock
from unittest.mock import Mock

import pytest

from _port_helpers import K8S, bare_controller


def test_worker_retries_deferred_apply_without_new_watch_event(monkeypatch):
    controller = bare_controller()
    controller._internal_lock = Lock()
    controller._pending_backends_lock = Lock()
    controller._pending_backends = {}
    controller._pending_apply = True
    controller._debounce_delay = 2
    controller._apply_retry_at = None
    controller._log_event_summary = Mock()
    controller._update_settings = Mock()
    controller.get_instances = Mock(return_value=[])
    controller.get_services = Mock(return_value=[])
    controller.get_configs = Mock(return_value=({}, {}))
    controller.update_needed = Mock(return_value=True)
    controller.have_to_wait = Mock(side_effect=[True, False])
    controller.apply_config = Mock(return_value=True)
    controller._set_autoconf_loaded = Mock()
    clock = [100.0]
    monkeypatch.setattr(K8S, "time", lambda: clock[0])
    controller._trigger_apply_if_idle()
    controller.apply_config.assert_not_called()

    class StopWorker(BaseException):
        pass

    def tick(seconds):
        clock[0] += seconds
        if clock[0] >= 102:
            raise StopWorker

    monkeypatch.setattr(K8S, "sleep", tick)
    with pytest.raises(StopWorker):
        controller._pending_backends_worker()
    controller.apply_config.assert_called_once_with()
    assert controller.have_to_wait.call_count == 2
    assert controller._pending_apply is False
    assert controller._apply_retry_at is None
