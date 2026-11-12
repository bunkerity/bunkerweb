"""Transport failures must match the status action's explicit expectation (UB5-1)."""

import errno
import importlib
import logging
import socket
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock
from copy import deepcopy

import httpx
import pytest
import yaml
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
LOGGER = logging.getLogger(__name__)


@pytest.fixture
def modules(monkeypatch):
    # Load only the HTTP handler and its model, without Selenium/Redis package side effects.
    loaded = []
    for alias, directory in (("t5_handlers", "core_handlers"), ("t5_models", "models")):
        package = ModuleType(alias)
        package.__path__ = [str(ROOT / "tests" / directory)]
        monkeypatch.setitem(sys.modules, alias, package)
        loaded.append(alias)
    handler = importlib.import_module("t5_handlers.http_status_handler")
    common = importlib.import_module("t5_handlers.http_common")
    status = importlib.import_module("t5_models.status")
    yield handler, common, status.Status
    for name in list(sys.modules):
        if any(name.startswith(f"{alias}.") for alias in loaded):
            sys.modules.pop(name)


def _request(monkeypatch, handler, response, error=None):
    monkeypatch.setattr(handler, "perform_request", lambda *_, **__: SimpleNamespace(response=response, error=error))


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("[Errno 111] Connection refused"),
        httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate"),
        httpx.ReadTimeout("timed out"),
        httpx.ConnectError("[Errno -2] Name or service not known"),
        httpx.InvalidURL("Invalid port"),
        httpx.ReadError("unrelated read failure"),
        httpx.RemoteProtocolError("illegal status line"),
    ],
)
def test_wrong_failure_kind_fails(modules, monkeypatch, error):
    handler, _, _ = modules
    _request(monkeypatch, handler, f"{type(error).__name__}: {error}", error)
    with pytest.raises(SystemExit) as failed:
        handler.handle(LOGGER, SimpleNamespace(status=None, expect_error={"connection_closed"}))
    assert failed.value.code == 1


@pytest.mark.parametrize(
    "kind,error",
    [
        ("connection_refused", httpx.ConnectError("[Errno 111] Connection refused")),
        ("connection_closed", httpx.ReadError("[Errno 104] Connection reset by peer")),
        ("connection_closed", httpx.RemoteProtocolError("Server disconnected without sending a response.")),
        ("connection_closed", httpx.RemoteProtocolError("Server disconnected")),
        ("tls_verify", httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate")),
    ],
)
def test_expected_failure_kind_passes(modules, monkeypatch, kind, error):
    handler, _, _ = modules
    _request(monkeypatch, handler, f"{type(error).__name__}: {error}", error)
    handler.handle(LOGGER, SimpleNamespace(status=None, expect_error={kind}))


def test_bare_failure_expectation_fails_even_if_model_was_bypassed(modules, monkeypatch):
    handler, _, _ = modules
    _request(monkeypatch, handler, "httpx.ConnectError: [Errno 111] Connection refused", httpx.ConnectError("[Errno 111] Connection refused"))
    with pytest.raises(SystemExit):
        handler.handle(LOGGER, SimpleNamespace(status=None, expect_error=set()))


def test_unexpected_success_fails(modules, monkeypatch):
    handler, _, _ = modules
    _request(monkeypatch, handler, httpx.Response(200))
    with pytest.raises(SystemExit):
        handler.handle(LOGGER, SimpleNamespace(status=None, expect_error={"connection_closed"}))


@pytest.mark.parametrize("response", [httpx.Response(200), "httpx.ConnectError: [Errno 111] Connection refused"])
def test_status_code_mismatch_or_transport_failure_fails(modules, monkeypatch, response):
    handler, _, _ = modules
    _request(monkeypatch, handler, response)
    with pytest.raises(SystemExit):
        handler.handle(LOGGER, SimpleNamespace(status=403, expect_error=set()))


def test_matching_status_passes(modules, monkeypatch):
    handler, _, _ = modules
    _request(monkeypatch, handler, httpx.Response(403))
    handler.handle(LOGGER, SimpleNamespace(status=403, expect_error=set()))


@pytest.mark.parametrize("data", [{}, {"expect_error": []}, {"status": 200, "expect_error": ["connection_closed"]}, {"expect_error": ["anything"]}])
def test_invalid_status_expectation_is_rejected(modules, data):
    _, _, status = modules
    with pytest.raises(ValidationError):
        status(url="https://www.example.com", **data)


def test_valid_model_keeps_explicit_error_kinds(modules):
    _, _, status = modules
    action = status(url="http://www.example.com", expect_error=["connection_refused", "connection_closed"])
    assert action.expect_error == {"connection_refused", "connection_closed"}
    assert status(url="http://www.example.com", status=200).status == 200


def test_request_context_keeps_original_exception(modules, monkeypatch):
    _, common, status = modules
    error = httpx.ConnectError("[Errno 111] Connection refused")
    client = MagicMock()
    client.__enter__.return_value.request.side_effect = error
    monkeypatch.setattr(common, "Client", MagicMock(return_value=client))
    context = common.perform_request(LOGGER, status(url="http://www.example.com", status=200))
    assert context.error is error
    assert "httpx.ConnectError: [Errno 111] Connection refused" in context.response


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(2)])
def test_process_control_exception_is_not_an_expected_network_failure(modules, monkeypatch, error):
    _, common, status = modules
    client = MagicMock()
    client.__enter__.return_value.request.side_effect = error
    monkeypatch.setattr(common, "Client", MagicMock(return_value=client))
    with pytest.raises(type(error)):
        common.perform_request(LOGGER, status(url="http://www.example.com", status=200))


