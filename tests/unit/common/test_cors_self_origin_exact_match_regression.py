"""``CORS_ALLOW_ORIGIN=self`` must match the service's own origin exactly, not as an unanchored regex.

The self origin was built from the server name and matched with an unescaped, unanchored regex, so an origin that merely
starts with it (``https://www.example.com.attacker.example``) or only contains it passed the deny check. This test runs the
real ``cors:access`` with ``CORS_DENY_REQUEST=yes`` and asserts look-alike origins are denied.
"""

import pytest
from _t2_helpers import requires_lua, run_plugin

pytestmark = requires_lua


def access(origin, *, https="no", server_name="www.example.com"):
    return run_plugin(
        "cors",
        f"""
VARIABLES = {{ USE_CORS = "yes", CORS_ALLOW_ORIGIN = "self", CORS_DENY_REQUEST = "yes" }}
local c = ctx({{ server_name = "{server_name}", http_origin = "{origin}", https_configured = "{https}" }})
local r = PLUGIN:new(c):access()
emit("msg", r.msg) emit("status", r.status) emit("metrics", metric_keys())
""",
    )


@pytest.mark.parametrize(
    "origin",
    [
        "http://www.example.com.attacker.example",
        "http://www.example.com:8080",
        "http://www.example.com/",
        "http://sub.www.example.com",
        "http://wwwxexample.com",
        "xhttp://www.example.com",
        "https://www.example.com",
    ],
)
def test_a_look_alike_of_the_self_origin_is_denied(origin):
    out = access(origin)
    assert out["status"] == "403"
    assert out["msg"].endswith("is not allowed, denying access")
    assert out["metrics"] == "counters:failed_cors"


def test_the_exact_self_origin_passes():
    out = access("http://www.example.com")
    assert out["status"] == "nil"
    assert out["msg"] == "standard request"


def test_the_self_origin_follows_https_when_configured_and_does_not_accept_http_then():
    assert access("https://www.example.com", https="yes")["status"] == "nil"
    assert access("http://www.example.com", https="yes")["status"] == "403"


def test_dots_in_the_server_name_are_not_wildcards():
    assert access("http://wwwXexampleYcom")["status"] == "403"
