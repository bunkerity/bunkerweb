"""``execute_job`` reads the ``regenerate`` job flag and asks for a re-render.

Exit code 1 ships the job's cache and reloads the fleet, but the configuration the instances
reload is the one the Scheduler rendered *before* the job ran. When a template READS what the
job wrote -- the CRS plugin tree, a real-IP list inlined into `real-ip.conf`, the reverse-proxy
client certificate probed with `is_file()` -- that render is stale and the push changes nothing
observable. Raising the plugin's config-changed flag is what makes the Scheduler render again.

1.6 hardcoded (mtls, client-cert) and (modsecurity, download-crs-plugins) in the Scheduler, so
every other job -- including any external or PRO one -- silently got a push and no re-render.
The flag is declared per job in `plugin.json` and travels in the dispatch payload; this pins the
worker end of it.

Same loading technique as ``test_execute_job_deferral_reason.py``: celery/redis are not in the
unit venv, so ``src/worker/tasks.py`` is loaded for real with its ``worker.*`` imports stubbed.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]


class _StubApp:
    def task(self, **options):
        def decorator(function):
            function.task_options = options
            return function

        return decorator


def _load_tasks():
    worker_pkg = ModuleType("worker")
    worker_app = ModuleType("worker.app")
    worker_executor = ModuleType("worker.executor")
    worker_app.app = _StubApp()
    worker_app.get_worker_db = lambda: None
    worker_executor.JobExecutor = Mock()
    modules = {"worker": worker_pkg, "worker.app": worker_app, "worker.executor": worker_executor}
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location("bw_worker_tasks_regenerate", ROOT / "src" / "worker" / "tasks.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


TASKS = _load_tasks()

LOGGER = Mock()
BROKER = "redis://broker:6379/0"


class _Self:
    def __init__(self, task_id="run-1"):
        self.request = type("R", (), {"id": task_id})()


JOB = {"name": "download-crs-plugins", "plugin_id": "modsecurity", "run_id": "run-1", "file": "download-crs-plugins.py", "path": "/x"}


@pytest.fixture
def stub_runtime(monkeypatch):
    logger_module = ModuleType("logger")
    logger_module.setup_logger = Mock(return_value=LOGGER)
    monkeypatch.setitem(sys.modules, "logger", logger_module)
    # No instances: proves the re-render request does NOT depend on a reachable fleet. The render
    # is owed to the Scheduler either way -- it is the push that has nowhere to go.
    monkeypatch.setattr(TASKS, "_get_apis", lambda *_args: None)
    monkeypatch.setattr(TASKS, "_load_job_config_env", lambda db, logger: {})
    monkeypatch.setattr(TASKS, "_mark_reload_owed", lambda *_a: None)
    monkeypatch.setenv("CELERY_BROKER_URL", BROKER)
    executor = Mock()
    executor.run = Mock(return_value=1)
    monkeypatch.setattr(TASKS, "JobExecutor", Mock(return_value=executor))

    redis_module = ModuleType("redis")
    redis_module.Redis = Mock()
    redis_module.Redis.from_url = Mock(side_effect=RuntimeError("no broker in this test"))
    monkeypatch.setitem(sys.modules, "redis", redis_module)
    return executor


def _run(monkeypatch, job_overrides=None, checked_changes=None):
    db = Mock(add_job_run=Mock(return_value=None), checked_changes=checked_changes or Mock(return_value=""))
    monkeypatch.setattr(TASKS, "get_worker_db", lambda: db)
    TASKS.execute_job(_Self(), dict(JOB, **(job_overrides or {})))
    return db


class TestTheFlagIsRead:
    def test_exit_1_with_the_flag_requests_a_re_render(self, stub_runtime, monkeypatch):
        db = _run(monkeypatch, {"regenerate": True})

        db.checked_changes.assert_called_once_with(["config"], plugins_changes=["modsecurity"], value=True)

    @pytest.mark.parametrize(
        "plugin_id,job_name",
        (("realip", "realip-download"), ("reverseproxy", "trusted-cert")),
    )
    def test_the_flag_reproduces_the_call_each_job_used_to_make_by_hand(self, stub_runtime, monkeypatch, plugin_id, job_name):
        """Both jobs carried `if status == 1: JOB.db.checked_changes(["config"], [<id>], True)`
        inline. The flag has to produce that exact call, or deleting the block loses the render.

        `modsecurity/download-crs-plugins` deliberately kept its own call: its condition is
        `render_changed and status == 1`, narrower than "exited 1", and it does not declare the
        flag. `tests/unit/scheduler/test_job_regenerate_flag.py` pins that the two are never
        combined -- declaring both would re-render twice.
        """
        db = _run(monkeypatch, {"plugin_id": plugin_id, "name": job_name, "regenerate": True})

        db.checked_changes.assert_called_once_with(["config"], plugins_changes=[plugin_id], value=True)

    def test_exit_1_without_the_flag_requests_nothing(self, stub_runtime, monkeypatch):
        """Anti-vacuity. A re-render on every changing job would render the whole fleet's
        configuration on every blacklist download."""
        db = _run(monkeypatch, {"regenerate": False})

        db.checked_changes.assert_not_called()

    def test_the_flag_absent_entirely_requests_nothing(self, stub_runtime, monkeypatch):
        """An older Scheduler, or a plugin.json predating the flag, must keep working."""
        db = _run(monkeypatch)

        db.checked_changes.assert_not_called()

    def test_exit_0_with_the_flag_requests_nothing(self, stub_runtime, monkeypatch):
        """Exit 0 means the job changed nothing, so the existing render is still correct. This is
        also what makes the loop converge: the re-render re-dispatches the plugin's jobs once,
        and that second run must not ask for another render."""
        stub_runtime.run = Mock(return_value=0)

        db = _run(monkeypatch, {"regenerate": True})

        db.checked_changes.assert_not_called()

    def test_a_crashed_job_with_the_flag_requests_nothing(self, stub_runtime, monkeypatch):
        stub_runtime.run = Mock(side_effect=RuntimeError("boom"))

        db = _run(monkeypatch, {"regenerate": True})

        db.checked_changes.assert_not_called()


class TestFailureIsReported:
    def test_a_refused_flag_write_is_logged_not_swallowed(self, stub_runtime, monkeypatch):
        """The DB returns an error string rather than raising. Left silent, the operator sees a
        successful run, a cache push, and a configuration that never changed."""
        LOGGER.reset_mock()

        _run(monkeypatch, {"regenerate": True}, checked_changes=Mock(return_value="The database is read-only, the changes will not be saved"))

        assert any("re-render" in str(call) for call in LOGGER.error.call_args_list), LOGGER.error.call_args_list

    def test_a_raising_flag_write_does_not_kill_the_run(self, stub_runtime, monkeypatch):
        LOGGER.reset_mock()
        db = Mock(add_job_run=Mock(return_value=None), checked_changes=Mock(side_effect=RuntimeError("db gone")))
        monkeypatch.setattr(TASKS, "get_worker_db", lambda: db)

        result = TASKS.execute_job(_Self(), dict(JOB, regenerate=True))

        assert result["return_code"] == 1 and result["success"] is True
        assert any("re-render" in str(call) for call in LOGGER.error.call_args_list), LOGGER.error.call_args_list
