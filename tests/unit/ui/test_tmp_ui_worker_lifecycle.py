"""Temporary UI worker bootstrap creates runtime paths and advertises health only while ready."""

import logging
import runpy
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def worker_config(monkeypatch):
    monkeypatch.setattr(sys, "path", sys.path.copy())
    logger = ModuleType("logger")
    logger.log_types = {}
    logger.getLogger = Mock(return_value=logging.getLogger("tmp-ui-lifecycle"))
    monkeypatch.setitem(sys.modules, "logger", logger)
    for name in ("CUSTOM_LOG_LEVEL", "LOG_LEVEL", "CAPTURE_OUTPUT", "LOG_FILE_PATH", "DEBUG", "LOG_SYSLOG_ADDRESS", "LOG_SYSLOG_TAG"):
        monkeypatch.delenv(name, raising=False)

    def load(log_types=None, **env):
        logger.log_types = log_types or {}
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        path = Path(__file__).resolve().parents[3] / "src/ui/utils/tmp-gunicorn.conf.py"
        return runpy.run_path(str(path))

    return load


@pytest.mark.parametrize("capture", ["no", "yes"])
def test_captured_output_uses_separate_error_and_access_files(worker_config, capture):
    config = worker_config(CAPTURE_OUTPUT=capture, LOG_FILE_PATH="/tmp/ui.errors.log")
    assert (config["errorlog"], config["accesslog"]) == (("/tmp/ui.errors.log", "/tmp/ui.errors-access.log") if capture == "yes" else ("-", "-"))
    assert config["capture_output"] is (capture == "yes")


def test_file_logging_uses_tmp_ui_default_without_capture(worker_config):
    config = worker_config({"file": {}})
    assert (config["errorlog"], config["accesslog"]) == ("/var/log/bunkerweb/tmp-ui.log", "/var/log/bunkerweb/tmp-ui-access.log")


@pytest.mark.parametrize(
    "address,expected",
    [("127.0.0.1:5514", "udp://127.0.0.1:5514"), ("tcp://127.0.0.1:5514", "tcp://127.0.0.1:5514"), ("/tmp/syslog.sock", "/tmp/syslog.sock")],
)
def test_syslog_keeps_transport_and_uses_tmp_ui_tag(worker_config, address, expected):
    config = worker_config({"syslog": {}}, LOG_SYSLOG_ADDRESS=f" {address} ", LOG_SYSLOG_TAG="setup-ui")
    assert config["syslog"] is True
    assert config["syslog_addr"] == expected and config["syslog_prefix"] == "setup-ui"


def test_debug_reload_excludes_static_assets_and_bytecode(worker_config, monkeypatch, tmp_path):
    files = [tmp_path / "app.py", tmp_path / "static/style.css", tmp_path / "__pycache__/app.pyc", tmp_path / "templates/setup.html"]
    monkeypatch.setattr(Path, "rglob", lambda self, pattern: iter(files))
    config = worker_config(DEBUG="yes", LOG_LEVEL="warning")
    assert config["reload"] is True and config["daemon"] is True
    assert config["loglevel"] == "debug"
    assert config["reload_extra_files"] == [str(files[0]), str(files[3])]


@pytest.mark.parametrize("secrets", [{}, {"UI_TEST_SECRET": "unit-only-value"}])
def test_start_ready_exit_manage_directories_secrets_and_health(worker_config, monkeypatch, tmp_path, caplog, secrets):
    config = worker_config(LOG_LEVEL="warning")
    # run_path returns a copy; hooks keep the original globals mapping.
    namespace = config["on_starting"].__globals__
    paths = {name: tmp_path / name for name in ("TMP_DIR", "TMP_UI_DIR", "RUN_DIR", "LIB_DIR", "TMP_UI_WORKER_TMP_DIR")}
    namespace.update(paths)
    health = tmp_path / "tmp-ui.healthy"
    namespace.update(HEALTH_FILE=health, handle_docker_secrets=lambda: secrets, worker_tmp_dir="/missing-shm")
    monkeypatch.delenv("UI_TEST_SECRET", raising=False)
    with caplog.at_level(logging.INFO, logger="tmp-ui-lifecycle"):
        config["on_starting"](None)
    assert all(path.is_dir() for path in paths.values())
    assert "TMP-UI is ready" in caplog.text
    if secrets:
        assert namespace["environ"].get("UI_TEST_SECRET") == "unit-only-value"
        assert "Loaded 1 Docker secrets" in caplog.text and "unit-only-value" not in caplog.text
    else:
        assert "UI_TEST_SECRET" not in namespace["environ"]
        assert "Loaded" not in caplog.text
    assert not health.exists()
    config["when_ready"](None)
    assert health.read_text() == "ok"
    config["on_exit"](None)
    config["on_exit"](None)
    assert not health.exists()
    assert config["loglevel"] == "warning" and config["daemon"] is False
