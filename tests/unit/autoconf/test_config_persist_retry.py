"""Comparison baselines track persisted writes independently of change notifications."""

from importlib import import_module
from unittest.mock import MagicMock

import pytest
from Config import Config


@pytest.fixture
def sqlite_config(fake_db, db, monkeypatch):
    from fixtures.seed import seed_minimal

    seed_minimal(db)
    ctrl = Config("swarm")
    ctrl._db = db
    # No scheduler runs in this isolated database to consume the flags.
    monkeypatch.setattr(ctrl, "wait_applying", lambda: None)
    return ctrl


@pytest.mark.parametrize("failure", ["return", "raise"])
@pytest.mark.parametrize("retry_mode", ["block", "detect"])
def test_signal_retry_reconciles_against_persisted_settings(sqlite_config, monkeypatch, failure, retry_mode):
    from model import Plugins

    ctrl = sqlite_config
    db = ctrl._db
    configs = {kind: {} for kind in ctrl._supported_config_types}
    services = [{"SERVER_NAME": "app.example.com", "SECURITY_MODE": "block"}]
    assert ctrl.apply([], services, configs=configs)
    assert db.checked_changes(plugins_changes="all") == ""
    original_save = db.save_config
    original_signal = db.checked_changes
    saves = []
    signals = []

    def save(config, *args, **kwargs):
        saves.append(config.copy())
        return original_save(config, *args, **kwargs)

    def signal(changes, **kwargs):
        signals.append((set(changes), kwargs["plugins_changes"].copy()))
        if len(signals) == 1:
            if failure == "raise":
                raise RuntimeError("temporary signaling failure")
            return "temporary signaling failure"
        return original_signal(changes, **kwargs)

    monkeypatch.setattr(db, "save_config", save)
    monkeypatch.setattr(db, "checked_changes", signal)
    services[0]["SECURITY_MODE"] = "detect"
    if failure == "raise":
        with pytest.raises(RuntimeError, match="temporary signaling failure"):
            ctrl.apply([], services, configs=configs)
    else:
        assert ctrl.apply([], services, configs=configs) is False
    assert db.get_config()["app.example.com_SECURITY_MODE"] == "detect"
    with db._db_session() as session:
        assert session.get(Plugins, "general").config_changed is False

    services[0]["SECURITY_MODE"] = retry_mode
    assert ctrl.update_needed([], services, configs)
    assert ctrl.apply([], services, configs=configs)
    assert db.get_config()["app.example.com_SECURITY_MODE"] == retry_mode
    assert [config["app.example.com_SECURITY_MODE"] for config in saves] == (["detect", "block"] if retry_mode == "block" else ["detect"])
    assert signals == [({"services", "config"}, {"general"})] * 2
    with db._db_session() as session:
        assert session.get(Plugins, "general").config_changed is True
    assert ctrl._Config__config["app.example.com_SECURITY_MODE"] == db.get_config()["app.example.com_SECURITY_MODE"]
    assert ctrl._Config__services == services
    assert not ctrl._pending_changes
    assert not ctrl._pending_plugins
    assert not ctrl.update_needed([], services, configs)


