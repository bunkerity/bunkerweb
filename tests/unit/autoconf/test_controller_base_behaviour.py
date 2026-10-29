"""Controller base class: waiting for the scheduler, first apply, the settings re-check worker and the lock bookkeeping."""

import logging
from threading import Lock, Thread
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from _autoconf_helpers import attach_log

import controllers.Controller as module
from controllers.Controller import Controller, HoldTimeLock


class Stop(BaseException):
    """Ends an endless worker loop: raised out of a patched sleep()."""


class Concrete(Controller):
    """Controller with scriptable orchestrator answers."""

    def __init__(self):
        super().__init__("docker")
        self.controller_instances = []
        self.controller_services = []
        self._internal_lock = Lock()

    def _get_controller_instances(self):
        return self.controller_instances

    def _to_instances(self, controller_instance):
        return [controller_instance]

    def _get_controller_services(self):
        return self.controller_services

    def _to_services(self, controller_service):
        return [controller_service]

    def get_configs(self):
        return {"http": {}}

    def apply_config(self, force=False):
        return True


@pytest.fixture
def ctrl(clean_env, fake_db):
    return Concrete()


@pytest.fixture
def no_sleep(monkeypatch):
    calls = []
    monkeypatch.setattr(module, "sleep", lambda seconds: calls.append(seconds))
    return calls


# --- construction -----------------------------------------------------------------------------------


def test_recheck_interval_defaults_to_300_and_rejects_garbage(clean_env, fake_db):
    assert Concrete()._settings_recheck_interval == 300

    clean_env.setenv("AUTOCONF_SETTINGS_RECHECK_INTERVAL", "abc")
    bad = Concrete()
    assert bad._settings_recheck_interval == 300

    clean_env.setenv("AUTOCONF_SETTINGS_RECHECK_INTERVAL", "-5")
    assert Concrete()._settings_recheck_interval == -5


def test_namespaces_are_split_on_whitespace(clean_env, fake_db):
    clean_env.setenv("NAMESPACES", " prod  staging ")

    assert Concrete()._namespaces == ["prod", "staging"]


def test_no_namespaces_means_everything_is_managed(ctrl):
    assert ctrl._namespaces is None


# --- wait() -----------------------------------------------------------------------------------------


def test_wait_returns_once_instances_are_up_and_healthy(ctrl, fake_db, no_sleep):
    healthy = {"name": "bw", "health": True}
    ctrl.controller_instances = [healthy]

    assert ctrl.wait(3) == [healthy]
    assert no_sleep == []


def test_wait_sleeps_while_the_database_is_not_ready(ctrl, fake_db, no_sleep):
    answers = iter([{"is_initialized": False}, "db error", {"is_initialized": True}])
    fake_db.get_metadata = lambda: next(answers)
    ctrl.controller_instances = [{"name": "bw", "health": True}]

    ctrl.wait(7)

    assert no_sleep == [7, 7]


def test_wait_retries_until_an_instance_exists_and_is_healthy(ctrl, no_sleep):
    rounds = iter([[], [{"name": "a", "health": False}], [{"name": "a", "health": True}]])
    ctrl.get_instances = lambda: next(rounds)
    log = attach_log(ctrl)

    assert ctrl.wait(2) == [{"name": "a", "health": True}]

    assert no_sleep == [2, 2]
    assert log.has("No instance found, waiting 2s", logging.WARNING)
    assert log.has("Instance a is not ready, waiting 2s", logging.WARNING)


def test_wait_survives_an_error_while_fetching_instances(ctrl, no_sleep):
    answers = iter([RuntimeError("boom"), [{"name": "a", "health": True}]])

    def get_instances():
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    ctrl.get_instances = get_instances
    log = attach_log(ctrl)

    assert ctrl.wait(1) == [{"name": "a", "health": True}]
    assert log.has("Error while fetching instances", logging.ERROR)


# --- instances / services ---------------------------------------------------------------------------


def test_instances_fall_back_to_the_database_on_first_start_only(ctrl, fake_db):
    fake_db.db_instances = [{"hostname": "db-bw"}]

    assert ctrl.get_instances() == [{"hostname": "db-bw"}]
    ctrl._first_start = False
    assert ctrl.get_instances() == []


def test_database_fallback_does_not_duplicate_a_hostname(ctrl, fake_db):
    fake_db.db_instances = [{"hostname": "db-bw", "name": "first"}, {"hostname": "db-bw", "name": "second"}]

    assert ctrl.get_instances() == [{"hostname": "db-bw", "name": "first"}]


