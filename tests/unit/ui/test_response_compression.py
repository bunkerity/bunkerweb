"""The Web UI compresses static assets and JSON, never HTML.

Dev compresses every text asset, and the whole 1.7 UI ships uncompressed unless an operator
turns on `USE_GZIP`/`USE_BROTLI` in front of it (memory `1-7-ui-perf-lot-d`: /services 1089 KB,
core.css 532 KB). The one thing that must NOT be compressed is HTML: each page carries a stable
CSRF secret and reflects query values into the same response, which is the BREACH precondition
(memory `compression-default-breach`).

This runs the Compress block that `main.py` really ships. Importing main.py boots the whole UI, so
the block is lifted by AST, like `test_security_headers_emitted.py` lifts `set_security_headers`:
the config under test is the shipped one, not a copy. An empty lift fails loudly instead of testing
a default `Flask-Compress`, whose mimetype list includes `text/html`.
"""

from ast import ClassDef, FunctionDef, parse, unparse
from gzip import decompress as gunzip
from pathlib import Path

import pytest

pytest.importorskip("flask_compress")
brotli = pytest.importorskip("brotli")

from flask import Flask, jsonify, url_for  # noqa: E402

MAIN = Path(__file__).resolve().parents[3] / "src" / "ui" / "main.py"

CSS = "body { color: #123456; margin: 0 auto; }\n" * 80  # ~3.3 KiB, compressible
HTML = "<html><body><input type='hidden' name='csrf_token' value='secret'>" + "<p>row</p>" * 400 + "</body></html>"


def _compress_block():
    """The module-level statements of main.py that wire Flask-Compress: import, config, call."""
    tree = parse(MAIN.read_text(encoding="utf-8"))
    return [n for n in tree.body if "compress" in unparse(n).lower() and not isinstance(n, (FunctionDef, ClassDef))]


@pytest.fixture
def client(tmp_path):
    from app.static_assets import version_static_urls

    (tmp_path / "css").mkdir()
    (tmp_path / "css" / "core.css").write_text(CSS, encoding="utf-8")
    (tmp_path / "css" / "tiny.css").write_text("a{}", encoding="utf-8")

    app = Flask(__name__, static_url_path="/", static_folder=str(tmp_path))
    version_static_urls(app)

    block = _compress_block()
    assert block, "main.py has no Flask-Compress block: nothing compresses the UI's static assets or JSON"
    exec(compile("\n".join(unparse(n) for n in block), str(MAIN), "exec"), {"app": app})  # noqa: S102

    @app.route("/rows.json")
    def rows():
        return jsonify([{"name": f"service-{i}", "enabled": True} for i in range(120)])

    @app.route("/small.json")
    def small():
        return jsonify({"ok": True})

    @app.route("/page")
    def page():
        return HTML

    with app.test_request_context("/"):
        app.config["TEST_FINGERPRINTED_CSS"] = url_for("static", filename="css/core.css")
    return app.test_client(), app


def _get(client, path, accept):
    return client.get(path, headers={"Accept-Encoding": accept})


def test_css_is_brotli_when_accepted(client):
    c, _ = client
    r = _get(c, "/css/core.css", "br, gzip")
    assert r.headers.get("Content-Encoding") == "br"
    assert brotli.decompress(r.data).decode() == CSS
    assert "Accept-Encoding" in r.headers.get("Vary", "")


def test_css_is_gzip_when_only_gzip_is_accepted(client):
    c, _ = client
    r = _get(c, "/css/core.css", "gzip")
    assert r.headers.get("Content-Encoding") == "gzip"
    assert gunzip(r.data).decode() == CSS
    assert "Accept-Encoding" in r.headers.get("Vary", "")


def test_json_above_one_kib_is_compressed(client):
    c, _ = client
    for accept, encoding in (("br, gzip", "br"), ("gzip", "gzip")):
        r = _get(c, "/rows.json", accept)
        assert r.headers.get("Content-Encoding") == encoding, accept
        assert "Accept-Encoding" in r.headers.get("Vary", "")
    assert len(_get(c, "/rows.json", "br").data) < len(c.get("/rows.json").data)


def test_small_responses_are_left_alone(client):
    c, _ = client
    assert "Content-Encoding" not in _get(c, "/small.json", "br, gzip").headers
    assert "Content-Encoding" not in _get(c, "/css/tiny.css", "br, gzip").headers


def test_no_encoding_without_the_request_header(client):
    c, _ = client
    r = c.get("/css/core.css", headers={"Accept-Encoding": "identity"})
    assert "Content-Encoding" not in r.headers
    assert r.data.decode() == CSS


@pytest.mark.parametrize("accept", ["br, gzip", "gzip", "br"])
def test_html_is_never_compressed_even_when_large(client, accept):
    """BREACH: a stable CSRF secret plus reflected input in the same response."""
    c, _ = client
    r = _get(c, "/page", accept)
    assert len(HTML) > 1024
    assert "Content-Encoding" not in r.headers
    assert r.data.decode() == HTML


def test_fingerprinted_url_keeps_its_immutable_header_and_is_still_compressed(client):
    c, app = client
    url = app.config["TEST_FINGERPRINTED_CSS"]
    assert "?v=" in url
    r = _get(c, url, "br, gzip")
    assert r.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert r.headers.get("Content-Encoding") == "br"
    assert brotli.decompress(r.data).decode() == CSS


def test_unfingerprinted_url_is_still_revalidated(client):
    c, _ = client
    assert _get(c, "/css/core.css", "br").headers["Cache-Control"] == "no-cache"