def test_every_status_spec_has_an_explicit_expectation(modules):
    _, _, status = modules
    integrations = ("Docker", "Linux", "Autoconf", "Kubernetes", "All-in-one")
    count = 0
    for suite in ("core", "api", "ui"):
        for path in sorted((ROOT / "tests" / suite).glob("*.yml")):
            for name, data in yaml.safe_load(path.read_text()).get("actions", {}).items():
                if data.get("type") != "status":
                    continue
                # parse_action merges each integration override before constructing Status.
                for integration in integrations:
                    if integration not in data.get("integrations", integrations):
                        continue
                    merged = {key: deepcopy(value) for key, value in data.items() if key not in integrations}
                    for key, value in data.get(integration, {}).items():
                        if value is None:
                            merged.pop(key, None)
                        elif isinstance(value, dict):
                            merged[key] = merged.get(key, {}) | value
                        else:
                            merged[key] = value
                    try:
                        status(**merged)
                    except ValidationError as error:
                        pytest.fail(f"{path.relative_to(ROOT)}:{name}/{integration}: {error}")
                    count += 1
    assert count > 0


def _fake_dns(monkeypatch, addresses):
    """Stand in for the runner's resolver: `addresses` maps a family (0 = any) to the answers."""
    real_calls = []

    def getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        real_calls.append(family)
        found = [a for a in addresses if family in (0, a[0])]
        if not found:
            raise socket.gaierror(socket.EAI_ADDRFAMILY, "Address family for hostname not supported")
        return [(af, socket.SOCK_STREAM, 6, "", (ip, port) + ((0, 0) if af == socket.AF_INET6 else ())) for af, ip in found]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    return real_calls


def _fake_connect(monkeypatch, refused=(socket.AF_INET,), unreachable=(socket.AF_INET6,)):
    """No network: an IPv4 target refuses the connection, an IPv6 one has no route (ENETUNREACH)."""
    attempts = []

    def connect(self, address):
        attempts.append(self.family)
        if self.family in unreachable:
            raise OSError(errno.ENETUNREACH, "Network is unreachable")
        raise ConnectionRefusedError(errno.ECONNREFUSED, "Connection refused")

    monkeypatch.setattr(socket.socket, "connect", connect)
    return attempts


def test_closed_port_with_an_unreachable_ipv6_answer_is_connection_refused(modules, monkeypatch):
    """STAGING 43194170054, Linux `misc;listen_http_disabled`.

    dnsmasq answers A from its hosts file but forwards AAAA upstream, and a runner has no IPv6 route:
    the closed port refuses 127.0.0.1, the AAAA address is then unreachable, and that last error won.
    """
    handler, _, status = modules
    attempts = _fake_connect(monkeypatch)
    _fake_dns(monkeypatch, [(socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "2606:4700:10::6814:179a")])
    handler.handle(LOGGER, status(url="http://www.example.com", expect_error=["connection_refused"]))
    assert socket.AF_INET in attempts


def test_unreachable_ipv6_alone_is_still_not_an_expected_failure(modules, monkeypatch):
    handler, _, status = modules
    _fake_connect(monkeypatch)
    _fake_dns(monkeypatch, [(socket.AF_INET6, "2606:4700:10::6814:179a")])
    with pytest.raises(SystemExit) as failed:
        handler.handle(LOGGER, status(url="http://www.example.com", expect_error=["connection_refused", "connection_closed"]))
    assert failed.value.code == 1


def test_ipv6_literal_url_keeps_working(modules, monkeypatch):
    handler, _, status = modules
    attempts = _fake_connect(monkeypatch, refused=(socket.AF_INET6,), unreachable=())
    _fake_dns(monkeypatch, [(socket.AF_INET6, "::1")])
    handler.handle(LOGGER, status(url="http://[::1]:8080", expect_error=["connection_refused"]))
    assert attempts == [socket.AF_INET6]


def test_ipv6_only_name_keeps_working(modules, monkeypatch):
    handler, _, status = modules
    attempts = _fake_connect(monkeypatch, refused=(socket.AF_INET6,), unreachable=())
    _fake_dns(monkeypatch, [(socket.AF_INET6, "fd42:1618:1::10")])
    handler.handle(LOGGER, status(url="http://v6.example.com", expect_error=["connection_refused"]))
    assert attempts == [socket.AF_INET6]


def test_resolver_is_restored_after_the_request(modules, monkeypatch):
    handler, _, status = modules
    _fake_connect(monkeypatch)
    _fake_dns(monkeypatch, [(socket.AF_INET, "127.0.0.1")])
    resolver = socket.getaddrinfo
    handler.handle(LOGGER, status(url="http://www.example.com", expect_error=["connection_refused"]))
    assert socket.getaddrinfo is resolver
