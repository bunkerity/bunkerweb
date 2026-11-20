"""API client defaults, pooled DB reuse, password boundaries and operator log contracts."""

import importlib.util
import logging
import socket
import sys
from io import StringIO
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

from bcrypt import checkpw, gensalt, hashpw
from fastapi import HTTPException
import pytest

from _api_http_helpers import VERSION  # noqa: F401 - signing-key/import bootstrap

import API as api_module
import Database as db_module
import app.deps as deps
import app.models.api_database as api_db_module
import app.utils as utils


@pytest.fixture
def clients(monkeypatch):
    database, api_class, caller = Mock(), Mock(), Mock()
    monkeypatch.setattr(deps, "get_db", Mock(return_value=database))
    monkeypatch.setattr(deps, "API", api_class)
    monkeypatch.setattr(deps, "ApiCaller", caller)
    monkeypatch.setattr(deps, "api_config", SimpleNamespace(internal_endpoint="https://internal:5443", internal_api_host_header="bwapi"))
    return database, api_class, caller


def test_internal_api_passes_endpoint_and_host_without_overriding_token_fallback(clients):
    _, api_class, _ = clients
    assert deps.get_internal_api() is api_class.return_value
    api_class.assert_called_once_with("https://internal:5443", "bwapi")


def test_broadcast_builds_each_valid_instance_skips_bad_rows(clients):
    database, api_class, caller = clients
    rows = [{"hostname": "one"}, {"hostname": "broken"}, {"hostname": "two"}]
    database.get_instances.return_value = rows
    one, two = object(), object()
    api_class.from_instance.side_effect = [one, ValueError("bad row"), two]
    assert deps.get_instances_api_caller() is caller.return_value
    assert [call.args[0] for call in api_class.from_instance.call_args_list] == rows
    caller.assert_called_once_with([one, two])
    api_class.assert_not_called()
    deps.get_db.assert_called_once_with(log=False)


def test_database_lookup_failure_falls_back_to_internal_api(clients):
    database, api_class, caller = clients
    database.get_instances.side_effect = RuntimeError("DB unavailable")
    deps.get_instances_api_caller()
    api_class.assert_called_once_with("https://internal:5443", "bwapi")
    caller.assert_called_once_with([api_class.return_value])


def test_no_instances_does_not_invent_internal_instance(clients):
    database, api_class, caller = clients
    database.get_instances.return_value = []
    deps.get_instances_api_caller()
    caller.assert_called_once_with([])
    api_class.assert_not_called()


@pytest.mark.parametrize("found", [True, False])
def test_single_instance_lookup_is_exact_or_not_found(clients, found):
    database, api_class, _ = clients
    row = {"hostname": "node", "port": 5001}
    database.get_instance.return_value = row if found else {}
    if found:
        assert deps.get_api_for_hostname("node") is api_class.from_instance.return_value
        api_class.from_instance.assert_called_once_with(row)
    else:
        with pytest.raises(HTTPException) as caught:
            deps.get_api_for_hostname("node")
        assert (caught.value.status_code, caught.value.detail) == (404, "Instance node not found")
        api_class.from_instance.assert_not_called()
    database.get_instance.assert_called_once_with("node")


def test_db_pool_is_reused_and_recreated_only_after_engine_is_lost(monkeypatch):
    first, replacement = SimpleNamespace(sql_engine=object()), SimpleNamespace(sql_engine=object())
    factory, pin = Mock(side_effect=[first, replacement]), Mock()
    monkeypatch.setattr(db_module, "Database", factory)
    monkeypatch.setattr(api_module.API, "pin_from_database", pin)
    monkeypatch.setattr(utils, "_DB_INSTANCE", None)
    assert utils.get_db(log=False) is first
    assert utils.get_db() is first
    factory.assert_called_once_with(utils.LOGGER, log=False)
    pin.assert_called_once_with(first)
    first.sql_engine = None
    assert utils.get_db() is replacement
    assert factory.call_count == 2 and pin.call_args.args == (replacement,)


def test_api_db_pool_has_independent_reuse_and_recovery(monkeypatch):
    first, replacement = SimpleNamespace(sql_engine=object()), SimpleNamespace(sql_engine=object())
    factory = Mock(side_effect=[first, replacement])
    monkeypatch.setattr(api_db_module, "APIDatabase", factory)
    monkeypatch.setattr(utils, "_API_DB_INSTANCE", None)
    assert utils.get_api_db(log=False) is first
    assert utils.get_api_db() is first
    factory.assert_called_once_with(utils.LOGGER, log=False)
    first.sql_engine = None
    assert utils.get_api_db() is replacement
    assert factory.call_count == 2


