"""``LETS_ENCRYPT_PASSTHROUGH=yes``: the exemption of a passed-through ACME challenge (dev 566375758, 9ed8ea52e).

With the pass-through on, BunkerWeb does not serve the challenge: the backend answers it. The request
used to run the whole access chain (blacklist, ban, ModSecurity, antibot...), so a protection could
refuse the ACME validator and the certificate was never issued. Dev exempts ONE shape of request, and
nothing wider, because the exemption also skips the ban check and the WAF for that request:

  * ``LETS_ENCRYPT_PASSTHROUGH=yes``,
  * method ``GET`` or ``HEAD``,
  * ``/.well-known/acme-challenge/<token>`` with exactly one token-shaped segment (base64url).

The exemption is taken twice: in the set phase (whitelist, because the ModSecurity kill switch reads
``ENV:is_whitelisted`` in phase 1) and in the access phase (ends the chain with ``ngx.OK``).

``9ed8ea52e`` keeps the client ``Host`` on such a request: the backend solver validates the challenge
against the requested name, so ``REVERSE_PROXY_CUSTOM_HOST`` must not replace it. Literal custom hosts
only (``$bw_reverse_proxy_host`` is declared by the reverse proxy template for those and no other).

Runs the shipped ``letsencrypt.lua`` under a plain Lua interpreter, same approach as
``tests/unit/common/test_letsencrypt_challenge_release.py``.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
LE_LUA = ROOT / "src" / "common" / "core" / "letsencrypt" / "letsencrypt.lua"
LUA_PATH = ROOT / "src" / "bw" / "lua"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

PREFIX = "/.well-known/acme-challenge/"

PREAMBLE = r"""
package.path = arg[2] .. "/?.lua;" .. package.path
_G.ngx = {
    ERR = 4, NOTICE = 5, OK = 0,
    HTTP_NOT_FOUND = 404, HTTP_OK = 200, HTTP_BAD_REQUEST = 400, HTTP_INTERNAL_SERVER_ERROR = 500,
}

local class = require "middleclass"
local plugin = class("plugin")
function plugin:initialize(id, ctx)
    self.id, self.ctx, self.variables = id, ctx, _G.VARIABLES or {}
    self.logger = { log = function() end }
end
-- Mirrors plugin.lua:109 exactly; a divergence here would make every assertion below meaningless.
function plugin:ret(ret, msg, status, redirect, data)
    return { ret = ret, msg = msg, status = status, redirect = redirect, data = data }
end
package.preload["bunkerweb.plugin"] = function() return plugin end

-- Other-plugin settings (REVERSE_PROXY_CUSTOM_HOST...) come from `utils.get_variable`, never from
-- `self.variables`, which only carries the plugin's own settings.
SETTINGS = {}
package.preload["bunkerweb.utils"] = function()
    return { get_variable = function(name) return SETTINGS[name] end }
end
package.preload["ngx.ssl"] = function() return {} end
package.preload["cjson"] = function() return { decode = function() return {} end } end

