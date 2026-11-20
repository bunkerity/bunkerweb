"""src/scheduler/main.py: the small pure helpers, signal handlers, the config generator call and the instance pushes."""

import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from scheduler_fakes import FakeApi, FakeScheduler, instance

# --- pure decisions -------------------------------------------------------------------------------


def test_needs_config_pushes_are_fast_then_sparse(sched_main):
    sched_main.NEEDS_CONFIG_PASSES.clear()
    answers = [sched_main.needs_config_push_due("bw1") for _ in range(sched_main.NEEDS_CONFIG_FAST_RETRIES + 21)]
    fast = sched_main.NEEDS_CONFIG_FAST_RETRIES
    assert answers[:fast] == [True] * fast
    slow_window = answers[fast:][:19]
    assert slow_window == [False] * 19
    assert answers[fast + 19] is True
    assert answers[fast + 20] is False
    sched_main.NEEDS_CONFIG_PASSES.clear()


def test_needs_config_counters_are_per_instance(sched_main):
    sched_main.NEEDS_CONFIG_PASSES.clear()
    for _ in range(sched_main.NEEDS_CONFIG_FAST_RETRIES + 1):
        sched_main.needs_config_push_due("bw1")
    assert sched_main.needs_config_push_due("bw2") is True
    sched_main.NEEDS_CONFIG_PASSES.clear()


@pytest.mark.parametrize("failures, delay", [(1, 30), (2, 60), (3, 120), (4, 300), (5, 300), (50, 300)])
def test_generation_retry_delay_backs_off_then_plateaus(sched_main, failures, delay):
    assert sched_main.generation_retry_delay(failures) == delay


@pytest.mark.parametrize(
    "pushed, deferrals, expected",
    [(True, 0, (False, 0)), (True, 2, (False, 0)), (False, 0, (True, 1)), (False, 2, (True, 3)), (False, 3, (False, 0)), (False, 9, (False, 0))],
)
def test_pre_push_deferral_is_bounded(sched_main, pushed, deferrals, expected):
    assert sched_main.pre_push_deferral(pushed, deferrals) == expected


@pytest.mark.parametrize(
    "first_start, readonly, ignore, done, rendered, changed, expected",
    [
        (True, False, False, True, True, False, True),
        (False, True, False, True, True, False, True),
        (False, False, True, True, True, False, True),
        (False, False, False, False, True, False, True),
        (False, False, False, True, False, False, True),
        (False, False, False, True, True, False, False),
        (False, False, False, True, True, True, True),
    ],
)
def test_once_jobs_republish_only_when_something_changed_or_the_push_is_unreliable(
    sched_main, monkeypatch, first_start, readonly, ignore, done, rendered, changed, expected
):
    monkeypatch.setattr(sched_main, "IGNORE_FAIL_SENDING_CONFIG", ignore)
    assert sched_main.once_jobs_republish(first_start, done, rendered, changed, readonly) is expected


@pytest.mark.parametrize(
    "err, failed",
    [
        ("", False),
        ("Service a.example not found, please check your config", False),
        ("Service a.example not found, please check your config\nService b not found, please check your config", False),
        ("The database is read-only, the changes will not be saved", True),
        ("Service a.example not found, please check your config\nboom", True),
        ("\n  \n", False),
    ],
)
def test_custom_configs_save_failed_tells_a_refused_write_from_a_report(sched_main, err, failed):
    assert sched_main.custom_configs_save_failed(err) is failed


# --- environment for the subprocesses ------------------------------------------------------------


