"""Celery worker database extension lifecycle."""

import importlib.util
import sys
from json import loads
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]


class _Conf(dict):
    __getattr__ = dict.get

    def __setattr__(self, name, value):
        self[name] = value


class _Celery:
    def __init__(self, *_args, **_kwargs):
        self.conf = _Conf()


class _Signal:
    def connect(self, function):
        return function


def _load_app():
    celery = ModuleType("celery")
    signals = ModuleType("celery.signals")
    kombu = ModuleType("kombu")
    celery.Celery = _Celery
    signals.worker_process_init = _Signal()
    signals.worker_process_shutdown = _Signal()
    kombu.Queue = lambda name: name
    modules = {"celery": celery, "celery.signals": signals, "kombu": kombu}
    with patch.dict(sys.modules, modules):
        path = ROOT / "src" / "worker" / "app.py"
        spec = importlib.util.spec_from_file_location("bw_worker_app", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


APP = _load_app()


def test_worker_registers_plugin_models_and_closes(monkeypatch):
    database = Mock()
    logger = Mock()
    register = Mock()
    database_module = ModuleType("Database")
    logger_module = ModuleType("logger")
    extensions_module = ModuleType("plugin_extensions")
    database_module.Database = Mock(return_value=database)
    logger_module.setup_logger = Mock(return_value=logger)
    extensions_module.register_plugin_models = register
    monkeypatch.setitem(sys.modules, "Database", database_module)
    monkeypatch.setitem(sys.modules, "logger", logger_module)
    monkeypatch.setitem(sys.modules, "plugin_extensions", extensions_module)
    monkeypatch.setenv("DATABASE_URI", "sqlite:///worker.db")

    APP.init_worker_db()
    register.assert_called_once_with(logger, db=database)
    assert APP.get_worker_db() is database

    APP.shutdown_worker_db()
    database.close.assert_called_once()
    assert APP.get_worker_db() is None


def test_worker_without_database_uri_is_noop(monkeypatch):
    monkeypatch.delenv("DATABASE_URI", raising=False)
    APP._worker_db = Mock()
    APP.init_worker_db()
    assert APP.get_worker_db() is None


def test_plugin_registration_failure_does_not_abort_worker(monkeypatch):
    database = Mock()
    logger = Mock()
    database_module = ModuleType("Database")
    logger_module = ModuleType("logger")
    extensions_module = ModuleType("plugin_extensions")
    database_module.Database = Mock(return_value=database)
    logger_module.setup_logger = Mock(return_value=logger)
    extensions_module.register_plugin_models = Mock(side_effect=RuntimeError("bad plugin"))
    monkeypatch.setitem(sys.modules, "Database", database_module)
    monkeypatch.setitem(sys.modules, "logger", logger_module)
    monkeypatch.setitem(sys.modules, "plugin_extensions", extensions_module)
    monkeypatch.setenv("DATABASE_URI", "sqlite:///worker.db")

    APP.init_worker_db()

    assert APP.get_worker_db() is database
    logger.error.assert_called_once()
    APP.shutdown_worker_db()


def test_route_job_uses_the_manifest_async_flag_when_present():
    assert APP.route_job("task", ({"name": "external-job", "async": True},), {}, {}) == {"queue": "heavy"}
    assert APP.route_job("task", ({"name": "backup-data", "async": False},), {}, {}) == {"queue": "default"}
    assert APP.route_job("task", ({"name": "backup-data"},), {}, {}) == {"queue": "heavy"}
    assert APP.route_job("task", ({"name": "cleanup"},), {}, {}) == {"queue": "default"}
    assert APP.route_job("task", ("not-a-dict",), {}, {}) == {"queue": "default"}


def test_worker_and_api_route_from_the_same_set():
    """The API used to carry a hand-synced copy of HEAVY_JOBS; both now import one set.

    Identity can't be asserted here — ``_load_app`` runs under ``patch.dict(sys.modules)``,
    which drops whatever it imported — so this pins the property that made the copies
    drift: no job name is written down anywhere but ``job_queues``.
    """
    import job_queues

    assert APP.HEAVY_JOBS == job_queues.HEAVY_JOBS
    assert job_queues.queue_for("external-job", is_async=True) == "heavy"
    assert job_queues.queue_for("push-configs", is_async=False) == "default"
    assert job_queues.queue_for("push-configs") == "heavy"
    assert job_queues.queue_for("update-check") == "default"

    for source in (ROOT / "src" / "worker" / "app.py", ROOT / "src" / "api" / "app" / "routers" / "jobs.py"):
        assert "backup-data" not in source.read_text(encoding="utf-8"), f"{source} grew a second copy of HEAVY_JOBS"


def test_core_manifest_async_flags_match_heavy_jobs():
    """The manifest source of truth and name-only fallback stay in lockstep."""
    import job_queues

    async_jobs = set()
    missing_async = []
    for manifest in (ROOT / "src" / "common" / "core").glob("*/plugin.json"):
        for job in loads(manifest.read_text(encoding="utf-8")).get("jobs", []):
            if not isinstance(job.get("async"), bool):
                missing_async.append(job["name"])
            if job.get("async") is True:
                async_jobs.add(job["name"])

    assert not missing_async, f"jobs without explicit async: {sorted(missing_async)}"
    assert job_queues.HEAVY_JOBS <= async_jobs, f"heavy jobs without async: {sorted(job_queues.HEAVY_JOBS - async_jobs)}"
    assert async_jobs <= job_queues.HEAVY_JOBS, f"non-heavy async jobs: {sorted(async_jobs - job_queues.HEAVY_JOBS)}"
