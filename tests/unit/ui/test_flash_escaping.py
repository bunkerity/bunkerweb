"""Flash messages are HTML-escaped once, in `app.utils.flash()`, before they reach the session.

`flash.html` and `sidebar-notifications.html` render the stored message with `|safe`, and many
messages interpolate request data (`routes/templates.py`: "Template {clone_id} not found." with
`?clone=` straight from the query string) -- a reflected XSS as long as the wrapper stored raw
strings.

The template cannot tell trusted markup from data by itself: Flask-Session 0.8 serializes the
session with msgspec msgpack, which encodes a `Markup` as a plain `str`, so the type is gone by
the next request. The escaping therefore happens at flash time, where `Markup` still means
"intended markup": a plain `str` is escaped, a `Markup` passes through.
"""

import ast
from pathlib import Path

import pytest
from flask import Flask, render_template, request, session
from markupsafe import Markup

from app.utils import flash

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "src" / "ui" / "app" / "templates"
PAYLOAD = "<img src=x onerror=alert(1)>"


def _strip_markup_like_msgpack():
    """What Flask-Session's msgpack round trip does to the queue: every `Markup` becomes `str`."""
    session["_flashes"] = [(category, str(message)) for category, message in session.get("_flashes", [])]
    if "flash_messages" in session:
        session["flash_messages"] = [(str(message), category, when) for message, category, when in session["flash_messages"]]


@pytest.fixture
def client():
    app = Flask(__name__, template_folder=str(TEMPLATES))
    app.secret_key = "test"

    @app.route("/flash")
    def do_flash():
        kind = request.args["kind"]
        if kind == "reflected":
            flash(f"Template {request.args['clone']} not found.", "error")
        elif kind == "link":
            flash(Markup("{} <a class='alert-link' href='/jobs'>{}</a>").format(request.args["clone"], "Jobs"), "error")
        session["flash_messages"] = session.get("flash_messages", [])
        _strip_markup_like_msgpack()
        return ""

    @app.route("/render")
    def render():
        return render_template("flash.html", theme="light", pro_diamond_url="", user_readonly=False, current_endpoint="home")

    return app.test_client()


def _toast_body(client, kind):
    client.get("/flash", query_string={"kind": kind, "clone": PAYLOAD})
    return client.get("/render").get_data(as_text=True)


def test_a_reflected_request_value_renders_escaped(client):
    html = _toast_body(client, "reflected")
    assert PAYLOAD not in html
    assert "Template &lt;img src=x onerror=alert(1)&gt; not found." in html


def test_intended_markup_built_with_markup_format_stays_a_link_and_escapes_its_values(client):
    html = _toast_body(client, "link")
    assert "<a class='alert-link' href='/jobs'>Jobs</a>" in html
    assert PAYLOAD not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html


def test_every_ui_flash_goes_through_the_escaping_wrapper():
    """Flask's own `flash` stores the raw string, which the `|safe` templates then render: only
    `app/utils.py` (the wrapper itself) may import it."""
    offenders = []
    roots = [ROOT / "src" / "ui", *(ROOT / "src" / "common" / "core").glob("*/ui")]
    for root in roots:
        for path in root.rglob("*.py"):
            if path == ROOT / "src" / "ui" / "app" / "utils.py":
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom) and node.module == "flask" and any(alias.name == "flash" for alias in node.names):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert offenders == []


@pytest.mark.parametrize("kind", ["reflected", "link"])
def test_the_session_stores_plain_str_the_msgspec_serializer_accepts(kind):
    """Flask-Session encodes the session with msgspec, which refuses any `str` subclass: a `Markup`
    left in `_flashes` or `flash_messages` raised "Encoding objects of type Markup is unsupported"
    and 500ed every request that flashed (the login MFA reminder first). The wrapper must store `str`."""
    app = Flask(__name__)
    app.secret_key = "test"
    with app.test_request_context("/"):
        session["flash_messages"] = []
        if kind == "link":
            flash(Markup("{} <a href='/jobs'>{}</a>").format(PAYLOAD, "Jobs"), "error")
        else:
            flash(PAYLOAD, "error")
        stored = [message for _, message in session["_flashes"]] + [message for message, _, _ in session["flash_messages"]]
        assert stored and all(type(message) is str for message in stored), [type(message) for message in stored]