def test_orchestrator_instances_win_over_the_database(ctrl, fake_db):
    fake_db.db_instances = [{"hostname": "db-bw"}]
    ctrl.controller_instances = [{"hostname": "live"}]

    assert ctrl.get_instances() == [{"hostname": "live"}]


def test_get_services_flattens_each_controller_service(ctrl):
    ctrl.controller_services = [{"SERVER_NAME": "a"}, {"SERVER_NAME": "b"}]

    assert ctrl.get_services() == [{"SERVER_NAME": "a"}, {"SERVER_NAME": "b"}]


# --- loaded marker ----------------------------------------------------------------------------------


def test_loaded_marker_is_written_once(ctrl, fake_db):
    ctrl._set_autoconf_load_db()
    ctrl._set_autoconf_load_db()

    assert fake_db.set_metadata_calls == [{"autoconf_loaded": True}]
    assert ctrl._loaded is True


def test_loaded_marker_failure_is_retried_later(ctrl, fake_db):
    fake_db.set_metadata_result = "db is read-only"
    log = attach_log(ctrl)

    ctrl._set_autoconf_load_db()

    assert ctrl._loaded is False
    assert log.has("Can't set autoconf loaded metadata to true in database: db is read-only", logging.WARNING)


# --- initial_apply ----------------------------------------------------------------------------------


def test_initial_apply_stores_plain_configs_and_marks_loaded(ctrl, fake_db):
    ctrl.controller_services = [{"SERVER_NAME": "a"}]

    assert ctrl.initial_apply() is True

    assert ctrl._configs == {"http": {}}
    assert ctrl._services == [{"SERVER_NAME": "a"}]
    assert ctrl._loaded is True


def test_initial_apply_splits_the_kubernetes_tuple(ctrl):
    ctrl.get_configs = lambda: ({"USE_ANTIBOT": "yes"}, {"http": {"a": "b"}})

    assert ctrl.initial_apply() is True

    assert ctrl._extra_config == {"USE_ANTIBOT": "yes"}
    assert ctrl._configs == {"http": {"a": "b"}}


def test_initial_apply_failure_is_not_marked_loaded(ctrl, fake_db):
    ctrl.apply_config = lambda force=False: False
    log = attach_log(ctrl)

    assert ctrl.initial_apply() is False

    assert fake_db.set_metadata_calls == []
    assert log.has("Initial autoconf apply failed", logging.ERROR)


def test_initial_apply_exception_is_contained(ctrl):
    def boom(force=False):
        raise RuntimeError("scheduler gone")

    ctrl.apply_config = boom
    log = attach_log(ctrl)

    assert ctrl.initial_apply() is False
    assert log.has("Exception during initial autoconf apply: scheduler gone", logging.ERROR)


# --- settings re-check worker -----------------------------------------------------------------------


def run_worker(ctrl, monkeypatch, ticks=1):
    """Run `ticks` loop bodies, then stop at the next sleep()."""
    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) > ticks:
            raise Stop

    monkeypatch.setattr(module, "sleep", fake_sleep)
    with pytest.raises(Stop):
        ctrl._settings_recheck_worker()
    return sleeps


def test_recheck_reapplies_with_force_when_the_settings_set_changed(ctrl, fake_db, monkeypatch):
    ctrl._applied_settings_signature = frozenset({"OLD"})
    ctrl.controller_services = [{"SERVER_NAME": "a"}]
    applied = []
    ctrl.apply_config = lambda force=False: applied.append(force) or True
    log = attach_log(ctrl)

    run_worker(ctrl, monkeypatch)

    assert applied == [True]
    assert fake_db.set_metadata_calls == [{"autoconf_loaded": True}]
    assert ctrl._services == [{"SERVER_NAME": "a"}]
    assert log.has("Successfully re-applied autoconf configuration after settings change", logging.INFO)


def test_recheck_does_nothing_when_settings_are_unchanged(ctrl, monkeypatch):
    ctrl._update_settings()
    ctrl._applied_settings_signature = frozenset(ctrl._settings)
    ctrl.apply_config = MagicMock()

    run_worker(ctrl, monkeypatch)

    ctrl.apply_config.assert_not_called()


def test_recheck_waits_while_the_scheduler_is_applying(ctrl, fake_db, monkeypatch):
    fake_db.metadata = {"is_initialized": True, "plugins_config_changed": True}
    ctrl._applied_settings_signature = frozenset({"OLD"})
    ctrl.apply_config = MagicMock()

    run_worker(ctrl, monkeypatch)

    ctrl.apply_config.assert_not_called()


