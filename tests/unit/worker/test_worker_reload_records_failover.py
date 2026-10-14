"""The worker's cache-push reload feeds the UI's failover banner, like push-configs does.

`_request_reload_debounced` used to ask for the reload and look only at the overall boolean, so an
instance that refused the configuration after a job's cache push never raised the banner, and a
reload that went through never cleared one a previous refusal had raised.
"""

from unittest.mock import Mock

import pytest

from test_delivery_guarantees import BROKER, LOGGER, TASKS
from test_reload_broadcast import _LockRedis, _with_redis

REFUSED = {"status": "error", "msg": 'config check failed: nginx: [emerg] unknown directive "bogus"'}
OK = {"status": "success", "msg": "reloaded"}
BUSY = {"status": "error", "msg": "a configuration swap is still in progress"}


def _apis(sent, responses):
    apis = Mock()
    apis.send_files = Mock(return_value=True)
    apis.send_to_apis = Mock(return_value=(sent, responses))
    return apis


@pytest.fixture
def db(monkeypatch):
    database = Mock()
    database.record_reload_outcome.return_value = ""
    monkeypatch.setattr(TASKS, "get_worker_db", lambda: database)
    return database


def _run(apis, client=None):
    client = client or _LockRedis()
    with _with_redis(client):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)
    return client


def test_the_reload_asks_for_the_answers_of_every_instance(db):
    apis = _apis(True, {"bw-1": OK})
    _run(apis)
    apis.send_to_apis.assert_called_once_with("POST", "/reload?test=yes", timeout=(5, 30), response=True)


def test_a_refused_reload_is_recorded_and_the_job_still_fails_and_stays_owed(db):
    client = _LockRedis()
    apis = _apis(False, {"bw-1": REFUSED})
    with pytest.raises(RuntimeError, match="Failed to request BunkerWeb reload"):
        _run(apis, client)

    db.record_reload_outcome.assert_called_once_with({"bw-1": REFUSED["msg"]}, fleet=True)
    assert TASKS.RELOAD_OWED_KEY in client.keys
    assert TASKS.RELOAD_LOCK_KEY not in client.keys


def test_a_reload_every_instance_accepted_is_recorded_so_it_can_clear_the_banner(db):
    _run(_apis(True, {"bw-1": OK, "bw-2": OK}))
    db.record_reload_outcome.assert_called_once_with({"bw-1": None, "bw-2": None}, fleet=True)


def test_one_refusal_next_to_a_success_keeps_each_hosts_own_verdict(db):
    with pytest.raises(RuntimeError):
        _run(_apis(False, {"bw-1": OK, "bw-2": REFUSED}))
    db.record_reload_outcome.assert_called_once_with({"bw-1": None, "bw-2": REFUSED["msg"]}, fleet=True)


def test_a_busy_instance_is_not_a_verdict(db):
    with pytest.raises(RuntimeError):
        _run(_apis(False, {"bw-1": BUSY}))
    db.record_reload_outcome.assert_not_called()


def test_no_answer_at_all_records_nothing(db):
    with pytest.raises(RuntimeError):
        _run(_apis(False, {}))
    db.record_reload_outcome.assert_not_called()


def test_a_missing_database_does_not_break_the_reload(monkeypatch):
    monkeypatch.setattr(TASKS, "get_worker_db", lambda: None)
    client = _run(_apis(True, {"bw-1": OK}))
    assert TASKS.RELOAD_LOCK_KEY not in client.keys


def test_a_recording_failure_never_changes_the_outcome(db):
    db.record_reload_outcome.side_effect = RuntimeError("database gone")
    client = _run(_apis(True, {"bw-1": OK}))
    assert TASKS.RELOAD_LOCK_KEY not in client.keys

    db.record_reload_outcome.return_value = "boom"
    with pytest.raises(RuntimeError, match="Failed to request BunkerWeb reload"):
        _run(_apis(False, {"bw-1": REFUSED}))
