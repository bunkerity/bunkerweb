"""Config.apply: the environment built from services, what reaches the database, and the read-only / busy-scheduler guards."""

import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from _autoconf_helpers import attach_log

import Config as config_module
from Config import Config

HOST = "app.example.com"


def make(kind="docker"):
    cfg = Config(kind)
    cfg.log = attach_log(SimpleNamespace(_logger=cfg._Config__logger))
    return cfg


@pytest.fixture
def cfg(fake_db):
    return make()


@pytest.fixture
def k8s_cfg(fake_db):
    return make("kubernetes")


def apply(cfg, services, **kwargs):
    return cfg.apply([{"name": "bw"}], services, **kwargs)


# --- the environment --------------------------------------------------------------------------------------


def test_service_settings_are_prefixed_with_the_primary_server_name(cfg, fake_db):
    assert apply(cfg, [{"SERVER_NAME": f"{HOST} alias.example.com", "USE_ANTIBOT": "captcha", "NAMESPACE": "prod", "CUSTOM_CONF_SERVER_HTTP_x": "y"}]) is True

    assert fake_db.saved_configs == [
        {"SERVER_NAME": HOST, "MULTISITE": "yes", f"{HOST}_SERVER_NAME": f"{HOST} alias.example.com", f"{HOST}_USE_ANTIBOT": "captcha"}
    ]


def test_already_prefixed_settings_are_kept_as_they_are(cfg, fake_db):
    apply(cfg, [{"SERVER_NAME": HOST, f"{HOST}_USE_ANTIBOT": "captcha"}])

    assert fake_db.saved_configs[0][f"{HOST}_USE_ANTIBOT"] == "captcha"
    assert f"{HOST}_{HOST}_USE_ANTIBOT" not in fake_db.saved_configs[0]


def test_services_without_a_server_name_contribute_nothing(cfg, fake_db):
    apply(cfg, [{"SERVER_NAME": "", "USE_ANTIBOT": "captcha"}, {"SERVER_NAME": HOST}])

    assert fake_db.saved_configs[0]["SERVER_NAME"] == HOST
    assert "USE_ANTIBOT" not in fake_db.saved_configs[0] and "_USE_ANTIBOT" not in fake_db.saved_configs[0]


def test_every_service_name_is_listed_in_order(cfg, fake_db):
    apply(cfg, [{"SERVER_NAME": "a.example.com"}, {"SERVER_NAME": "b.example.com alias"}])

    assert fake_db.saved_configs[0]["SERVER_NAME"] == "a.example.com b.example.com"


def test_invalid_settings_are_dropped_with_a_warning(cfg, fake_db):
    apply(cfg, [{"SERVER_NAME": HOST, "NOT_A_SETTING": "x"}])

    assert f"{HOST}_NOT_A_SETTING" not in fake_db.saved_configs[0]
    assert cfg.log.has("Variable NOT_A_SETTING: x is not a valid autoconf setting (setting NOT_A_SETTING not found), ignoring it", logging.WARNING)


def test_validation_knows_the_services_already_in_the_database(cfg, fake_db):
    seen = []
    fake_db.is_valid_setting = lambda setting, value=None, multisite=False, extra_services=None: seen.append(extra_services) or (True, "")
    fake_db.services = [{"id": "stored.example.com"}, {"id": ""}, {}]

    apply(cfg, [{"SERVER_NAME": HOST, "USE_ANTIBOT": "captcha"}])

    assert seen[0] == [HOST, "stored.example.com"]


def test_kubernetes_falls_back_to_a_global_setting(k8s_cfg, fake_db):
    fake_db.is_valid_setting = lambda setting, value=None, multisite=False, extra_services=None: (not multisite, "multisite only" if multisite else "")

    apply(k8s_cfg, [{"SERVER_NAME": HOST, "SECURITY_MODE": "detect"}])

    assert fake_db.saved_configs[0]["SECURITY_MODE"] == "detect"
    assert f"{HOST}_SECURITY_MODE" not in fake_db.saved_configs[0]
    assert k8s_cfg.log.has("Variable SECURITY_MODE is a global value and will be applied globally", logging.WARNING)


def test_a_global_setting_cannot_redefine_server_name(k8s_cfg, fake_db):
    fake_db.is_valid_setting = lambda setting, value=None, multisite=False, extra_services=None: (not multisite, "")

    apply(k8s_cfg, [{"SERVER_NAME": HOST}])

    assert fake_db.saved_configs[0]["SERVER_NAME"] == HOST
    assert k8s_cfg.log.has("Global variable SERVER_NAME can't be set via annotations", logging.WARNING)


