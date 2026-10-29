"""src/scheduler/main.py healthcheck_job: instance state handling, config pushes and the pending bookkeeping."""

import logging
from types import SimpleNamespace

import pytest

from scheduler_fakes import FakeApi, instance

OK = (True, "", 200, {"status": "success", "msg": "ok"})


def state(msg):
    return (True, "", 200, {"status": "success", "msg": msg})


class Caller:
    """ApiCaller stand-in: records the reload sent to the one instance."""

    reload_ok = True
    created = []

    def __init__(self, apis):
        self.apis = apis
        self.reloads = []
        Caller.created.append(self)

    def send_to_apis(self, method, url, **kwargs):
        self.reloads.append((method, url, kwargs["timeout"]))
        return Caller.reload_ok, {}


@pytest.fixture
def health(sched_main, fake_sched, fake_api, sandbox, monkeypatch):
    Caller.reload_ok = True
    Caller.created = []
    monkeypatch.setattr(sched_main, "ApiCaller", Caller)
    sends = SimpleNamespace(calls=[], ok=True, renders=0, render_ok=True)

    def send(path, endpoint, logger=None, *, api_caller=None):
        sends.calls.append(endpoint)
        return sends.ok

    monkeypatch.setattr(sched_main, "send_file_to_bunkerweb", send)
    monkeypatch.setattr(sched_main, "generate_configs", lambda logger=None: setattr(sends, "renders", sends.renders + 1) or sends.render_ok)
    sched_main.NEEDS_CONFIG_PASSES.clear()
    sched_main.NEEDS_CONFIG_PENDING.clear()
    sched_main.HEALTHCHECK_EVENT.clear()
    sched_main.APPLYING_CHANGES.clear()
    fake_sched.db.instances = [instance("bw1")]
    yield SimpleNamespace(sched=fake_sched, api=fake_api, sends=sends, main=sched_main)
    sched_main.NEEDS_CONFIG_PASSES.clear()
    sched_main.NEEDS_CONFIG_PENDING.clear()
    sched_main.HEALTHCHECK_EVENT.clear()


def statuses(h):
    return [c[1:] for c in h.sched.db.calls if c[0] == "update_instance"]


def test_a_healthy_instance_is_marked_up_and_registered(health):
    health.main.healthcheck_job()
    assert statuses(health) == [("bw1", "up")]
    assert [a.endpoint for a in health.sched.apis] == ["http://bw1:5000/"]
    assert health.sends.calls == []
    assert not health.main.HEALTHCHECK_EVENT.is_set()


def test_a_known_healthy_instance_is_not_registered_twice(health):
    health.sched.apis = [FakeApi("http://bw1:5000/")]
    health.main.healthcheck_job()
    assert len(health.sched.apis) == 1


def test_an_unreachable_instance_is_marked_down_and_dropped(health, caplog):
    health.api.answers["bw1"] = (False, "refused", 500, {})
    health.sched.apis = [FakeApi("http://bw1:5000/"), FakeApi("http://other:5000/")]
    with caplog.at_level(logging.WARNING):
        health.main.healthcheck_job()
    assert statuses(health) == [("bw1", "down")]
    assert [a.endpoint for a in health.sched.apis] == ["http://other:5000/"]
    assert "Can't send API request to http://bw1:5000/health : refused" in caplog.text


def test_a_request_that_raises_counts_as_down(health):
    health.api.answers["bw1"] = ConnectionError("reset")
    health.main.healthcheck_job()
    assert statuses(health) == [("bw1", "down")]


def test_an_error_status_is_down_and_a_database_error_is_logged(health, caplog):
    health.api.answers["bw1"] = (True, "", 503, {"status": "error", "msg": "nginx is down"})
    health.sched.db.update_instance_result = "locked"
    with caplog.at_level(logging.WARNING):
        health.main.healthcheck_job()
    assert "status = error, msg = nginx is down" in caplog.text
    assert "Couldn't update instance http://bw1:5000/ status to down in the database: locked" in caplog.text


def test_a_loading_instance_gets_the_whole_configuration_then_a_reload(health):
    health.api.answers["bw1"] = state("loading")
    health.main.healthcheck_job()
    assert sorted(health.sends.calls) == ["/cache", "/confs", "/custom_configs", "/plugins", "/pro_plugins"]
    assert health.sends.renders == 1
    assert Caller.created[0].reloads[0][:2] == ("POST", "/reload?test=yes")
    assert statuses(health) == [("bw1", "up")]
    assert [a.endpoint for a in health.sched.apis] == ["http://bw1:5000/"]


def test_a_reload_without_configuration_testing_uses_test_no(health, monkeypatch):
    monkeypatch.setattr(health.main, "DISABLE_CONFIGURATION_TESTING", True)
    health.api.answers["bw1"] = state("loading")
    health.main.healthcheck_job()
    assert Caller.created[0].reloads[0][1] == "/reload?test=no"


