"""src/scheduler/main.py main(): startup, the first iteration, the once-jobs publication and the change-detection loop.

``main()`` is driven end to end over fakes (database, JobScheduler, API clients). The run ends when the
``HEALTHY_PATH.is_file()`` call that closes each iteration raises ``StopLoop``, or when ``stop()`` is called.
No signal handler is installed, no real directory outside ``tmp_path`` is touched, nothing sleeps.
"""

import logging
import sys
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace

import pytest

from scheduler_fakes import instance


class StopLoop(BaseException):
    """Ends main(): raised by the patched stop()/_exit(). main()'s bare ``except`` turns any exception into stop(1)."""


class IterationsDone(StopLoop):
    """Raised by the end-of-iteration hook: the run is over, and the stop(1) it ends up in is not a real stop."""


class HealthyProxy:
    """HEALTHY_PATH stand-in: ``is_file()`` marks the end of an iteration and calls back into the test."""

    def __init__(self, real, hook):
        self.real = real
        self.hook = hook
        self.count = 0

    def is_file(self):
        self.count += 1
        self.hook(self.count)
        return self.real.is_file()

    def write_text(self, *args, **kwargs):
        return self.real.write_text(*args, **kwargs)

    def unlink(self, *args, **kwargs):
        return self.real.unlink(*args, **kwargs)


