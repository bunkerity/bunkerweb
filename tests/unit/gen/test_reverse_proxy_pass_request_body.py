"""`REVERSE_PROXY_PASS_REQUEST_BODY=no` also clears the `Content-Length` sent to the upstream.

`proxy_pass_request_body off;` drops the body but, on its own, keeps the client's `Content-Length`: the
upstream waits for a body that never comes, and on a kept-alive upstream connection the next request is
read as that body. Rendered through the real Configurator and Templator.
"""

import re

import pytest

from _t4_helpers import full_renderer  # type: ignore

BASE = {"SERVER_NAME": "www.example.com", "USE_REVERSE_PROXY": "yes", "REVERSE_PROXY_HOST": "http://backend:8080"}
RESET = 'proxy_set_header Content-Length "";'


@pytest.fixture(scope="module")
def render():
    with full_renderer() as renderer:
        yield lambda **variables: renderer(**(BASE | variables))["server-http/reverse-proxy.conf"]


def _locations(text):
    return {match.group(1): match.group(2) for match in re.finditer(r"^(location [^\n{]*?) \{\n(.*?)^\}", text, re.S | re.M)}


def test_body_off_resets_the_content_length(render):
    out = render(REVERSE_PROXY_PASS_REQUEST_BODY="no")
    assert "proxy_pass_request_body off;" in out
    assert RESET in out


@pytest.mark.parametrize("variables", [{}, {"REVERSE_PROXY_PASS_REQUEST_BODY": "yes"}])
def test_body_on_keeps_the_content_length(render, variables):
    out = render(**variables)
    assert "proxy_pass_request_body" not in out
    assert "Content-Length" not in out


def test_only_the_location_with_the_body_off_resets_it(render):
    out = render(
        REVERSE_PROXY_URL="/",
        REVERSE_PROXY_HOST_1="http://b1:80",
        REVERSE_PROXY_URL_1="/nobody",
        REVERSE_PROXY_PASS_REQUEST_BODY_1="no",
        REVERSE_PROXY_HOST_2="http://b2:80",
        REVERSE_PROXY_URL_2="/body",
    )
    blocks = _locations(out)
    assert RESET in blocks['location "/nobody"'] and "proxy_pass_request_body off;" in blocks['location "/nobody"']
    for name in ('location "/"', 'location "/body"'):
        assert "Content-Length" not in blocks[name] and "proxy_pass_request_body" not in blocks[name]


def test_a_custom_content_length_header_wins_over_the_reset(render):
    out = render(REVERSE_PROXY_PASS_REQUEST_BODY="no", REVERSE_PROXY_HEADERS="Content-Length 42")
    assert "proxy_pass_request_body off;" in out
    assert re.findall(r"proxy_set_header Content-Length [^;]*;", out) == ["proxy_set_header Content-Length 42;"]
