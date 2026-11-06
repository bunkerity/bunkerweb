"""#4086: a reload or a push the instance did not take must never be reported as applied.

Driven over the same fakes as ``test_main_loop.py``. The instance answers the reload with 200 and
``confirmed: false`` when its new workers are not ready within the API's own wait; the scheduler then asks
``GET /health`` instead of reloading again. A busy 503 on a push keeps the instance and keeps the
configuration pending. Log lines say what happened.
"""

import logging
from types import SimpleNamespace

import pytest
import reload_utils

from scheduler_fakes import FakeApi, instance
import test_main_loop
from test_main_loop import reloads, set_metadata_calls

# The loop harness lives in test_main_loop.py; an alias keeps pytest finding the fixture without a shadowing import.
drive = test_main_loop.drive

OK = (True, "", 200, {"status": "success", "msg": "ok"})
RELOADING = (True, "", 200, {"status": "success", "msg": "reloading"})
UNCONFIRMED = {"bw1": {"status": "success", "msg": "reload signalled but readiness is unconfirmed", "confirmed": False}}


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    monkeypatch.setattr(reload_utils, "sleep", lambda _: None)


def health_states(drive, monkeypatch, *states):
    """Make every API client built by main.py answer GET /health with the given states, the last one repeating."""
    original = drive.main.API.from_instance
    script = list(states)
    polls = []

    def from_instance(db_instance):
        api = original(db_instance)

        def request(method, url, **kwargs):
            polls.append((db_instance["hostname"], method, url))
            state = script.pop(0) if len(script) > 1 else script[0]
            if isinstance(state, BaseException):
                raise state
            return state

        api.request = request
        return api

    monkeypatch.setattr(drive.main, "API", SimpleNamespace(from_instance=from_instance, build_endpoint=drive.main.API.build_endpoint))
    return polls


@pytest.fixture
def no_wait(drive, monkeypatch):
    """A clock that jumps 20 s per reading (``drive`` already stubs sleep): the confirmation bound runs out fast."""
    ticks = iter(range(0, 10**7, 20))
    monkeypatch.setattr(reload_utils, "monotonic", lambda: next(ticks))


# --- an unconfirmed reload is confirmed by health, not by a second reload -------------------------------


def test_an_unconfirmed_reload_is_applied_once_health_answers_ok(drive, monkeypatch, caplog):
    drive.sched.reload_answer = (True, dict(UNCONFIRMED))
    polls = health_states(drive, monkeypatch, RELOADING, RELOADING, OK)
    with caplog.at_level(logging.INFO):
        drive.run()
    assert len(polls) >= 3 and {(p[1], p[2]) for p in polls} == {("GET", "health")}
    assert set_metadata_calls(drive)[0]["failover"] is False
    assert "retrying the generation" not in caplog.text
    assert "Successfully reloaded bunkerweb" in caplog.text


def test_an_unconfirmed_reload_that_never_turns_ok_stays_pending_with_a_truthful_message(drive, monkeypatch, no_wait, caplog):
    drive.sched.reload_answer = (True, dict(UNCONFIRMED))
    health_states(drive, monkeypatch, RELOADING)
    with caplog.at_level(logging.INFO):
        drive.run()
    metadata = set_metadata_calls(drive)[0]
    assert metadata["failover"] is True
    assert "bw1:5000 - the reload was signalled but not confirmed" in metadata["failover_message"]
    assert "still reloading" in metadata["failover_message"]
    assert "Retrying in 30s (failed attempt 1)" in metadata["failover_message"]
    assert "Successfully reloaded bunkerweb" not in caplog.text
    assert "retrying the generation in 30s" in caplog.text
    assert [a.endpoint for a in drive.sched.apis] == ["http://bw1:5000/"]
    assert ("update_instance", "bw1", "up") in drive.db.calls


def test_a_health_endpoint_that_cannot_be_reached_counts_as_not_confirmed(drive, monkeypatch, no_wait):
    drive.sched.reload_answer = (True, dict(UNCONFIRMED))
    health_states(drive, monkeypatch, RuntimeError("connection reset"))
    drive.run()
    metadata = set_metadata_calls(drive)[0]
    assert metadata["failover"] is True and "not confirmed" in metadata["failover_message"]


def test_the_confirmation_wait_is_bounded_for_several_instances(drive, monkeypatch):
    """One shared deadline: two stuck instances cost one bound, not two."""
    drive.db.instances = [instance("bw1"), instance("bw2")]
    drive.sched.reload_answer = (True, {"bw1": UNCONFIRMED["bw1"], "bw2": UNCONFIRMED["bw1"]})
    now = [0]
    slept = []
    monkeypatch.setattr(reload_utils, "monotonic", lambda: now[0])
    monkeypatch.setattr(reload_utils, "sleep", lambda s: (slept.append(s), now.__setitem__(0, now[0] + s)))
    health_states(drive, monkeypatch, RELOADING)
    drive.run()
    bound = drive.main.RELOAD_CONFIRM_MIN_WAIT + 4
    assert 0 < sum(slept) <= 2 * bound  # two reload blocks on a first start, each bounded once for both instances
    assert set_metadata_calls(drive)[0]["failover"] is True


# --- a busy push keeps the instance and keeps the configuration pending ---------------------------------