class InlineExecutor:
    """Runs every submitted task on the calling thread, so what main() hands to the pool is done when submit() returns.

    The real pool made ``backup_failover`` (submitted and never awaited at the end of a successful iteration) race
    the assertions on it.
    """

    def submit(self, fn, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as e:
            future.set_exception(e)
        return future

    def shutdown(self, wait=True):
        pass


class JobStub:
    def __init__(self):
        self.restored = []

    def restore_cache(self, job_name=None, plugin_id=None):
        self.restored.append((job_name, plugin_id))


@pytest.fixture
def drive(sched_main, sandbox, fake_sched, fake_api, monkeypatch, tmp_path):
    h = SimpleNamespace(
        main=sched_main,
        sched=fake_sched,
        db=fake_sched.db,
        api=fake_api,
        sandbox=sandbox,
        stops=[],
        saver_calls=[],
        saver_rc=0,
        sleeps=[],
        sends=[],
        renders=0,
        render_ok=True,
        backups=0,
        iterations=1,
        on_iteration={},
        job=JobStub(),
        database_args=[],
        caches=set(),
    )
    schedule_calls = []
    h.schedule_calls = schedule_calls

    def stop(status):
        if not isinstance(sys.exc_info()[1], StopLoop):
            h.stops.append(status)
        raise StopLoop(status)

    def end_of_iteration(count):
        if count in h.on_iteration:
            h.on_iteration[count]()
        if count >= h.iterations:
            raise IterationsDone("iterations done")

    def generate(logger=None):
        h.renders += 1
        return h.render_ok

    monkeypatch.setattr(sched_main, "environ", dict(__import__("os").environ))
    monkeypatch.setattr(sched_main, "SCHEDULER_TASKS_EXECUTOR", InlineExecutor())
    monkeypatch.setattr(sched_main, "ensure_runtime_dirs", lambda: None)
    monkeypatch.setattr(sched_main, "install_signal_handlers", lambda: None)
    monkeypatch.setattr(sched_main, "handle_docker_secrets", lambda: {})
    monkeypatch.setattr(sched_main, "stop", stop)
    monkeypatch.setattr(sched_main, "_exit", stop)
    monkeypatch.setattr(sched_main, "sleep", lambda s: h.sleeps.append(s))
    monkeypatch.setattr(sched_main, "run_pending", lambda: None)
    monkeypatch.setattr(sched_main, "schedule_every", lambda n: SimpleNamespace(seconds=SimpleNamespace(do=lambda fn: schedule_calls.append((n, fn)))))
    monkeypatch.setattr(sched_main, "subprocess_run", lambda cmd, **kw: h.saver_calls.append(cmd) or SimpleNamespace(returncode=h.saver_rc))
    monkeypatch.setattr(sched_main, "Database", lambda logger, sqlalchemy_string=None: h.database_args.append(sqlalchemy_string) or fake_sched.db)
    monkeypatch.setattr(sched_main, "JobScheduler", lambda logger, db=None, generate_configs=None: fake_sched)
    monkeypatch.setattr(sched_main, "Job", lambda logger, file, db: h.job)
    monkeypatch.setattr(sched_main, "generate_configs", generate)
    monkeypatch.setattr(sched_main, "send_file_to_bunkerweb", lambda path, endpoint, *a, **k: h.sends.append(endpoint))
    monkeypatch.setattr(sched_main, "backup_failover", lambda: setattr(h, "backups", h.backups + 1))
    monkeypatch.setattr(sched_main, "wait_for_reachable_instance", lambda timeout=60: bool(fake_sched.apis))
    monkeypatch.setattr(sched_main, "generate_caches", lambda: h.caches)
    monkeypatch.setattr(sched_main, "get_plugin_validator", lambda: SimpleNamespace(_Configurator__validate_plugin=lambda data: (True, "")))
    monkeypatch.setattr(sched_main, "HEALTHY_PATH", HealthyProxy(sandbox.HEALTHY_PATH, end_of_iteration))
    monkeypatch.setattr(sched_main, "RUN", True)
    monkeypatch.setattr(sched_main, "RELOAD_SCAN_CONFIGS", False)
    monkeypatch.setattr(sched_main, "JOB", None, raising=False)
    monkeypatch.setattr(sys, "argv", ["main.py"])
    sched_main.APPLYING_CHANGES.clear()
    sched_main.NEEDS_CONFIG_PASSES.clear()
    fake_sched.db.instances = [instance("bw1")]
    fake_sched.reload_answer = (True, {"bw1": {"status": "success", "msg": ""}})

    def run():
        with pytest.raises(StopLoop):
            sched_main.main()

    h.run = run
    yield h
    sched_main.APPLYING_CHANGES.clear()


def reloads(h):
    return [c for c in h.sched.send_to_apis_calls if c[1].startswith("/reload")]


def set_metadata_calls(h):
    return [c[1] for c in h.db.calls if c[0] == "set_metadata"]


# --- startup --------------------------------------------------------------------------------------


def test_an_already_running_scheduler_exits_before_touching_anything(drive):
    pid = drive.sandbox.root / "var" / "run" / "bunkerweb" / "scheduler.pid"
    pid.write_text("123")
    drive.run()
    assert drive.stops == [1]
    assert pid.read_text() == "123"
    assert drive.saver_calls == []


def test_startup_writes_the_pid_file_and_runs_the_config_saver_with_first_run(drive):
    drive.run()
    pid = drive.sandbox.root / "var" / "run" / "bunkerweb" / "scheduler.pid"
    assert pid.read_text().isdigit()
    first = drive.saver_calls[0]
    assert first[1].endswith("gen/save_config.py") and "--first-run" in first
    assert Path(first[first.index("--variables") + 1]) == drive.sandbox.NGINX_TMP_VARIABLES_PATH
    assert "PATH=" in drive.sandbox.NGINX_TMP_VARIABLES_PATH.read_text()


def test_the_variables_argument_points_the_saver_and_the_database_at_that_file(drive, tmp_path, monkeypatch):
    variables = tmp_path / "vars.env"
    variables.write_text("DATABASE_URI=sqlite:////tmp/from-file.db\nFOO=bar\n")
    monkeypatch.setattr(sys, "argv", ["main.py", "--variables", str(variables)])
    drive.run()
    assert drive.database_args == ["sqlite:////tmp/from-file.db"]
    assert drive.saver_calls[0][drive.saver_calls[0].index("--variables") + 1] == str(variables)


def test_docker_secrets_are_loaded_into_the_environment(drive, monkeypatch):
    monkeypatch.setattr(drive.main, "handle_docker_secrets", lambda: {"SECRET_A": "1"})
    drive.run()
    assert drive.main.environ["SECRET_A"] == "1"


def test_a_failing_config_saver_is_reported_but_startup_goes_on(drive, caplog):
    drive.saver_rc = 2
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "Config saver failed with return code 2" in caplog.text
    assert drive.db.calls  # the scheduler still went on to read the database


def test_a_read_only_database_skips_the_config_saver(drive, caplog):
    drive.db.readonly = True
    with caplog.at_level(logging.WARNING):
        drive.run()
    assert drive.saver_calls == []
    assert "The database is read-only, no need to save the changes in the configuration" in caplog.text
    assert not drive.sandbox.NGINX_TMP_VARIABLES_PATH.exists()


def test_startup_waits_for_the_database_to_be_initialised(drive, caplog):
    drive.db.metadata_script = ["connection refused", {**drive.db.metadata, "is_initialized": False}]
    with caplog.at_level(logging.WARNING):
        drive.run()
    assert drive.sleeps[:2] == [5, 5]
    assert caplog.text.count("Database is not initialized, retrying in 5s") == 2


def test_startup_publishes_the_environment_to_the_job_scheduler(drive, monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Paris")
    drive.db.config = {"SERVER_NAME": "a.example", "X": "1"}
    drive.run()
    assert drive.sched.env["SERVER_NAME"] == "a.example"
    assert drive.sched.env["DATABASE_URI"] == drive.db.database_uri
    assert drive.sched.env["TZ"] == "Europe/Paris"
    assert drive.sched.env["RELOAD_MIN_TIMEOUT"] == str(drive.main.RELOAD_MIN_TIMEOUT)
    assert [a.endpoint for a in drive.sched.apis] == ["http://bw1:5000/"]


def test_a_failed_startup_is_logged_and_stops_with_status_one(drive, caplog):
    drive.db.get_instances = lambda: (_ for _ in ()).throw(RuntimeError("db gone"))
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert drive.stops == [1]
    assert "Exception while executing scheduler" in caplog.text and "db gone" in caplog.text


def test_manual_plugins_found_at_startup_are_saved_and_trigger_a_config_saver_run(drive):
    plugin = drive.sandbox.EXTERNAL_PLUGINS_PATH / "mine"
    (plugin / "ui").mkdir(parents=True)
    (plugin / "plugin.json").write_text('{"id": "mine", "name": "mine", "jobs": [{"name": "j"}]}')
    drive.run()
    saved = [c for c in drive.db.calls if c[0] == "update_external_plugins" and c[2] == "external"]
    assert saved and saved[0][1][0]["id"] == "mine" and saved[0][1][0]["page"] is True
    assert saved[0][1][0]["jobs"] == [{"name": "j"}]
    assert len(drive.saver_calls) == 2
    assert drive.sched.updated_jobs >= 1


def test_an_invalid_manual_plugin_json_is_ignored_and_preserved(drive, caplog):
    plugin = drive.sandbox.EXTERNAL_PLUGINS_PATH / "broken"
    plugin.mkdir()
    (plugin / "plugin.json").write_text("[1, 2]")
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "Ignoring invalid manual plugin broken" in caplog.text
    assert not [c for c in drive.db.calls if c[0] == "update_external_plugins"]


def test_a_plugin_validation_that_is_unavailable_skips_the_manual_plugin_scan(drive, monkeypatch, caplog):
    monkeypatch.setattr(drive.main, "get_plugin_validator", lambda: (_ for _ in ()).throw(OSError("settings.json missing")))
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "Skipping manual plugin scan because validation is unavailable: settings.json missing" in caplog.text


def test_plugins_changed_in_the_database_are_regenerated_before_the_first_render(drive):
    drive.db.metadata.update(pro_plugins_changed=True, external_plugins_changed=True)
    drive.run()
    kinds = [c[1] for c in drive.db.calls if c[0] == "get_plugins"]
    assert "pro" in kinds and "external" in kinds
    assert len(drive.saver_calls) >= 2


def test_plugin_download_jobs_failures_are_named(drive, caplog):
    drive.sched.run_once_result = False
    drive.sched.failed_jobs = ["misc/download-plugins"]
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert drive.sched.run_once_calls[0] == ["misc", "pro"]
    assert "Plugin download jobs failed: misc/download-plugins" in caplog.text


def test_plugin_download_failures_without_names_still_log(drive, caplog):
    drive.sched.run_once_result = False
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "At least one plugin download job failed (no failed-job names captured)" in caplog.text


def test_the_failover_backup_cache_is_restored_and_changes_are_claimed_before_the_first_render(drive):
    order = []
    original = drive.db.checked_changes
    drive.db.checked_changes = lambda changes=None, plugins_changes=None: order.append("claim") or original(changes, plugins_changes)
    drive.main.generate_configs = lambda logger=None: order.append("render") or True
    drive.run()
    assert drive.job.restored == [("failover-backup", "jobs")]
    assert order[:2] == ["claim", "render"]


# --- the first iteration --------------------------------------------------------------------------


def test_the_first_iteration_pushes_then_runs_jobs_then_publishes_once(drive):
    drive.run()
    sched = drive.sched
    env, changed, ignored = sched.reload_calls[0]
    assert ignored == ["misc", "pro"]
    assert env["TZ"] == "UTC" or "TZ" in env
    assert drive.renders == 2  # the pre-push render, then the one that picks up files the jobs created
    assert len(reloads(drive)) == 2
    assert set_metadata_calls(drive)[0] == {"failover": False, "failover_message": ""}
    assert drive.backups == 1
    assert drive.sandbox.HEALTHY_PATH.is_file() is False  # the proxy raised before the file was written


def test_the_first_iteration_marks_the_scheduler_first_start_as_done(drive):
    drive.db.metadata["scheduler_first_start"] = True
    drive.run()
    assert {"scheduler_first_start": False} in set_metadata_calls(drive)


@pytest.mark.parametrize(
    "answer, expected_log",
    [
        ("The database is read-only, the changes will not be saved", "scheduler first start will not be saved"),
        ("boom", "setting the scheduler first start : boom"),
    ],
)
def test_a_refused_first_start_flag_is_logged(drive, caplog, answer, expected_log):
    drive.db.metadata["scheduler_first_start"] = True
    drive.db.set_metadata_result = answer
    with caplog.at_level(logging.WARNING):
        drive.run()
    assert expected_log in caplog.text


def test_the_healthcheck_job_is_scheduled_every_interval(drive):
    drive.iterations = 2
    drive.on_iteration[1] = lambda: drive.db.metadata.update(plugins_config_changed=["x"])
    drive.run()
    assert drive.schedule_calls[0] == (drive.main.HEALTHCHECK_INTERVAL, drive.main.healthcheck_job)


def test_without_any_instance_the_reload_is_skipped_but_the_run_counts_as_successful(drive, caplog):
    drive.db.instances = []
    with caplog.at_level(logging.INFO):
        drive.run()
    assert reloads(drive) == []
    assert "No BunkerWeb instance found, skipping bunkerweb reload" in caplog.text
    assert set_metadata_calls(drive)[0]["failover"] is False


def test_failing_once_jobs_are_named_in_the_log(drive, caplog):
    drive.sched.reload_result = False
    drive.sched.failed_jobs = ["letsencrypt/certbot-new"]
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "Jobs failed in run_once(): letsencrypt/certbot-new" in caplog.text


def test_with_a_read_only_database_the_job_caches_are_restored_from_the_database(drive, caplog):
    drive.db.readonly = True
    drive.caches = {"plug/j"}
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "generate_caches() failed to restore: plug/j" in caplog.text


def test_a_crash_while_restoring_the_job_caches_is_logged(drive, monkeypatch, caplog):
    drive.db.readonly = True
    monkeypatch.setattr(drive.main, "generate_caches", lambda: (_ for _ in ()).throw(RuntimeError("disk")))
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "Exception while restoring the job caches : disk" in caplog.text


def test_a_fault_in_the_pre_push_is_a_failed_push_not_a_reason_to_leave(drive, monkeypatch, caplog):
    monkeypatch.setattr(drive.main, "pre_push_configuration", lambda env, first: (_ for _ in ()).throw(RuntimeError("socket")))
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "Exception while pushing the configuration before running jobs : socket" in caplog.text
    assert drive.stops == []
    assert drive.sched.reload_calls == []  # deferred: the once-jobs wait for a configuration the instances hold


# --- a generation that fails ----------------------------------------------------------------------


def test_a_failed_generation_defers_the_jobs_and_reports_a_retry_delay(drive, caplog):
    drive.render_ok = False
    with caplog.at_level(logging.ERROR):
        drive.run()
    metadata = set_metadata_calls(drive)[0]
    assert metadata["failover"] is True
    assert "Retrying in 30s (failed attempt 1)" in metadata["failover_message"]
    assert drive.sched.reload_calls == []
    assert "could not be generated, deferring them (1/3)" in caplog.text
    assert "retrying the generation in 30s" in caplog.text
    assert reloads(drive) == []


def test_the_retry_runs_again_once_the_delay_elapsed_and_clears_the_failover(drive, monkeypatch, caplog):
    drive.render_ok = False
    drive.iterations = 2
    clock = iter(range(0, 10_000, 100))
    monkeypatch.setattr(drive.main, "monotonic", lambda: next(clock))
    drive.on_iteration[1] = lambda: setattr(drive, "render_ok", True)
    with caplog.at_level(logging.INFO):
        drive.run()
    assert "Retrying the pending configuration" in caplog.text
    calls = set_metadata_calls(drive)
    assert calls[0]["failover"] is True and calls[1]["failover"] is False
    assert drive.sched.reload_calls


def test_a_generation_that_keeps_failing_gives_way_after_the_bounded_deferrals(drive, monkeypatch, caplog):
    drive.render_ok = False
    drive.iterations = drive.main.PRE_PUSH_MAX_DEFERRALS + 1
    clock = iter(range(0, 10**7, 1000))
    monkeypatch.setattr(drive.main, "monotonic", lambda: next(clock))
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "could not be generated, deferring them (3/3)" in caplog.text
    assert len(drive.sched.reload_calls) == 1  # the jobs finally ran, against the old configuration


# --- the reload and the failover ------------------------------------------------------------------


def answer(drive, status, msg=""):
    drive.sched.reload_answer = (status == "success", {"bw1": {"status": status, "msg": msg}})


def test_a_config_check_failure_puts_the_instance_in_failover_and_fails_over_to_the_last_working_config(drive, caplog):
    answer(drive, "error", "config check failed: unknown directive\nnginx: [emerg] bad")
    for sub in ("config", "custom_configs", "cache"):
        (drive.sandbox.FAILOVER_PATH / sub).mkdir(parents=True, exist_ok=True)
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert ("update_instance", "bw1", "failover") in drive.db.calls
    metadata = [m for m in set_metadata_calls(drive) if m["failover"]][0]
    assert "bw1:5000 - nginx: [emerg] bad" in metadata["failover_message"]
    assert "failing over to last working configuration" in caplog.text
    assert any(c[1] == "/reload?test=yes" for c in drive.sched.send_to_apis_calls)
    assert drive.backups == 0


def test_without_a_stored_failover_the_failover_is_skipped(drive, caplog):
    answer(drive, "error", "config check failed: x")
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "No failover configuration found, ignoring failover" in caplog.text


def test_a_failed_reload_with_a_failover_that_also_fails_is_logged(drive, caplog):
    answer(drive, "error", "config check failed: x")
    for sub in ("config", "custom_configs", "cache"):
        (drive.sandbox.FAILOVER_PATH / sub).mkdir(parents=True, exist_ok=True)
    drive.sched.send_to_apis = lambda method, url, **kw: (False, {"bw1": {"status": "error", "msg": "config check failed: x"}})
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "Error while reloading bunkerweb with failover configuration, skipping" in caplog.text


def test_an_instance_that_is_down_is_dropped_and_no_failover_is_attempted(drive, caplog):
    answer(drive, "error", "connection refused")
    with caplog.at_level(logging.WARNING):
        drive.run()
    assert ("update_instance", "bw1", "down") in drive.db.calls
    assert drive.sched.apis == []
    assert "No BunkerWeb instance is reachable, skipping failover" in caplog.text


def test_an_instance_still_applying_another_change_is_kept_up_and_the_generation_retried(drive):
    answer(drive, "error", "a reload is in progress (12s)")
    drive.run()
    assert ("update_instance", "bw1", "up") in drive.db.calls
    metadata = set_metadata_calls(drive)[0]
    assert metadata["failover"] is True and "The configuration could not be confirmed" in metadata["failover_message"]


def test_a_failed_instance_initialisation_is_a_generation_failure(drive):
    answer(drive, "error", "reload failed: nginx did not start")
    drive.run()
    assert ("update_instance", "bw1", "failover") in drive.db.calls
    assert "The configuration could not be confirmed" in set_metadata_calls(drive)[0]["failover_message"]


def test_an_unconfirmed_reload_readiness_is_logged_as_a_warning(drive, caplog):
    drive.sched.reload_answer = (True, {"bw1": {"status": "success", "msg": "workers not ready yet", "confirmed": False}})
    with caplog.at_level(logging.WARNING):
        drive.run()
    assert "Reload readiness is unconfirmed on bw1: workers not ready yet" in caplog.text
    assert set_metadata_calls(drive)[0]["failover"] is False


def test_a_refused_failover_flag_write_does_not_stop_the_scheduler(drive, monkeypatch, caplog):
    original = drive.db.set_metadata
    monkeypatch.setattr(drive.db, "set_metadata", lambda data: (_ for _ in ()).throw(RuntimeError("db busy")) if "failover" in data else original(data))
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "Error while setting failover to true in the database: db busy" in caplog.text


def test_an_instance_status_update_error_is_logged(drive, caplog):
    drive.db.update_instance_result = "locked"
    drive.sched.reload_answer = (True, {"bw1": {"status": "success", "msg": ""}})
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "Couldn't update instance bw1 status to up in the database: locked" in caplog.text


# --- the once-jobs republication (#4106) ----------------------------------------------------------


def second_iteration_after_a_plugins_config_change(drive, pending):
    """Iteration 1 is the first start. A plugins-config change then asks for the once-jobs again (iteration 2)."""
    drive.iterations = 2
    drive.sched.pending = pending
    mark = {}

    def change():
        mark["reloads"] = len(reloads(drive))
        mark["sent"] = len(drive.sends)
        mark["renders"] = drive.renders
        drive.db.metadata["plugins_config_changed"] = ["antibot"]

    drive.on_iteration[1] = change
    drive.run()
    return mark


def sent_since(drive, mark):
    start = mark["sent"]
    return drive.sends[start:]


def test_once_jobs_that_changed_nothing_do_not_trigger_a_second_push_and_reload(drive, caplog):
    with caplog.at_level(logging.INFO):
        mark = second_iteration_after_a_plugins_config_change(drive, (False, False))
    assert len(reloads(drive)) - mark["reloads"] == 1  # the pre-job push reloaded; nothing after the jobs
    assert sorted(sent_since(drive, mark)) == ["/cache", "/confs"]
    assert drive.renders - mark["renders"] == 1
    assert "No once-job changed anything since the configuration was pushed, skipping the second push and reload" in caplog.text
    assert set_metadata_calls(drive)[-1]["failover"] is False


def test_once_jobs_that_changed_something_still_publish_a_second_time(drive, caplog):
    with caplog.at_level(logging.INFO):
        mark = second_iteration_after_a_plugins_config_change(drive, (True, False))
    assert len(reloads(drive)) - mark["reloads"] == 2
    assert sorted(sent_since(drive, mark)) == ["/cache", "/cache", "/confs", "/confs"]
    assert "Regenerating config after once-jobs to pick up files created by jobs" in caplog.text


def test_once_jobs_that_need_a_new_render_force_the_republication(drive):
    mark = second_iteration_after_a_plugins_config_change(drive, (False, True))
    assert len(reloads(drive)) - mark["reloads"] == 2


# --- the change-detection loop --------------------------------------------------------------------


def changed_checks(drive):
    return [c for c in drive.db.calls if c[0] == "checked_changes" and c[1] is not None]


@pytest.mark.parametrize(
    "flag, value, expected",
    [
        ("pro_plugins_changed", True, ["pro_plugins", "config"]),
        ("external_plugins_changed", True, ["external_plugins", "config"]),
        ("custom_configs_changed", True, ["custom_configs", "config"]),
        ("plugins_config_changed", ["antibot", "limit"], ["config"]),
        ("instances_changed", True, ["instances", "custom_configs", "external_plugins", "pro_plugins", "config"]),
    ],
)
def test_a_database_change_is_claimed_with_exactly_the_flags_it_raised(drive, flag, value, expected):
    drive.iterations = 2
    drive.on_iteration[1] = lambda: drive.db.metadata.update({flag: value})
    drive.run()
    claimed = changed_checks(drive)
    assert claimed and claimed[0][1] == expected
    if flag == "plugins_config_changed":
        assert claimed[0][2] == ["antibot", "limit"]
        assert drive.sched.reload_calls[-1][1] == ["antibot", "limit"]


def test_an_instances_change_rebuilds_the_api_list_from_the_database(drive):
    drive.iterations = 2

    def change():
        drive.db.instances = [instance("bw1"), instance("bw2")]
        drive.sched.reload_answer = (True, {"bw1": {"status": "success", "msg": ""}, "bw2": {"status": "success", "msg": ""}})
        drive.db.metadata["instances_changed"] = True

    drive.on_iteration[1] = change
    drive.run()
    assert sorted(a.endpoint for a in drive.sched.apis) == ["http://bw1:5000/", "http://bw2:5000/"]


def test_a_new_api_port_is_pushed_to_the_instances_records(drive):
    drive.iterations = 2

    def change():
        drive.db.config = {**drive.db.config, "API_HTTP_PORT": "5001"}
        drive.db.metadata["plugins_config_changed"] = ["misc"]

    drive.on_iteration[1] = change
    drive.run()
    update = [c for c in drive.db.calls if c[0] == "update_instances"]
    assert update and update[0][2] == "scheduler"
    assert update[0][1][0]["env"] == {"API_HTTP_PORT": "5001", "API_SERVER_NAME": "bwapi"}


def test_a_refused_instances_update_is_logged(drive, caplog, monkeypatch):
    drive.iterations = 2
    monkeypatch.setattr(drive.db, "update_instances", lambda instances, method=None: "locked")

    def change():
        drive.db.config = {**drive.db.config, "API_SERVER_NAME": "other"}
        drive.db.metadata["plugins_config_changed"] = ["misc"]

    drive.on_iteration[1] = change
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert "Couldn't update instances in the database: locked" in caplog.text


def test_a_sighup_rescan_that_finds_a_change_regenerates_everything(drive, monkeypatch):
    drive.iterations = 2
    monkeypatch.setattr(drive.main, "check_configs_changes", lambda generate=True: True)
    drive.on_iteration[1] = lambda: setattr(drive.main, "RELOAD_SCAN_CONFIGS", True)
    drive.run()
    assert changed_checks(drive)[0][1] == ["custom_configs", "config"]
    assert drive.main.RELOAD_SCAN_CONFIGS is False


def test_a_sighup_rescan_whose_write_was_refused_stays_pending_and_backs_off(drive, monkeypatch):
    drive.iterations = 2
    scans = []
    monkeypatch.setattr(drive.main, "check_configs_changes", lambda generate=True: scans.append(1) if not generate else None)

    def hup():
        drive.main.RELOAD_SCAN_CONFIGS = True
        ticks = []

        def tick():
            ticks.append(1)
            if len(ticks) >= 4:
                drive.main.RUN = False

        drive.sched.run_pending = tick

    drive.on_iteration[1] = hup
    drive.run()
    assert scans == [1]
    assert drive.main.RELOAD_SCAN_CONFIGS is True


def test_a_sighup_rescan_is_skipped_for_a_read_only_database(drive, monkeypatch):
    drive.iterations = 2
    monkeypatch.setattr(drive.main, "check_configs_changes", lambda generate=True: pytest.fail("must not scan a read-only database"))

    def hup():
        drive.db.readonly = True
        drive.main.RELOAD_SCAN_CONFIGS = True
        drive.sched.run_pending = lambda: setattr(drive.main, "RUN", False)

    drive.on_iteration[1] = hup
    drive.run()
    assert drive.main.RELOAD_SCAN_CONFIGS is False


def test_a_busy_database_lock_skips_the_tick(drive, monkeypatch, caplog):
    drive.iterations = 2

    def busy(path, timeout=30.0):
        drive.main.RUN = False
        raise drive.main.DatabaseLockBusy("db.lock is held by bwcli")

    monkeypatch.setattr(drive.main, "acquire_db_lock", busy)
    drive.db.metadata["plugins_config_changed"] = ["x"]
    with caplog.at_level(logging.WARNING):
        drive.run()
    assert "db.lock is held by bwcli, skipping this scheduler tick" in caplog.text
    assert changed_checks(drive) == []


def test_a_metadata_error_that_persists_stops_the_scheduler_with_status_one(drive, caplog):
    drive.on_iteration[1] = lambda: setattr(drive.db, "metadata_error", "OperationalError: server closed the connection")
    drive.iterations = 5
    with caplog.at_level(logging.ERROR):
        drive.run()
    assert drive.stops == [1]
    assert drive.sleeps.count(5) == 6
    assert "An error occurred when checking for changes in the database" in caplog.text


def test_a_read_only_database_ignores_an_unchanged_snapshot(drive):
    drive.iterations = 3
    drive.db.readonly = True
    drive.db.metadata.update(custom_configs_changed=True, last_custom_configs_change="t1")

    def settle():
        ticks = []

        def tick():
            ticks.append(1)
            if len(ticks) >= 3:
                drive.main.RUN = False

        drive.sched.run_pending = tick

    drive.on_iteration[2] = settle
    drive.run()
    assert [c[1] for c in changed_checks(drive)] == [["custom_configs", "config"]]


def test_the_loop_collects_garbage_every_ten_ticks(drive, monkeypatch):
    drive.iterations = 2
    collected = []
    monkeypatch.setattr(drive.main, "collect", lambda: collected.append(1))

    def many_ticks():
        ticks = []

        def tick():
            ticks.append(1)
            if len(ticks) >= 10:
                drive.main.RUN = False

        drive.sched.run_pending = tick

    drive.on_iteration[1] = many_ticks
    drive.run()
    assert collected == [1]


def test_the_job_scheduler_is_told_while_a_generation_is_pending(drive):
    drive.iterations = 2
    seen = []

    def watch():
        def tick():
            seen.append(drive.sched.generation_pending)
            drive.main.RUN = False

        drive.sched.run_pending = tick

    drive.on_iteration[1] = watch
    drive.run()
    assert seen == [False]