def test_build_cmd_env_forwards_logging_and_custom_conf(sched_main, monkeypatch):
    for key in ("TZ", "CUSTOM_LOG_LEVEL", "LOG_TYPES", "LOG_FILE_PATH", "LOG_SYSLOG_ADDRESS", "LOG_SYSLOG_TAG", "SCHEDULER_LOG_TO_FILE", "DATABASE_LOG_LEVEL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PATH", "/bin")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("DATABASE_URI", "sqlite:///x")
    monkeypatch.setenv("LOG_TYPES", "file")
    monkeypatch.setenv("TZ", "Europe/Paris")
    monkeypatch.setenv("MY_CUSTOM_CONF_HTTP_a", "x")
    env = sched_main.build_cmd_env()
    assert env["PATH"] == "/bin"
    assert env["LOG_LEVEL"] == "debug"
    assert env["DATABASE_URI"] == "sqlite:///x"
    assert env["LOG_TYPES"] == "file"
    assert env["TZ"] == "Europe/Paris"
    assert env["MY_CUSTOM_CONF_HTTP_a"] == "x"


def test_build_cmd_env_leaves_unset_logging_variables_out(sched_main, monkeypatch):
    monkeypatch.delenv("CUSTOM_LOG_LEVEL", raising=False)
    monkeypatch.setenv("SCHEDULER_LOG_TO_FILE", "")
    env = sched_main.build_cmd_env()
    assert "CUSTOM_LOG_LEVEL" not in env
    assert "SCHEDULER_LOG_TO_FILE" not in env


def test_instance_endpoint_follows_the_https_settings(sched_main):
    assert sched_main._instance_endpoint({"hostname": "bw1", "port": 5000}) == "http://bw1:5000"
    assert sched_main._instance_endpoint({"hostname": "bw1", "port": 5000, "listen_https": True, "https_port": 5443}) == "https://bw1:5443"


# --- stop and signal handlers ---------------------------------------------------------------------


class Executor:
    def __init__(self):
        self.shutdowns = []

    def shutdown(self, wait=True):
        self.shutdowns.append(wait)


def test_stop_removes_the_pid_and_healthy_files_then_exits(sched_main, sandbox, monkeypatch):
    pid = sandbox.root / "var" / "run" / "bunkerweb" / "scheduler.pid"
    pid.write_text("1")
    sandbox.HEALTHY_PATH.write_text("now")
    executor, exits = Executor(), []
    monkeypatch.setattr(sched_main, "SCHEDULER_TASKS_EXECUTOR", executor)
    monkeypatch.setattr(sched_main, "_exit", exits.append)
    sched_main.stop(7)
    assert not pid.exists() and not sandbox.HEALTHY_PATH.exists()
    assert executor.shutdowns == [False]
    assert exits == [7]


def test_stop_tolerates_missing_files(sched_main, sandbox, monkeypatch):
    exits = []
    monkeypatch.setattr(sched_main, "SCHEDULER_TASKS_EXECUTOR", Executor())
    monkeypatch.setattr(sched_main, "_exit", exits.append)
    sched_main.stop(0)
    assert exits == [0]


def test_handle_stop_waits_for_applying_changes_then_clears_the_scheduler_and_stops(sched_main, fake_sched, monkeypatch, caplog):
    stops = []
    monkeypatch.setattr(sched_main, "stop", stops.append)
    sched_main.APPLYING_CHANGES.set()
    monkeypatch.setattr(sched_main, "sleep", lambda s: sched_main.APPLYING_CHANGES.clear())
    with caplog.at_level(logging.WARNING):
        sched_main.handle_stop(15, None)
    assert "Waiting for the changes to be applied before stopping" in caplog.text
    assert fake_sched.cleared is True
    assert ("close",) in fake_sched.db.calls
    assert stops == [0]


def test_handle_stop_gives_up_waiting_after_thirty_seconds(sched_main, fake_sched, monkeypatch, caplog):
    base = datetime(2026, 1, 1).astimezone()
    times = iter([base, base + timedelta(seconds=31)])
    monkeypatch.setattr(sched_main, "datetime", SimpleNamespace(now=lambda: next(times)))
    monkeypatch.setattr(sched_main, "stop", lambda status: None)
    sched_main.APPLYING_CHANGES.set()
    try:
        with caplog.at_level(logging.WARNING):
            sched_main.handle_stop(15, None)
    finally:
        sched_main.APPLYING_CHANGES.clear()
    assert "Timeout reached, stopping without waiting" in caplog.text