def test_recheck_gives_up_the_apply_when_the_scheduler_started_meanwhile(ctrl, fake_db, monkeypatch):
    ctrl._applied_settings_signature = frozenset({"OLD"})
    answers = iter([False, True])
    ctrl.have_to_wait = lambda: next(answers)
    ctrl.apply_config = MagicMock()

    run_worker(ctrl, monkeypatch)

    ctrl.apply_config.assert_not_called()


def test_recheck_reports_a_failed_apply(ctrl, monkeypatch):
    ctrl._applied_settings_signature = frozenset({"OLD"})
    ctrl.apply_config = lambda force=False: False
    log = attach_log(ctrl)

    run_worker(ctrl, monkeypatch)

    assert log.has("Error while re-applying autoconf configuration after settings change", logging.ERROR)
    assert ctrl._loaded is False


def test_recheck_survives_an_exception_and_releases_the_lock(ctrl, monkeypatch):
    ctrl._applied_settings_signature = frozenset({"OLD"})
    ctrl.get_instances = MagicMock(side_effect=RuntimeError("api down"))
    log = attach_log(ctrl)

    run_worker(ctrl, monkeypatch)

    assert log.has("Exception in settings recheck worker", logging.ERROR)
    assert ctrl._internal_lock.acquire(timeout=0.1)


def test_recheck_splits_a_kubernetes_style_configs_tuple(ctrl, monkeypatch):
    ctrl._applied_settings_signature = frozenset({"OLD"})
    ctrl.get_configs = lambda: ({"X": "1"}, {"http": {}})
    ctrl.apply_config = lambda force=False: True

    run_worker(ctrl, monkeypatch)

    assert ctrl._extra_config == {"X": "1"}


def test_worker_is_not_started_when_disabled(ctrl, monkeypatch):
    ctrl._settings_recheck_interval = 0
    started = []
    monkeypatch.setattr(module, "Thread", lambda **kw: started.append(kw) or MagicMock())
    log = attach_log(ctrl)

    ctrl._start_settings_recheck_worker()

    assert started == []
    assert log.has("Settings recheck worker disabled", logging.INFO)


def test_worker_is_started_as_a_daemon_thread(ctrl, monkeypatch):
    ctrl._settings_recheck_interval = 60
    thread = MagicMock()
    created = []
    monkeypatch.setattr(module, "Thread", lambda **kw: created.append(kw) or thread)

    ctrl._start_settings_recheck_worker()

    assert created == [{"target": ctrl._settings_recheck_worker, "daemon": True}]
    thread.start.assert_called_once_with()


# --- _is_service_present ----------------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, 12, "", "   "])
def test_non_names_are_never_present(ctrl, value):
    assert ctrl._is_service_present(value) is False


def test_service_presence_uses_the_primary_name_of_known_and_stored_services(ctrl, fake_db):
    ctrl._services = [{"SERVER_NAME": "a.example.com alias.example.com"}, {"SERVER_NAME": ""}]
    fake_db.services = [{"id": "stored.example.com"}]

    assert ctrl._is_service_present("a.example.com extra") is True
    assert ctrl._is_service_present("alias.example.com") is False
    assert ctrl._is_service_present("stored.example.com") is True
    assert ctrl._is_service_present("ghost.example.com") is False


# --- HoldTimeLock and the watchdog ------------------------------------------------------------------


def test_hold_time_lock_tracks_the_holder_and_resets_on_release():
    lock = HoldTimeLock()
    assert lock.held_for() == 0.0 and lock.stalled_for() == 0.0

    with lock:
        assert lock.held_for() >= 0.0
        lock._last_progress_at -= 100
        assert lock.stalled_for() >= 100
        lock.progress()
        assert lock.stalled_for() < 1

    assert lock._owner is None and lock.held_for() == 0.0


def test_progress_from_another_thread_only_counts_when_it_is_a_database_call():
    lock = HoldTimeLock()
    lock.acquire()
    lock._last_progress_at -= 100
    results = {}

    def other():
        lock.progress()
        results["plain"] = lock.stalled_for()
        lock.progress(database=True)
        results["db"] = lock.stalled_for()

    thread = Thread(target=other)
    thread.start()
    thread.join()
    lock.release()

    assert results["plain"] >= 100
    assert results["db"] < 1


def test_failed_non_blocking_acquire_records_nothing():
    lock = HoldTimeLock()
    lock.acquire()
    other = SimpleNamespace(result=None)

    thread = Thread(target=lambda: setattr(other, "result", lock.acquire(blocking=False)))
    thread.start()
    thread.join()

    assert other.result is False
    assert lock._owner is not None
    lock.release()


