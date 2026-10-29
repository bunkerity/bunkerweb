"""The default server's landing page must answer on ``/`` only.

``page.conf`` declared ``location / {`` -- a prefix match -- so the default server answered 200 with
the landing page for every path and every method (``/.env``, ``/.git/config``, a ``POST``, a
``DELETE``), which scanners read as "the file exists" and which hid real 404s. It is now
``location = /``: the page is served on the root and the other paths fall through to the normal
not-found handling.

Refs: #3992.
"""

import re

import pytest

from _t4_helpers import full_renderer


@pytest.fixture(scope="module")
def render():
    with full_renderer() as render:
        yield render


def locations(text):
    """Every ``location`` header of the rendered file, whitespace normalised."""
    return [re.sub(r"\s+", " ", match.strip()) for match in re.findall(r"^\s*(location\s[^{]*?)\{", text, re.M)]


@pytest.mark.parametrize("multisite", ["yes", "no"])
def test_the_landing_page_is_an_exact_match_on_the_root(render, multisite):
    tree = render(MULTISITE=multisite, SERVER_NAME="app.example.com")
    assert locations(tree["default-server-http/page.conf"]) == ["location = /"]


def test_no_prefix_location_catches_every_other_path(render):
    page = render(MULTISITE="yes", SERVER_NAME="app.example.com")["default-server-http/page.conf"]
    assert not re.search(r"^\s*location\s+/\s*\{", page, re.M)


def test_a_disabled_default_server_still_scopes_to_the_root(render):
    page = render(MULTISITE="yes", SERVER_NAME="app.example.com", DISABLE_DEFAULT_SERVER="yes", DENY_HTTP_STATUS="403")["default-server-http/page.conf"]
    assert locations(page) == ["location = /"]
    assert "return 403;" in page
