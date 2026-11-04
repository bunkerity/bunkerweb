"""Execute real Gunicorn configs, stubbing unrelated application bootstrap imports."""

import runpy
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "config,component,port",
    [("ui/utils/gunicorn.conf.py", "UI", "7000"), ("ui/utils/tmp-gunicorn.conf.py", "UI", "7000"), ("api/utils/gunicorn.conf.py", "API", "8888")],
)
@pytest.mark.parametrize("host", ["2001:db8::1", "[2001:db8::1]", "::", "[::]", "127.0.0.1", "example.com", None])
@pytest.mark.parametrize("legacy", [False, True])
def test_gunicorn_bind_brackets_ipv6(monkeypatch, config, component, port, host, legacy):
    monkeypatch.setattr(sys, "path", sys.path.copy())
    for name in ("app.models.ui_database", "app.models.api_database", "app.dependencies", "app.utils", "biscuit_auth", "passlib.totp"):
        monkeypatch.setitem(sys.modules, name, MagicMock())
    logger = MagicMock()
    logger.log_types = {}
    monkeypatch.setitem(sys.modules, "logger", logger)
    for name in ("LISTEN_ADDR", "LISTEN_PORT", f"{component}_LISTEN_ADDR", f"{component}_LISTEN_PORT", "DEBUG"):
        monkeypatch.delenv(name, raising=False)
    if host is not None:
        monkeypatch.setenv("LISTEN_ADDR" if legacy else f"{component}_LISTEN_ADDR", host)
    namespace = runpy.run_path(str(ROOT / "src" / config))
    expected = host or "0.0.0.0"
    if ":" in expected and not expected.startswith("["):
        expected = f"[{expected}]"
    assert namespace["bind"] == f"{expected}:{port}"