def test_handle_stop_without_a_scheduler_just_stops(sched_main, monkeypatch):
    stops = []
    monkeypatch.setattr(sched_main, "SCHEDULER", None)
    monkeypatch.setattr(sched_main, "stop", stops.append)
    sched_main.handle_stop(2, None)
    assert stops == [0]


def test_handle_stop_survives_a_database_that_refuses_to_close(sched_main, fake_sched, monkeypatch):
    stops = []
    fake_sched.db.close = lambda: (_ for _ in ()).throw(RuntimeError("busy"))
    monkeypatch.setattr(sched_main, "stop", stops.append)
    sched_main.handle_stop(2, None)
    assert stops == [0]


def test_handle_reload_runs_the_config_saver_and_asks_for_a_custom_config_rescan(sched_main, fake_sched, monkeypatch):
    calls = []
    monkeypatch.setattr(sched_main, "RELOAD_SCAN_CONFIGS", False)
    monkeypatch.setattr(sched_main, "RUN", True)
    monkeypatch.setattr(sched_main, "subprocess_run", lambda cmd, **kw: calls.append((cmd, kw)) or SimpleNamespace(returncode=0))
    sched_main.handle_reload(1, None)
    assert sched_main.RELOAD_SCAN_CONFIGS is True
    cmd, kwargs = calls[0]
    assert cmd[1].endswith("gen/save_config.py")
    assert cmd[-2:] == ["--variables", "/etc/bunkerweb/variables.env"]
    assert "--first-run" not in cmd
    assert kwargs["check"] is False


def test_handle_reload_reports_a_failing_config_saver(sched_main, fake_sched, monkeypatch, caplog):
    monkeypatch.setattr(sched_main, "RUN", True)
    monkeypatch.setattr(sched_main, "subprocess_run", lambda cmd, **kw: SimpleNamespace(returncode=3))
    with caplog.at_level(logging.ERROR):
        sched_main.handle_reload(1, None)
    assert "Config saver failed with return code 3" in caplog.text


def test_handle_reload_is_ignored_for_a_read_only_database(sched_main, fake_sched, monkeypatch, caplog):
    fake_sched.db.readonly = True
    monkeypatch.setattr(sched_main, "RUN", True)
    monkeypatch.setattr(sched_main, "RELOAD_SCAN_CONFIGS", False)
    monkeypatch.setattr(sched_main, "subprocess_run", lambda *a, **k: pytest.fail("config saver must not run"))
    with caplog.at_level(logging.WARNING):
        sched_main.handle_reload(1, None)
    assert sched_main.RELOAD_SCAN_CONFIGS is False
    assert "The database is read-only" in caplog.text


def test_handle_reload_is_ignored_when_the_scheduler_is_not_running(sched_main, monkeypatch, caplog):
    monkeypatch.setattr(sched_main, "SCHEDULER", None)
    with caplog.at_level(logging.WARNING):
        sched_main.handle_reload(1, None)
    assert "Ignored reload operation because scheduler is not running" in caplog.text


def test_handle_reload_never_raises_out_of_a_signal_handler(sched_main, fake_sched, monkeypatch, caplog):
    monkeypatch.setattr(sched_main, "RUN", True)
    monkeypatch.setattr(sched_main, "subprocess_run", lambda *a, **k: (_ for _ in ()).throw(OSError("no python")))
    with caplog.at_level(logging.ERROR):
        sched_main.handle_reload(1, None)
    assert "Exception while reloading scheduler : no python" in caplog.text


def test_install_signal_handlers_binds_stop_and_reload(sched_main, monkeypatch):
    import signal as signal_module

    bound = {}
    monkeypatch.setattr(sched_main, "signal", lambda sig, handler: bound.__setitem__(sig, handler))
    sched_main.install_signal_handlers()
    assert bound == {
        signal_module.SIGINT: sched_main.handle_stop,
        signal_module.SIGTERM: sched_main.handle_stop,
        signal_module.SIGHUP: sched_main.handle_reload,
    }


