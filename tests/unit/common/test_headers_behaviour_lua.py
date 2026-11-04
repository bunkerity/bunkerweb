"""Behaviour of ``headers.lua``: which response headers are set, removed or kept."""

import pytest
from _lua_request_helpers import requires_lua, run

pytestmark = requires_lua

BASE_VARS = {
    "STRICT_TRANSPORT_SECURITY": "",
    "CONTENT_SECURITY_POLICY": "",
    "REFERRER_POLICY": "",
    "PERMISSIONS_POLICY": "",
    "X_FRAME_OPTIONS": "",
    "X_CONTENT_TYPE_OPTIONS": "",
    "X_DNS_PREFETCH_CONTROL": "",
    "CONTENT_SECURITY_POLICY_REPORT_ONLY": "no",
    "KEEP_UPSTREAM_HEADERS": "",
    "REMOVE_HEADERS": "",
    "COOKIE_AUTO_SECURE_FLAG": "no",
}


def respond(variables=None, *, upstream="", custom="{}", scheme="http", server_custom=None):
    """Run header() over upstream headers (Lua table body ``upstream``); emit each header named in ``watch``."""
    merged = {**BASE_VARS, **(variables or {})}
    lua_vars = ", ".join(f'{k} = "{v}"' for k, v in merged.items())
    server = f'["www.example.com"] = {server_custom}' if server_custom else ""
    return run(
        "headers",
        f"""
VARIABLES = {{ {lua_vars} }}
STORE["plugin_headers_custom_headers"] = {{ global = {custom}, {server} }}
ngx.header = {{ {upstream} }}
local r = PLUGIN:new(ctx({{ scheme = "{scheme}" }})):header()
emit("msg", r.msg)
for _, h in ipairs({{ "Strict-Transport-Security", "Content-Security-Policy", "Content-Security-Policy-Report-Only",
                      "X-Frame-Options", "Referrer-Policy", "X-Custom", "Server", "X-Powered-By" }}) do
    emit(h, ngx.header[h])
end
local cookie = ngx.header["Set-Cookie"]
emit("cookie", type(cookie) == "table" and table.concat(cookie, " | ") or cookie)
""",
    )


def test_a_configured_header_is_set():
    assert respond({"X_FRAME_OPTIONS": "SAMEORIGIN"})["X-Frame-Options"] == "SAMEORIGIN"


def test_an_empty_value_removes_the_upstream_header():
    out = respond(upstream='["X-Frame-Options"] = "DENY"')
    assert out["X-Frame-Options"] == "nil"


class TestKeepUpstream:
    def test_a_kept_header_wins_over_the_configured_value(self):
        out = respond({"X_FRAME_OPTIONS": "SAMEORIGIN", "KEEP_UPSTREAM_HEADERS": "X-Frame-Options"}, upstream='["X-Frame-Options"] = "DENY"')
        assert out["X-Frame-Options"] == "DENY"

    def test_keep_only_applies_to_the_listed_headers(self):
        out = respond(
            {"X_FRAME_OPTIONS": "SAMEORIGIN", "REFERRER_POLICY": "no-referrer", "KEEP_UPSTREAM_HEADERS": "Referrer-Policy"},
            upstream='["X-Frame-Options"] = "DENY", ["Referrer-Policy"] = "origin"',
        )
        assert out["X-Frame-Options"] == "SAMEORIGIN"
        assert out["Referrer-Policy"] == "origin"

    def test_star_keeps_every_upstream_header(self):
        out = respond({"X_FRAME_OPTIONS": "SAMEORIGIN", "KEEP_UPSTREAM_HEADERS": "*"}, upstream='["X-Frame-Options"] = "DENY"')
        assert out["X-Frame-Options"] == "DENY"

    def test_keep_does_not_help_when_upstream_sent_nothing(self):
        out = respond({"X_FRAME_OPTIONS": "SAMEORIGIN", "KEEP_UPSTREAM_HEADERS": "X-Frame-Options"})
        assert out["X-Frame-Options"] == "SAMEORIGIN"


class TestHsts:
    def test_not_sent_over_plain_http(self):
        assert respond({"STRICT_TRANSPORT_SECURITY": "max-age=1"}, scheme="http")["Strict-Transport-Security"] == "nil"

    def test_sent_over_https(self):
        assert respond({"STRICT_TRANSPORT_SECURITY": "max-age=1"}, scheme="https")["Strict-Transport-Security"] == "max-age=1"


class TestCspReportOnly:
    def test_report_only_moves_the_policy_to_the_report_only_header(self):
        out = respond(
            {"CONTENT_SECURITY_POLICY": "default-src 'self'", "CONTENT_SECURITY_POLICY_REPORT_ONLY": "yes"}, upstream='["Content-Security-Policy"] = "x"'
        )
        assert out["Content-Security-Policy"] == "nil"
        assert out["Content-Security-Policy-Report-Only"] == "default-src 'self'"

    def test_enforcing_mode_sets_the_enforcing_header(self):
        out = respond({"CONTENT_SECURITY_POLICY": "default-src 'self'"})
        assert out["Content-Security-Policy"] == "default-src 'self'"
        assert out["Content-Security-Policy-Report-Only"] == "nil"


class TestCustomAndRemoved:
    def test_custom_header_is_set_and_the_server_value_overrides_the_global_one(self):
        out = respond(custom='{ ["X-Custom"] = "global" }', server_custom='{ ["X-Custom"] = "server" }')
        assert out["X-Custom"] == "server"

    def test_an_empty_custom_value_removes_the_header(self):
        out = respond(custom='{ ["X-Custom"] = "" }', upstream='["X-Custom"] = "upstream"')
        assert out["X-Custom"] == "nil"

    def test_remove_headers_drops_each_listed_name(self):
        out = respond({"REMOVE_HEADERS": "Server X-Powered-By"}, upstream='["Server"] = "nginx", ["X-Powered-By"] = "php"')
        assert out["Server"] == out["X-Powered-By"] == "nil"


class TestCookieSecureFlag:
    ON = {"COOKIE_AUTO_SECURE_FLAG": "yes"}

    def test_string_cookie_gets_secure_over_https(self):
        assert respond(self.ON, upstream='["Set-Cookie"] = "a=1"', scheme="https")["cookie"] == "a=1; Secure"

    def test_an_already_secure_cookie_is_not_doubled(self):
        assert respond(self.ON, upstream='["Set-Cookie"] = "a=1; Secure"', scheme="https")["cookie"] == "a=1; Secure"

    def test_every_cookie_of_a_list_is_flagged(self):
        out = respond(self.ON, upstream='["Set-Cookie"] = { "a=1", "b=2; Secure" }', scheme="https")
        assert out["cookie"] == "a=1; Secure | b=2; Secure"

    @pytest.mark.parametrize(("variables", "scheme"), [(ON, "http"), ({"COOKIE_AUTO_SECURE_FLAG": "no"}, "https")])
    def test_cookie_is_left_alone_off_https_or_when_disabled(self, variables, scheme):
        assert respond(variables, upstream='["Set-Cookie"] = "a=1"', scheme=scheme)["cookie"] == "a=1"


def test_init_stores_valid_custom_headers_per_service():
    out = run(
        "headers",
        r"""
MULTI_VARS = { global = { CUSTOM_HEADER = "X-One: 1", CUSTOM_HEADER_2 = "not a header" } }
local r = PLUGIN:new(ctx()):init()
local stored = STORE["plugin_headers_custom_headers"].global
emit("msg", r.msg) emit("one", stored["X-One"])
""",
    )
    assert out["msg"] == "successfully loaded 2 custom headers"
    assert out["one"] == "1"