def test_only_kubernetes_may_fall_back_to_globals(cfg, fake_db):
    fake_db.is_valid_setting = lambda setting, value=None, multisite=False, extra_services=None: (not multisite, "multisite only")

    apply(cfg, [{"SERVER_NAME": HOST, "SECURITY_MODE": "detect"}])

    assert "SECURITY_MODE" not in fake_db.saved_configs[0]


def test_extra_config_wins_over_service_settings(cfg, fake_db):
    apply(cfg, [{"SERVER_NAME": HOST}], extra_config={"USE_ANTIBOT": "yes", "MULTISITE": "no"})

    assert fake_db.saved_configs[0]["USE_ANTIBOT"] == "yes"
    assert fake_db.saved_configs[0]["MULTISITE"] == "no"


def test_force_revalidates_labels_even_when_nothing_else_changed(cfg, fake_db):
    services = [{"SERVER_NAME": HOST, "USE_ANTIBOT": "captcha"}]
    apply(cfg, services)
    fake_db.saved_configs.clear()

    apply(cfg, services)
    assert fake_db.saved_configs == []

    fake_db.is_valid_setting = lambda *a, **k: (False, "license expired")
    apply(cfg, services, force=True)
    assert fake_db.saved_configs == [{"SERVER_NAME": HOST, "MULTISITE": "yes"}]


# --- what is saved ----------------------------------------------------------------------------------------


def test_custom_configs_are_split_into_site_type_and_name(cfg, fake_db):
    configs = {"server-http": {f"{HOST}/hello.conf": b"a"}, "http": {"global.conf": b"b"}, "bogus": {"x": b"c"}}

    apply(cfg, [{"SERVER_NAME": HOST}], configs=configs)

    assert fake_db.saved_custom_configs == [
        [{"value": b"a", "exploded": [HOST, "server-http", "hello"]}, {"value": b"b", "exploded": [None, "http", "global"]}]
    ]
    assert cfg.log.has("Unsupported custom config type: bogus", logging.WARNING)


def test_cleanup_can_be_disabled_by_environment(clean_env, fake_db):
    clean_env.setenv("AUTOCONF_DISABLE_CLEANUP", "YES")
    cfg = Config("docker")

    apply(cfg, [{"SERVER_NAME": HOST}], configs={"http": {"a": b"b"}})

    assert fake_db.save_kwargs[0]["disable_cleanup"] is True


def test_cleanup_is_on_by_default(cfg, fake_db):
    apply(cfg, [{"SERVER_NAME": HOST}])

    assert fake_db.save_kwargs[0]["disable_cleanup"] is False


def test_changes_are_reported_to_the_scheduler_only_when_there_are_some(cfg, fake_db):
    services = [{"SERVER_NAME": HOST}]

    apply(cfg, services)
    apply(cfg, services)

    assert fake_db.checked == [["instances", "services", "custom_configs", "config"]]


def test_first_apply_always_reports_everything(cfg, fake_db):
    apply(cfg, [{"SERVER_NAME": HOST}], first=True)

    assert fake_db.checked == [["instances", "services", "custom_configs", "extra_config", "config"]]


def test_database_errors_fail_the_apply_without_hiding_the_other_writes(cfg, fake_db):
    fake_db.save_config = lambda *a, **k: "disk full"
    fake_db.update_instances = lambda *a, **k: "locked"
    fake_db.save_custom_configs = lambda *a, **k: "no space"
    fake_db.checked_changes = lambda *a, **k: "no signal"

    assert apply(cfg, [{"SERVER_NAME": HOST}], configs={"http": {"a": b"b"}}) is False

    for fragment in ("Failed to update instances: locked", "Can't save config in database: disk full", "no space", "no signal"):
        assert cfg.log.has(fragment, logging.ERROR)
    assert cfg._applied_settings_signature is None


def test_a_good_apply_records_the_settings_baseline(cfg, fake_db):
    cfg._update_settings()
    assert cfg.settings_changed() is False

    apply(cfg, [{"SERVER_NAME": HOST}])
    assert cfg.settings_changed() is False

    cfg._settings = {**cfg._settings, "NEW_SETTING": {}}
    assert cfg.settings_changed() is True


def test_no_plugins_keeps_the_previous_settings(cfg, fake_db):
    cfg._update_settings()
    known = dict(cfg._settings)
    fake_db.plugins = []

    cfg._update_settings()

    assert cfg._settings == known
    assert cfg.log.has("No plugins in database, can't update settings", logging.ERROR)


# --- update_needed ----------------------------------------------------------------------------------------


def test_update_needed_tracks_each_part_of_the_state(cfg):
    instances, services, configs, extra = [{"name": "bw"}], [{"SERVER_NAME": HOST}], {"http": {"a": b"b"}}, {"X": "1"}
    cfg.apply(instances, services, configs=configs, extra_config=extra)

    assert cfg.update_needed(instances, services, configs, extra) is False
    assert cfg.update_needed([], services, configs, extra) is True
    assert cfg.update_needed(instances, [], configs, extra) is True
    assert cfg.update_needed(instances, services, {}, extra) is True
    assert cfg.update_needed(instances, services, configs, {"X": "2"}) is True
    assert cfg.update_needed(instances, services, configs, {"X": "1", "Y": "2"}) is True