@pytest.mark.parametrize("methods", [False, True])
def test_reportable_config_retains_explicit_template_and_plain_values(methods):
    config = {
        "DEFAULT": {"value": "default", "method": "default"},
        "EXPLICIT": {"value": "value", "method": "api"},
        "TEMPLATE": {"value": "template", "template": "custom"},
        "SERVER_NAME": "example",
    }
    expected = {"EXPLICIT": config["EXPLICIT"] if methods else "value", "TEMPLATE": config["TEMPLATE"] if methods else "template", "SERVER_NAME": "example"}
    assert utils.reportable_config(config, methods=methods) == expected
    assert "DEFAULT" in config


@pytest.mark.parametrize("password,exceeds", [("x" * 72, False), ("x" * 73, True), ("é" * 36, False), ("é" * 37, True)])
def test_password_limit_counts_utf8_bytes(password, exceeds):
    assert utils.password_exceeds_bcrypt_limit(password) is exceeds


def test_legacy_long_password_verification_truncates_at_72_bytes():
    password = "é" * 37
    encoded = password.encode()[:72]
    hashed = hashpw(encoded, gensalt(rounds=4))
    assert utils.check_password(password, hashed) is True
    assert utils.check_password("wrong", hashed) is False


def test_unusable_hash_is_refused_and_spends_normal_verification_work(monkeypatch):
    verify = Mock(side_effect=[ValueError("bad salt"), False])
    warning = Mock()
    monkeypatch.setattr(utils, "checkpw", verify)
    monkeypatch.setattr(utils.LOGGER, "warning", warning)
    assert utils.check_password("secret", b"invalid") is False
    assert verify.call_count == 2
    assert verify.call_args_list[1].args[0] == b"secret"
    assert verify.call_args_list[1].args[1].startswith(b"$2b$13$")
    warning.assert_called_once_with("Stored bcrypt hash is unusable, credential check refused")


def test_generated_hash_uses_cost_13_and_checks_password(monkeypatch):
    real_gensalt = utils.gensalt
    salt = Mock(side_effect=lambda **kwargs: real_gensalt(rounds=4))
    monkeypatch.setattr(utils, "gensalt", salt)
    hashed = utils.gen_password_hash("strong-password")
    salt.assert_called_once_with(rounds=13)
    assert checkpw(b"strong-password", hashed)


@pytest.mark.parametrize("value", ["plain", "$2z$04$" + "x" * 53, "$2b$99$" + "x" * 53])
def test_bcrypt_shape_and_library_validation_both_required(value):
    assert utils.is_bcrypt_hash(value) is False


def test_valid_bcrypt_hash_reports_its_actual_cost():
    hashed = hashpw(b"secret", gensalt(rounds=4)).decode()
    assert utils.is_bcrypt_hash(hashed) is True
    assert utils.bcrypt_cost(hashed) == 4


@pytest.fixture
def logging_module(monkeypatch):
    path = Path(__file__).resolve().parents[3] / "src/api/utils/logger.py"
    spec = importlib.util.spec_from_file_location("api_coverage_logger", path)
    module = importlib.util.module_from_spec(spec)
    # Gunicorn is a process-server boundary, absent from the API unit-test pins.
    glogging = ModuleType("gunicorn.glogging")
    glogging.Logger = type("GunicornLogger", (), {"setup": Mock()})
    glogging.SYSLOG_FACILITIES = logging.handlers.SysLogHandler.facility_names
    glogging.logging = logging
    glogging.parse_syslog_address = Mock(return_value=(socket.SOCK_DGRAM, ("127.0.0.1", 5514)))
    monkeypatch.setitem(sys.modules, "gunicorn", ModuleType("gunicorn"))
    monkeypatch.setitem(sys.modules, "gunicorn.glogging", glogging)
    monkeypatch.setenv("LOG_SYSLOG_TAG", "test-api")
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def api_logger(logging_module, monkeypatch):
    module = logging_module
    loggers = {
        name: logging.Logger(name, logging.WARNING if name.endswith("ACCESS") else logging.INFO)
        for name in ("API", "API.ACCESS", "uvicorn.error", "uvicorn.access")
    }
    streams = {name: StringIO() for name in ("API", "API.ACCESS")}
    for name, stream in streams.items():
        loggers[name].addHandler(logging.StreamHandler(stream))
    monkeypatch.setattr(module, "getLogger", lambda name: loggers[name])
    # Gunicorn setup owns file/socket creation; keep custom synchronization and filters real.
    instance = module.APILogger(SimpleNamespace())
    return module, instance, loggers, streams


