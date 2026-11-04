"""src/ui/temp.py rendered with the real Jinja templates: ``starting.html`` extends ``base.html``, which reads ``current_user``."""

import signal
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

TEMP_PY = Path(__file__).resolve().parents[4] / "src" / "ui" / "temp.py"


@pytest.fixture
def temp(tmp_path, monkeypatch):
    saved = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    spec = spec_from_file_location("bw_temp_ui_real_templates", TEMP_PY)
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        for sig, handler in saved.items():
            signal.signal(sig, handler)  # the module binds SIGINT/SIGTERM to its own stop()
    monkeypatch.setattr(module, "ERROR_FILE", tmp_path / "ui.error")
    module.app.config["PROPAGATE_EXCEPTIONS"] = False
    yield module
    sys.modules.pop(spec.name, None)


@pytest.mark.parametrize("path", ["/", "/loading", "/setup", "/deep/nested/path"])
def test_every_temporary_route_renders_the_starting_page(temp, path):
    resp = temp.app.test_client().get(path)
    assert resp.status_code == 200
    assert b"BunkerWeb UI is starting..." in resp.data


def test_the_anonymous_theme_script_is_rendered(temp):
    resp = temp.app.test_client().get("/")
    assert resp.status_code == 200
    assert b"Anti-FOUC" in resp.data and b"serverTheme" in resp.data
    assert b'data-authenticated="false"' in resp.data


def test_startup_error_page_renders_without_the_detail(temp):
    temp.ERROR_FILE.write_text("Traceback ... FLASK_SECRET=hunter2")
    resp = temp.app.test_client().get("/")
    assert resp.status_code == 200
    assert b"encountered an error while starting" in resp.data
    assert b"hunter2" not in resp.data