def test_stalled_lock_removes_the_healthy_marker(ctrl, tmp_path):
    ctrl._internal_lock = HoldTimeLock()
    ctrl._internal_lock.acquire()
    ctrl._internal_lock._last_progress_at -= 1000
    marker = tmp_path / "autoconf.healthy"
    marker.write_text("ok")
    log = attach_log(ctrl)

    assert ctrl._check_lock_hold(marker, max_hold=600) is True

    assert not marker.exists()
    assert log.has("marking autoconf unhealthy", logging.ERROR)


def test_lock_within_its_budget_keeps_the_marker(ctrl, tmp_path):
    ctrl._internal_lock = HoldTimeLock()
    ctrl._internal_lock.acquire()
    marker = tmp_path / "autoconf.healthy"
    marker.write_text("ok")

    assert ctrl._check_lock_hold(marker, max_hold=600) is False
    assert marker.exists()


def test_stalled_lock_with_no_marker_still_reports_stalled(ctrl, tmp_path):
    ctrl._internal_lock = HoldTimeLock()
    ctrl._internal_lock.acquire()
    ctrl._internal_lock._last_progress_at -= 1000

    assert ctrl._check_lock_hold(tmp_path / "missing", max_hold=1) is True


def test_watchdog_budget_covers_the_database_timeouts(ctrl, fake_db, monkeypatch):
    fake_db.database_uri = "sqlite:////tmp/x.db"
    fake_db.database_uri_readonly = ""
    fake_db._connect_timeout = 10
    fake_db._read_timeout = 30
    fake_db._engine_kwargs = {"pool_timeout": 5, "connect_args": {}}
    fake_db._request_retry_attempts = 2
    fake_db._request_retry_delay = 1
    monkeypatch.setattr(module.event, "listen", lambda *a, **k: None)
    monkeypatch.setattr(module.event, "contains", lambda *a, **k: False)

    ctrl._configure_lock_watchdog()

    # 2 attempts * (4 * (10 + 30 + 30) + 5) + 1 * 1 + 60
    assert ctrl._lock_max_hold == max(module.LOCK_MAX_HOLD, 2 * (4 * 70 + 5) + 1 + 60)


def test_watchdog_budget_grows_with_a_slow_database(ctrl, fake_db, monkeypatch):
    fake_db.database_uri = "mysql://u@h/db"
    fake_db.database_uri_readonly = "mysql://u@ro/db?read_timeout=900"
    fake_db._connect_timeout = 10
    fake_db._read_timeout = 30
    fake_db._engine_kwargs = {"pool_timeout": 30, "connect_args": {}}
    fake_db._request_retry_attempts = 3
    fake_db._request_retry_delay = 2
    monkeypatch.setattr(module.event, "listen", lambda *a, **k: None)
    monkeypatch.setattr(module.event, "contains", lambda *a, **k: False)

    ctrl._configure_lock_watchdog()

    budget = 10 + 900 + 30
    assert ctrl._lock_max_hold == 3 * (4 * budget + 30) + 2 * 2 + 60


def test_database_progress_only_counts_the_controllers_own_engine(ctrl, fake_db):
    ctrl._internal_lock = HoldTimeLock()
    ctrl._internal_lock.acquire()
    ctrl._internal_lock._last_progress_at -= 100
    fake_db.sql_engine = object()

    ctrl._database_progress(SimpleNamespace(engine=object()))
    assert ctrl._internal_lock.stalled_for() >= 100

    ctrl._database_progress(SimpleNamespace(engine=fake_db.sql_engine))
    assert ctrl._internal_lock.stalled_for() < 1


def test_lock_watchdog_loop_checks_every_interval(ctrl, monkeypatch, tmp_path):
    seen = []
    ctrl._check_lock_hold = lambda path: seen.append(path)
    ticks = []

    def fake_sleep(seconds):
        ticks.append(seconds)
        if len(ticks) > 2:
            raise Stop

    monkeypatch.setattr(module, "sleep", fake_sleep)
    with pytest.raises(Stop):
        ctrl._lock_watchdog(tmp_path / "h")

    assert ticks == [module.LOCK_WATCHDOG_INTERVAL] * 3
    assert seen == [tmp_path / "h"] * 2


def test_start_lock_watchdog_configures_then_spawns_a_daemon(ctrl, monkeypatch, tmp_path):
    order = []
    ctrl._configure_lock_watchdog = lambda: order.append("configure")
    thread = MagicMock()
    monkeypatch.setattr(module, "Thread", lambda **kw: order.append(kw["daemon"]) or thread)

    ctrl._start_lock_watchdog(tmp_path / "h")

    assert order == ["configure", True]
    thread.start.assert_called_once_with()
