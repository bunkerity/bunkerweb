"""Exit code 3 = "changed material, run failed": the worker publishes it, and records the run failed.

A job that rotated some material and failed on the rest (`certbot-renew.py` renewing lineage A while
lineage B errors out) used to exit 2: the run was recorded failed and nothing was pushed, so the
renewed certificate sat in the database and on the worker's disk while every instance kept serving
the old one until an unrelated reload. Exit 3 says both things at once. Every publish branch of
`execute_job` keys on `CHANGED_CODES` (1, 3), and only `SUCCESS_CODES` (0, 1) make a run a success.

Same loading technique as ``test_execute_job_deferral_reason.py``.
"""

from unittest.mock import Mock

import pytest

from test_execute_job_deferral_reason import JOB, TASKS, _Self, _clean, stub_runtime  # noqa: F401


def _run(monkeypatch, *, code, apis=object(), job=None, db=None):
    db = db if db is not None else Mock(add_job_run=Mock(return_value=None), checked_changes=Mock(return_value=None))
    monkeypatch.setattr(TASKS, "get_worker_db", lambda: db)
    if isinstance(apis, BaseException):
        monkeypatch.setattr(TASKS, "_get_apis", Mock(side_effect=apis))
    else:
        monkeypatch.setattr(TASKS, "_get_apis", lambda *_args: apis)
    reload = Mock()
    monkeypatch.setattr(TASKS, "_request_reload_debounced", reload)
    monkeypatch.setattr(TASKS, "_reload_is_owed", lambda *_args: False)
    owed = Mock()
    monkeypatch.setattr(TASKS, "_mark_reload_owed", owed)
    data = dict(JOB)
    data.update(job or {})
    result = TASKS.execute_job(_Self(), data)
    return result, db, reload, owed


@pytest.fixture
def exits(stub_runtime):  # noqa: F811
    def _exit_with(code):
        stub_runtime.run = Mock(side_effect=SystemExit(code))

    return _exit_with


def test_the_protocol_constants_are_named_once():
    assert TASKS.SUCCESS_CODES == (0, 1)
    assert TASKS.CHANGED_CODES == (1, 3)


class TestExitThree:
    def test_it_is_recorded_a_failed_run_that_still_needs_a_reload(self, exits, monkeypatch):
        exits(3)
        result, db, _, _ = _run(monkeypatch, code=3)

        assert result["success"] is False
        assert result["needs_reload"] is True
        assert result["return_code"] == 3
        call = db.add_job_run.call_args
        assert call.args[1] is False
        assert "3" in call.kwargs["error"]

    def test_it_ships_the_cache_and_reloads_when_instances_exist(self, exits, monkeypatch):
        exits(3)
        apis = object()
        _, _, reload, owed = _run(monkeypatch, code=3, apis=apis)

        reload.assert_called_once()
        assert reload.call_args.args[0] is apis
        owed.assert_not_called()

    def test_with_no_instance_the_push_is_owed_not_dropped(self, exits, monkeypatch):
        exits(3)
        _, _, reload, owed = _run(monkeypatch, code=3, apis=None)

        owed.assert_called_once()
        reload.assert_not_called()

    def test_an_unresolvable_fleet_is_owed_too(self, exits, monkeypatch):
        exits(3)
        _, _, reload, owed = _run(monkeypatch, code=3, apis=RuntimeError("bad instance row"))

        owed.assert_called_once()
        reload.assert_not_called()

    def test_a_regenerate_job_raises_the_config_changed_flag(self, exits, monkeypatch):
        exits(3)
        _, db, _, _ = _run(monkeypatch, code=3, job={"regenerate": True})

        db.checked_changes.assert_called_once_with(["config"], plugins_changes=[JOB["plugin_id"]], value=True)

    def test_a_job_that_does_not_declare_regenerate_does_not(self, exits, monkeypatch):
        exits(3)
        _, db, _, _ = _run(monkeypatch, code=3)

        db.checked_changes.assert_not_called()


class TestTheOtherCodesAreUnchanged:
    @pytest.mark.parametrize("code,success,changed", [(0, True, False), (1, True, True), (2, False, False), (4, False, False)])
    def test_success_and_change_per_code(self, exits, monkeypatch, code, success, changed):
        exits(code)
        result, _, reload, owed = _run(monkeypatch, code=code, apis=object(), job={"regenerate": True})

        assert result["success"] is success
        assert result["needs_reload"] is changed
        assert (reload.call_count == 1) is changed
        assert owed.call_count == 0

    def test_exit_one_still_defers_when_nobody_is_reachable(self, exits, monkeypatch):
        exits(1)
        _, _, _, owed = _run(monkeypatch, code=1, apis=None)
        owed.assert_called_once()

    def test_a_plain_return_zero_never_publishes(self, stub_runtime, monkeypatch):  # noqa: F811
        stub_runtime.run = Mock(return_value=0)
        result, _, reload, _ = _run(monkeypatch, code=0)
        assert result["needs_reload"] is False
        reload.assert_not_called()
