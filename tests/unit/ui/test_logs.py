"""Logs blueprint: multi-source live-tail stream, path-traversal guard, and the
single-file routes (download / stream) regression. Plus template + asset shape.

The route module (``app/routes/logs.py``) has no ``app.dependencies`` import, so
it loads standalone via importlib — no container-only state to stub (unlike the
web_cache route). The SSE poll loop is bounded by ``STREAM_MAX_SECONDS``; setting
it negative makes the loop break on its first iteration so the generator runs to
completion and can be consumed synchronously.
"""

import importlib.util
import json
from pathlib import Path

import pytest
from flask import Flask

_SRC = Path(__file__).resolve().parents[3] / "src" / "ui"


@pytest.fixture(scope="module")
def logs_module():
    route_path = _SRC / "app" / "routes" / "logs.py"
    spec = importlib.util.spec_from_file_location("logs_route_under_test", route_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def env(logs_module, tmp_path, monkeypatch):
    """Point the route at a tmp log dir, seed two main log files, bound the SSE loop."""
    monkeypatch.setattr(logs_module, "LOGS_PATH", tmp_path)
    monkeypatch.setattr(logs_module, "STREAM_MAX_SECONDS", -1)
    monkeypatch.setattr(logs_module, "_active_streams", 0)
    (tmp_path / "access.log").write_text("[2024-01-01 00:00:01 +0000] GET / 200\n", encoding="utf-8")
    (tmp_path / "error.log").write_text("[2024-01-01 00:00:02 +0000] [error] boom\n", encoding="utf-8")
    app = Flask(__name__)
    app.secret_key = "test"
    return logs_module, app, tmp_path


def _frames(text):
    """Parse the JSON payloads out of an SSE text/event-stream body."""
    out = []
    for line in text.split("\n"):
        if line.startswith("data: "):
            out.append(json.loads(line.removeprefix("data: ")))
    return out


def _consume(response):
    return "".join(response.response)


# --------------------------------------------------------------------------- #
# stream_multi
# --------------------------------------------------------------------------- #
def test_stream_multi_emits_a_refresh_frame_per_source(env):
    module, app, _ = env
    with app.test_request_context("/logs/stream/multi?sources=access.log,error.log"):
        response = module.stream_multi.__wrapped__()
    frames = _frames(_consume(response))

    refreshes = [f for f in frames if f["type"] == "refresh"]
    sources = {f["source"] for f in refreshes}
    assert sources == {"access.log", "error.log"}
    by_source = {f["source"]: f["content"] for f in refreshes}
    assert "GET / 200" in by_source["access.log"]
    assert "boom" in by_source["error.log"]


def test_stream_multi_rejects_path_traversal(env):
    module, app, _ = env
    with app.test_request_context("/logs/stream/multi?sources=../etc/passwd"):
        response = module.stream_multi.__wrapped__()
    assert response.status_code == 404


def test_stream_multi_drops_invalid_keeps_valid(env):
    module, app, _ = env
    with app.test_request_context("/logs/stream/multi?sources=access.log,../etc/passwd,ghost.log"):
        response = module.stream_multi.__wrapped__()
    frames = _frames(_consume(response))
    sources = {f["source"] for f in frames if f["type"] == "refresh"}
    assert sources == {"access.log"}


def test_stream_multi_caps_source_count(env):
    module, app, tmp_path = env
    for i in range(module.MAX_MULTI_SOURCES + 5):
        (tmp_path / f"svc{i:02d}.log").write_text(f"line {i}\n", encoding="utf-8")
    # Build a sources list longer than the cap (main files are globbed + sorted).
    names = ",".join(sorted(p.name for p in tmp_path.glob("*.log")))
    with app.test_request_context(f"/logs/stream/multi?sources={names}"):
        response = module.stream_multi.__wrapped__()
    frames = _frames(_consume(response))
    refreshes = [f for f in frames if f["type"] == "refresh"]
    assert len(refreshes) == module.MAX_MULTI_SOURCES


# --------------------------------------------------------------------------- #
# single-file routes — regression (must stay byte-behaviour identical)
# --------------------------------------------------------------------------- #
def test_download_valid_and_traversal(env):
    module, app, _ = env
    with app.test_request_context("/logs/download?file=access.log"):
        ok = module.download_log.__wrapped__()
    assert ok.status_code == 200
    assert "attachment" in ok.headers.get("Content-Disposition", "")

    with app.test_request_context("/logs/download?file=../etc/passwd"):
        bad = module.download_log.__wrapped__()
    assert bad.status_code == 404


def test_single_file_stream_still_refreshes(env):
    module, app, _ = env
    with app.test_request_context("/logs/stream?file=access.log"):
        response = module.stream_logs.__wrapped__()
    frames = _frames(_consume(response))
    refresh = [f for f in frames if f["type"] == "refresh"]
    assert len(refresh) == 1
    assert "source" not in refresh[0]  # single-file frames are un-namespaced
    assert "GET / 200" in refresh[0]["content"]


# --------------------------------------------------------------------------- #
# template + assets shape
# --------------------------------------------------------------------------- #
def test_template_has_live_dashboard_and_keeps_ace_and_pagination():
    source = (_SRC / "app" / "templates" / "logs.html").read_text(encoding="utf-8")
    # Live dashboard landing.
    assert 'id="log-stream"' in source
    assert "logs-live.js" in source
    assert "logs.level_all" in source
    assert "logs.level_errors_only" in source
    assert "logs.level_security_only" in source
    assert "logs.all_sources" in source
    # Preserved ACE viewer + pagination (must not be deleted to match the mockup).
    assert "code_editor(" in source
    assert "pages-dropdown-menu" in source
    assert "js/pages/logs.js" in source


def test_css_ships_terminal_stream_tokens():
    css = (_SRC / "app" / "static" / "css" / "pages" / "logs.css").read_text(encoding="utf-8")
    assert ".log-stream" in css
    assert ".lg-err" in css
    assert ".log-stream.fullview" in css
    assert "prefers-reduced-motion" in css


def test_classifier_extraction_preserves_security_guard():
    js_dir = _SRC / "app" / "static" / "js" / "pages"
    classify = (js_dir / "logs-classify.js").read_text(encoding="utf-8")
    # The pre-quote prefix guard is the security-sensitive core — an injected
    # "[ERROR]" in a quoted URL/UA must not classify the line as an error.
    assert "const q = line.indexOf('\"');" in classify
    assert "export function levelOf" in classify
    # Both consumers import the shared classifier rather than re-implementing it.
    logs_js = (js_dir / "logs.js").read_text(encoding="utf-8")
    live_js = (js_dir / "logs-live.js").read_text(encoding="utf-8")
    assert './logs-classify.js"' in logs_js
    assert './logs-classify.js"' in live_js
    # The old inline copy must be gone from logs.js (single source of truth).
    assert "function levelOf(line)" not in logs_js