@pytest.mark.parametrize("message", ["another push swap is in progress", "a configuration generation is in progress"])
def test_a_busy_push_keeps_the_instance_and_does_not_report_success(sched_main, fake_sched, fake_api, tmp_path, caplog, message):
    fake_sched.db.instances = [instance("bw1")]
    fake_sched.apis = [FakeApi("http://bw1:5000/")]
    fake_sched.send_ok = False
    fake_sched.responses = {"bw1": {"status": "error", "msg": message}}
    with caplog.at_level(logging.INFO):
        assert sched_main.send_file_to_bunkerweb(tmp_path, "/confs") is False
    assert [a.endpoint for a in fake_sched.apis] == ["http://bw1:5000/"]
    assert ("update_instance", "bw1", "down") not in fake_sched.db.calls
    assert "removing them from the list of reachable instances" not in caplog.text
    assert "Successfully sent" not in caplog.text
    assert "bw1:5000" in caplog.text and "busy" in caplog.text
    assert sched_main.take_busy_pushes() == {"bw1": message}
    assert sched_main.take_busy_pushes() == {}


def busy_confs_push(drive, monkeypatch, armed):
    def busy(path, endpoint, *a, **k):
        drive.sends.append(endpoint)
        if armed["on"] and endpoint == "/confs":
            drive.main.PUSH_BUSY["bw1"] = "another push swap is in progress"

    monkeypatch.setattr(drive.main, "send_file_to_bunkerweb", busy)


def test_a_busy_push_makes_the_generation_pending_and_the_reload_is_not_trusted(drive, monkeypatch, caplog):
    """The reload that follows a busy push may be accepted (the marker cleared meanwhile): it would load the old configuration."""
    armed = {"on": False}
    busy_confs_push(drive, monkeypatch, armed)
    drive.iterations = 2
    drive.sched.reload_answer = (True, {"bw1": {"status": "success", "msg": "", "confirmed": True}})

    def change():
        armed["on"] = True
        drive.db.metadata.update(custom_configs_changed=True, last_custom_configs_change="t1")

    drive.on_iteration[1] = change
    with caplog.at_level(logging.INFO):
        drive.run()
    metadata = set_metadata_calls(drive)[-1]
    assert metadata["failover"] is True
    assert "bw1:5000 - another push swap is in progress" in metadata["failover_message"]
    assert "Retrying in 30s (failed attempt 1)" in metadata["failover_message"]
    assert drive.backups == 1  # the first start only
    assert drive.main.PUSH_BUSY == {}


def test_a_busy_push_before_the_once_jobs_is_not_reported_as_applied(drive, monkeypatch, caplog):
    """The pre-job push is deferred and retried; the reload of the same iteration must not claim success or back it up."""
    busy_confs_push(drive, monkeypatch, {"on": True})
    drive.sched.reload_answer = (True, {"bw1": {"status": "success", "msg": "", "confirmed": True}})
    with caplog.at_level(logging.INFO):
        drive.run()
    assert "deferring them for 30s (1/3)" in caplog.text
    assert "Successfully reloaded bunkerweb" not in caplog.text
    assert drive.backups == 0
    assert drive.main.PUSH_BUSY == {}


# --- logs say what happened -----------------------------------------------------------------------------


def test_no_success_line_and_no_failover_backup_when_no_instance_is_listed(drive, caplog):
    drive.sched.apis = []
    drive.db.instances = []
    with caplog.at_level(logging.INFO):
        drive.run()
    assert "Successfully reloaded bunkerweb" not in caplog.text
    assert drive.backups == 0
    assert reloads(drive) == []


def test_the_not_reachable_line_says_which_instance_answered_what(drive, caplog):
    drive.sched.reload_answer = (False, {"bw1": {"status": "error", "msg": "connection refused"}})
    with caplog.at_level(logging.WARNING):
        drive.run()
    assert "No BunkerWeb instance is reachable" not in caplog.text
    assert "Every BunkerWeb instance failed the reload, skipping failover: bw1:5000 - connection refused" in caplog.text
    assert drive.sched.apis == []


def test_a_reload_that_got_no_answer_is_retried(drive, caplog):
    drive.sched.reload_answer = (False, {})
    with caplog.at_level(logging.ERROR):
        drive.run()
    metadata = set_metadata_calls(drive)[0]
    assert metadata["failover"] is True and "Retrying in 30s" in metadata["failover_message"]
    assert "retrying the generation in 30s" in caplog.text


def test_a_pending_generation_survives_an_iteration_where_the_instance_is_not_listed_yet(drive, monkeypatch):
    drive.iterations = 3
    drive.sched.reload_answer = (False, {})
    clock = iter(range(0, 10**7, 1000))
    monkeypatch.setattr(drive.main, "monotonic", lambda: next(clock))
    drive.run()
    flags = [m["failover"] for m in set_metadata_calls(drive)]
    assert flags and all(flags)  # never flipped back to "applied" while nothing took the configuration


# --- the responses are keyed by the lowercased URL hostname ---------------------------------------------


def test_an_instance_registered_with_capitals_is_read_from_its_lowercased_response(drive):
    drive.db.instances = [instance("BW1")]
    drive.sched.reload_answer = (True, {"bw1": {"status": "success", "msg": "", "confirmed": True}})
    drive.run()
    assert ("update_instance", "BW1", "up") in drive.db.calls
    assert ("update_instance", "BW1", "down") not in drive.db.calls
    assert set_metadata_calls(drive)[0]["failover"] is False


def test_a_push_answer_for_an_instance_with_capitals_is_read_case_insensitively(sched_main, fake_sched, fake_api, tmp_path):
    fake_sched.db.instances = [instance("BW1")]
    fake_sched.responses = {"bw1": {"status": "success"}}
    assert sched_main.send_file_to_bunkerweb(tmp_path, "/confs") is True
    assert ("update_instance", "BW1", "up") in fake_sched.db.calls
