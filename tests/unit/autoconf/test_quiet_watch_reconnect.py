"""Quiet watches reconnect within proxy idle limits without losing their resource version."""

from types import SimpleNamespace as NS

import pytest

from _port_helpers import K8S, bare_controller


def test_quiet_watches_survive_repeated_server_timeouts(monkeypatch, tmp_path):
    controller = bare_controller()
    monkeypatch.setattr(K8S, "HEALTHY_PATH", tmp_path / "autoconf.healthy")
    clock, calls = [1000.0], []

    def stream(what, **kwargs):
        calls.append(kwargs)
        if len(calls) > 3:
            raise K8S.ApiException(status=500, reason="failed")
        clock[0] += 45
        return iter(())

    monkeypatch.setattr(K8S.watch, "Watch", lambda: NS(stream=stream, resource_version=None))
    monkeypatch.setattr(K8S, "time", lambda: clock[0])
    monkeypatch.setattr(K8S, "sleep", lambda seconds: None)
    with pytest.raises(RuntimeError, match="after 2 retries"):
        list(controller._get_stream_with_retries("pod", lambda: None, retries=2))
    assert len(calls) == 5, "quiet but healthy 45-second closes exhausted the retry budget"
    assert calls[0]["timeout_seconds"] == 45
    assert calls[0]["_request_timeout"] == (10, 60)
    assert not controller._watch_healthy_path("pod").exists()


def test_custom_resource_watch_keeps_version_and_clears_it_on_gone(monkeypatch, tmp_path):
    controller = bare_controller()
    monkeypatch.setattr(K8S, "HEALTHY_PATH", tmp_path / "autoconf.healthy")
    calls = []
    event = {"type": "MODIFIED", "raw_object": {"metadata": {"resourceVersion": "123"}}}

    def stream(what, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return iter([event])
        if len(calls) == 2:
            raise K8S.ApiException(status=410, reason="Gone")
        raise K8S.ApiException(status=500, reason="failed")

    monkeypatch.setattr(K8S.watch, "Watch", lambda: NS(stream=stream, resource_version=None))
    monkeypatch.setattr(K8S, "sleep", lambda seconds: None)
    events = controller._get_stream_with_retries("gateway", lambda: None, retries=3)
    assert next(events) == event
    with pytest.raises(RuntimeError):
        list(events)
    assert [call.get("resource_version") for call in calls] == [None, "123", None]


def test_repeated_brief_clean_closes_still_fail_health(monkeypatch, tmp_path):
    controller = bare_controller()
    monkeypatch.setattr(K8S, "HEALTHY_PATH", tmp_path / "autoconf.healthy")
    controller._mark_healthy("pod")
    calls = []

    def stream(what, **kwargs):
        calls.append(kwargs)
        return iter(())

    monkeypatch.setattr(K8S.watch, "Watch", lambda: NS(stream=stream, resource_version=None))
    monkeypatch.setattr(K8S, "sleep", lambda seconds: None)
    with pytest.raises(RuntimeError):
        list(controller._get_stream_with_retries("pod", lambda: None, retries=2))
    assert len(calls) == 2
    assert not controller._watch_healthy_path("pod").exists()
