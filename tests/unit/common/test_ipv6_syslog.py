"""Syslog setup passes unbracketed IPv6 hosts to Python socket APIs."""

import logging
import runpy
from pathlib import Path
from socket import SOCK_DGRAM, SOCK_STREAM
from unittest.mock import MagicMock

import pytest

LOGGER = Path(__file__).resolve().parents[3] / "src/common/utils/logger.py"


@pytest.fixture
def load_logger(monkeypatch):
    monkeypatch.setenv("LOG_TYPES", "syslog")
    for name in ("basicConfig", "setLoggerClass", "addLevelName"):
        monkeypatch.setattr(logging, name, lambda *args, **kwargs: None)
    handler = MagicMock()
    monkeypatch.setattr("logging.handlers.SysLogHandler", handler)

    def load(address, error=None):
        monkeypatch.setenv("LOG_SYSLOG_ADDRESS", address)
        handler.side_effect = error
        return runpy.run_path(str(LOGGER))

    return load


@pytest.mark.parametrize("prefix,socktype", [("udp://", SOCK_DGRAM), ("tcp://", SOCK_STREAM), ("", None)])
@pytest.mark.parametrize(
    "authority,expected",
    [
        ("[2001:db8::1]:1514", ("2001:db8::1", 1514)),
        ("[::1]", ("::1", 514)),
        ("[::ffff:192.0.2.1]:514", ("::ffff:192.0.2.1", 514)),
        ("192.0.2.1:514", ("192.0.2.1", 514)),
        ("logs.example.com:1514", ("logs.example.com", 1514)),
        ("logs.example.com", ("logs.example.com", 514)),
    ],
)
def test_syslog_network_authority(load_logger, prefix, socktype, authority, expected):
    namespace = load_logger(prefix + authority)
    assert namespace["log_types"]["syslog"]["address"] == expected
    actual_socktype = socktype if socktype is not None or authority.endswith(":514") or authority.endswith(":1514") else SOCK_DGRAM
    assert namespace["log_types"]["syslog"]["socktype"] == actual_socktype


def test_syslog_unix_socket_preserved(load_logger):
    assert load_logger("/dev/log")["log_types"]["syslog"]["address"] == "/dev/log"


@pytest.mark.parametrize(
    "address,error",
    [
        ("udp://[::1]:514", OSError("unreachable")),
        ("tcp://[::1]:514", OSError("unreachable")),
        ("udp://[broken]:514", None),
        ("udp://[::1]:oops", None),
        ("udp://[fe80::1%eth0]:514", None),
    ],
)
def test_syslog_errors_fall_back_to_stderr(load_logger, address, error):
    namespace = load_logger(address, error)
    assert set(namespace["log_types"]) == {"stderr"}
    assert namespace["warnings"]