@pytest.mark.parametrize("failure", ["return", "raise"])
def test_partial_persistence_retries_only_failed_settings(sqlite_config, monkeypatch, failure):
    from sqlalchemy import event

    ctrl = sqlite_config
    db = ctrl._db
    configs = {kind: {} for kind in ctrl._supported_config_types}
    services = [{"SERVER_NAME": "app.example.com", "SECURITY_MODE": "block"}]
    assert ctrl.apply([], services, configs=configs)
    assert db.checked_changes(plugins_changes="all") == ""
    original_instances = db.update_instances
    original_save = db.save_config
    instance_saves = []
    settings_saves = []

    def instances_save(*args, **kwargs):
        instance_saves.append(args[0])
        return original_instances(*args, **kwargs)

    def fail_session(*_args, **_kwargs):
        raise RuntimeError("temporary settings failure")

    def fail_sql(_connection, _cursor, statement, *_args):
        if statement.lstrip().startswith(("INSERT ", "UPDATE ", "DELETE ")):
            raise RuntimeError("temporary settings failure")

    def settings_save(*args, **kwargs):
        settings_saves.append(args[0])
        if len(settings_saves) == 1:
            if failure == "raise":
                with monkeypatch.context() as context:
                    context.setattr(db, "_db_session", fail_session)
                    return original_save(*args, **kwargs)
            event.listen(db.sql_engine, "before_cursor_execute", fail_sql)
            try:
                result = original_save(*args, **kwargs)
                assert "temporary settings failure" in result
                return result
            finally:
                event.remove(db.sql_engine, "before_cursor_execute", fail_sql)
        return original_save(*args, **kwargs)

    monkeypatch.setattr(db, "update_instances", instances_save)
    monkeypatch.setattr(db, "save_config", settings_save)
    instances = [{"hostname": "bw.example.com", "env": {}}]
    services[0]["SECURITY_MODE"] = "detect"
    if failure == "raise":
        with pytest.raises(RuntimeError, match="temporary settings failure"):
            ctrl.apply(instances, services, configs=configs)
    else:
        assert ctrl.apply(instances, services, configs=configs) is False
    assert [instance["hostname"] for instance in db.get_instances()] == ["bw.example.com"]
    assert db.get_config()["app.example.com_SECURITY_MODE"] == "block"
    assert ctrl.apply(instances, services, configs=configs)
    assert len(instance_saves) == 1
    assert len(settings_saves) == 2
    assert db.get_config()["app.example.com_SECURITY_MODE"] == "detect"
    assert ctrl._Config__instances == instances
    assert ctrl._Config__services == services
    assert not ctrl._pending_changes
    assert not ctrl._pending_plugins
    assert not ctrl.update_needed(instances, services, configs)


