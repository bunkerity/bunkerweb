"""app/models/reverse_proxied.py: the WSGI environ the UI sees behind BunkerWeb."""

import pytest

from app.models.reverse_proxied import ReverseProxied

BASE = {
    "REQUEST_METHOD": "GET",
    "REMOTE_ADDR": "172.18.0.5",
    "wsgi.url_scheme": "http",
    "HTTP_HOST": "ui:7000",
    "SERVER_NAME": "ui",
    "SERVER_PORT": "7000",
    "SCRIPT_NAME": "",
    "PATH_INFO": "/home",
}


def _run(headers=None, **proxy_kwargs):
    seen = {}

    def inner(environ, start_response):
        seen.update(environ)
        return [b""]

    environ = dict(BASE)
    environ.update(headers or {})
    ReverseProxied(inner, **proxy_kwargs)(environ, lambda *a: None)
    return seen


def test_no_forwarded_headers_leaves_the_request_as_is():
    env = _run(x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
    assert (env["REMOTE_ADDR"], env["wsgi.url_scheme"], env["HTTP_HOST"]) == ("172.18.0.5", "http", "ui:7000")
    assert env["ABSOLUTE_URI"] == "http://ui:7000/"
    assert env["SESSION_COOKIE_DOMAIN"] == "ui:7000"


def test_originals_are_kept_aside():
    env = _run({"HTTP_X_FORWARDED_FOR": "9.9.9.9"}, x_for=1)
    assert env["werkzeug.proxy_fix.orig"] == {
        "REMOTE_ADDR": "172.18.0.5",
        "wsgi.url_scheme": "http",
        "HTTP_HOST": "ui:7000",
        "SERVER_NAME": "ui",
        "SERVER_PORT": "7000",
        "SCRIPT_NAME": "",
    }
    assert env["REMOTE_ADDR"] == "9.9.9.9"


def test_forwarded_headers_are_ignored_when_not_trusted():
    env = _run({"HTTP_X_FORWARDED_FOR": "9.9.9.9", "HTTP_X_FORWARDED_PROTO": "https", "HTTP_X_FORWARDED_HOST": "evil.test"}, x_for=0, x_proto=0, x_host=0)
    assert (env["REMOTE_ADDR"], env["wsgi.url_scheme"], env["HTTP_HOST"]) == ("172.18.0.5", "http", "ui:7000")


def test_proto_and_host_rewrite_the_absolute_uri():
    env = _run({"HTTP_X_FORWARDED_PROTO": "https", "HTTP_X_FORWARDED_HOST": "www.example.com"}, x_proto=1, x_host=1)
    assert env["wsgi.url_scheme"] == "https"
    assert env["HTTP_HOST"] == env["SERVER_NAME"] == "www.example.com"
    assert env["ABSOLUTE_URI"] == "https://www.example.com/"
    assert env["SESSION_COOKIE_DOMAIN"] == "www.example.com"


def test_host_with_port_splits_server_name_and_port():
    env = _run({"HTTP_X_FORWARDED_HOST": "www.example.com:8443"}, x_host=1)
    assert (env["SERVER_NAME"], env["SERVER_PORT"], env["HTTP_HOST"]) == ("www.example.com", "8443", "www.example.com:8443")


def test_bare_ipv6_host_is_not_split():
    env = _run({"HTTP_X_FORWARDED_HOST": "[::1]"}, x_host=1)
    assert env["SERVER_NAME"] == "[::1]" and env["SERVER_PORT"] == "7000"


@pytest.mark.parametrize(
    ("host", "expected"),
    [("ui:7000", "ui:8443"), ("ui", "ui:8443"), ("[::1]", "[::1]:8443"), ("[::1]:7000", "[::1]:8443")],
)
def test_forwarded_port_replaces_or_appends(host, expected):
    env = _run({"HTTP_HOST": host, "HTTP_X_FORWARDED_PORT": "8443"}, x_port=1)
    assert env["HTTP_HOST"] == expected and env["SERVER_PORT"] == "8443"


def test_prefix_is_stripped_from_the_path():
    env = _run({"HTTP_X_FORWARDED_PREFIX": "/bw", "PATH_INFO": "/bw/home"}, x_prefix=1)
    assert env["SCRIPT_NAME"] == "/bw" and env["PATH_INFO"] == "/home"
    assert env["ABSOLUTE_URI"] == "http://ui:7000/bw/"
