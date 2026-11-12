"""The shared confirmation wait spends one budget across all instances and probes."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import reload_utils

UNCONFIRMED = {"status": "success", "confirmed": False}


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(reload_utils, "monotonic", lambda: now[0])
    monkeypatch.setattr(reload_utils, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    return now


def test_one_deadline_includes_request_timeouts_for_every_instance(clock):
    calls = []

    def timeout(method, url, **kwargs):
        assert (method, url) == ("GET", "health")
        assert sum(kwargs["timeout"]) <= 5 - clock[0]
        calls.append(kwargs["timeout"])
        clock[0] += sum(kwargs["timeout"])
        raise TimeoutError("slow health endpoint")

    apis = [SimpleNamespace(endpoint=f"http://bw{i}:5000/", request=timeout) for i in range(2)]
    pending, failed = reload_utils.wait_for_reload(apis, {f"bw{i}": UNCONFIRMED for i in range(2)}, 5)
    assert pending == {"bw0": "unreachable", "bw1": "unreachable"}
    assert failed == {} and len(calls) == 1 and clock[0] == 5


def test_stuck_instance_does_not_hide_another_instances_confirmation(clock):
    stuck = Mock(return_value=(True, "", 200, {"status": "success", "msg": "reloading"}))
    ready = Mock(return_value=(True, "", 200, {"status": "success", "msg": "ok"}))
    apis = [SimpleNamespace(endpoint="http://BW1:5000/", request=stuck), SimpleNamespace(endpoint="https://[2001:db8::1]:5443/", request=ready)]
    pending, failed = reload_utils.wait_for_reload(apis, {"bw1": UNCONFIRMED, "2001:db8::1": UNCONFIRMED}, 5)
    assert pending == {"bw1": "reloading"} and failed == {}
    ready.assert_called_once()
    assert clock[0] == 5


@pytest.mark.parametrize("response", [{"status": "success", "confirmed": True}, {"status": "success"}, {"status": "error"}, None])
def test_confirmed_legacy_and_rejected_replies_do_not_poll(response, clock):
    request = Mock()
    result = reload_utils.wait_for_reload([SimpleNamespace(endpoint="http://bw1:5000/", request=request)], {"bw1": response}, 5)
    assert result == ({}, {})
    request.assert_not_called()
    assert clock[0] == 0


@pytest.mark.parametrize("status", [200, 500])
def test_explicit_health_error_is_failed_not_pending(status, clock):
    request = Mock(return_value=(True, "", status, {"status": "error", "msg": "initialization failed"}))
    result = reload_utils.wait_for_reload([SimpleNamespace(endpoint="http://bw1:5000/", request=request)], {"bw1": UNCONFIRMED}, 5)
    assert result == ({}, {"bw1": "initialization failed"})
    request.assert_called_once()
    assert clock[0] == 0