@pytest.mark.parametrize("failure", ["return", "raise", "custom_configs_raise"])
@pytest.mark.parametrize("next_change", [False, True])
def test_committed_plugin_changes_are_signaled_after_recovery(fake_db, db, monkeypatch, failure, next_change):
    from sqlalchemy import event
    from fixtures.seed import add_setting, seed_minimal, session as seed_session
    from model import Metadata, Plugins

    seed_minimal(db)
    with seed_session(db) as session:
        session.add(Plugins(id="headers", name="Headers", description="h", version="1.0"))
    add_setting(db, "TEST_HEADER", plugin_id="headers", context="multisite")
    ctrl = Config("docker")
    ctrl._db = db
    # No scheduler runs in this isolated database to consume the flags.
    monkeypatch.setattr(ctrl, "wait_applying", lambda: None)
    configs = {kind: {} for kind in ctrl._supported_config_types}
    services = [{"SERVER_NAME": "app.example.com", "SECURITY_MODE": "detect"}]
    assert ctrl.apply([], services, configs=configs)
    assert db.checked_changes(plugins_changes="all") == ""
    original_signal = db.checked_changes
    original_save = db.save_config
    saved_plugins = []
    attempts = []

    def save(*args, **kwargs):
        result = original_save(*args, **kwargs)
        saved_plugins.append(result)
        return result

    def fail_sql(*_args):
        raise RuntimeError("temporary signaling failure")

    def signal(*args, **kwargs):
        attempts.append((set(args[0]), set(kwargs["plugins_changes"])))
        if len(attempts) == 1 and failure != "custom_configs_raise":
            if failure == "raise":
                # Session acquisition sits outside checked_changes()'s exception handler.
                with monkeypatch.context() as context:
                    context.setattr(db, "_db_session", fail_sql)
                    return original_signal(*args, **kwargs)
            # Exercise checked_changes()'s real SQL-error-to-string path.
            event.listen(db.sql_engine, "before_cursor_execute", fail_sql)
            try:
                result = original_signal(*args, **kwargs)
                assert "temporary signaling failure" in result
                return result
            finally:
                event.remove(db.sql_engine, "before_cursor_execute", fail_sql)
        return original_signal(*args, **kwargs)

    monkeypatch.setattr(db, "save_config", save)
    monkeypatch.setattr(db, "checked_changes", signal)
    if failure == "custom_configs_raise":
        original_custom_save = db.save_custom_configs

        def fail_custom_save(*args, **kwargs):
            monkeypatch.setattr(db, "save_custom_configs", original_custom_save)
            raise RuntimeError("temporary signaling failure")

        monkeypatch.setattr(db, "save_custom_configs", fail_custom_save)
    services = [{"SERVER_NAME": "app.example.com", "SECURITY_MODE": "block"}]
    instances = [{"hostname": "bw.example.com", "env": {}}]
    configs["http"]["new.conf"] = b"# new"
    if failure != "return":
        with pytest.raises(RuntimeError, match="temporary signaling failure"):
            ctrl.apply(instances, services, configs=configs)
    else:
        assert ctrl.apply(instances, services, configs=configs) is False
    assert db.get_config()["app.example.com_SECURITY_MODE"] == "block"
    with db._db_session() as session:
        assert session.get(Plugins, "general").config_changed is False
        assert session.get(Metadata, 1).instances_changed is False
        assert session.get(Metadata, 1).custom_configs_changed is False
    assert saved_plugins == [{"general"}]

    if next_change:
        services[0]["TEST_HEADER"] = "new header"
    assert ctrl.apply(instances, services, configs=configs)
    # Persisted settings are rewritten only for a new desired change.
    assert saved_plugins == ([{"general"}, {"headers"}] if next_change else [{"general"}])
    with db._db_session() as session:
        assert session.get(Plugins, "general").config_changed is True
        assert session.get(Plugins, "headers").config_changed is next_change
        assert session.get(Metadata, 1).instances_changed is True
        assert session.get(Metadata, 1).custom_configs_changed is True
    assert attempts[-1][1] == ({"general", "headers"} if next_change else {"general"})
    assert not ctrl._pending_changes
    assert not ctrl._pending_plugins
    assert not ctrl.update_needed(instances, services, configs)
    assert ctrl.apply(instances, services, configs=configs)
    assert len(attempts) == (1 if failure == "custom_configs_raise" else 2)


def test_pending_signal_is_sent_even_when_next_apply_writes_nothing(sqlite_config, monkeypatch):
    from model import Plugins

    ctrl = sqlite_config
    db = ctrl._db
    configs = {kind: {} for kind in ctrl._supported_config_types}
    services = [{"SERVER_NAME": "app.example.com", "SECURITY_MODE": "block"}]
    assert ctrl.apply([], services, configs=configs)
    assert db.checked_changes(plugins_changes="all") == ""
    original_signal = db.checked_changes
    monkeypatch.setattr(db, "checked_changes", lambda *_a, **_k: "temporary signaling failure")
    services[0]["SECURITY_MODE"] = "detect"
    assert ctrl.apply([], services, configs=configs) is False
    assert ctrl.update_needed([], services, configs)

    def no_write(*_args, **_kwargs):
        pytest.fail("A signal-only retry must not write unchanged inputs")

    for writer in ("save_config", "save_custom_configs", "update_instances"):
        monkeypatch.setattr(db, writer, no_write)
    signals = []

    def signal(changes, **kwargs):
        signals.append((set(changes), kwargs))
        return original_signal(changes, **kwargs)

    monkeypatch.setattr(db, "checked_changes", signal)
    assert ctrl.apply([], services, configs=configs)
    assert signals == [({"services", "config"}, {"plugins_changes": {"general"}, "value": True})]
    assert db.get_config()["app.example.com_SECURITY_MODE"] == "detect"
    with db._db_session() as session:
        assert session.get(Plugins, "general").config_changed is True
    assert not ctrl._pending_changes
    assert not ctrl._pending_plugins
    assert not ctrl._pending_first
    assert not ctrl._pending_force
    assert not ctrl.update_needed([], services, configs)


