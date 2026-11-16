"""CORS origin policy: exact ``self`` origin, credentials to allowed origins only, no echo of excluded origins.

Runs the shipped ``cors.lua`` and ``misc.lua`` under plain Lua with the framework stubbed. ``regex_match``
stands in for PCRE with an *unanchored* ``string.find`` on a Lua pattern, which is what makes the
look-alike case observable: the old ``self`` mode fed the rendered origin through it as a regex.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORS_LUA = ROOT / "src" / "common" / "core" / "cors" / "cors.lua"
MISC_LUA = ROOT / "src" / "common" / "core" / "misc" / "misc.lua"
LUA_PATH = ROOT / "src" / "bw" / "lua"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

PREAMBLE = r"""
package.path = arg[3] .. "/?.lua;" .. package.path
local headers = {}
local request_vars = {}
_G.ngx = { HTTP_NO_CONTENT = 204, HTTP_NOT_ALLOWED = 405, HTTP_BAD_REQUEST = 400, HTTP_CLOSE = 444, header = headers, var = request_vars }

local class = require "middleclass"
local plugin = class("plugin")
function plugin:initialize(id, ctx)
    self.id, self.ctx, self.variables = id, ctx, ctx.variables
end
function plugin:ret(ret, msg, status)
    return { ret = ret, msg = msg, status = status }
end
function plugin:set_metric() end
package.preload["bunkerweb.plugin"] = function() return plugin end

local store = {}
local utils = {
    -- unanchored, like PCRE without ^ $
    regex_match = function(value, pattern)
        if pattern == "^[A-Z][A-Z_-]{2,}$" then -- misc.lua's method check
            return string.match(value, "^%u[%u_-][%u_-]+$") and {} or nil
        end
        return string.find(value, pattern) ~= nil and {} or nil
    end,
    get_deny_status = function() return 403 end,
    parse_duration = function() return 86400 end,
    public_authority = function(_, _, name) return name end,
    get_security_mode = function() return "block" end,
    get_variable = function(name) return store[name], nil end,
}
package.preload["bunkerweb.utils"] = function() return utils end

local function load(path) return dofile(path) end
local function make(cls, variables, bw)
    return cls:new({ variables = variables, bw = bw })
end
local function cors_vars(extra)
    local vars = {
        USE_CORS = "yes", CORS_ALLOW_ORIGIN = "^http://app1%.example%.com$", CORS_DENY_REQUEST = "yes",
        CORS_ALLOW_CREDENTIALS = "yes", CORS_ALLOW_METHODS = "GET, POST, OPTIONS", CORS_ALLOW_HEADERS = "Content-Type",
        CORS_EXPOSE_HEADERS = "", CORS_MAX_AGE = "1d", CROSS_ORIGIN_OPENER_POLICY = "",
        CROSS_ORIGIN_EMBEDDER_POLICY = "", CROSS_ORIGIN_RESOURCE_POLICY = "",
    }
    for k, v in pairs(extra or {}) do vars[k] = v end
    return vars
end
local function reset() for k in pairs(headers) do headers[k] = nil end for k in pairs(request_vars) do request_vars[k] = nil end end
local function header(extra, origin, method)
    reset()
    local obj = make(load(arg[1]), cors_vars(extra), { http_origin = origin, request_method = method or "GET", server_name = "example.com", https_configured = "yes" })
    return obj:header()
end
local function access(extra, origin, method)
    reset()
    local obj = make(load(arg[1]), cors_vars(extra), { http_origin = origin, request_method = method or "GET", server_name = "example.com", https_configured = "yes" })
    return obj:access()