def test_uvicorn_uses_api_handlers_levels_names_and_format(api_logger):
    module, instance, loggers, streams = api_logger
    for target, source in (("uvicorn.error", "API"), ("uvicorn.access", "API.ACCESS")):
        logger = loggers[target]
        assert logger.handlers == loggers[source].handlers
        assert logger.level == loggers[source].level and logger.propagate is False
        assert loggers[source].propagate is False
        logger.warning("operator-visible failure")
        text = streams[source].getvalue()
        assert f"[{source}]" in text and "operator-visible failure" in text
        assert logger.handlers[0].formatter._fmt == module.LOG_FORMAT
        assert logger.handlers[0].formatter.datefmt == module.DATE_FORMAT
    assert instance._uvicorn_synced is True


def test_repeated_setup_does_not_duplicate_uvicorn_filters(api_logger):
    module, instance, loggers, _ = api_logger
    filters = {name: list(loggers[name].filters) for name in ("uvicorn.error", "uvicorn.access")}
    instance.setup(instance.cfg)
    assert {name: loggers[name].filters for name in filters} == filters
    assert module.Logger.setup.call_count == 2


def test_syslog_sync_sets_ident_and_reuses_already_correct_formatter(logging_module, monkeypatch):
    module = logging_module
    loggers = {name: logging.Logger(name) for name in ("API", "API.ACCESS", "uvicorn.error", "uvicorn.access")}
    formatter = logging.Formatter(module.LOG_FORMAT, module.DATE_FORMAT)
    for name in ("API", "API.ACCESS"):
        handler = logging.handlers.SysLogHandler.__new__(logging.handlers.SysLogHandler)
        logging.Handler.__init__(handler)
        handler.socket = None
        handler.setFormatter(formatter)
        loggers[name].addHandler(handler)
    monkeypatch.setattr(module, "getLogger", lambda name: loggers[name])
    module.APILogger(SimpleNamespace())
    for name, ident in (("uvicorn.error", "test-api: "), ("uvicorn.access", "test-api-access: ")):
        handler = loggers[name].handlers[0]
        assert handler.ident == ident and handler.formatter is formatter


@pytest.mark.parametrize("name,prefix,expected", [("error", "explicit", "explicit"), ("access", None, "worker.api-access")])
def test_syslog_handler_uses_facility_address_and_process_prefix(logging_module, monkeypatch, name, prefix, expected):
    module = logging_module
    handler = logging.NullHandler()
    factory = Mock(return_value=handler)
    monkeypatch.setattr(module.logging.handlers, "SysLogHandler", factory)
    cfg = SimpleNamespace(syslog_prefix=prefix, proc_name="worker:api", syslog_facility="LOCAL0", syslog_addr="udp://127.0.0.1:5514")
    logger = logging.Logger("test")
    module.APILogger._set_syslog_handler(None, logger, cfg, "%(message)s", name)
    module.parse_syslog_address.assert_called_once_with(cfg.syslog_addr)
    factory.assert_called_once_with(address=("127.0.0.1", 5514), facility=module.SYSLOG_FACILITIES["local0"], socktype=socket.SOCK_DGRAM)
    assert logger.handlers == [handler] and handler._gunicorn is True
    record = logger.makeRecord("test", logging.INFO, __file__, 0, "hello", (), None)
    assert handler.formatter.format(record) == f"{expected}: hello"


def test_unknown_syslog_facility_fails_before_socket_creation(logging_module, monkeypatch):
    factory = Mock()
    monkeypatch.setattr(logging_module.logging.handlers, "SysLogHandler", factory)
    cfg = SimpleNamespace(syslog_prefix="api", proc_name="worker", syslog_facility="unknown")
    with pytest.raises(RuntimeError, match="unknown facility name"):
        logging_module.APILogger._set_syslog_handler(None, logging.Logger("test"), cfg, "%(message)s", "error")
    factory.assert_not_called()
