"""The API's two reload routes feed the UI's failover banner.

`POST /instances/reload` (fleet) and `POST /instances/{hostname}/reload` used to look only at the
overall boolean, so a manual reload that went through never cleared a banner a refusal had raised,
and one that an instance refused never raised it.
"""

from unittest.mock import Mock

import pytest

from test_instance_reload_timeout import _load_route

REFUSED = {"status": "error", "msg": 'config check failed: nginx: [emerg] unknown directive "bogus"'}
OK = {"status": "success", "msg": "reloaded"}
BUSY = {"status": "error", "msg": "a configuration swap is still in progress"}


@pytest.fixture
def db():
    database = Mock()
    database.record_reload_outcome.return_value = ""
    return database


def _fleet(db, sent, responses):
    api_caller = Mock()
    api_caller.send_to_apis.return_value = (sent, responses)
    return _load_route("reload_config", db=db)(True, api_caller), api_caller


def _single(db, sent, responses):
    api_caller = Mock()
    api_caller.send_to_apis.return_value = (sent, responses)
    return _load_route("reload_one", lambda apis: api_caller, db=db)("bw-1", True, Mock()), api_caller


class TestFleetReload:
    def test_a_refusal_is_recorded_and_the_route_still_answers_502(self, db):
        response, _ = _fleet(db, False, {"bw-1": REFUSED, "bw-2": OK})
        assert response.status_code == 502
        db.record_reload_outcome.assert_called_once_with({"bw-1": REFUSED["msg"], "bw-2": None}, fleet=True)

    def test_a_clean_reload_is_recorded_so_it_can_clear_the_banner(self, db):
        response, _ = _fleet(db, True, {"bw-1": OK, "bw-2": OK})
        assert response.status_code == 200
        db.record_reload_outcome.assert_called_once_with({"bw-1": None, "bw-2": None}, fleet=True)

    def test_a_busy_or_silent_fleet_records_nothing(self, db):
        _fleet(db, False, {"bw-1": BUSY})
        _fleet(db, False, {})
        db.record_reload_outcome.assert_not_called()

    def test_a_recording_failure_never_changes_the_answer(self, db):
        db.record_reload_outcome.side_effect = RuntimeError("database gone")
        response, _ = _fleet(db, True, {"bw-1": OK})
        assert response.status_code == 200


class TestSingleReload:
    def test_a_refusal_is_recorded_for_that_host_only(self, db):
        response, _ = _single(db, False, {"bw-1": REFUSED})
        assert response.status_code == 502
        db.record_reload_outcome.assert_called_once_with({"bw-1": REFUSED["msg"]}, fleet=False)

    def test_a_success_clears_only_that_hosts_entry(self, db):
        """Not a fleet reload: another host's refusal, and a legacy entry, must survive it."""
        response, _ = _single(db, True, {"bw-1": OK})
        assert response.status_code == 200
        db.record_reload_outcome.assert_called_once_with({"bw-1": None}, fleet=False)

    def test_a_busy_instance_records_nothing(self, db):
        _single(db, False, {"bw-1": BUSY})
        db.record_reload_outcome.assert_not_called()

    def test_a_recording_failure_never_changes_the_answer(self, db):
        db.record_reload_outcome.return_value = "boom"
        response, _ = _single(db, True, {"bw-1": OK})
        assert response.status_code == 200