end
local ACAO, ACAC = "Access-Control-Allow-Origin", "Access-Control-Allow-Credentials"
"""


def run(body: str) -> None:
    assert LUA is not None
    result = subprocess.run(
        [LUA, "-", str(CORS_LUA), str(MISC_LUA), str(LUA_PATH)],
        input=PREAMBLE + body,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


class TestSelfOriginIsExact:
    def test_look_alike_origins_are_denied(self):
        run("""
            for _, origin in ipairs({ "https://exampleXcom", "https://example.com.evil.net", "https://evil.net/https://example.com" }) do
                local res = access({ CORS_ALLOW_ORIGIN = "self" }, origin)
                assert(res.status == 403, origin .. " passed in self mode: " .. tostring(res.status))
            end
            """)

    def test_the_exact_self_origin_passes(self):
        run("""
            local res = access({ CORS_ALLOW_ORIGIN = "self" }, "https://example.com")
            assert(res.status == nil, "self origin denied: " .. tostring(res.status))
            """)


class TestCredentials:
    def test_allowed_origin_gets_credentials_on_a_real_response(self):
        run("""
            header({}, "http://app1.example.com", "GET")
            assert(headers[ACAC] == "true", tostring(headers[ACAC]))
            assert(headers[ACAO] == "http://app1.example.com")
            """)

    def test_allowed_origin_gets_credentials_on_a_preflight(self):
        run("""
            header({}, "http://app1.example.com", "OPTIONS")
            assert(headers[ACAC] == "true", tostring(headers[ACAC]))
            """)

    def test_a_disallowed_origin_gets_no_credentials_denied_or_not(self):
        run("""
            for _, method in ipairs({ "GET", "OPTIONS" }) do
                for _, deny in ipairs({ "yes", "no" }) do
                    header({ CORS_DENY_REQUEST = deny }, "http://evil.example.net", method)
                    assert(headers[ACAC] == nil, method .. "/" .. deny .. " sent credentials: " .. tostring(headers[ACAC]))
                end
            end
            """)

    def test_a_look_alike_self_origin_gets_no_credentials(self):
        run("""
            header({ CORS_ALLOW_ORIGIN = "self", CORS_DENY_REQUEST = "no" }, "https://exampleXcom", "OPTIONS")
            assert(headers[ACAC] == nil, tostring(headers[ACAC]))
            header({ CORS_ALLOW_ORIGIN = "self" }, "https://example.com", "GET")
            assert(headers[ACAC] == "true")
            """)

    def test_wildcard_never_carries_credentials(self):
        run("""
            header({ CORS_ALLOW_ORIGIN = "*" }, "http://evil.example.net", "OPTIONS")
            assert(headers[ACAO] == "*" and headers[ACAC] == nil)
            """)

    def test_an_upstream_credentials_header_is_dropped_for_a_disallowed_origin(self):
        run("""
            reset()
            headers[ACAC] = "true"
            local obj = make(load(arg[1]), cors_vars({ CORS_DENY_REQUEST = "no" }), { http_origin = "http://evil.example.net", request_method = "GET", server_name = "example.com" })
            obj:header()
            assert(headers[ACAC] == nil, tostring(headers[ACAC]))
            """)

    def test_credentials_stay_off_when_disabled(self):
        run("""
            header({ CORS_ALLOW_CREDENTIALS = "no" }, "http://app1.example.com", "GET")
            assert(headers[ACAC] == nil)
            """)


class TestRegexModeEcho:
    def test_excluded_origin_gets_no_allow_origin(self):
        run("""
            for _, method in ipairs({ "GET", "OPTIONS" }) do
                for _, deny in ipairs({ "yes", "no" }) do
                    header({ CORS_DENY_REQUEST = deny }, "http://evil.example.net", method)
                    assert(headers[ACAO] == nil, method .. "/" .. deny .. " echoed " .. tostring(headers[ACAO]))
                end
            end
            """)

    def test_an_upstream_allow_origin_is_dropped_for_an_excluded_origin(self):
        run("""
            reset()
            headers[ACAO] = "http://evil.example.net"
            local obj = make(load(arg[1]), cors_vars({ CORS_DENY_REQUEST = "no" }), { http_origin = "http://evil.example.net", request_method = "GET", server_name = "example.com" })
            obj:header()
            assert(headers[ACAO] == nil, tostring(headers[ACAO]))
            """)

    def test_allowed_origin_is_echoed_and_vary_is_kept(self):
        run("""
            header({}, "http://app1.example.com", "GET")
            assert(headers[ACAO] == "http://app1.example.com")
            header({ CORS_DENY_REQUEST = "no" }, "http://evil.example.net", "GET")
            assert(headers.Vary == "Origin")
            """)


MISC_BODY = r"""
local function misc_access(method, origin, acrm, use_cors, allowed)
    reset()
    request_vars.http_access_control_request_method = acrm
    store.USE_CORS = use_cors
    local obj = make(load(arg[2]), { ALLOWED_METHODS = allowed or "GET|POST|HEAD" }, { request_method = method, http_origin = origin, server_name = "example.com" })
    return obj:access()
end
"""


class TestPreflightBypass:
    def test_a_real_cors_preflight_passes_when_options_is_not_allowed(self):
        run(MISC_BODY + """
            local res = misc_access("OPTIONS", "https://app.example.net", "POST", "yes")
            assert(res.status == nil, "preflight refused: " .. tostring(res.status))
            """)

    def test_an_options_without_a_preflight_shape_is_still_refused(self):
        run(MISC_BODY + """
            assert(misc_access("OPTIONS", nil, nil, "yes").status == 405, "bare OPTIONS passed")
            assert(misc_access("OPTIONS", "https://app.example.net", nil, "yes").status == 405, "OPTIONS+Origin passed")
            assert(misc_access("OPTIONS", nil, "POST", "yes").status == 405, "OPTIONS+ACRM passed")
            """)

    def test_a_preflight_is_refused_when_cors_is_off(self):
        run(MISC_BODY + """
            assert(misc_access("OPTIONS", "https://app.example.net", "POST", "no").status == 405)
            """)

    def test_the_bypass_is_limited_to_options(self):
        run(MISC_BODY + """
            assert(misc_access("PUT", "https://app.example.net", "POST", "yes").status == 405)
            """)
