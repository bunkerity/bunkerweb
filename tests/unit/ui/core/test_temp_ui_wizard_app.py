"""src/ui/temp.py: the temporary UI served while the real one starts (unauthenticated, port 7000)."""

import re
import signal
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import MagicMock

import pytest

TEMP_PY = Path(__file__).resolve().parents[4] / "src" / "ui" / "temp.py"


@pytest.fixture
def temp(tmp_path, monkeypatch):
    saved = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    spec = spec_from_file_location("bw_temp_ui_under_test", TEMP_PY)
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        for sig, handler in saved.items():
            signal.signal(sig, handler)  # the module binds SIGINT/SIGTERM to its own stop()
    monkeypatch.setattr(module, "ERROR_FILE", tmp_path / "ui.error")
    module.render_template = lambda template, **context: f"{template}|{context['message']}|{context['error']}"
    yield module
    sys.modules.pop(spec.name, None)


def test_any_path_shows_the_starting_page(temp):
    client = temp.app.test_client()
    for path in ("/", "/anything", "/deep/nested/path"):
        resp = client.get(path)
        assert resp.status_code == 200 and resp.data == b"starting.html|BunkerWeb UI is starting...|"


def test_startup_error_is_reported_without_its_detail(temp):
    temp.ERROR_FILE.write_text("Traceback ... FLASK_SECRET=hunter2 ... mysql://user:pw@db")
    resp = temp.app.test_client().get("/")
    assert b"encountered an error while starting" in resp.data
    assert b"hunter2" not in resp.data and b"mysql" not in resp.data


def test_security_headers_and_a_fresh_nonce_per_request(temp):
    client = temp.app.test_client()
    first, second = client.get("/"), client.get("/")
    assert first.headers["X-Frame-Options"] == "DENY" and first.headers["X-Content-Type-Options"] == "nosniff"
    assert first.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    nonce = re.search(r"'nonce-([^']+)'", first.headers["Content-Security-Policy"]).group(1)
    other = re.search(r"'nonce-([^']+)'", second.headers["Content-Security-Policy"]).group(1)
    assert nonce != other and len(nonce) >= 32
    assert "object-src 'none'" in first.headers["Content-Security-Policy"]


def test_wsgi_app_is_wrapped_by_the_reverse_proxy_fix(temp):
    assert type(temp.app.wsgi_app).__name__ == "ReverseProxied"


class TestStop:
    def patch(self, temp, monkeypatch, tmp_path, pid_bytes=None, pgrep=b"4321\n"):
        pid_file = tmp_path / "tmp-ui.pid"
        if pid_bytes is not None:
            pid_file.write_bytes(pid_bytes)
        popen = MagicMock()
        popen.return_value.communicate.return_value = (pgrep, None)
        monkeypatch.setattr(temp, "Path", lambda *parts: pid_file)
        monkeypatch.setattr(temp, "Popen", popen)
        call, exit_ = MagicMock(), MagicMock()
        monkeypatch.setattr(temp, "call", call)
        monkeypatch.setattr(temp, "_exit", exit_)
        return call, exit_, popen

    def test_pid_file_wins_over_pgrep(self, temp, monkeypatch, tmp_path):
        call, exit_, popen = self.patch(temp, monkeypatch, tmp_path, pid_bytes=b"777\n")
        temp.stop(3)
        call.assert_called_once_with(["kill", "-SIGTERM", "777"])
        exit_.assert_called_once_with(3)
        popen.assert_not_called()

    def test_without_pid_file_pgrep_picks_the_first_gunicorn(self, temp, monkeypatch, tmp_path):
        call, exit_, popen = self.patch(temp, monkeypatch, tmp_path, pgrep=b"4321\n99\n")
        temp.stop(0)
        call.assert_called_once_with(["kill", "-SIGTERM", "4321"])
        assert popen.call_args.args[0] == ["pgrep", "-f", "gunicorn"]

    def test_signal_handler_stops_with_status_zero(self, temp, monkeypatch, tmp_path):
        call, exit_, _ = self.patch(temp, monkeypatch, tmp_path, pid_bytes=b"5")
        temp.handle_stop(signal.SIGTERM, None)
        exit_.assert_called_once_with(0)
