"""Celery worker database extension lifecycle."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

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
    previous = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        path = ROOT / "src" / "worker" / "app.py"
        spec = importlib.util.spec_from_file_location("bw_worker_app", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


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


def test_route_job_uses_heavy_queue_only_for_known_jobs():
    assert APP.route_job("task", ({"name": "backup-data"},), {}, {}) == {"queue": "heavy"}
    assert APP.route_job("task", ({"name": "cleanup"},), {}, {}) == {"queue": "default"}
