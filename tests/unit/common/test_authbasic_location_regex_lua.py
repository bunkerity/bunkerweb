"""UB1-1: location matching must neither bypass authentication nor protect unrelated paths.

Execute the real plugin with the request harness. The local regex stub accepts only the
shared Lua/PCRE pattern used here and honours ``i``; this checks option forwarding and
authentication decisions, not OpenResty's PCRE engine.
"""

import pytest
import _lua_request_helpers as lua

pytestmark = lua.requires_lua


@pytest.fixture
def location_regex(monkeypatch):
    stub = r"""
REGEX_CALLS = 0
package.loaded["bunkerweb.utils"].regex_match = function(subject, pattern, options, setting)
    assert(pattern == "^/admin/.+$", "unexpected regex in location test")
    assert(options == nil or options == "i", "unexpected regex options")
    assert(setting == "AUTH_BASIC_LOCATION", "unexpected regex setting")
    REGEX_CALLS = REGEX_CALLS + 1
    emit("regex_options", options)
    if options == "i" then subject = subject:lower() end
    return subject:match(pattern) and { subject } or nil
end
"""
    anchor = 'PLUGIN = dofile("__MODULE__")'
    assert lua.HARNESS.count(anchor) == 1
    monkeypatch.setattr(lua, "HARNESS", lua.HARNESS.replace(anchor, stub + anchor))


@pytest.mark.parametrize(
    ("location", "uri", "protected", "options"),
    [
        pytest.param("~ ^/admin/.+$", "/admin/page", True, "nil", id="sensitive-match"),
        pytest.param("~ ^/admin/.+$", "/ADMIN/page", False, "nil", id="sensitive-case-mismatch"),
        pytest.param("~ ^/admin/.+$", "/public", False, "nil", id="sensitive-unrelated"),
        pytest.param("~ ^/admin/.+$", "/admin/", False, "nil", id="sensitive-empty-suffix"),
        pytest.param("~* ^/admin/.+$", "/admin/page", True, "i", id="insensitive-match"),
        pytest.param("~* ^/admin/.+$", "/ADMIN/page", True, "i", id="insensitive-uppercase"),
        pytest.param("~* ^/admin/.+$", "/public", False, "i", id="insensitive-unrelated"),
        pytest.param("~* ^/admin/.+$", "/admin/", False, "i", id="insensitive-empty-suffix"),
        pytest.param("/admin", "/admin/page", True, None, id="prefix-match"),
        pytest.param("/admin", "/ADMIN/page", False, None, id="prefix-case-mismatch"),
        pytest.param("/admin", "/public", False, None, id="prefix-unrelated"),
    ],
)
def test_only_matching_locations_challenge(location_regex, location, uri, protected, options):
    out = lua.run(
        "authbasic",
        f"""
VARIABLES = {{ USE_AUTH_BASIC = "yes" }}
MULTI_VARS = {{ global = {{ USE_AUTH_BASIC = "yes", AUTH_BASIC_LOCATION = "{location}",
    AUTH_BASIC_TEXT = "Private", AUTH_BASIC_USER = "alice", AUTH_BASIC_PASSWORD = "secret" }} }}
local init = PLUGIN:new(ctx())
assert(init:init().ret)
local result = PLUGIN:new(ctx({{ uri = "{uri}" }})):access()
emit("ret", result.ret)
emit("status", result.status)
emit("msg", result.msg)
emit("challenge", ngx.header["WWW-Authenticate"])
emit("regex_calls", REGEX_CALLS)
""",
    )
    assert out["ret"] == "true"
    if protected:
        assert out["status"] == "401"
        assert out["msg"] == "missing Authorization header"
        assert out["challenge"] == 'Basic realm="Private", charset="UTF-8"'
    else:
        assert out["status"] == "nil"
        assert out["msg"] == "URI outside protected scope"
        assert out["challenge"] == "nil"
    assert out["regex_calls"] == ("0" if options is None else "1")
    assert out.get("regex_options") == options
