"""Settings rechecks retry notifications even after the persisted signature advances."""

from unittest.mock import MagicMock

import pytest
from Config import Config
from fixtures.seed import add_setting, seed_minimal
from model import Plugins

import controllers.Controller as controller_module
import controllers.DockerController as docker_module


class StopWorker(BaseException):
    """Stop the real worker at its next sleep, outside its exception handler."""


@pytest.fixture
def sqlite_controller(clean_env, fake_db, db, monkeypatch):
    seed_minimal(db)
    monkeypatch.setattr(docker_module, "DockerClient", lambda **_kwargs: MagicMock())
    ctrl = docker_module.DockerController("unix:///fake.sock")
    ctrl._db = db
    ctrl._loaded = True
    # No scheduler runs in this isolated database to consume the flags.
    monkeypatch.setattr(ctrl, "wait_applying", lambda: None)
    monkeypatch.setattr(ctrl, "get_instances", lambda: [])
    services = [{"SERVER_NAME": "app.example.com", "USE_TEST_PROTECTION": "yes"}]
    monkeypatch.setattr(ctrl, "get_services", lambda: services)
    monkeypatch.setattr(ctrl, "get_configs", lambda: ctrl._configs)
    ctrl._update_settings()
    assert ctrl.apply([], services, configs=ctrl._configs)
    assert db.checked_changes(plugins_changes="all") == ""
    return ctrl


def run_two_ticks(ctrl, monkeypatch, after_tick):
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) > 1:
            after_tick(len(sleeps) - 1)
        if len(sleeps) == 3:
            raise StopWorker

    monkeypatch.setattr(controller_module, "sleep", sleep)
    with pytest.raises(StopWorker):
        ctrl._settings_recheck_worker()
    assert sleeps == [ctrl._settings_recheck_interval] * 3
    assert ctrl._internal_lock.acquire(blocking=False)
    ctrl._internal_lock.release()


@pytest.mark.parametrize("failure", ["return", "raise"])
def test_worker_retries_failed_signal_on_next_tick(sqlite_controller, monkeypatch, failure):
    ctrl = sqlite_controller
    db = ctrl._db
    add_setting(db, "USE_TEST_PROTECTION", context="multisite", type="check", regex="^(yes|no)$", default="no")
    original_signal = db.checked_changes
    signals = []

    def signal(changes, **kwargs):
        signals.append((set(changes), kwargs["plugins_changes"].copy()))
        if len(signals) == 1:
            if failure == "raise":
                raise RuntimeError("temporary signaling failure")
            return "temporary signaling failure"
        return original_signal(changes, **kwargs)

    monkeypatch.setattr(db, "checked_changes", signal)
    ticks = []

    def after_tick(tick):
        with db._db_session() as session:
            ticks.append((tick, session.get(Plugins, "general").config_changed, ctrl._pending_force, ctrl._pending_changes.copy()))
        assert not ctrl.settings_changed()
        assert db.get_config()["app.example.com_USE_TEST_PROTECTION"] == "yes"

    run_two_ticks(ctrl, monkeypatch, after_tick)

    assert signals == [({"config"}, {"general"})] * 2
    assert ticks == [(1, False, True, {"config"}), (2, True, False, set())]
    assert not ctrl._pending_first
    assert not ctrl._pending_plugins
    assert not ctrl.update_needed([], ctrl.get_services(), ctrl._configs)


def test_worker_does_not_apply_unchanged_settings_without_pending_work(sqlite_controller, monkeypatch):
    ctrl = sqlite_controller
    applied = MagicMock(wraps=ctrl.apply_config)
    monkeypatch.setattr(ctrl, "apply_config", applied)

    run_two_ticks(ctrl, monkeypatch, lambda _tick: None)

    applied.assert_not_called()
    with ctrl._db._db_session() as session:
        assert session.get(Plugins, "general").config_changed is False


@pytest.mark.parametrize("pending", [None, "changes", "plugins", "first", "force"])
def test_pending_work_predicate_is_shared_with_update_needed(fake_db, pending):
    ctrl = Config("docker")
    configs = {kind: {} for kind in ctrl._supported_config_types}
    assert ctrl.apply([], [], configs=configs)
    if pending in ("changes", "plugins"):
        getattr(ctrl, f"_pending_{pending}").add("config" if pending == "changes" else "general")
    elif pending:
        setattr(ctrl, f"_pending_{pending}", True)

    assert ctrl.has_pending_work() is (pending is not None)
    assert ctrl.update_needed([], [], configs) is (pending is not None)
