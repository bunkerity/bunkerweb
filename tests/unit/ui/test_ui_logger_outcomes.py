"""UI worker logs keep their identity, avoid duplicate root output and validate syslog settings."""

import importlib.util
import logging
import logging.handlers
import socket
import sys
from io import StringIO
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def ui_logging(monkeypatch):
    # Gunicorn owns process/file setup and is absent from the unit pins, as in the API logger tests.
    boundary = ModuleType("gunicorn.glogging")
    boundary.Logger = type("GunicornLogger", (), {"setup": Mock()})
    boundary.SYSLOG_FACILITIES = logging.handlers.SysLogHandler.facility_names
    boundary.logging = logging
    boundary.parse_syslog_address = Mock(return_value=(socket.SOCK_DGRAM, ("127.0.0.1", 5514)))
    monkeypatch.setitem(sys.modules, "gunicorn", ModuleType("gunicorn"))
    monkeypatch.setitem(sys.modules, "gunicorn.glogging", boundary)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    path = Path(__file__).resolve().parents[3] / "src/ui/utils/logger.py"
    spec = importlib.util.spec_from_file_location("ui_logger_outcomes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    loggers = {name: logging.Logger(name, logging.INFO) for name in ("UI", "UI.ACCESS", "TMP-UI", "TMP-UI.ACCESS")}
    monkeypatch.setattr(module, "getLogger", lambda name: loggers[name])
    return module, loggers


@pytest.mark.parametrize("class_name,names", [("UiLogger", ("UI", "UI.ACCESS")), ("TmpUiLogger", ("TMP-UI", "TMP-UI.ACCESS"))])
def test_worker_records_keep_component_names_without_root_duplicates(ui_logging, class_name, names):
    module, loggers = ui_logging
    cfg = SimpleNamespace()
    instance = getattr(module, class_name)(cfg)
    parent_stream = StringIO()
    parent = logging.Logger("parent", logging.INFO)
    parent.addHandler(logging.StreamHandler(parent_stream))
    for logger in (instance.error_log, instance.access_log):
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter(instance.error_fmt, instance.datefmt))
        logger.addHandler(handler)
        logger.parent = parent
        logger.warning("worker-visible diagnostic")
        assert f"[{logger.name}]" in stream.getvalue()
        assert stream.getvalue().count("worker-visible diagnostic") == 1
    assert (instance.error_log, instance.access_log) == tuple(loggers[name] for name in names)
    assert parent_stream.getvalue() == ""
    module.Logger.setup.assert_called_once_with(cfg)


def test_preconfigured_loggers_are_retained_without_changing_their_destinations(ui_logging, monkeypatch):
    module, loggers = ui_logging
    monkeypatch.setattr(module.UiLogger, "error_log", loggers["UI"])
    monkeypatch.setattr(module.UiLogger, "access_log", loggers["UI.ACCESS"])
    monkeypatch.setattr(module, "getLogger", Mock(side_effect=AssertionError("must preserve configured loggers")))
    instance = module.UiLogger(SimpleNamespace())
    assert instance.error_log is loggers["UI"] and instance.access_log is loggers["UI.ACCESS"]
    assert not instance.error_log.propagate and not instance.access_log.propagate


@pytest.mark.parametrize(
    "name,prefix,expected",
    [("error", "custom-ui", "custom-ui"), ("access", "custom-ui", "custom-ui-access"), ("error", None, "worker.ui"), ("access", None, "worker.ui-access")],
)
def test_syslog_records_use_facility_address_and_component_prefix(ui_logging, monkeypatch, name, prefix, expected):
    module, _ = ui_logging
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    factory = Mock(return_value=handler)
    monkeypatch.setattr(module.logging.handlers, "SysLogHandler", factory)
    cfg = SimpleNamespace(syslog_prefix=prefix, proc_name="worker:ui", syslog_facility="LOCAL0", syslog_addr="udp://127.0.0.1:5514")
    logger = logging.Logger("record", logging.INFO)
    module.UiLogger._set_syslog_handler(None, logger, cfg, "%(message)s", name)
    logger.info("request diagnostic")
    assert stream.getvalue() == f"{expected}: request diagnostic\n"
    module.parse_syslog_address.assert_called_once_with(cfg.syslog_addr)
    factory.assert_called_once_with(address=("127.0.0.1", 5514), facility=16, socktype=socket.SOCK_DGRAM)
    assert handler._gunicorn is True


def test_invalid_facility_fails_before_creating_a_syslog_socket(ui_logging, monkeypatch):
    module, _ = ui_logging
    factory = Mock()
    monkeypatch.setattr(module.logging.handlers, "SysLogHandler", factory)
    cfg = SimpleNamespace(syslog_prefix="ui", proc_name="worker", syslog_facility="invalid")
    logger = logging.Logger("record")
    with pytest.raises(RuntimeError, match="unknown facility name"):
        module.UiLogger._set_syslog_handler(None, logger, cfg, "%(message)s", "error")
    factory.assert_not_called()
    assert logger.handlers == []