def test_ensure_runtime_dirs_creates_every_folder_the_scheduler_writes_to(sched_main, sandbox, tmp_path, monkeypatch):
    fresh = tmp_path / "fresh"
    monkeypatch.setattr(sched_main, "CACHE_PATH", fresh / "cache")
    monkeypatch.setattr(sched_main, "CUSTOM_CONFIGS_PATH", fresh / "configs")
    monkeypatch.setattr(sched_main, "EXTERNAL_PLUGINS_PATH", fresh / "plugins")
    monkeypatch.setattr(sched_main, "PRO_PLUGINS_PATH", fresh / "pro")
    monkeypatch.setattr(sched_main, "TMP_PATH", fresh / "tmp")
    monkeypatch.setattr(sched_main, "FAILOVER_PATH", fresh / "tmp" / "failover")
    sched_main.ensure_runtime_dirs()
    for sub in sched_main.CUSTOM_CONFIGS_DIRS:
        assert (fresh / "configs" / sub).is_dir()
    assert (fresh / "tmp" / "failover").is_dir() and (fresh / "pro").is_dir()


# --- generate_configs -----------------------------------------------------------------------------


def test_generate_configs_runs_the_generator_and_snapshots_the_variables(sched_main, sandbox, monkeypatch):
    sandbox.NGINX_VARIABLES_PATH.write_text("A=1\n")
    calls = []
    monkeypatch.setattr(sched_main, "subprocess_run", lambda cmd, **kw: calls.append((cmd, kw)) or SimpleNamespace(returncode=0))
    assert sched_main.generate_configs() is True
    cmd = calls[0][0]
    assert cmd[1].endswith("gen/main.py")
    assert cmd[cmd.index("--output") + 1] == sandbox.CONFIG_PATH.as_posix()
    assert sandbox.NGINX_TMP_VARIABLES_PATH.read_text() == "A=1\n"


def test_generate_configs_failure_returns_false_and_keeps_the_old_snapshot(sched_main, sandbox, monkeypatch, caplog):
    sandbox.NGINX_VARIABLES_PATH.write_text("NEW=1\n")
    sandbox.NGINX_TMP_VARIABLES_PATH.write_text("OLD=1\n")
    monkeypatch.setattr(sched_main, "subprocess_run", lambda cmd, **kw: SimpleNamespace(returncode=1))
    with caplog.at_level(logging.ERROR):
        assert sched_main.generate_configs() is False
    assert sandbox.NGINX_TMP_VARIABLES_PATH.read_text() == "OLD=1\n"
    assert "Config generator failed" in caplog.text


def test_the_render_for_jobs_holds_applying_changes_and_releases_it(sched_main, monkeypatch):
    seen = []
    monkeypatch.setattr(sched_main, "generate_configs", lambda: seen.append(sched_main.APPLYING_CHANGES.is_set()) or True)
    sched_main.APPLYING_CHANGES.clear()
    assert sched_main._render_holding_applying_changes() is True
    assert seen == [True]
    assert not sched_main.APPLYING_CHANGES.is_set()


def test_the_render_for_jobs_leaves_an_event_someone_else_holds(sched_main, monkeypatch):
    monkeypatch.setattr(sched_main, "generate_configs", lambda: False)
    sched_main.APPLYING_CHANGES.set()
    try:
        assert sched_main._render_holding_applying_changes() is False
        assert sched_main.APPLYING_CHANGES.is_set()
    finally:
        sched_main.APPLYING_CHANGES.clear()


