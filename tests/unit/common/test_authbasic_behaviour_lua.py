"""Behaviour of ``authbasic.lua``: what a client gets for missing, wrong and right credentials.

Runs the real plugin under plain Lua (see ``_lua_request_helpers``). The password KDF is a
deterministic fake, so the tests prove the plugin's own decisions (scope, header parsing, which
failure is reported, challenge header, what is stored), not scrypt.
"""

import pytest
from _lua_request_helpers import requires_lua, run

pytestmark = requires_lua

# What init() stores for one global user, reused by the request-path tests.
SCOPE = r"""
VARIABLES = { USE_AUTH_BASIC = "yes" }
MULTI_VARS = { global = { USE_AUTH_BASIC = "yes", AUTH_BASIC_LOCATION = "%s", AUTH_BASIC_TEXT = "%s",
                          AUTH_BASIC_USER = "alice", AUTH_BASIC_PASSWORD = "secret" } }
local init = PLUGIN:new(ctx())
init:init()
"""


def request(uri="/", header=None, location="sitewide", realm="", extra=""):
    auth = f"HEADERS = {{ authorization = {header} }}" if header else "HEADERS = {}"
    return run(
        "authbasic",
        SCOPE % (location, realm) + extra + f"""
{auth}
local p = PLUGIN:new(ctx({{ uri = "{uri}" }}))
local r = p:access()
emit("msg", r.msg) emit("status", r.status) emit("ret", r.ret)
emit("challenge", ngx.header["WWW-Authenticate"]) emit("metrics", metric_keys())
""",
    )


class TestInit:
    def test_stores_a_hashed_credential_never_the_plain_password(self):
        out = run(
            "authbasic",
            SCOPE % ("sitewide", "") + r"""
local entry = STORE["plugin_authbasic_configs"].global.credentials.alice
emit("type", type(entry)) emit("algo", entry.algorithm) emit("has_hash", entry.hash ~= nil and entry.salt ~= nil)
emit("plain_stored", entry == "secret" or entry.password ~= nil)
""",
        )
        assert out["type"] == "table"
        assert out["algo"] == "scrypt"
        assert out["has_hash"] == "true"
        assert out["plain_stored"] == "false"

    def test_scope_without_credentials_is_skipped_with_a_warning(self):
        out = run(
            "authbasic",
            r"""
MULTI_VARS = { global = { USE_AUTH_BASIC = "yes", AUTH_BASIC_USER = "alice", AUTH_BASIC_PASSWORD = "" } }
local r = PLUGIN:new(ctx()):init()
emit("msg", r.msg) emit("scopes", next(STORE["plugin_authbasic_configs"]) and "some" or "none") emit("log", LOGS[1])
""",
        )
        assert out["msg"] == "no auth basic scope enabled"
        assert out["scopes"] == "none"
        assert out["log"].startswith("WARN: no credentials configured for scope global")


class TestRequest:
    def test_disabled_service_is_not_challenged(self):
        out = run(
            "authbasic",
            r"""
VARIABLES = { USE_AUTH_BASIC = "no" }
local r = PLUGIN:new(ctx()):access()
emit("msg", r.msg) emit("status", r.status)
""",
        )
        assert out["msg"] == "auth basic disabled"
        assert out["status"] == "nil"

    def test_missing_header_is_401_with_the_realm_challenge(self):
        out = request(realm="Staff only")
        assert out["status"] == "401"
        assert out["msg"] == "missing Authorization header"
        assert out["challenge"] == 'Basic realm="Staff only", charset="UTF-8"'
        assert out["metrics"] == "counters:failed_authbasic,tables:authentications"

    def test_default_realm_when_none_configured(self):
        assert request()["challenge"] == 'Basic realm="Restricted area", charset="UTF-8"'

    @pytest.mark.parametrize("wrong", ["nope", "secreX"])  # shorter, and same length as "secret"
    def test_wrong_password_is_rejected_and_names_the_user(self, wrong):
        out = request(header=f'basic_auth("alice", "{wrong}")')
        assert out["status"] == "401"
        assert out["msg"] == "invalid password for user alice"

    def test_right_password_passes_without_a_status(self):
        out = request(header='basic_auth("alice", "secret")')
        assert out["status"] == "nil"
        assert out["msg"] == "authenticated user alice"
        assert out["challenge"] == "nil"
        assert out["metrics"] == "counters:passed_authbasic,counters:passed_user_alice,tables:authentications"

    @pytest.mark.parametrize(
        ("header", "message"),
        [
            ('basic_auth("bob", "secret")', "unknown user bob"),
            ('"Bearer abc"', "invalid Authorization scheme"),
            ('"Basic " .. ngx.encode_base64("nocolon")', "malformed credential"),
        ],
    )
    def test_other_credential_failures_are_401_with_their_own_reason(self, header, message):
        out = request(header=header)
        assert out["status"] == "401"
        assert out["msg"] == message

    def test_password_may_contain_a_colon(self):
        # Only the first ':' splits user from password.
        out = request(
            header='basic_auth("alice", "se:cret")',
            extra='MULTI_VARS.global.AUTH_BASIC_PASSWORD = "se:cret"\nlocal init2 = PLUGIN:new(ctx())\ninit2:init()\n',
        )
        assert out["msg"] == "authenticated user alice"


class TestScope:
    @pytest.mark.parametrize(
        ("location", "uri", "protected"),
        [
            ("sitewide", "/anything", True),
            ("=/admin", "/admin", True),
            ("=/admin", "/admin/x", False),
            ("^~ /api", "/api/v1", True),
            ("^~ /api", "/other", False),
            ("/api", "/api", True),
        ],
    )
    def test_only_the_configured_location_is_challenged(self, location, uri, protected):
        out = request(uri=uri, location=location)
        if protected:
            assert out["status"] == "401"
        else:
            assert out["status"] == "nil"
            assert out["msg"] == "URI outside protected scope"


def test_server_scope_overrides_the_global_one():
    out = run(
        "authbasic",
        r"""
VARIABLES = { USE_AUTH_BASIC = "yes" }
local function conf(realm) return { realm = realm, matcher = { kind = "sitewide" }, credentials = { alice = "secret" } } end
STORE["plugin_authbasic_configs"] = { global = conf("Global"), ["www.example.com"] = conf("Server") }
HEADERS = {}
PLUGIN:new(ctx()):access()
emit("challenge", ngx.header["WWW-Authenticate"])
""",
    )
    assert out["challenge"] == 'Basic realm="Server", charset="UTF-8"'
