"""The ACME challenge whitelist must be armed only when a challenge is really pending.

``letsencrypt:access()`` answers a URI under ``/.well-known/acme-challenge/`` with ``ngx.OK``,
and ``server-http/access-lua.conf:154-186`` **breaks** its plugin loop on any returned status --
so that answer does not merely allow the request, it ends the access phase at position 2 of
``order.json`` and skips ``blacklist``, ``greylist``, ``country``, ``dnsbl``, ``crowdsec``,
``bunkernet``, ``reversescan``, ``limit``, ``authbasic``, ``misc``, ``cors``, ``workflows`` and
``antibot`` for that request.

The only condition used to be ``LETS_ENCRYPT_PASSTHROUGH == "no"``, which is the DEFAULT: every
service of every installation carried the bypass, including services with ``AUTO_LETS_ENCRYPT=no``
that will never see an ACME request, and it was never released after issuance because nothing
armed it in the first place.

Runs the shipped ``letsencrypt.lua`` under a plain Lua interpreter with the real ``middleclass``,
a stubbed ``bunkerweb.plugin`` mirroring ``plugin.lua:109``, and an in-memory ``io``/``os`` so the
assertions are about what the code does rather than about what it contains -- and so the round
trip below proves ``api()`` and ``access()`` agree on the challenge directory, which is exactly
what a shared constant can break silently.
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
-- `bunkerweb.utils` pulls in ngx.errlog through the logger and cannot load outside OpenResty.
-- access() and api() call none of it, so an empty table is honest rather than a stand-in.
package.preload["bunkerweb.utils"] = function() return {} end
package.preload["ngx.ssl"] = function() return {} end
package.preload["cjson"] = function() return { decode = function() return _G.BODY end } end

-- An in-memory filesystem, installed BEFORE the plugin is loaded because letsencrypt.lua captures
-- `io.open`, `os.remove` and `os.execute` as locals at load time. No temp directory and no write
-- to the hardcoded /var/tmp path: the point is that both halves compute the SAME path, not what
-- that path is.
FILES = {}
OPENED = {}
io.open = function(path, mode)
    OPENED[#OPENED + 1] = path
    if mode == nil or mode == "r" then
        if FILES[path] == nil then return nil, "no such file or directory" end
        return { close = function() end, read = function() return FILES[path] end }
    end
    local buffer = {}
    return {
        write = function(_, chunk) buffer[#buffer + 1] = chunk end,
        close = function() FILES[path] = table.concat(buffer) end,
    }
end
os.remove = function(path)
    if FILES[path] == nil then return nil, "no such file or directory" end
    FILES[path] = nil
    return true
end
os.execute = function() return true end

local letsencrypt = dofile(arg[1])

local function access(uri, variables)
    _G.VARIABLES = variables
    return letsencrypt:new({ bw = { uri = uri } }):access()
end

local function challenge_api(method, body)
    _G.BODY = body
    _G.VARIABLES = {}
    _G.ngx.req = { read_body = function() end, get_body_data = function() return "{}" end }
    return letsencrypt:new({ bw = { uri = "/lets-encrypt/challenge", request_method = method } }):api()
end

local ARMED = { LETS_ENCRYPT_PASSTHROUGH = "no", AUTO_LETS_ENCRYPT = "yes", LETS_ENCRYPT_CHALLENGE = "http" }
local function armed(overrides)
    local variables = {}
    for key, value in pairs(ARMED) do variables[key] = value end
    for key, value in pairs(overrides or {}) do variables[key] = value end
    return variables
end
"""