-- What `whitelist:set()` does for ModSecurity's phase-1 kill switch.
ENV_CALLS = {}
package.preload["resty.env"] = function()
    return { set = function(name, value) ENV_CALLS[#ENV_CALLS + 1] = name .. "=" .. value end }
end

-- A faithful `ngx.var`: reading an undeclared variable yields nil, writing one raises the error
-- OpenResty raises, and `DECLARED` plays the role of the `set $name` directives of the config.
DECLARED = { is_whitelisted = true, bw_reverse_proxy_host = true }
local values = { host = "www.example.com" }
_G.ngx.var = setmetatable({}, {
    __index = function(_, name) return values[name] end,
    __newindex = function(_, name, value)
        if not DECLARED[name] then
            error('variable "' .. name .. '" not found for writing; maybe it is a built-in variable?', 2)
        end
        values[name] = value
    end,
})

-- An in-memory filesystem: access() reads the pending-challenge file of the local-serving mode.
FILES = {}
io.open = function(path, mode)
    if FILES[path] == nil then return nil, "no such file or directory" end
    local content = FILES[path]
    return { close = function() end, read = function(_, count) if content == "" then return nil end return content:sub(1, count) end }
end
os.execute = function() return true end

local letsencrypt = dofile(arg[1])

-- One request. `overrides` change the plugin settings, `method` and `uri` the request.
local function request(method, uri, overrides)
    ENV_CALLS = {}
    ngx.var.is_whitelisted = nil
    local variables = {
        LETS_ENCRYPT_PASSTHROUGH = "yes", AUTO_LETS_ENCRYPT = "yes", LETS_ENCRYPT_CHALLENGE = "http",
    }
    for key, value in pairs(overrides or {}) do variables[key] = value end
    _G.VARIABLES = variables
    local ctx = { bw = { uri = uri, request_method = method } }
    local plugin_obj = letsencrypt:new(ctx)
    local set_ret = plugin_obj:set()
    local access_ret = plugin_obj:access()
    return { set = set_ret, access = access_ret, ctx = ctx, whitelisted = ngx.var.is_whitelisted, env = ENV_CALLS }
end

local function assert_exempt(r, what)
    assert(r.set.ret == true, what .. ": set() must not fail")
    assert(r.whitelisted == "yes", what .. ": ngx.var.is_whitelisted is " .. tostring(r.whitelisted))
    assert(r.ctx.bw.is_whitelisted == "yes", what .. ": ctx.bw.is_whitelisted is " .. tostring(r.ctx.bw.is_whitelisted))
    assert(r.env[1] == "is_whitelisted=yes", what .. ": the ModSecurity kill switch variable was not set")
    assert(r.access.status == ngx.OK, what .. ": access() must end the chain with ngx.OK, got " .. tostring(r.access.status))
end

local function assert_full_chain(r, what)
    assert(r.set.ret == true, what .. ": set() must not fail")
    assert(r.whitelisted == nil, what .. ": was whitelisted (" .. tostring(r.whitelisted) .. ")")
    assert(r.ctx.bw.is_whitelisted == nil, what .. ": ctx.bw.is_whitelisted was set")
    assert(#r.env == 0, what .. ": the ModSecurity kill switch variable was set")
    assert(r.access.status == nil, what .. ": access() ended the chain with status " .. tostring(r.access.status))
    assert(r.access.ret == true, what .. ": access() must carry on, not refuse")
end
"""


def _run(body: str) -> str:
    result = subprocess.run([LUA, "-", str(LE_LUA), str(LUA_PATH)], input=PREAMBLE + body, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


# ---- 566375758 (D17): the exemption and its limits --------------------------------------------


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_a_token_shaped_get_or_head_is_exempt(method):
    """Anti-vacuity: every negative case below would pass for the wrong reason if this stopped firing."""
    _run(f'assert_exempt(request("{method}", "{PREFIX}Tok3n_-AZaz09"), "{method}")')


@pytest.mark.parametrize(
    "case, method, uri",
    [
        ("a second path segment", "GET", f"{PREFIX}tok3n/extra"),
        ("a deeper backend route", "GET", f"{PREFIX}tok3n/../../admin"),
        ("a trailing slash", "GET", f"{PREFIX}tok3n/"),
        ("a dot-dot token", "GET", f"{PREFIX}.."),
        ("a dot in the token", "GET", f"{PREFIX}tok3n.txt"),
        ("a query smuggled into the uri", "GET", f"{PREFIX}tok3n?x=/../admin"),
        ("a query that hides a second segment", "GET", f"{PREFIX}tok3n?/admin"),
        ("an encoded slash", "GET", f"{PREFIX}tok3n%2Fextra"),
        ("an encoded dot-dot", "GET", f"{PREFIX}%2e%2e"),
        ("a double-encoded slash", "GET", f"{PREFIX}tok3n%252Fextra"),
        ("a backslash", "GET", f"{PREFIX}tok3n\\\\extra"),
        ("a trailing newline", "GET", f"{PREFIX}tok3n\\n"),
        ("a trailing space", "GET", f"{PREFIX}tok3n "),
        ("an empty token", "GET", PREFIX),
        ("the prefix without its last slash", "GET", "/.well-known/acme-challenge"),
        ("a longer prefix", "GET", "/.well-known/acme-challenge-x/tok3n"),
        ("a prefix in the middle of the path", "GET", f"/app{PREFIX}tok3n"),
        ("a prefix in a redirect parameter", "GET", f"/redir?next={PREFIX}tok3n"),
        ("another case spelling", "GET", "/.Well-Known/ACME-challenge/tok3n"),
        ("another well-known path", "GET", "/.well-known/security.txt"),
        ("an ordinary path", "GET", "/index.html"),
        ("POST", "POST", f"{PREFIX}tok3n"),
        ("PUT", "PUT", f"{PREFIX}tok3n"),
        ("DELETE", "DELETE", f"{PREFIX}tok3n"),
        ("PATCH", "PATCH", f"{PREFIX}tok3n"),
        ("OPTIONS", "OPTIONS", f"{PREFIX}tok3n"),
        ("a lower-case method", "get", f"{PREFIX}tok3n"),
        ("a method with a suffix", "GETX", f"{PREFIX}tok3n"),
    ],
)
def test_everything_else_goes_through_the_full_chain(case, method, uri):
    _run(f'assert_full_chain(request("{method}", "{uri}"), "{case}")')


def test_no_request_method_goes_through_the_full_chain():
    """A phase without a method (stream, a subrequest) must not match by omission."""
    _run(f'assert_full_chain(request(nil, "{PREFIX}tok3n"), "no method")')


def test_no_uri_does_not_raise():
    """The stream subsystem has no uri; a nil must be a clean miss, never an error in the set phase."""
    _run('assert_full_chain(request("GET", nil), "no uri")')


@pytest.mark.parametrize("value", ["no", ""])
def test_the_exemption_is_off_unless_passthrough_is_yes(value):
    """``LETS_ENCRYPT_PASSTHROUGH`` defaults to ``no``: nothing may exempt a service that did not ask for it."""
    _run(f'assert_full_chain(request("GET", "{PREFIX}tok3n", {{ LETS_ENCRYPT_PASSTHROUGH = "{value}" }}), "passthrough {value!r}")')


def test_the_exemption_is_off_when_the_setting_is_absent():
    _run(f'assert_full_chain(request("GET", "{PREFIX}tok3n", {{ LETS_ENCRYPT_PASSTHROUGH = false }}), "no setting")')


def test_a_neighbouring_request_is_not_exempted_by_a_previous_one():
    """The decision is per request: nothing is remembered between two of them."""
    _run(f"""
        assert_exempt(request("GET", "{PREFIX}tok3n"), "first")
        assert_full_chain(request("GET", "/index.html"), "second")
        assert_full_chain(request("POST", "{PREFIX}tok3n"), "third")
        """)


def test_the_local_serving_mode_is_unchanged():
    """``LETS_ENCRYPT_PASSTHROUGH=no`` still serves a pending token itself and a missing one is not
    exempted (``tests/unit/common/test_letsencrypt_challenge_release.py`` pins the rest)."""
    _run(f"""
        local r = request("GET", "{PREFIX}tok3n", {{ LETS_ENCRYPT_PASSTHROUGH = "no" }})
        assert(r.access.status == nil, "no pending token, yet status " .. tostring(r.access.status))
        FILES["/var/tmp/bunkerweb/lets-encrypt{PREFIX}tok3n"] = "payload"
        r = request("GET", "{PREFIX}tok3n", {{ LETS_ENCRYPT_PASSTHROUGH = "no" }})
        assert(r.access.status == ngx.OK and r.access.msg == "visit from LE", "pending token must still be served")
        """)


# ---- 9ed8ea52e: the client Host survives a literal REVERSE_PROXY_CUSTOM_HOST ---------------------


def test_a_literal_custom_host_is_replaced_by_the_client_host():
    _run(f"""
        SETTINGS = {{ REVERSE_PROXY_CUSTOM_HOST = "backend.local", USE_REVERSE_PROXY = "yes" }}
        local r = request("GET", "{PREFIX}tok3n")
        assert_exempt(r, "passthrough")
        assert(ngx.var.bw_reverse_proxy_host == "www.example.com", "got " .. tostring(ngx.var.bw_reverse_proxy_host))
        """)


@pytest.mark.parametrize(
    "case, settings",
    [
        ("a custom host built from nginx variables", 'REVERSE_PROXY_CUSTOM_HOST = "$http_host", USE_REVERSE_PROXY = "yes"'),
        ("a variable inside a literal", 'REVERSE_PROXY_CUSTOM_HOST = "api-$host", USE_REVERSE_PROXY = "yes"'),
        ("no custom host", 'REVERSE_PROXY_CUSTOM_HOST = "", USE_REVERSE_PROXY = "yes"'),
        ("an unset custom host", 'USE_REVERSE_PROXY = "yes"'),
        ("the reverse proxy off", 'REVERSE_PROXY_CUSTOM_HOST = "backend.local", USE_REVERSE_PROXY = "no"'),
    ],
)
def test_the_host_is_left_alone_unless_a_literal_custom_host_applies(case, settings):
    """The template declares the variable for literal hosts only; writing anything else would either
    raise (undeclared) or replace a host built from nginx variables."""
    _run(f"""
        SETTINGS = {{ {settings} }}
        ngx.var.bw_reverse_proxy_host = "sentinel"
        assert_exempt(request("GET", "{PREFIX}tok3n"), "{case}")
        assert(ngx.var.bw_reverse_proxy_host == "sentinel", "{case}: the host was rewritten to " .. tostring(ngx.var.bw_reverse_proxy_host))
        """)


def test_the_host_is_left_alone_on_a_request_that_is_not_exempt():
    _run(f"""
        SETTINGS = {{ REVERSE_PROXY_CUSTOM_HOST = "backend.local", USE_REVERSE_PROXY = "yes" }}
        ngx.var.bw_reverse_proxy_host = "sentinel"
        assert_full_chain(request("POST", "{PREFIX}tok3n"), "POST")
        assert_full_chain(request("GET", "{PREFIX}tok3n/extra"), "two segments")
        assert(ngx.var.bw_reverse_proxy_host == "sentinel", "rewritten to " .. tostring(ngx.var.bw_reverse_proxy_host))
        """)


def test_a_worker_on_the_previous_configuration_keeps_the_configured_host():
    """During a reload a worker may still run a configuration that does not declare the variable. The
    write raises there; the request must keep going, still exempt, with the configured host."""
    _run(f"""
        SETTINGS = {{ REVERSE_PROXY_CUSTOM_HOST = "backend.local", USE_REVERSE_PROXY = "yes" }}
        DECLARED.bw_reverse_proxy_host = nil
        assert_exempt(request("GET", "{PREFIX}tok3n"), "undeclared variable")
        """)