def test_the_config_is_read_once_for_several_loading_instances(health):
    health.sched.db.instances = [instance("bw1"), instance("bw2")]
    health.api.answers["bw1"] = state("loading")
    health.api.answers["bw2"] = state("loading")
    reads = []
    original = health.sched.db.get_config
    health.sched.db.get_config = lambda: reads.append(1) or original()
    health.main.healthcheck_job()
    assert len(reads) == 1 and len(Caller.created) == 2


def test_an_incomplete_push_skips_the_reload_and_keeps_the_instance_loading(health, caplog):
    health.api.answers["bw1"] = state("loading")
    health.sends.ok = False
    with caplog.at_level(logging.ERROR):
        health.main.healthcheck_job()
    assert Caller.created[0].reloads == []
    assert statuses(health) == [("bw1", "loading")]
    assert "reload skipped, it will be retried" in caplog.text
    assert health.sched.apis == []


def test_a_failed_reload_keeps_the_instance_loading(health, caplog):
    health.api.answers["bw1"] = state("loading")
    Caller.reload_ok = False
    with caplog.at_level(logging.ERROR):
        health.main.healthcheck_job()
    assert statuses(health) == [("bw1", "loading")]
    assert "Error while reloading instance http://bw1:5000/" in caplog.text


def test_a_loading_instance_in_failover_is_marked_down_without_a_push(health, caplog):
    health.api.answers["bw1"] = state("loading")
    health.sched.db.instances = [instance("bw1", status="failover")]
    with caplog.at_level(logging.WARNING):
        health.main.healthcheck_job()
    assert statuses(health) == [("bw1", "down")]
    assert health.sends.calls == []
    assert "is in failover mode and reports loading" in caplog.text


def test_a_restarted_instance_that_asks_for_its_config_is_pushed_and_tracked(health, caplog):
    health.api.answers["bw1"] = state("needs_config")
    Caller.reload_ok = False
    with caplog.at_level(logging.INFO):
        health.main.healthcheck_job()
    assert "bw1" in health.main.NEEDS_CONFIG_PENDING
    assert "restarted with its configuration preserved" in caplog.text


def test_a_successful_needs_config_push_clears_the_pending_mark(health):
    health.api.answers["bw1"] = state("needs_config")
    health.main.healthcheck_job()
    assert "bw1" not in health.main.NEEDS_CONFIG_PENDING
    assert statuses(health) == [("bw1", "up")]


def test_an_ok_instance_with_a_pending_push_is_treated_as_needing_its_config(health):
    health.main.NEEDS_CONFIG_PENDING.add("bw1")
    health.main.healthcheck_job()
    assert sorted(health.sends.calls) == ["/cache", "/confs", "/custom_configs", "/plugins", "/pro_plugins"]
    assert "bw1" not in health.main.NEEDS_CONFIG_PENDING


def test_an_ok_answer_forgets_the_needs_config_counter(health):
    health.main.NEEDS_CONFIG_PASSES["bw1"] = 2
    health.main.healthcheck_job()
    assert "bw1" not in health.main.NEEDS_CONFIG_PASSES


def test_needs_config_pushes_stop_after_the_fast_retries_with_one_error(health, caplog):
    health.api.answers["bw1"] = state("needs_config")
    Caller.reload_ok = False
    with caplog.at_level(logging.ERROR):
        for _ in range(health.main.NEEDS_CONFIG_FAST_RETRIES + 3):
            health.main.healthcheck_job()
    assert len(Caller.created) == health.main.NEEDS_CONFIG_FAST_RETRIES
    assert caplog.text.count("still asks for its configuration") == 1


def test_a_healthcheck_already_running_is_skipped(health, caplog):
    health.main.HEALTHCHECK_EVENT.set()
    with caplog.at_level(logging.WARNING):
        health.main.healthcheck_job()
    assert "already running, skipping execution" in caplog.text
    assert statuses(health) == []


def test_the_healthcheck_waits_while_changes_are_being_applied_and_releases_its_event(health):
    health.main.APPLYING_CHANGES.set()
    try:
        health.main.healthcheck_job()
    finally:
        health.main.APPLYING_CHANGES.clear()
    assert statuses(health) == []
    assert not health.main.HEALTHCHECK_EVENT.is_set()


def test_the_healthcheck_does_nothing_before_the_scheduler_exists(health, monkeypatch):
    monkeypatch.setattr(health.main, "SCHEDULER", None)
    health.main.healthcheck_job()
    assert not health.main.HEALTHCHECK_EVENT.is_set()


def test_an_exception_while_checking_one_instance_evicts_it_and_the_next_is_still_checked(health, caplog):
    health.sched.db.instances = [instance("bw1"), instance("bw2")]
    health.sched.apis = [FakeApi("http://bw1:5000/")]
    health.api.answers["bw1"] = (True, "", 200, {"status": "success"})  # no "msg": the state lookup raises KeyError
    with caplog.at_level(logging.ERROR):
        health.main.healthcheck_job()
    assert "Exception while checking instance http://bw1:5000/" in caplog.text
    assert [a.endpoint for a in health.sched.apis] == ["http://bw2:5000/"]
    assert ("bw2", "up") in statuses(health)