def _run(body: str) -> str:
    result = subprocess.run([LUA, "-", str(LE_LUA), str(LUA_PATH)], input=PREAMBLE + body, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_a_pending_challenge_is_still_whitelisted():
    """Anti-vacuity, and the whole reason the bypass exists. If this stopped firing, every
    assertion below would pass for the wrong reason and http-01 would break outright."""
    _run(f"""
        challenge_api("POST", {{ token = "tok3n", validation = "payload" }})
        local r = access("{PREFIX}tok3n", armed())
        assert(r.status == _G.ngx.OK, "a pending challenge must be whitelisted, got " .. tostring(r.status))
        assert(r.msg == "visit from LE", r.msg)
        """)


def test_the_whitelist_is_released_once_the_token_is_cleaned_up():
    """``certbot-cleanup.py`` DELETEs the token on every instance when the order finishes. From
    that moment the prefix is an ordinary path again -- which is the ~89 days out of 90 the bypass
    used to stay open for."""
    _run(f"""
        challenge_api("POST", {{ token = "tok3n", validation = "payload" }})
        challenge_api("DELETE", {{ token = "tok3n" }})
        local r = access("{PREFIX}tok3n", armed())
        assert(r.status == nil, "the whitelist survived cleanup, status " .. tostring(r.status))
        assert(r.ret == true, "the request must carry on through the access chain, not be refused")
        """)


def test_api_and_access_agree_on_the_challenge_directory():
    """The two halves build the path independently. A constant renamed on one side only would
    leave http-01 silently unvalidatable, so the round trip is asserted rather than the literal."""
    _run(f"""
        challenge_api("POST", {{ token = "tok3n", validation = "payload" }})
        local written = nil
        for path in pairs(FILES) do written = path end
        assert(written, "api() wrote nothing")
        local r = access("{PREFIX}tok3n", armed())
        assert(r.status == _G.ngx.OK, "access() looked somewhere else than " .. written)
        """)


class TestTheBypassIsNotArmedForAServiceThatWillNeverBeValidated:
    """Each of these used to end the access chain at plugin 2 for any URI under the prefix."""

    def test_a_service_without_lets_encrypt(self):
        _run(f"""
            challenge_api("POST", {{ token = "tok3n", validation = "payload" }})
            local r = access("{PREFIX}tok3n", armed({{ AUTO_LETS_ENCRYPT = "no" }}))
            assert(r.status == nil, "status " .. tostring(r.status))
            """)

    def test_a_service_using_the_dns_challenge(self):
        _run(f"""
            challenge_api("POST", {{ token = "tok3n", validation = "payload" }})
            local r = access("{PREFIX}tok3n", armed({{ LETS_ENCRYPT_CHALLENGE = "dns" }}))
            assert(r.status == nil, "status " .. tostring(r.status))
            """)

    def test_a_service_answering_the_challenge_itself(self):
        """``LETS_ENCRYPT_PASSTHROUGH=yes`` was already the one gate; it must stay one."""
        _run(f"""
            challenge_api("POST", {{ token = "tok3n", validation = "payload" }})
            local r = access("{PREFIX}tok3n", armed({{ LETS_ENCRYPT_PASSTHROUGH = "yes" }}))
            assert(r.status == nil, "status " .. tostring(r.status))
            """)


def test_an_ordinary_uri_is_untouched():
    _run("""
        challenge_api("POST", { token = "tok3n", validation = "payload" })
        local r = access("/index.html", armed())
        assert(r.status == nil, "status " .. tostring(r.status))
        """)


def test_the_prefix_is_anchored_and_not_merely_contained():
    _run(f"""
        challenge_api("POST", {{ token = "tok3n", validation = "payload" }})
        local r = access("/redir?next={PREFIX}tok3n", armed())
        assert(r.status == nil, "status " .. tostring(r.status))
        """)


def test_a_token_outside_the_base64url_charset_is_never_stat_ed():
    """The lookup builds a filesystem path out of a client-supplied path segment. ``ngx.var.uri``
    is already normalised, but the charset gate is what makes that irrelevant -- and it must fire
    BEFORE the open, so a crafted value cannot even probe for a file outside the directory."""
    _run(f"""
        local r = access("{PREFIX}../../../etc/passwd", armed())
        assert(r.status == nil, "status " .. tostring(r.status))
        assert(#OPENED == 0, "a rejected token was still opened: " .. tostring(OPENED[1]))
        """)


def test_an_empty_token_is_rejected():
    """``{PREFIX}`` with nothing after it would otherwise open the directory itself."""
    _run(f"""
        local r = access("{PREFIX}", armed())
        assert(r.status == nil, "status " .. tostring(r.status))
        assert(#OPENED == 0, "the empty token was opened: " .. tostring(OPENED[1]))
        """)
