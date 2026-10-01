"""Static asset URLs carry a content fingerprint, and the cache headers follow from it.

Why this is a defect, stated without reference to any current output: `url_for('static', ...)`
used to build a bare `/js/pages/templates.js`, served with `max-age=86400`. A browser that loaded
the page before an upgrade kept running the previous release's page script against the new
templates for up to a day -- a form handler missing, the form falling back to a native post that
the server refuses. Nothing short of a URL change can reach a cached copy, so:

  * every URL built for the `static` endpoint carries `v=<content fingerprint>`, which changes the
    moment the file does (an upgrade, or a dev edit);
  * a request carrying the *current* fingerprint may be cached for a year -- its URL changes with
    its content;
  * anything else (an ES-module child import, a URL built in JS, an old fingerprint) is served
    `no-cache`: the browser keeps it but revalidates, so it can never run stale.
"""

import re
from pathlib import Path

import pytest
from flask import Flask, url_for

REPO = Path(__file__).resolve().parents[3]
UI = REPO / "src" / "ui"


@pytest.fixture
def app(tmp_path):
    from app.static_assets import version_static_urls

    (tmp_path / "js").mkdir()
    (tmp_path / "js" / "page.js").write_text("console.log(1);", encoding="utf-8")
    (tmp_path / "img" / "flags").mkdir(parents=True)
    (tmp_path / "img" / "flags" / "fr.svg").write_text("<svg/>", encoding="utf-8")
    app = Flask(__name__, static_url_path="/", static_folder=str(tmp_path))
    version_static_urls(app)
    return app


def _url(app, filename):
    with app.test_request_context("/"):
        return url_for("static", filename=filename)


def test_static_url_carries_a_fingerprint_that_follows_the_content(app):
    before = _url(app, "js/page.js")
    assert re.fullmatch(r"/js/page\.js\?v=[0-9a-f]{16}", before), before

    Path(app.static_folder, "js", "page.js").write_text("console.log(2); // changed", encoding="utf-8")
    after = _url(app, "js/page.js")
    assert after != before, "an edited file kept its URL, so a cached copy would still be served"


def test_directory_base_url_stays_bare(app):
    """`bans.html` builds `url_for('static', filename='img/flags')` and JS appends `/<code>.svg`:
    a query on the base would put the file name inside the query string."""
    assert _url(app, "img/flags") == "/img/flags"


def test_fingerprint_never_reads_outside_the_static_folder(app, tmp_path):
    """On the response side the file name is the client's: it must not steer a read elsewhere."""
    from app.static_assets import static_fingerprint

    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    assert static_fingerprint(app.static_folder, "../outside.txt") is None
    assert static_fingerprint(app.static_folder, str(outside)) is None


def test_an_explicit_v_is_left_alone(app):
    with app.test_request_context("/"):
        assert url_for("static", filename="js/page.js", v="pinned") == "/js/page.js?v=pinned"


def test_current_fingerprint_is_cached_long_anything_else_revalidates(app):
    client = app.test_client()
    versioned = _url(app, "js/page.js")

    fresh = client.get(versioned)
    assert fresh.status_code == 200
    assert fresh.headers["Cache-Control"] == "public, max-age=31536000, immutable"

    for url in ("/js/page.js", "/js/page.js?v=0000000000000000", "/img/flags/fr.svg"):
        response = client.get(url)
        assert response.status_code == 200, url
        assert response.headers["Cache-Control"] == "no-cache", url


def test_unversioned_revalidation_answers_304(app):
    """`no-cache` is only cheap if revalidation works: an unchanged file must come back 304."""
    client = app.test_client()
    first = client.get("/js/page.js")
    etag = first.headers["ETag"]
    again = client.get("/js/page.js", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.headers["Cache-Control"] == "no-cache"


@pytest.mark.parametrize("entry_point", ["main.py", "temp.py"])
def test_both_ui_apps_install_the_versioning(entry_point):
    """`temp.py` serves the starting page while the UI boots -- right after an upgrade, which is
    exactly when a stale script is most likely."""
    source = (UI / entry_point).read_text(encoding="utf-8")
    assert re.search(r"^version_static_urls\(app\)$", source, re.M), f"{entry_point} never calls version_static_urls(app)"
