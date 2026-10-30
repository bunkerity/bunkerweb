"""JobScheduler: job discovery, validation, execution outcomes and the publication that follows them."""

import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import schedule


class FakeDb:
    def __init__(self):
        self.readonly = False
        self.last_connection_retry = None
        self.database_uri = "sqlite:///fake.db"
        self.database_uri_readonly = None
        self.write_error = None
        self.job_runs = []
        self.add_error = ""
        self.ran = threading.Event()

    def test_write(self):
        if self.write_error:
            raise self.write_error

    def add_job_run(self, name, success, start_date, end_date):
        self.job_runs.append((name, success))
        self.ran.set()
        return self.add_error


def write_plugin(root: Path, name: str, jobs, scripts=None):
    plugin = root / name
    (plugin / "jobs").mkdir(parents=True)
    import json

    (plugin / "plugin.json").write_text(json.dumps({"id": name, "jobs": jobs}), encoding="utf-8")
    for file, body in (scripts or {}).items():
        (plugin / "jobs" / file).write_text(body, encoding="utf-8")
    return plugin


@pytest.fixture
def make_scheduler(job_scheduler_module, monkeypatch, tmp_path, sched_logger):
    """Build a JobScheduler over plugins under tmp_path, with os.environ, schedule and cache walking isolated."""
    JS = job_scheduler_module
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(JS, "cache_tree", lambda path: [])
    created = []
    plugins_root = tmp_path / "plugins"
    plugins_root.mkdir()

    def factory(plugins=None, **kwargs):
        for name, jobs, scripts in plugins or []:
            write_plugin(plugins_root, name, jobs, scripts)
        monkeypatch.setattr(JS, "glob", lambda pattern: sorted(str(p) for p in plugins_root.glob("*/plugin.json")) if "core" in pattern else [])
        db = kwargs.pop("db", None) or FakeDb()
        sched = JS.JobScheduler(sched_logger, db=db, **kwargs)
        sched.fake_db = db
        created.append(sched)
        return sched

    schedule.clear()
    yield factory
    schedule.clear()
    for sched in created:
        sched._JobScheduler__executor.shutdown(wait=True)
    for key in [k for k in sys.modules if k.startswith("bw_job_")]:
        del sys.modules[key]


def job(name, file, every="once", reload=False, **extra):
    return {"name": name, "file": file, "every": every, "reload": reload, **extra}


def wait_job_run(sched):
    assert sched.fake_db.ran.wait(5)
    sched.fake_db.ran.clear()