@pytest.mark.parametrize("intent", ["first", "force"])
def test_pending_signal_keeps_apply_intent_and_change_kinds(fake_db, monkeypatch, intent):
    ctrl = Config("kubernetes")
    configs = {kind: {} for kind in ctrl._supported_config_types}
    services = [{"SERVER_NAME": "app.example.com", "USE_ANTIBOT": "captcha"}]
    assert ctrl.apply([], services, configs=configs)
    if intent == "force":
        monkeypatch.setattr(fake_db, "is_valid_setting", lambda *_a, **_k: (False, "license expired"))
    monkeypatch.setattr(fake_db, "checked_changes", lambda *_a, **_k: "temporary signaling failure")
    assert ctrl.apply([], services, configs=configs, **{intent: True}) is False
    assert ctrl.update_needed([], services, configs)
    assert ("app.example.com_USE_ANTIBOT" in ctrl._Config__config) is (intent != "force")

    monkeypatch.setattr(fake_db, "checked_changes", type(fake_db).checked_changes.__get__(fake_db))
    assert ctrl.apply([], services, configs=configs)
    if intent == "force":
        assert "app.example.com_USE_ANTIBOT" not in ctrl._Config__config
    else:
        assert set(fake_db.checked[-1]) == {"instances", "services", "custom_configs", "extra_config", "config"}
    assert not ctrl._pending_changes
    assert not ctrl._pending_plugins
    assert not ctrl.update_needed([], services, configs)


def test_successful_baseline_is_a_snapshot_of_caller_data(fake_db):
    ctrl = Config("docker")
    instances = [{"hostname": "old-instance", "env": {}}]
    services = [{"SERVER_NAME": "old.example.com"}]
    configs = {"http": {"site.conf": b"# old"}}
    assert ctrl.apply(instances, services, configs=configs)
    instances[0]["hostname"] = "new-instance"
    services[0]["SERVER_NAME"] = "new.example.com"
    configs["http"]["site.conf"] = b"# new"
    assert ctrl.update_needed(instances, services, configs)
    assert ctrl.apply(instances, services, configs=configs)
    assert fake_db.saved_configs[-1]["SERVER_NAME"] == "new.example.com"
    assert fake_db.saved_instances[-1][0]["hostname"] == "new-instance"
    assert fake_db.saved_custom_configs[-1][0]["value"] == b"# new"


@pytest.mark.parametrize(
    ("writer", "failure", "instances_saved", "settings_saved", "configs_saved"),
    [
        ("update_instances", "return", False, True, True),
        ("update_instances", "raise", False, False, False),
        ("save_config", "return", True, False, True),
        ("save_config", "raise", True, False, False),
        ("save_custom_configs", "return", True, True, False),
        ("save_custom_configs", "raise", True, True, False),
        ("checked_changes", "return", True, True, True),
        ("checked_changes", "raise", True, True, True),
    ],
)
def test_each_write_advances_only_its_own_persisted_baseline(fake_db, monkeypatch, writer, failure, instances_saved, settings_saved, configs_saved):
    ctrl = Config("kubernetes")
    assert ctrl.apply([], [{"SERVER_NAME": "old.example.com"}], configs={"http": {}}, extra_config={"SECURITY_MODE": "block"})
    ctrl._settings = {"NEW_SETTING": {}}
    instances = [{"hostname": "new-instance", "env": {}}]
    services = [{"SERVER_NAME": "new.example.com"}]
    configs = {"http": {"new.conf": b"# new"}}
    extra = {"SECURITY_MODE": "detect"}
    original = getattr(fake_db, writer)

    def fail(*_args, **_kwargs):
        if failure == "raise":
            raise RuntimeError("temporary save failure")
        return "temporary save failure"

    monkeypatch.setattr(fake_db, writer, fail)
    if failure == "raise":
        with pytest.raises(RuntimeError, match="temporary save failure"):
            ctrl.apply(instances, services, configs=configs, extra_config=extra)
    else:
        assert ctrl.apply(instances, services, configs=configs, extra_config=extra) is False

    assert ctrl._Config__instances == (instances if instances_saved else [])
    assert ctrl._Config__services == (services if settings_saved else [{"SERVER_NAME": "old.example.com"}])
    assert ctrl._Config__configs == (configs if configs_saved else {"http": {}})
    assert ctrl._Config__extra_config == (extra if settings_saved else {"SECURITY_MODE": "block"})
    assert ctrl._Config__config["SERVER_NAME"] == ("new.example.com" if settings_saved else "old.example.com")
    assert ctrl.update_needed(instances, services, configs, extra)
    assert ctrl.settings_changed() is not settings_saved
    monkeypatch.setattr(fake_db, writer, original)
    assert ctrl.apply(instances, services, configs=configs, extra_config=extra)
    assert not ctrl.update_needed(instances, services, configs, extra)
    assert not ctrl.settings_changed()
    assert fake_db.saved_configs[-1]["SERVER_NAME"] == "new.example.com"
    assert fake_db.saved_instances[-1] == instances
    assert fake_db.saved_custom_configs[-1] == [{"value": b"# new", "exploded": [None, "http", "new"]}]


