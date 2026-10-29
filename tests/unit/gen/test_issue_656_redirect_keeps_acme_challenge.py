"""`REDIRECT_TO` must not swallow the ACME challenge, and the global CRS must always get a method list.

A bare `return 301 …;` in the server block runs in the rewrite phase, before any `location`, so a service with
`REDIRECT_TO` could never answer `/.well-known/acme-challenge/` and its certificate renewal failed; the redirect now
lives in `location /`, which the longer challenge prefix beats. Separately, with `MULTISITE=yes` and no service the
per-service union of `ALLOWED_METHODS` is empty and the global CRS file got `tx.allowed_methods=` (nothing allowed);
it falls back to the global `ALLOWED_METHODS`. Rendered through the real Configurator and Templator.
Refs #656, #3761.
"""

import re

import pytest

from _t4_helpers import full_renderer  # type: ignore

REDIRECT = {"SERVER_NAME": "www.example.com", "REDIRECT_TO": "https://other.example.com", "AUTO_LETS_ENCRYPT": "yes"}


@pytest.fixture(scope="module")
def render():
    with full_renderer() as renderer:
        yield renderer


def _top_level_returns(text):
    """The ``return`` statements that sit directly in the server block, outside every ``location``."""
    depth = 0
    found = []
    for line in text.splitlines():
        code = line.split("#")[0]
        if depth == 0 and code.strip().startswith("return "):
            found.append(code.strip())
        depth += code.count("{") - code.count("}")
    return found


@pytest.mark.parametrize(
    "request_uri,expected", [("no", "return 301 https://other.example.com;"), ("yes", "return 301 https://other.example.com$request_uri;")]
)
def test_the_redirect_lives_in_location_root(render, request_uri, expected):
    out = render(**REDIRECT, REDIRECT_TO_REQUEST_URI=request_uri)["server-http/redirect.conf"]

    assert re.search(r'^location "/" \{\n\t' + re.escape(expected) + r"\n\}", out, re.M), out
    assert _top_level_returns(out) == []


def test_no_server_level_return_precedes_the_acme_challenge(render):
    files = render(**REDIRECT)

    assert "acme-challenge" in files["server-http/lets-encrypt.conf"]
    assert {path: _top_level_returns(text) for path, text in files.items() if path.startswith("server-http/") and _top_level_returns(text)} == {}


def test_without_redirect_to_nothing_is_rendered(render):
    assert render(SERVER_NAME="www.example.com")["server-http/redirect.conf"].strip() == ""


def _allowed_methods(files):
    return re.findall(r"tx\.allowed_methods=([^'\"]*)", files["http/modsecurity-rules-global-crs.conf.modsec"])


def test_global_crs_without_any_service_falls_back_to_the_global_allowed_methods(render):
    files = render(MULTISITE="yes", SERVER_NAME="", USE_MODSECURITY="yes", USE_MODSECURITY_GLOBAL_CRS="yes", ALLOWED_METHODS="GET|PUT")

    assert _allowed_methods(files) == ["GET PUT"]


def test_global_crs_with_services_uses_the_union_of_their_methods(render):
    files = render(
        MULTISITE="yes",
        SERVER_NAME="a.example.com b.example.com",
        USE_MODSECURITY="yes",
        USE_MODSECURITY_GLOBAL_CRS="yes",
        **{"a.example.com_ALLOWED_METHODS": "GET|POST", "b.example.com_ALLOWED_METHODS": "POST|PUT"},
    )

    assert _allowed_methods(files) == ["GET POST PUT"]
