"""The reverse-proxy locations are rendered in the order, form and mode the settings ask for.

Three things the `reverse-proxy.conf` template once got wrong: a global `REVERSE_PROXY_HTTP_VERSION=2` locked the
web UI out, the locations followed the order of the settings in the environment instead of their numeric suffix,
and an anchored `REVERSE_PROXY_URL` (`^/api/.*$`) was emitted as a prefix location that never matches. Rendered
through the real Configurator and Templator. Refs #3550, #1930, #3768.
"""

import re

import pytest

from _t4_helpers import full_renderer  # type: ignore

BASE = {"SERVER_NAME": "www.example.com", "USE_REVERSE_PROXY": "yes", "REVERSE_PROXY_HOST": "http://backend:8080"}


@pytest.fixture(scope="module")
def render():
    with full_renderer() as renderer:
        yield lambda **variables: renderer(**(BASE | variables))["server-http/reverse-proxy.conf"]


def _locations(text):
    """``{location line: its block}`` for every top-level ``location`` of the rendered file."""
    return {match.group(1): match.group(2) for match in re.finditer(r"^(location [^\n{]*?) \{\n(.*?)^\}", text, re.S | re.M)}


def test_global_http2_does_not_reach_the_proxy_when_the_ui_is_enabled(render):
    out = render(REVERSE_PROXY_HTTP_VERSION="2", USE_UI="yes")
    assert "proxy_http_version 2" not in out


def test_global_http2_keeps_the_keepalive_connection_on_http_1_1_when_the_ui_is_enabled(render):
    out = render(REVERSE_PROXY_HTTP_VERSION="2", REVERSE_PROXY_KEEPALIVE="yes", USE_UI="yes")
    assert "proxy_http_version 1.1;" in out
    assert "proxy_http_version 2" not in out


def test_http2_is_still_applied_when_the_ui_is_not_enabled(render):
    out = render(REVERSE_PROXY_HTTP_VERSION="2", USE_UI="no")
    assert "proxy_http_version 2;" in out


def test_locations_follow_the_numeric_suffix_not_the_order_of_the_settings(render):
    out = render(
        REVERSE_PROXY_HOST_10="http://b10:80",
        REVERSE_PROXY_URL_10="/ten",
        REVERSE_PROXY_HOST_2="http://b2:80",
        REVERSE_PROXY_URL_2="/two",
        REVERSE_PROXY_HOST_1="http://b1:80",
        REVERSE_PROXY_URL_1="/one",
        REVERSE_PROXY_URL="/zero",
    )
    assert list(_locations(out)) == ['location "/zero"', 'location "/one"', 'location "/two"', 'location "/ten"']
    assert 'set $backend10 "http://b10:80";' in out


@pytest.mark.parametrize("url", ["^/api/.*$", "/files/.*\\.png$"])
def test_an_anchored_url_is_rendered_as_a_regex_location(render, url):
    out = render(REVERSE_PROXY_URL=url)
    quoted = url.replace("\\", "\\\\")  # the template writes a quoted nginx string
    blocks = _locations(out)
    assert f'location ~ "{quoted}"' in blocks, list(blocks)
    block = blocks[f'location ~ "{quoted}"']
    assert "X-Forwarded-Prefix" not in block, "a regex location has no fixed prefix to forward"


def test_a_plain_url_stays_a_prefix_location(render):
    out = render(REVERSE_PROXY_URL="/api/")
    assert 'X-Forwarded-Prefix "/api/"' in _locations(out)['location "/api/"']
