"""Reload callers distinguish readiness from HTTP acceptance without signalling twice."""

import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ApiCaller import ApiCaller
import reload_utils
from scheduler_fakes import instance
import test_jobscheduler_jobs as jobs
import test_main_healthcheck as checks

make_scheduler = jobs.make_scheduler
reloading = jobs.reloading
health = checks.health

UNCONFIRMED = (True, "", 200, {"status": "success", "confirmed": False})
OK = checks.state("ok")
RELOADING = checks.state("reloading")
ERROR = (True, "", 500, {"status": "error", "msg": "initialization failed"})


@pytest.fixture
def clock(sched_main, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(reload_utils, "monotonic", lambda: now[0])
    monkeypatch.setattr(reload_utils, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    sched_main.HEALTHCHECK_RELOADS.clear()
    yield now
    sched_main.HEALTHCHECK_RELOADS.clear()


def scripted_api(outcome, initial=False, clock=None):
    api = SimpleNamespace(endpoint="http://bw1:5000/", calls=[], ready=False)
    states = [checks.state("loading")] if initial else []
    states += [RELOADING, OK] if outcome == "confirmed" else [RELOADING]

    def request(method, url, **kwargs):
        api.calls.append((method, url, kwargs))
        if method == "POST":
            return ERROR if outcome == "rejected" else UNCONFIRMED
        if api.ready:
            return OK
        if initial and len(api.calls) == 1:
            return states.pop(0)
        if outcome == "poll-error":
            return ERROR
        if outcome == "timeout":
            if clock is not None:
                clock[0] += sum(kwargs["timeout"])
            raise TimeoutError("health timed out")
        return states.pop(0) if len(states) > 1 else states[0]

    api.request = request
    return api


@pytest.mark.parametrize("outcome", ["confirmed", "pending", "rejected", "poll-error", "timeout"])
def test_periodic_reload_requires_confirmation(reloading, clock, outcome, caplog):
    api = scripted_api(outcome, clock=clock)
    reloading.apis = [api]
    reloading.send_files = Mock(return_value=True)
    with caplog.at_level(logging.INFO):
        result = reloading.run_pending()
    assert result is (outcome == "confirmed")
    assert clock[0] <= 60
    assert ("Successfully reloaded nginx" in caplog.text) is (outcome == "confirmed")
    if outcome in {"pending", "timeout"}:
        assert "pending" in caplog.text
        reloading._JobScheduler__publish_retry_at = None
        assert reloading.run_pending() is False
        api.ready = True
        reloading._JobScheduler__publish_retry_at = None
        assert reloading.run_pending() is True
        assert reloading.send_files.call_count == 1
    assert sum(method == "POST" for method, _, _ in api.calls) == 1
    if outcome != "rejected":
        assert any(method == "GET" for method, _, _ in api.calls)


@pytest.mark.parametrize("outcome", ["confirmed", "pending", "rejected", "poll-error", "timeout"])
def test_healthcheck_reload_requires_confirmation(health, clock, monkeypatch, outcome, caplog):
    api = scripted_api(outcome, initial=True, clock=clock)
    monkeypatch.setattr(health.main.API, "from_instance", lambda _: api)
    monkeypatch.setattr(health.main, "ApiCaller", ApiCaller)
    with caplog.at_level(logging.INFO):
        health.main.healthcheck_job()
    assert ("Successfully reloaded instance" in caplog.text) is (outcome == "confirmed")
    assert checks.statuses(health)[-1] == ("bw1", "up" if outcome == "confirmed" else "loading")
    assert clock[0] <= 60
    if outcome == "confirmed":
        assert sum(method == "GET" for method, _, _ in api.calls) == 3
    if outcome in {"pending", "timeout"}:
        assert "pending" in caplog.text
        health.main.healthcheck_job()
        api.ready = True
        health.main.healthcheck_job()
        assert checks.statuses(health)[-1] == ("bw1", "up")
        assert health.sends.renders == 1
    assert sum(method == "POST" for method, _, _ in api.calls) == 1


def test_new_job_changes_wait_for_earlier_reload_then_publish_once(reloading, clock):
    api = scripted_api("pending")
    reloading.apis = [api]
    reloading.send_files = Mock(return_value=True)
    assert reloading.run_pending() is False
    reloading.run_single("a")
    reloading._JobScheduler__publish_retry_at = None
    assert reloading.run_pending() is False
    assert sum(method == "POST" for method, _, _ in api.calls) == 1
    api.ready = True
    reloading._JobScheduler__publish_retry_at = None
    assert reloading.run_pending() is True
    assert sum(method == "POST" for method, _, _ in api.calls) == 2
    assert reloading.send_files.call_count == 2


def test_pending_healthcheck_does_not_erase_a_later_configuration_rejection(health, clock, monkeypatch):
    api = scripted_api("pending", initial=True)
    monkeypatch.setattr(health.main.API, "from_instance", lambda _: api)
    health.sched.db.instances = [instance("bw1", status="failover")]
    health.main.HEALTHCHECK_RELOADS["bw1"] = {"bw1": UNCONFIRMED[3]}
    health.main.healthcheck_job()
    assert checks.statuses(health)[-1] == ("bw1", "failover")
    assert not any(method == "POST" for method, _, _ in api.calls)
    assert health.sends.renders == 0