def test_the_render_for_jobs_releases_the_event_when_the_generator_raises(sched_main, monkeypatch):
    monkeypatch.setattr(sched_main, "generate_configs", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    sched_main.APPLYING_CHANGES.clear()
    with pytest.raises(RuntimeError):
        sched_main._render_holding_applying_changes()
    assert not sched_main.APPLYING_CHANGES.is_set()


def test_generate_configs_for_jobs_waits_for_the_failover_backup_first(sched_main, monkeypatch):
    sched_main.BACKING_UP_FAILOVER.set()
    monkeypatch.setattr(sched_main, "sleep", lambda s: sched_main.BACKING_UP_FAILOVER.clear())
    monkeypatch.setattr(sched_main, "generate_configs", lambda: True)
    assert sched_main.generate_configs_for_jobs() is True
    assert not sched_main.BACKING_UP_FAILOVER.is_set()


# --- claim_changes --------------------------------------------------------------------------------


def test_claim_changes_acknowledges_before_it_reads_the_snapshot(sched_main, fake_sched, monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Paris")
    order = []
    fake_sched.db.checked_changes = lambda changes, plugins_changes=None: order.append("checked") or ""
    fake_sched.db.get_config = lambda: order.append("config") or {"A": "1"}
    env = sched_main.claim_changes(["config"], plugins_changes="all")
    assert order == ["checked", "config"]
    assert env == {"A": "1", "DATABASE_URI": fake_sched.db.database_uri, "TZ": "Europe/Paris"}


def test_claim_changes_still_returns_a_snapshot_when_the_acknowledgement_fails(sched_main, fake_sched, monkeypatch, caplog):
    monkeypatch.delenv("TZ", raising=False)
    fake_sched.db.checked_changes_result = "locked"
    with caplog.at_level(logging.ERROR):
        env = sched_main.claim_changes()
    assert "setting the changes to checked in the database : locked" in caplog.text
    assert "TZ" not in env and env["SERVER_NAME"] == "www.example.com"


def test_claim_changes_survives_an_exception_from_the_database(sched_main, fake_sched, caplog):
    fake_sched.db.checked_changes = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("gone"))
    with caplog.at_level(logging.ERROR):
        env = sched_main.claim_changes()
    assert "Error while setting changes to checked in the database: gone" in caplog.text
    assert env["DATABASE_URI"] == fake_sched.db.database_uri


# --- reaching the instances -----------------------------------------------------------------------


def test_wait_for_reachable_instance_returns_at_once_when_one_answers(sched_main, fake_sched, fake_api):
    fake_sched.db.instances = [instance("bw1")]
    assert sched_main.wait_for_reachable_instance(timeout=5) is True
    assert [a.endpoint for a in fake_sched.apis] == ["http://bw1:5000/"]


def test_wait_for_reachable_instance_does_not_add_a_known_instance_twice(sched_main, fake_sched, fake_api):
    fake_sched.db.instances = [instance("bw1")]
    fake_sched.apis = [FakeApi("http://bw1:5000/")]
    assert sched_main.wait_for_reachable_instance(timeout=5) is True
    assert len(fake_sched.apis) == 1


def test_wait_for_reachable_instance_skips_an_instance_that_does_not_answer(sched_main, fake_sched, fake_api):
    fake_sched.db.instances = [instance("down"), instance("up")]
    fake_api.answers["down"] = (False, "refused", 500, {})
    fake_api.answers["up"] = (True, "", 200, {"status": "success", "msg": "loading"})
    assert sched_main.wait_for_reachable_instance(timeout=5) is True
    assert [a.endpoint for a in fake_sched.apis] == ["http://up:5000/"]


def test_wait_for_reachable_instance_waits_then_gives_up(sched_main, fake_sched, fake_api, monkeypatch, caplog):
    fake_sched.db.instances = [instance("down")]
    fake_api.answers["down"] = ConnectionError("refused")
    clock = [0.0]
    monkeypatch.setattr(sched_main, "monotonic", lambda: clock[0])
    sleeps = []
    monkeypatch.setattr(sched_main, "sleep", lambda s: sleeps.append(s) or clock.__setitem__(0, clock[0] + s))
    with caplog.at_level(logging.INFO):
        assert sched_main.wait_for_reachable_instance(timeout=6) is False
    assert sleeps == [2, 2, 2]
    assert caplog.text.count("Waiting up to 6s") == 1
    assert "No BunkerWeb instance answered within 6s" in caplog.text
    assert fake_sched.apis == []


def test_wait_for_reachable_instance_succeeds_once_an_instance_comes_up(sched_main, fake_sched, fake_api, monkeypatch):
    fake_sched.db.instances = [instance("bw1")]
    fake_api.answers["bw1"] = ConnectionError("not yet")

    def wake(seconds):
        fake_api.answers.pop("bw1")

    monkeypatch.setattr(sched_main, "sleep", wake)
    assert sched_main.wait_for_reachable_instance(timeout=60) is True


# --- send_file_to_bunkerweb -----------------------------------------------------------------------


def test_send_marks_answering_instances_up_and_registers_them(sched_main, fake_sched, fake_api, tmp_path):
    fake_sched.db.instances = [instance("bw1")]
    fake_sched.responses = {"bw1": {"status": "success"}}
    assert sched_main.send_file_to_bunkerweb(tmp_path, "/confs") is True
    assert ("update_instance", "bw1", "up") in fake_sched.db.calls
    assert [a.endpoint for a in fake_sched.apis] == ["http://bw1:5000/"]
    assert fake_sched.sent == [(tmp_path.as_posix(), "/confs")]


def test_send_drops_a_known_instance_that_did_not_answer(sched_main, fake_sched, fake_api, tmp_path, caplog):
    fake_sched.db.instances = [instance("bw1"), instance("bw2")]
    fake_sched.apis = [FakeApi("http://bw1:5000/"), FakeApi("http://bw2:5000/")]
    fake_sched.responses = {"bw1": {"status": "success"}}
    with caplog.at_level(logging.WARNING):
        assert sched_main.send_file_to_bunkerweb(tmp_path, "/confs") is True
    assert [a.endpoint for a in fake_sched.apis] == ["http://bw1:5000/"]
    assert ("update_instance", "bw2", "down") in fake_sched.db.calls
    assert "removing them from the list of reachable instances: bw2:5000" in caplog.text


def test_send_to_one_instance_does_not_evict_the_others(sched_main, fake_sched, fake_api, tmp_path):
    fake_sched.db.instances = [instance("bw1"), instance("bw2")]
    other = FakeApi("http://bw2:5000/")
    target = FakeApi("http://bw1:5000/")
    fake_sched.apis = [target, other]
    caller = FakeScheduler(apis=[target])
    caller.responses = {"bw1": {"status": "success"}}
    sched_main.send_file_to_bunkerweb(tmp_path, "/confs", api_caller=caller)
    assert fake_sched.apis == [target, other]
    assert all(call[1] != "bw2" for call in fake_sched.db.calls if call[0] == "update_instance")
    assert caller.sent == [(tmp_path.as_posix(), "/confs")] and fake_sched.sent == []


def test_send_reports_a_total_failure(sched_main, fake_sched, fake_api, tmp_path, caplog):
    fake_sched.db.instances = [instance("bw1")]
    fake_sched.send_ok = False
    with caplog.at_level(logging.ERROR):
        assert sched_main.send_file_to_bunkerweb(tmp_path, "/confs") is False
    assert "Error while sending" in caplog.text


def test_send_logs_a_database_error_while_updating_the_status(sched_main, fake_sched, fake_api, tmp_path, caplog):
    fake_sched.db.instances = [instance("bw1")]
    fake_sched.responses = {"bw1": {"status": "success"}}
    fake_sched.db.update_instance_result = "locked"
    with caplog.at_level(logging.ERROR):
        sched_main.send_file_to_bunkerweb(tmp_path, "/confs")
    assert "Couldn't update instance bw1 status to down in the database: locked" in caplog.text


def test_send_with_ignore_fail_sending_config_leaves_the_instances_alone(sched_main, fake_sched, fake_api, tmp_path, monkeypatch):
    monkeypatch.setattr(sched_main, "IGNORE_FAIL_SENDING_CONFIG", True)
    fake_sched.db.instances = [instance("bw1")]
    assert sched_main.send_file_to_bunkerweb(tmp_path, "/confs") is True
    assert fake_sched.db.calls == []


def test_send_shows_the_https_port_for_an_https_instance(sched_main, fake_sched, fake_api, tmp_path, caplog):
    fake_sched.db.instances = [instance("bw1", listen_https=True)]
    fake_sched.apis = [FakeApi("https://bw1:5443/")]
    fake_sched.responses = {"other": {"status": "success"}}
    with caplog.at_level(logging.WARNING):
        sched_main.send_file_to_bunkerweb(tmp_path, "/confs")
    assert "bw1:5443" in caplog.text


# --- pre_push_configuration -----------------------------------------------------------------------


@pytest.fixture
def pushing(sched_main, fake_sched, monkeypatch):
    """pre_push_configuration with the render and the sends stubbed; returns what happened."""
    state = SimpleNamespace(rendered=True, sends=[], send_raises=None)
    monkeypatch.setattr(sched_main, "generate_configs", lambda logger=None: state.rendered)

    def send(path, endpoint, *args, **kwargs):
        state.sends.append(endpoint)
        if state.send_raises:
            raise state.send_raises
        return True

    monkeypatch.setattr(sched_main, "send_file_to_bunkerweb", send)
    return state


def test_pre_push_does_nothing_without_a_known_instance(sched_main, fake_sched, pushing):
    assert sched_main.pre_push_configuration({}, first_start=False) == (False, False, False)
    assert pushing.sends == []


def test_pre_push_on_first_start_waits_for_an_instance(sched_main, fake_sched, pushing, monkeypatch):
    monkeypatch.setattr(sched_main, "wait_for_reachable_instance", lambda: False)
    assert sched_main.pre_push_configuration({}, first_start=True) == (False, False, False)


def test_pre_push_reports_a_failed_generation_apart_from_a_failed_push(sched_main, fake_sched, pushing):
    fake_sched.apis = [FakeApi()]
    pushing.rendered = False
    assert sched_main.pre_push_configuration({}, first_start=False) == (False, False, True)
    assert pushing.sends == []


def test_pre_push_pushes_confs_and_cache_then_reloads(sched_main, fake_sched, pushing):
    fake_sched.apis = [FakeApi()]
    assert sched_main.pre_push_configuration({"SERVER_NAME": "a b c d e f"}, first_start=False) == (True, True, False)
    assert sorted(pushing.sends) == ["/cache", "/confs"]
    method, url, kwargs = fake_sched.send_to_apis_calls[0]
    assert (method, url) == ("POST", "/reload?test=yes")
    assert kwargs["timeout"] == max(sched_main.RELOAD_MIN_TIMEOUT, 18)


def test_pre_push_without_configuration_testing_reloads_with_test_no(sched_main, fake_sched, pushing, monkeypatch):
    monkeypatch.setattr(sched_main, "DISABLE_CONFIGURATION_TESTING", True)
    fake_sched.apis = [FakeApi()]
    sched_main.pre_push_configuration({}, first_start=False)
    assert fake_sched.send_to_apis_calls[0][1] == "/reload?test=no"


def test_pre_push_counts_one_node_taking_the_configuration(sched_main, fake_sched, pushing):
    fake_sched.apis = [FakeApi(), FakeApi("http://bw2:5000/")]
    fake_sched.reload_answer = (False, {"bw1": {"status": "success"}, "bw2": {"status": "error"}})
    assert sched_main.pre_push_configuration({}, first_start=False) == (True, True, False)


def test_pre_push_fails_when_no_node_took_it(sched_main, fake_sched, pushing):
    fake_sched.apis = [FakeApi()]
    fake_sched.reload_answer = (False, {"bw1": {"status": "error"}})
    assert sched_main.pre_push_configuration({}, first_start=False) == (False, True, False)


def test_pre_push_fails_when_a_push_raised_even_if_the_reload_worked(sched_main, fake_sched, pushing, caplog):
    fake_sched.apis = [FakeApi()]
    pushing.send_raises = ConnectionError("reset")
    with caplog.at_level(logging.ERROR):
        assert sched_main.pre_push_configuration({}, first_start=False) == (False, True, False)
    assert "Exception while sending the configuration before running jobs : reset" in caplog.text


def test_pre_push_ignore_fail_sending_config_proceeds_regardless(sched_main, fake_sched, pushing, monkeypatch):
    monkeypatch.setattr(sched_main, "IGNORE_FAIL_SENDING_CONFIG", True)
    fake_sched.apis = [FakeApi()]
    fake_sched.reload_answer = (False, {})
    assert sched_main.pre_push_configuration({}, first_start=False) == (True, True, False)


def test_pre_push_with_the_apis_emptied_by_the_sends_reports_nothing_delivered(sched_main, fake_sched, pushing, monkeypatch):
    fake_sched.apis = [FakeApi()]
    monkeypatch.setattr(sched_main, "send_file_to_bunkerweb", lambda *a, **k: fake_sched.apis.clear() or False)
    fake_sched.reload_answer = (True, {})
    assert sched_main.pre_push_configuration({}, first_start=False) == (False, True, False)


# --- backup_failover ------------------------------------------------------------------------------


class Job:
    def __init__(self, result=(True, "")):
        self.result = result
        self.cached = []

    def cache_dir(self, path, job_name=None):
        self.cached.append((path, job_name))
        return self.result


def test_backup_failover_snapshots_config_custom_configs_and_cache(sched_main, sandbox, monkeypatch):
    job = Job()
    monkeypatch.setattr(sched_main, "JOB", job, raising=False)
    (sandbox.CONFIG_PATH / "nginx.conf").write_text("c")
    (sandbox.CUSTOM_CONFIGS_PATH / "http").mkdir()
    (sandbox.CUSTOM_CONFIGS_PATH / "http" / "a.conf").write_text("a")
    (sandbox.CACHE_PATH / "plug").mkdir()
    (sandbox.CACHE_PATH / "plug" / "f").write_text("f")
    (sandbox.FAILOVER_PATH / "stale").write_text("old")
    sched_main.backup_failover()
    assert (sandbox.FAILOVER_PATH / "config" / "nginx.conf").read_text() == "c"
    assert (sandbox.FAILOVER_PATH / "custom_configs" / "http" / "a.conf").read_text() == "a"
    assert (sandbox.FAILOVER_PATH / "cache" / "plug" / "f").read_text() == "f"
    assert not (sandbox.FAILOVER_PATH / "stale").exists()
    assert job.cached == [(sandbox.FAILOVER_PATH, "failover-backup")]
    assert not sched_main.BACKING_UP_FAILOVER.is_set()


def test_backup_failover_logs_a_failed_cache_and_still_releases_the_flag(sched_main, sandbox, monkeypatch, caplog):
    monkeypatch.setattr(sched_main, "JOB", Job((False, "db busy")), raising=False)
    with caplog.at_level(logging.ERROR):
        sched_main.backup_failover()
    assert "Error while caching failover backup: db busy" in caplog.text
    assert not sched_main.BACKING_UP_FAILOVER.is_set()


def test_backup_failover_skips_a_source_it_cannot_copy(sched_main, sandbox, monkeypatch, caplog):
    import shutil

    sandbox.CACHE_PATH.rmdir()
    monkeypatch.setattr(sched_main, "JOB", Job(), raising=False)
    with caplog.at_level(logging.ERROR):
        sched_main.backup_failover()
    assert "Error copying" in caplog.text
    assert (sandbox.FAILOVER_PATH / "config").is_dir()
    assert shutil


def test_backup_failover_releases_the_flag_when_even_the_job_raises(sched_main, sandbox, monkeypatch, caplog):
    class Boom:
        def cache_dir(self, *a, **k):
            raise RuntimeError("nope")

    monkeypatch.setattr(sched_main, "JOB", Boom(), raising=False)
    with caplog.at_level(logging.ERROR):
        sched_main.backup_failover()
    assert "Failed to initialize failover backup: nope" in caplog.text
    assert not sched_main.BACKING_UP_FAILOVER.is_set()