# --- have_to_wait / wait_applying -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ("db error", True),
        ({"is_initialized": False}, True),
        ({"is_initialized": True}, False),
        ({"is_initialized": True, "custom_configs_changed": True}, True),
        ({"is_initialized": True, "external_plugins_changed": True}, True),
        ({"is_initialized": True, "pro_plugins_changed": True}, True),
        ({"is_initialized": True, "plugins_config_changed": True}, True),
        ({"is_initialized": True, "instances_changed": True}, True),
        ({"is_initialized": True, "first_config_saved": True, "autoconf_loaded": True}, False),
    ],
)
def test_have_to_wait(cfg, fake_db, metadata, expected):
    fake_db.metadata = metadata

    assert cfg.have_to_wait() is expected


class Clock:
    """datetime stand-in: each sleep() moves time forward."""

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __init__(self):
        self.t = 0

    def now(self):
        return SimpleNamespace(astimezone=lambda: self.base + timedelta(seconds=self.t))


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(config_module, "datetime", c)
    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        c.t += seconds

    monkeypatch.setattr(config_module, "sleep", fake_sleep)
    c.sleeps = sleeps
    return c


def test_wait_applying_returns_at_once_when_idle(cfg, clock):
    cfg.wait_applying()

    assert clock.sleeps == []


def test_wait_applying_retries_through_errors_and_busy_periods(cfg, fake_db, clock):
    answers = iter(["db error", {"is_initialized": True, "instances_changed": True}, {"is_initialized": True}])
    fake_db.get_metadata = lambda: next(answers)

    cfg.wait_applying()

    assert clock.sleeps == [5, 5]
    assert cfg.log.has("An error occurred when checking for changes in the database : db error", logging.ERROR)
    assert cfg.log.has("Scheduler is already applying a configuration, retrying in 5 seconds", logging.WARNING)


def test_wait_applying_gives_up_after_four_minutes(cfg, fake_db, clock):
    fake_db.metadata = {"is_initialized": True, "instances_changed": True}

    with pytest.raises(Exception, match="Too many retries while waiting for scheduler"):
        cfg.wait_applying()

    assert sum(clock.sleeps) >= 240


# --- read-only database -----------------------------------------------------------------------------------


def test_a_database_that_refuses_writes_blocks_the_apply(cfg, fake_db):
    fake_db.write_error = RuntimeError("read-only replica")

    assert apply(cfg, [{"SERVER_NAME": HOST}]) is False

    assert fake_db.readonly is True
    assert fake_db.saved_configs == [] and fake_db.checked == []


def test_a_recovered_database_returns_to_read_write(cfg, fake_db):
    fake_db.readonly = True
    fake_db.database_uri = "mysql://db"

    assert apply(cfg, [{"SERVER_NAME": HOST}]) is True

    assert fake_db.readonly is False
    assert fake_db.retries == [{"pool_timeout": 1}, {"log": False}]
    assert cfg.log.has("The database is no longer read-only", logging.INFO)
    assert len(fake_db.saved_configs) == 1


def test_a_still_read_only_database_stays_read_only(cfg, fake_db):
    fake_db.readonly = True
    fake_db.database_uri = "mysql://db"
    fake_db.retry_outcomes = [RuntimeError("write failed"), None, None]

    assert apply(cfg, [{"SERVER_NAME": HOST}]) is False

    assert fake_db.readonly is True
    assert fake_db.retries[1:] == [{"readonly": True, "pool_timeout": 1}, {"readonly": True, "log": False}]
    assert cfg.log.has("Database is in read-only mode, configuration will not be saved", logging.ERROR)
    assert fake_db.saved_configs == []


def test_an_unreachable_primary_tries_the_read_only_replica_then_the_fallback(cfg, fake_db):
    fake_db.readonly = True
    fake_db.database_uri = "mysql://db"
    fake_db.database_uri_readonly = "mysql://ro"
    fake_db.retry_outcomes = [RuntimeError("a"), RuntimeError("b"), None, None]

    assert apply(cfg, [{"SERVER_NAME": HOST}]) is False

    assert {"fallback": True, "pool_timeout": 1} in fake_db.retries
    assert {"fallback": True, "log": False} in fake_db.retries


def test_without_a_database_uri_a_read_only_database_is_just_reported(cfg, fake_db):
    fake_db.readonly = True

    assert apply(cfg, [{"SERVER_NAME": HOST}]) is False
    assert fake_db.retries == []