@pytest.mark.parametrize("kind", ["Docker", "Swarm"])
@pytest.mark.parametrize("failure", ["return", "raise"])
def test_same_event_after_failed_save_still_persists(clean_env, fake_db, monkeypatch, kind, failure):
    module = import_module(f"controllers.{kind}Controller")
    client = MagicMock()
    monkeypatch.setattr(module, "DockerClient", lambda **_kwargs: client)
    ctrl = getattr(module, f"{kind}Controller")("unix:///fake.sock")
    ctrl._loaded = True
    ctrl._first_start = False
    setattr(ctrl, f"_{kind}Controller__debounce_delay", 0)
    monkeypatch.setattr(ctrl, "_start_settings_recheck_worker", lambda: None)
    assert ctrl.apply([], [{"SERVER_NAME": "old.example.com"}], configs=ctrl._configs)
    services = [{"SERVER_NAME": "new.example.com"}]
    monkeypatch.setattr(ctrl, "get_instances", lambda: [])
    monkeypatch.setattr(ctrl, "get_services", lambda: services)
    monkeypatch.setattr(ctrl, "get_configs", lambda: ctrl._configs)
    event = {"Action": "start", "Type": "service", "Actor": {"ID": "web", "Attributes": {"bunkerweb.SERVER_NAME": "new.example.com"}}}
    if kind == "Swarm":
        ctrl._SwarmController__swarm_services = ["web"]
    attempts = []
    original_save = fake_db.save_config

    def fail_once(*args, **kwargs):
        attempts.append(args[0].copy())
        if len(attempts) == 1:
            if failure == "raise":
                raise RuntimeError("temporary save failure")
            return "temporary save failure"
        return original_save(*args, **kwargs)

    def two_events(**_kwargs):
        yield event
        yield event
        raise RuntimeError("watch has no more events")

    class StopLoop(BaseException):
        pass

    def stop_sleep(_seconds):
        assert ctrl._internal_lock.acquire(blocking=False)
        ctrl._internal_lock.release()
        raise StopLoop

    monkeypatch.setattr(fake_db, "save_config", fail_once)
    monkeypatch.setattr(client, "events", two_events)
    monkeypatch.setattr(module, "sleep", stop_sleep)
    with pytest.raises(StopLoop):
        if kind == "Docker":
            ctrl.process_events()
        else:
            ctrl._SwarmController__event("service")
    assert len(attempts) == 2
    assert fake_db.saved_configs[-1]["SERVER_NAME"] == "new.example.com"
    assert not ctrl.update_needed([], services, ctrl._configs)
