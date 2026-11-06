"""Warn about uncached new responses without changing reverse-proxy configuration."""

import logging
from pathlib import Path

import pytest

import Templator as T  # type: ignore
from Configurator import Configurator  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
SERVICE = "app.example.com"
OTHER = "other.example.com"
BASE = {
    "SERVER_NAME": SERVICE,
    "USE_REVERSE_PROXY": "yes",
    "USE_PROXY_CACHE": "yes",
    "REVERSE_PROXY_HOST": "http://backend.invalid:8080/private",
    "REVERSE_PROXY_BUFFERING": "no",
    "REVERSE_PROXY_HEADERS": "Authorization secret-value",
}


@pytest.fixture
def render(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(T, "sep", str(tmp_path))
    monkeypatch.setattr(T, "logger", logging.getLogger("TEMPLATOR"))
    caplog.set_level(logging.WARNING, logger="TEMPLATOR")
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    pro_plugins = tmp_path / "pro-plugins"
    pro_plugins.mkdir()

    def run(variables, sparse=False):
        full = Configurator(
            str(ROOT / "src/common/settings.json"), str(ROOT / "src/common/core"), str(plugins), str(pro_plugins), variables, logging.getLogger("test-config")
        ).get_config(None)
        config = full.copy()
        if sparse:
            # Scheduler omits default-valued settings from its non-default view.
            config.pop("SERVER_TYPE", None)
        templator = T.Templator(
            str(ROOT / "src/common/confs"),
            str(ROOT / "src/common/core"),
            str(plugins),
            str(pro_plugins),
            str(tmp_path / "out"),
            "/etc/nginx",
            config,
            full,
            full,
        )
        assert templator._render_global() == []
        servers = full["SERVER_NAME"].split() if full["MULTISITE"] == "yes" else [full["SERVER_NAME"]]
        for server in servers:
            assert templator._render_server(server) == []
        return {str(p.relative_to(tmp_path / "out")): p.read_bytes() for p in sorted((tmp_path / "out").rglob("*")) if p.is_file()}

    return run


@pytest.mark.parametrize("sparse", [False, True], ids=["environment", "scheduler-defaults"])
def test_warns_once_per_affected_slot(render, caplog, sparse):
    variables = BASE | {
        "REVERSE_PROXY_HOST_1": "http://backend.invalid:8081",
        "REVERSE_PROXY_URL_1": "/one",
        "REVERSE_PROXY_BUFFERING_1": "no",
        "REVERSE_PROXY_HOST_2": "http://backend.invalid:8082",
        "REVERSE_PROXY_URL_2": "/two",
        "REVERSE_PROXY_BUFFERING_2": "no",
        "REVERSE_PROXY_HOST_3": "http://backend.invalid:8083",
        "REVERSE_PROXY_URL_3": "/three",
        "REVERSE_PROXY_BUFFERING_3": "yes",
    }
    tree = render(variables, sparse=sparse)
    messages = [r.message for r in caplog.records if r.name == "TEMPLATOR" and r.levelno == logging.WARNING]
    assert len(messages) == 3, messages
    for setting in ("REVERSE_PROXY_BUFFERING=no", "REVERSE_PROXY_BUFFERING_1=no", "REVERSE_PROXY_BUFFERING_2=no"):
        assert sum(SERVICE in message and setting in message for message in messages) == 1
    for message in messages:
        assert "new responses are not cached" in message
        assert "buffering is off" in message
        assert "backend.invalid" not in message
        assert "secret-value" not in message
        assert "Authorization" not in message
    proxy = tree["server-http/reverse-proxy.conf"]
    assert b"proxy_cache proxycache;" in proxy
    assert proxy.count(b"proxy_buffering off;") == 3
    assert proxy.count(b"proxy_buffering on;") == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"SERVER_TYPE": "stream"},
        {"USE_REVERSE_PROXY": "no"},
        {"USE_PROXY_CACHE": "no"},
        {"REVERSE_PROXY_HOST": ""},
        {"REVERSE_PROXY_BUFFERING": "yes"},
        {"REVERSE_PROXY_BUFFERING": "yes", "REVERSE_PROXY_REQUEST_BUFFERING": "no"},
        {"REVERSE_PROXY_BUFFERING": "yes", "REVERSE_PROXY_HOST_1": "http://backend.invalid:8081", "REVERSE_PROXY_URL_1": "/one"},
        {"REVERSE_PROXY_HOST": "", "REVERSE_PROXY_HOST_2": "", "REVERSE_PROXY_BUFFERING_2": "no"},
    ],
    ids=["stream", "proxy-disabled", "cache-disabled", "empty-host", "buffered", "request-buffering-only", "numbered-default", "empty-numbered-host"],
)
def test_unaffected_services_do_not_warn(render, caplog, overrides):
    render(BASE | overrides)
    assert not [r.message for r in caplog.records if r.name == "TEMPLATOR" and r.levelno == logging.WARNING]


def test_multisite_inheritance_and_overrides(render, caplog):
    render(
        BASE
        | {
            "MULTISITE": "yes",
            "SERVER_NAME": f"{SERVICE} {OTHER}",
            f"{SERVICE}_REVERSE_PROXY_HOST_2": "http://backend.invalid:8082",
            f"{SERVICE}_REVERSE_PROXY_URL_2": "/two",
            f"{SERVICE}_REVERSE_PROXY_BUFFERING_2": "no",
            f"{OTHER}_REVERSE_PROXY_BUFFERING": "yes",
        }
    )
    messages = [r.message for r in caplog.records if r.name == "TEMPLATOR" and r.levelno == logging.WARNING]
    assert len(messages) == 2, messages
    assert all(SERVICE in message and OTHER not in message for message in messages)
    assert sum("REVERSE_PROXY_BUFFERING=no" in message for message in messages) == 1
    assert sum("REVERSE_PROXY_BUFFERING_2=no" in message for message in messages) == 1