def wait_until(condition, timeout=5.0):
    """Poll a condition the executor thread makes true shortly after the job returned."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


# --- worker count ---------------------------------------------------------------------------------


@pytest.mark.parametrize("cpus, expected", [(1, 2), (2, 4), (3, 6), (4, 8), (32, 8)])
def test_auto_max_workers_follows_cpu_count_within_bounds(job_scheduler_module, monkeypatch, cpus, expected):
    monkeypatch.setattr(job_scheduler_module, "effective_cpu_count", lambda: cpus)
    assert job_scheduler_module.JobScheduler._auto_max_workers() == expected


def test_max_workers_env_is_honoured(make_scheduler, monkeypatch):
    monkeypatch.setenv("SCHEDULER_MAX_WORKERS", "3")
    assert make_scheduler()._JobScheduler__executor._max_workers == 3


@pytest.mark.parametrize("raw, message", [("lots", "Invalid SCHEDULER_MAX_WORKERS"), ("0", "must be > 0"), ("-2", "must be > 0")])
def test_bad_max_workers_falls_back_to_the_default_with_a_warning(make_scheduler, monkeypatch, caplog, job_scheduler_module, raw, message):
    monkeypatch.setattr(job_scheduler_module, "effective_cpu_count", lambda: 1)
    monkeypatch.setenv("SCHEDULER_MAX_WORKERS", raw)
    with caplog.at_level(logging.WARNING):
        sched = make_scheduler()
    assert sched._JobScheduler__executor._max_workers == 2
    assert message in caplog.text


def test_max_workers_above_the_db_pool_capacity_warns(make_scheduler, monkeypatch, caplog):
    monkeypatch.setenv("SCHEDULER_MAX_WORKERS", "9")
    monkeypatch.setenv("DATABASE_POOL_SIZE", "2")
    monkeypatch.setenv("DATABASE_POOL_MAX_OVERFLOW", "1")
    with caplog.at_level(logging.WARNING):
        make_scheduler()
    assert "exceeds the DB pool capacity" in caplog.text


def test_unlimited_pool_overflow_skips_the_capacity_warning(make_scheduler, monkeypatch, caplog):
    monkeypatch.setenv("SCHEDULER_MAX_WORKERS", "9")
    monkeypatch.setenv("DATABASE_POOL_SIZE", "2")
    monkeypatch.setenv("DATABASE_POOL_MAX_OVERFLOW", "-1")
    with caplog.at_level(logging.WARNING):
        make_scheduler()
    assert "exceeds the DB pool capacity" not in caplog.text


# --- environment publication ----------------------------------------------------------------------


def test_env_setter_publishes_the_env_without_changing_os_environ_identity(make_scheduler):
    sched = make_scheduler()
    sched.env = {"A": "1", "SERVER_NAME": "a.example"}
    published = os.environ
    assert published["A"] == "1"
    sched.env = {"B": "2"}
    assert os.environ is published
    assert published["B"] == "2"


def test_env_setter_prunes_keys_a_later_env_no_longer_carries(make_scheduler):
    sched = make_scheduler()
    sched.env = {"www.example.com_USE_ANTIBOT": "captcha", "KEEP": "1"}
    sched.env = {"KEEP": "1"}
    assert "www.example.com_USE_ANTIBOT" not in os.environ
    assert sched.env["KEEP"] == "1"


# --- job discovery and validation -----------------------------------------------------------------


def test_only_valid_job_definitions_are_kept(make_scheduler):
    jobs = [
        job("good", "good.py", "day", True),
        {"name": "no-file", "every": "day", "reload": False},
        job("bad name!", "x.py"),
        job("bad-file", "has space.py"),
        job("bad-every", "x.py", every="fortnight"),
        job("bad-reload", "x.py", reload="yes"),
        job("bad-async", "x.py", **{"async": "yes"}),
    ]
    sched = make_scheduler([("plug", jobs, {})])
    kept = sched._JobScheduler__jobs["plug"]
    assert [j["name"] for j in kept] == ["good"]
    assert kept[0]["path"].endswith("/plug")


def test_a_job_file_cannot_climb_out_of_the_jobs_folder(make_scheduler):
    sched = make_scheduler([("plug", [job("escape", "../../outside.py")], {})])
    assert sched._JobScheduler__jobs["plug"] == []


def test_invalid_job_definitions_are_logged(make_scheduler, caplog):
    with caplog.at_level(logging.WARNING):
        make_scheduler([("plug", [job("bad-every", "x.py", every="fortnight"), {"name": "n"}], {})])
    assert "Invalid job definition in plugin plug" in caplog.text
    assert "Missing keys in job definition in plugin plug" in caplog.text


def test_unreadable_plugin_json_gives_the_plugin_no_jobs(make_scheduler, tmp_path, caplog):
    plugin = tmp_path / "plugins" / "broken"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text("{not json", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        sched = make_scheduler()
    assert sched._JobScheduler__jobs["broken"] == []
    assert "Exception while getting jobs for plugin broken" in caplog.text


def test_vanished_plugin_file_is_reported(make_scheduler, job_scheduler_module, monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(job_scheduler_module, "glob", lambda pattern: [str(tmp_path / "gone" / "plugin.json")] if "core" in pattern else [])
    with caplog.at_level(logging.WARNING):
        sched = job_scheduler_module.JobScheduler(logging.getLogger("bw-scheduler-unit"), db=FakeDb())
    try:
        assert sched._JobScheduler__jobs == {"gone": []}
        assert "Plugin file not found" in caplog.text
    finally:
        sched._JobScheduler__executor.shutdown(wait=True)


# --- scheduling -----------------------------------------------------------------------------------


def test_setup_registers_periodic_jobs_but_not_once_jobs(make_scheduler):
    sched = make_scheduler(
        [
            (
                "plug",
                [
                    job("every-min", "a.py", "minute"),
                    job("every-hour", "a.py", "hour"),
                    job("every-day", "a.py", "day"),
                    job("every-week", "a.py", "week"),
                    job("one", "a.py", "once"),
                ],
                {},
            )
        ]
    )
    sched.setup()
    assert sorted(j.unit for j in schedule.jobs) == ["days", "hours", "minutes", "weeks"]


def test_setup_survives_a_job_that_cannot_be_scheduled(make_scheduler, caplog):
    sched = make_scheduler([("plug", [job("fine", "a.py", "day")], {})])
    sched._JobScheduler__jobs["plug"].insert(0, {"name": "weird", "file": "a.py", "every": "fortnight", "path": "/x"})
    with caplog.at_level(logging.ERROR):
        sched.setup()
    assert "Exception while scheduling job 'weird' for plugin 'plug'" in caplog.text
    assert len(schedule.jobs) == 1


def test_clear_drops_every_scheduled_job(make_scheduler):
    sched = make_scheduler([("plug", [job("j", "a.py", "day")], {})])
    sched.setup()
    sched.clear()
    assert schedule.jobs == []


# --- run_single and job outcomes ------------------------------------------------------------------

EXIT = "import sys\nsys.exit({code})\n"


@pytest.mark.parametrize(
    "code, ok, reload_pending",
    [(0, True, False), (1, True, True), (2, False, False), (3, False, True)],
)
def test_job_exit_status_decides_success_and_the_pending_reload(make_scheduler, code, ok, reload_pending):
    sched = make_scheduler([("plug", [job("j", "j.py")], {"j.py": EXIT.format(code=code)})])
    assert sched.run_single("j") is ok
    wait_job_run(sched)
    assert sched.fake_db.job_runs == [("j", ok)]
    assert sched.failed_jobs == ([] if ok else ["plug/j"])
    assert sched.consume_pending_publication() == (reload_pending, False)


def test_a_job_that_raises_is_a_failed_job(make_scheduler, caplog):
    sched = make_scheduler([("plug", [job("j", "j.py")], {"j.py": "raise RuntimeError('boom')\n"})])
    with caplog.at_level(logging.ERROR):
        assert sched.run_single("j") is False
    assert "Exception while executing job 'j' from plugin 'plug': boom" in caplog.text
    assert sched.failed_jobs == ["plug/j"]


def test_a_job_whose_file_is_missing_fails(make_scheduler):
    sched = make_scheduler([("plug", [job("j", "absent.py")], {})])
    assert sched.run_single("j") is False
    assert sched.failed_jobs == ["plug/j"]


def test_status_three_still_fails_when_an_earlier_job_already_failed(make_scheduler):
    sched = make_scheduler([("plug", [job("a", "a.py"), job("b", "b.py")], {"a.py": EXIT.format(code=2), "b.py": EXIT.format(code=3)})])
    assert sched.run_once() is False
    assert sorted(sched.failed_jobs) == ["plug/a", "plug/b"]
    assert sched.consume_pending_publication() == (True, False)


@pytest.mark.parametrize(
    "plugin, name", [("mtls", "client-cert"), ("modsecurity", "download-crs-plugins"), ("grpc", "grpc-trusted-cert"), ("reverseproxy", "trusted-cert")]
)
def test_certificate_jobs_that_changed_something_ask_for_a_new_render(make_scheduler, plugin, name):
    sched = make_scheduler([(plugin, [job(name, "j.py")], {"j.py": EXIT.format(code=1)})])
    assert sched.run_single(name) is True
    assert sched.consume_pending_publication() == (True, True)


def test_a_job_with_no_special_name_asks_only_for_a_reload(make_scheduler):
    sched = make_scheduler([("plug", [job("j", "j.py")], {"j.py": EXIT.format(code=1)})])
    sched.run_single("j")
    assert sched.consume_pending_publication() == (True, False)


def test_consume_pending_publication_clears_the_state(make_scheduler):
    sched = make_scheduler([("plug", [job("j", "j.py")], {"j.py": EXIT.format(code=1)})])
    sched.run_single("j")
    sched.consume_pending_publication()
    assert sched.consume_pending_publication() == (False, False)


def test_a_failed_job_run_is_recorded_with_the_database_error_logged(make_scheduler, caplog):
    sched = make_scheduler([("plug", [job("j", "j.py")], {"j.py": EXIT.format(code=0)})])
    sched.fake_db.add_error = "disk full"
    with caplog.at_level(logging.WARNING):
        sched.run_single("j")
        assert wait_until(lambda: "Failed to add job run for the job 'j': disk full" in caplog.text)


def test_run_single_reports_an_unknown_job(make_scheduler, caplog):
    sched = make_scheduler([("plug", [job("j", "j.py")], {})])
    with caplog.at_level(logging.WARNING):
        assert sched.run_single("nope") is False
    assert "Job 'nope' not found" in caplog.text


def test_run_single_holds_the_lock_while_running_and_releases_it(make_scheduler):
    lock = threading.Lock()
    seen = []
    sched = make_scheduler([("plug", [job("j", "j.py")], {"j.py": EXIT.format(code=0)})], lock=lock)
    original = sched._JobScheduler__job_wrapper
    sched._JobScheduler__job_wrapper = lambda *a: seen.append(lock.locked()) or original(*a)
    sched.run_single("j")
    assert seen == [True]
    assert not lock.locked()


def test_run_single_releases_the_lock_even_for_an_unknown_job(make_scheduler):
    lock = threading.Lock()
    sched = make_scheduler([("plug", [], {})], lock=lock)
    sched.run_single("nope")
    assert not lock.locked()


def test_nothing_runs_while_the_database_is_read_only(make_scheduler, caplog):
    sched = make_scheduler([("plug", [job("j", "j.py")], {"j.py": EXIT.format(code=0)})])
    sched.fake_db.write_error = OSError("ro")
    with caplog.at_level(logging.ERROR):
        assert sched.run_single("j") is True
        assert sched.run_once() is True
    assert sched.fake_db.job_runs == []
    assert "single job 'j' will not be executed" in caplog.text
    assert "jobs will not be executed" in caplog.text


# --- run_once -------------------------------------------------------------------------------------


def test_run_once_runs_every_job_including_async_ones(make_scheduler, tmp_path):
    marker = tmp_path / "ran"
    body = f"import sys\nwith open({str(marker)!r}, 'a') as f: f.write('x')\nsys.exit(0)\n"
    sched = make_scheduler([("plug", [job("a", "a.py"), job("b", "a.py", **{"async": True}), job("c", "a.py")], {"a.py": body})])
    assert sched.run_once() is True
    assert marker.read_text() == "xxx"


def test_run_once_filters_by_plugin(make_scheduler, tmp_path):
    marker = tmp_path / "ran"
    body = f"import sys\nwith open({str(marker)!r}, 'a') as f: f.write('x')\nsys.exit(0)\n"
    sched = make_scheduler([("one", [job("a", "a.py")], {"a.py": body}), ("two", [job("b", "a.py")], {"a.py": body})])
    sched.run_once(["one"])
    assert marker.read_text() == "x"
    sched.run_once(ignore_plugins=["one"])
    assert marker.read_text() == "xx"


def test_run_once_returns_false_when_a_job_failed(make_scheduler):
    sched = make_scheduler([("plug", [job("ok", "ok.py"), job("ko", "ko.py")], {"ok.py": EXIT.format(code=0), "ko.py": EXIT.format(code=2)})])
    assert sched.run_once() is False
    assert sched.failed_jobs == ["plug/ko"]


def test_run_once_forgets_the_failed_jobs_of_the_previous_batch(make_scheduler):
    sched = make_scheduler([("plug", [job("ko", "ko.py")], {"ko.py": EXIT.format(code=2)})])
    sched.run_once()
    sched._JobScheduler__jobs["plug"] = []
    assert sched.run_once() is True
    assert sched.failed_jobs == []


def test_failed_jobs_returns_a_copy(make_scheduler):
    sched = make_scheduler([("plug", [job("ko", "ko.py")], {"ko.py": EXIT.format(code=2)})])
    sched.run_once()
    sched.failed_jobs.append("tamper")
    assert sched.failed_jobs == ["plug/ko"]


def test_a_job_directory_is_on_sys_path_only_during_the_batch(make_scheduler):
    sched = make_scheduler([("plug", [job("a", "a.py")], {"a.py": EXIT.format(code=0)})])
    jobs_dir = sched._JobScheduler__jobs["plug"][0]["path"] + "/jobs"
    sched.run_once()
    assert jobs_dir not in sys.path
    assert sched._JobScheduler__module_paths == set()


NO_EXIT = "VALUE = 1\n"


def test_job_modules_are_dropped_from_sys_modules_after_the_batch(make_scheduler):
    sched = make_scheduler([("plug", [job("a", "a.py")], {"a.py": NO_EXIT})])
    sched.run_once()
    assert not [k for k in sys.modules if k.startswith("bw_job_a_")]


def test_a_job_that_exits_does_not_stay_in_sys_modules(make_scheduler):
    sched = make_scheduler([("plug", [job("a", "a.py")], {"a.py": EXIT.format(code=0)})])
    sched.run_once()
    assert not [k for k in sys.modules if k.startswith("bw_job_a_")]


def test_a_cached_job_module_is_reloaded_with_its_new_code(make_scheduler, tmp_path):
    marker = tmp_path / "count"
    marker.write_text("")
    body = f"with open({str(marker)!r}, 'a') as f: f.write('x')\n"
    sched = make_scheduler([("plug", [job("a", "a.py")], {"a.py": body})])
    sched.run_single("a")
    sched.run_single("a")
    assert marker.read_text() == "xx"


def test_a_failing_reload_of_a_cached_module_falls_back_to_a_fresh_import(make_scheduler, job_scheduler_module, monkeypatch, tmp_path, caplog):
    marker = tmp_path / "count"
    marker.write_text("")
    body = f"with open({str(marker)!r}, 'a') as f: f.write('x')\n"
    sched = make_scheduler([("plug", [job("a", "a.py")], {"a.py": body})])
    sched.run_single("a")

    def refuse(module):
        raise ImportError("cannot reload")

    monkeypatch.setattr(job_scheduler_module, "importlib_reload", refuse)
    with caplog.at_level(logging.WARNING):
        assert sched.run_single("a") is True
    assert "Failed to reload cached module a, re-importing" in caplog.text
    assert marker.read_text() == "xx"


def test_cleanup_modules_removes_what_the_cache_registered(make_scheduler):
    sched = make_scheduler([("plug", [job("a", "a.py")], {"a.py": NO_EXIT})])
    sched.run_single("a")
    assert [k for k in sys.modules if k.startswith("bw_job_a_")]
    sched.cleanup_modules()
    assert not [k for k in sys.modules if k.startswith("bw_job_a_")]
    assert sched._JobScheduler__module_cache == {}


# --- cache permissions ----------------------------------------------------------------------------


class Item:
    def __init__(self, path):
        self.path = path

    def lstat(self):
        return self.path.lstat()

    def chmod(self, mode, follow_symlinks=True):
        self.path.chmod(mode)


def test_cache_permissions_are_normalised_once_per_batch(make_scheduler, job_scheduler_module, monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    (cache / "sub").mkdir(parents=True)
    (cache / "f.txt").write_text("x")
    (cache / "sub" / "g.txt").write_text("x")
    (tmp_path / "target").write_text("x")
    (cache / "link").symlink_to(tmp_path / "target")
    (tmp_path / "target").chmod(0o600)
    for p in (cache / "f.txt", cache / "sub" / "g.txt"):
        p.chmod(0o666)
    (cache / "sub").chmod(0o777)
    monkeypatch.setattr(
        job_scheduler_module, "cache_tree", lambda path: [Item(p) for p in (cache / "sub", cache / "f.txt", cache / "sub" / "g.txt", cache / "link")]
    )
    sched = make_scheduler([("plug", [job("a", "a.py")], {"a.py": EXIT.format(code=0)})])
    sched.run_once()
    assert (cache / "sub").stat().st_mode & 0o777 == 0o740
    assert (cache / "f.txt").stat().st_mode & 0o777 == 0o640
    assert (cache / "sub" / "g.txt").stat().st_mode & 0o777 == 0o640
    assert (tmp_path / "target").stat().st_mode & 0o777 == 0o600


def test_a_cache_walk_error_is_logged_and_does_not_fail_the_batch(make_scheduler, job_scheduler_module, monkeypatch, caplog):
    def explode(path):
        raise OSError("walk failed")

    monkeypatch.setattr(job_scheduler_module, "cache_tree", explode)
    sched = make_scheduler([("plug", [job("a", "a.py")], {"a.py": EXIT.format(code=0)})])
    with caplog.at_level(logging.ERROR):
        assert sched.run_once() is True
    assert "Error while updating cache permissions: walk failed" in caplog.text


# --- run_pending and publication ------------------------------------------------------------------


def due(sched):
    for scheduled in schedule.jobs:
        scheduled.next_run = datetime.now() - timedelta(seconds=1)


def test_run_pending_is_a_no_op_with_nothing_due_and_nothing_to_publish(make_scheduler):
    sched = make_scheduler([("plug", [job("a", "a.py", "day")], {"a.py": EXIT.format(code=0)})])
    sched.setup()
    assert sched.run_pending() is True
    assert sched.fake_db.job_runs == []


def test_run_pending_runs_due_jobs(make_scheduler, tmp_path):
    marker = tmp_path / "ran"
    body = f"import sys\nopen({str(marker)!r}, 'w').write('x')\nsys.exit(0)\n"
    sched = make_scheduler([("plug", [job("a", "a.py", "day")], {"a.py": body})])
    sched.setup()
    due(sched)
    assert sched.run_pending() is True
    assert marker.read_text() == "x"


def test_run_pending_reports_a_failing_due_job(make_scheduler):
    sched = make_scheduler([("plug", [job("a", "a.py", "day")], {"a.py": EXIT.format(code=2)})])
    sched.setup()
    due(sched)
    assert sched.run_pending() is False
    assert sched.failed_jobs == ["plug/a"]


def test_run_pending_skips_everything_while_the_database_is_read_only(make_scheduler, tmp_path, caplog):
    marker = tmp_path / "ran"
    body = f"import sys\nopen({str(marker)!r}, 'w').write('x')\nsys.exit(0)\n"
    sched = make_scheduler([("plug", [job("a", "a.py", "day")], {"a.py": body})])
    sched.setup()
    due(sched)
    sched.fake_db.write_error = OSError("ro")
    with caplog.at_level(logging.ERROR):
        assert sched.run_pending() is True
    assert not marker.exists()
    assert "Database is in read-only mode, pending jobs will not be executed" in caplog.text


class Recorder:
    """send_files / send_to_apis stand-ins that record what the publication pushed."""

    def __init__(self, files_ok=True, reload_ok=True):
        self.files_ok = files_ok
        self.reload_ok = reload_ok
        self.pushed = []
        self.reloads = []

    def attach(self, sched):
        sched.apis = [SimpleNamespace(endpoint="http://bw:5000/")]
        sched.send_files = lambda path, endpoint, timeout=None: self.pushed.append((path, endpoint)) or self.files_ok
        sched.send_to_apis = lambda method, url, **kw: self.reloads.append((method, url, kw["timeout"])) or (self.reload_ok, {})


@pytest.fixture
def reloading(make_scheduler):
    sched = make_scheduler([("plug", [job("a", "a.py")], {"a.py": EXIT.format(code=1)})])
    sched.run_single("a")
    return sched


def test_a_pending_reload_is_pushed_and_reloaded_then_cleared(reloading):
    rec = Recorder()
    rec.attach(reloading)
    assert reloading.run_pending() is True
    assert rec.pushed == [("/var/cache/bunkerweb", "/cache")]
    assert rec.reloads == [("POST", "/reload?test=yes", rec.reloads[0][2])]
    assert reloading.consume_pending_publication() == (False, False)


def test_a_regenerating_job_also_pushes_the_nginx_configuration(make_scheduler):
    sched = make_scheduler([("mtls", [job("client-cert", "j.py")], {"j.py": EXIT.format(code=1)})], generate_configs=lambda: True)
    sched.run_single("client-cert")
    rec = Recorder()
    rec.attach(sched)
    assert sched.run_pending() is True
    assert rec.pushed == [("/var/cache/bunkerweb", "/cache"), ("/etc/nginx", "/confs")]


def test_the_render_is_kept_when_the_push_fails_so_the_retry_does_not_render_again(make_scheduler):
    renders = []
    sched = make_scheduler([("mtls", [job("client-cert", "j.py")], {"j.py": EXIT.format(code=1)})], generate_configs=lambda: renders.append(1) or True)
    sched.run_single("client-cert")
    rec = Recorder(files_ok=False)
    rec.attach(sched)
    assert sched.run_pending() is False
    rec.files_ok = True
    sched._JobScheduler__publish_retry_at = None
    assert sched.run_pending() is True
    assert renders == [1]


def test_a_failed_render_keeps_the_publication_pending(make_scheduler, caplog):
    sched = make_scheduler([("mtls", [job("client-cert", "j.py")], {"j.py": EXIT.format(code=1)})], generate_configs=lambda: False)
    sched.run_single("client-cert")
    rec = Recorder()
    rec.attach(sched)
    with caplog.at_level(logging.ERROR):
        assert sched.run_pending() is False
    assert "Configuration generation failed; keeping the pending job publication for retry" in caplog.text
    assert rec.pushed == []
    assert sched.consume_pending_publication() == (True, True)


def test_no_render_function_counts_as_a_failed_render(make_scheduler):
    sched = make_scheduler([("mtls", [job("client-cert", "j.py")], {"j.py": EXIT.format(code=1)})])
    sched.run_single("client-cert")
    Recorder().attach(sched)
    assert sched.run_pending() is False


def test_publication_is_held_while_a_generation_is_pending(reloading, caplog):
    rec = Recorder()
    rec.attach(reloading)
    reloading.generation_pending = True
    with caplog.at_level(logging.DEBUG):
        assert reloading.run_pending() is False
    assert rec.pushed == []
    assert "Configuration generation is pending; holding job publication" in caplog.text


def test_publication_with_no_instance_clears_the_flags_without_pushing(reloading):
    reloading.apis = []
    assert reloading.run_pending() is True
    assert reloading.consume_pending_publication() == (False, False)


def test_a_failed_reload_is_a_failed_run_and_stays_pending(reloading):
    rec = Recorder(reload_ok=False)
    rec.attach(reloading)
    assert reloading.run_pending() is False
    assert reloading.consume_pending_publication() == (True, False)


def test_an_exception_while_publishing_is_a_failed_run(reloading, caplog):
    rec = Recorder()
    rec.attach(reloading)
    reloading.send_files = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("socket gone"))
    with caplog.at_level(logging.ERROR):
        assert reloading.run_pending() is False
    assert "Exception while reloading after job scheduling: socket gone" in caplog.text


def test_failed_publications_back_off_exponentially_and_idle_ticks_do_nothing(reloading, job_scheduler_module, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(job_scheduler_module, "monotonic", lambda: now[0])
    rec = Recorder(reload_ok=False)
    rec.attach(reloading)
    delays = []
    for _ in range(3):
        assert reloading.run_pending() is False
        delays.append(reloading._JobScheduler__publish_retry_at - now[0])
        now[0] = reloading._JobScheduler__publish_retry_at
    assert delays == [1, 2, 4]
    calls = len(rec.reloads)
    now[0] -= 0.5
    reloading._JobScheduler__publish_retry_at = now[0] + 3
    assert reloading.run_pending() is True
    assert len(rec.reloads) == calls


def test_backoff_never_exceeds_the_maximum_delay(reloading, job_scheduler_module, monkeypatch):
    monkeypatch.setattr(job_scheduler_module, "monotonic", lambda: 0.0)
    rec = Recorder(reload_ok=False)
    rec.attach(reloading)
    reloading._JobScheduler__publish_retry_delay = 250
    reloading.run_pending()
    assert reloading._JobScheduler__publish_retry_delay == 300
    reloading._JobScheduler__publish_retry_at = None
    reloading.run_pending()
    assert reloading._JobScheduler__publish_retry_delay == 300


def test_a_successful_publication_resets_the_backoff(reloading, job_scheduler_module, monkeypatch):
    monkeypatch.setattr(job_scheduler_module, "monotonic", lambda: 0.0)
    rec = Recorder(reload_ok=False)
    rec.attach(reloading)
    reloading.run_pending()
    reloading._JobScheduler__publish_retry_at = None
    rec.reload_ok = True
    assert reloading.run_pending() is True
    assert reloading._JobScheduler__publish_retry_delay == job_scheduler_module.JobScheduler.PUBLISH_RETRY_MIN_DELAY
    assert reloading._JobScheduler__publish_retry_at is None


def test_reload_timeout_scales_with_the_service_count(reloading, monkeypatch):
    rec = Recorder()
    rec.attach(reloading)
    os.environ["SERVER_NAME"] = " ".join(f"s{i}.example" for i in range(10))
    assert reloading.run_pending() is True
    assert rec.reloads[0][2] == 30


def test_configuration_testing_can_be_switched_off_for_the_reload(reloading):
    rec = Recorder()
    rec.attach(reloading)
    os.environ["DISABLE_CONFIGURATION_TESTING"] = "YES"
    reloading.run_pending()
    assert rec.reloads[0][1] == "/reload?test=no"


def test_invalid_timeouts_fall_back_with_an_error_log(reloading, caplog):
    rec = Recorder()
    rec.attach(reloading)
    os.environ["RELOAD_MIN_TIMEOUT"] = "soon"
    os.environ["SEND_FILES_MIN_TIMEOUT"] = "later"
    with caplog.at_level(logging.ERROR):
        assert reloading.run_pending() is True
    assert "RELOAD_MIN_TIMEOUT must be a duration" in caplog.text
    assert "SEND_FILES_MIN_TIMEOUT must be a duration" in caplog.text


# --- reload() -------------------------------------------------------------------------------------


def test_reload_applies_the_env_runs_once_jobs_then_registers_periodic_jobs(make_scheduler, tmp_path):
    marker = tmp_path / "ran"
    body = f"import os, sys\nopen({str(marker)!r}, 'w').write(os.environ['MY_SETTING'])\nsys.exit(0)\n"
    sched = make_scheduler([("plug", [job("once", "a.py"), job("daily", "a.py", "day")], {"a.py": body})])
    assert sched.reload({"MY_SETTING": "hello"}, [SimpleNamespace(endpoint="http://x/")]) is True
    assert marker.read_text() == "hello"
    assert len(schedule.jobs) == 1
    assert [a.endpoint for a in sched.apis] == ["http://x/"]


def test_reload_keeps_the_known_apis_when_none_are_given(make_scheduler):
    sched = make_scheduler([("plug", [], {})])
    sched.apis = [SimpleNamespace(endpoint="http://keep/")]
    assert sched.reload({}) is True
    assert [a.endpoint for a in sched.apis] == ["http://keep/"]


def test_reload_drops_stale_scheduled_jobs(make_scheduler):
    sched = make_scheduler([("plug", [job("daily", "a.py", "day")], {"a.py": EXIT.format(code=0)})])
    sched.reload({})
    sched.reload({})
    assert len(schedule.jobs) == 1


def test_reload_turns_an_exception_into_a_failed_reload(make_scheduler, caplog):
    sched = make_scheduler([("plug", [], {})])
    sched.run_once = lambda *a: (_ for _ in ()).throw(RuntimeError("bad"))
    with caplog.at_level(logging.ERROR):
        assert sched.reload({}) is False
    assert "Exception while reloading scheduler: bad" in caplog.text


def test_reload_passes_changed_and_ignored_plugins_to_run_once(make_scheduler):
    sched = make_scheduler([("plug", [], {})])
    seen = []
    sched.run_once = lambda changed, ignored: seen.append((changed, ignored)) or True
    sched.reload({}, changed_plugins=["a"], ignore_plugins=["b"])
    assert seen == [(["a"], ["b"])]


# --- read-only detection --------------------------------------------------------------------------


class RoDb(FakeDb):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.fail = {}

    def retry_connection(self, **kwargs):
        self.calls.append(tuple(sorted(kwargs)))
        key = tuple(sorted(k for k in kwargs if k in ("readonly", "fallback")))
        if key in self.fail:
            raise self.fail[key]


def test_a_writable_database_is_not_read_only(make_scheduler):
    sched = make_scheduler(db=RoDb())
    assert sched.try_database_readonly() is False
    assert sched.fake_db.readonly is False


def test_a_failing_write_probe_marks_the_database_read_only(make_scheduler):
    db = RoDb()
    db.write_error = RuntimeError("read-only")
    sched = make_scheduler(db=db)
    assert sched.try_database_readonly() is True
    assert db.readonly is True


def test_a_read_only_database_that_came_back_is_writable_again(make_scheduler, caplog):
    db = RoDb()
    db.readonly = True
    sched = make_scheduler(db=db)
    with caplog.at_level(logging.INFO):
        assert sched.try_database_readonly() is False
    assert db.readonly is False
    assert "no longer read-only" in caplog.text
    assert db.calls == [("pool_timeout",), ("log",)]


def test_a_database_that_stays_down_is_retried_read_only(make_scheduler):
    db = RoDb()
    db.readonly = True
    db.fail = {(): ConnectionError("down")}
    sched = make_scheduler(db=db)
    assert sched.try_database_readonly() is True
    assert db.calls == [("pool_timeout",), ("pool_timeout", "readonly"), ("log", "readonly")]


def test_the_fallback_uri_is_tried_when_the_read_only_retry_fails_too(make_scheduler):
    db = RoDb()
    db.readonly = True
    db.database_uri_readonly = "sqlite:///ro.db"
    db.fail = {(): ConnectionError("down"), ("readonly",): ConnectionError("down")}
    sched = make_scheduler(db=db)
    assert sched.try_database_readonly() is True
    assert ("fallback", "pool_timeout") in db.calls
    assert ("fallback", "log") in db.calls


def test_a_read_only_database_is_not_probed_again_within_the_retry_window(make_scheduler):
    db = RoDb()
    db.readonly = True
    db.last_connection_retry = datetime.now().astimezone() - timedelta(seconds=60)
    sched = make_scheduler(db=db)
    assert sched.try_database_readonly() is True
    assert db.calls == []


def test_force_probes_a_read_only_database_regardless_of_the_retry_window(make_scheduler):
    db = RoDb()
    db.readonly = True
    db.last_connection_retry = datetime.now().astimezone() - timedelta(seconds=60)
    sched = make_scheduler(db=db)
    assert sched.try_database_readonly(force=True) is False
    assert db.calls


def test_a_read_only_database_without_a_uri_is_left_alone(make_scheduler):
    db = RoDb()
    db.readonly = True
    db.database_uri = ""
    sched = make_scheduler(db=db)
    assert sched.try_database_readonly() is True
    assert db.calls == []
