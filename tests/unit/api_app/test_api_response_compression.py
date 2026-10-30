"""The API gzips JSON above 1 KiB and leaves what must not be touched alone.

`create_app()` is not called: it opens the database in its lifespan and wires auth. What matters
here is the middleware `main.py` really adds, so it is lifted by AST and mounted on a small FastAPI
app next to the response kinds the API produces: JSON, the gzip'd plugin page (`/plugins/{id}/page`),
the octet-stream cache download, and a server-sent-event stream (none exists today; the test pins
that one added later is not buffered by the compressor).

Run with:

    BW_API_APP_LANE=1 .venv-unit/bin/python -m pytest tests/unit/api_app
"""

import ast
from gzip import compress as gzip_compress, decompress as gunzip
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.testclient import TestClient

MAIN = Path(__file__).resolve().parents[3] / "src" / "api" / "app" / "main.py"

ROWS = [{"name": f"service-{i}", "enabled": True} for i in range(120)]
ALREADY_GZIPPED = gzip_compress(b"plugin page " * 400)


def _middleware_calls():
    """The `app.add_middleware(GZipMiddleware, ...)` statements in main.py, and nothing else."""
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    return [node for node in ast.walk(tree) if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and "GZipMiddleware" in ast.unparse(node.value)]


@pytest.fixture
def client():
    from starlette.middleware.gzip import GZipMiddleware

    calls = _middleware_calls()
    assert calls, "main.py does not add GZipMiddleware: API replies are never compressed"

    app = FastAPI()
    exec(compile("\n".join(ast.unparse(c) for c in calls), str(MAIN), "exec"), {"app": app, "GZipMiddleware": GZipMiddleware})  # noqa: S102

    @app.get("/rows")
    def rows():
        return JSONResponse(ROWS)

    @app.get("/small")
    def small():
        return JSONResponse({"status": "success"})

    @app.get("/plugin-page")
    def plugin_page():
        return Response(ALREADY_GZIPPED, media_type="application/gzip")

    @app.get("/cache-download")
    def cache_download():
        return Response(b"x" * 4096, media_type="application/octet-stream", headers={"Content-Disposition": 'attachment; filename="f.bin"'})

    @app.get("/events")
    def events():
        def gen():
            for i in range(3):
                yield f"data: {i}\n\n" * 100

        return StreamingResponse(gen(), media_type="text/event-stream")

    return TestClient(app)


def _raw(client, path, **headers):
    """The response as sent, with the transport's own gzip decoding turned off."""
    with client.stream("GET", path, headers=headers) as r:
        r.read()
        return r


def test_json_above_one_kib_is_gzipped(client):
    r = client.get("/rows", headers={"Accept-Encoding": "gzip"})
    assert r.headers["Content-Encoding"] == "gzip"
    assert "Accept-Encoding" in r.headers["Vary"]
    assert r.json() == ROWS


def test_json_below_one_kib_is_not(client):
    r = client.get("/small", headers={"Accept-Encoding": "gzip"})
    assert "Content-Encoding" not in r.headers


def test_no_gzip_without_the_request_header(client):
    r = client.get("/rows", headers={"Accept-Encoding": "identity"})
    assert "Content-Encoding" not in r.headers
    assert r.json() == ROWS


def test_gzipped_plugin_page_is_not_gzipped_twice(client):
    r = _raw(client, "/plugin-page", **{"Accept-Encoding": "gzip"})
    assert "Content-Encoding" not in r.headers
    assert gunzip(r.content).startswith(b"plugin page")


def test_octet_stream_download_keeps_its_attachment_header(client):
    r = client.get("/cache-download", headers={"Accept-Encoding": "gzip"})
    assert r.headers["Content-Disposition"] == 'attachment; filename="f.bin"'
    assert r.content == b"x" * 4096


def test_event_stream_is_not_compressed(client):
    r = _raw(client, "/events", **{"Accept-Encoding": "gzip"})
    assert "Content-Encoding" not in r.headers
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.text.startswith("data: 0")
