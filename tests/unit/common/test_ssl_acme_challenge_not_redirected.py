"""The HTTPS redirect must not swallow the ACME HTTP-01 challenge.

`order.json` runs `ssl` at position 0 and `letsencrypt` at position 2, so by the time
`letsencrypt:access()` would whitelist `/.well-known/acme-challenge/...` (letsencrypt.lua:515) the
`ssl` plugin has already answered it with a 301 to https. ACME servers *do* follow that redirect,
which is why the failure is not obvious: validation still succeeds whenever 443 happens to be
reachable and the handshake happens to work. It fails precisely in the case the challenge exists to
serve -- a name issuing its first certificate, which by definition has none to present yet.

The plugin returns without a status for that prefix, so only the redirect is skipped; `whitelist`,
`letsencrypt` and every later plugin in the access chain still run. That distinction is asserted
below rather than assumed, because "return true" in an access hook is one character away from a
fail-open.

Runs `ssl.lua` under a plain Lua interpreter with the real `middleclass` and a stubbed
`bunkerweb.plugin`, so the assertions are about what the code does, not about what it contains.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SSL_LUA = ROOT / "src" / "common" / "core" / "ssl" / "ssl.lua"
LE_LUA = ROOT / "src" / "common" / "core" / "letsencrypt" / "letsencrypt.lua"
ORDER_JSON = ROOT / "src" / "common" / "core" / "order.json"
LUA_PATH = ROOT / "src" / "bw" / "lua"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

PREAMBLE = r"""
package.path = arg[2] .. "/?.lua;" .. package.path
_G.ngx = { HTTP_MOVED_PERMANENTLY = 301 }

local class = require "middleclass"
local plugin = class("plugin")
function plugin:initialize(id, ctx)
    self.id, self.ctx, self.variables = id, ctx, _G.VARIABLES or {}
end
-- Mirrors plugin.lua:109 exactly; a divergence here would make every assertion below meaningless.
function plugin:ret(ret, msg, status, redirect, data)
    return { ret = ret, msg = msg, status = status, redirect = redirect, data = data }
end
package.preload["bunkerweb.plugin"] = function() return plugin end

local function access(uri, request_uri, variables)
    _G.VARIABLES = variables
    local ssl = dofile(arg[1])
    local instance = ssl:new({
        bw = { uri = uri, request_uri = request_uri or uri, scheme = "http", http_host = "example.com", https_configured = "yes" },
    })
    return instance:access()
end
"""

REDIRECT_ON = '{ AUTO_REDIRECT_HTTP_TO_HTTPS = "yes" }'


def _run(body: str) -> None:
    result = subprocess.run([LUA, "-", str(SSL_LUA), str(LUA_PATH)], input=PREAMBLE + body, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_harness_itself_redirects_an_ordinary_request():
    """Anti-vacuity. If the stub were wrong and `access` never redirected anything, every
    assertion about the challenge *not* redirecting would pass for the wrong reason."""
    _run(
        f"""
        local r = access("/index.html", "/index.html", {REDIRECT_ON})
        assert(r.status == 301, "an ordinary request must still be redirected, got " .. tostring(r.status))
        assert(r.redirect == "https://example.com/index.html", "wrong redirect target: " .. tostring(r.redirect))
        """
    )


def test_the_acme_challenge_is_not_redirected():
    _run(
        f"""
        local r = access("/.well-known/acme-challenge/tok3n", "/.well-known/acme-challenge/tok3n", {REDIRECT_ON})
        assert(r.status == nil, "the challenge was answered with status " .. tostring(r.status))
        assert(r.redirect == nil, "the challenge was redirected to " .. tostring(r.redirect))
        """
    )


def test_the_challenge_is_allowed_on_rather_than_terminated():
    """The distinction that keeps this from being a fail-open: `ssl` declines to redirect, it does
    not answer the request. A status of OK here would end the access chain and skip `whitelist`,
    `blacklist` and the rest for any URL under the challenge prefix."""
    _run(
        f"""
        local r = access("/.well-known/acme-challenge/tok3n", nil, {REDIRECT_ON})
        assert(r.ret == true, "expected a successful, non-terminating return")
        assert(r.status == nil, "a status here would terminate the access chain at plugin 0")
        """
    )


def test_the_prefix_is_anchored_and_not_merely_contained():
    """`sub(uri, 1, #prefix)`, not `find`. A path that mentions the challenge further along is an
    ordinary request and must still be redirected."""
    _run(
        f"""
        local r = access("/redir?next=/.well-known/acme-challenge/tok3n", nil, {REDIRECT_ON})
        assert(r.status == 301, "a path merely containing the prefix must still redirect")
        """
    )


def test_both_plugins_spell_the_prefix_the_same_way():
    """Two hardcoded copies of one string. If they drift, `ssl` exempts a path `letsencrypt` does
    not serve, or the other way round, and the symptom is again a silent validation failure."""
    prefix = "/.well-known/acme-challenge/"
    assert f'"{prefix}"' in SSL_LUA.read_text(encoding="utf-8"), "ssl.lua no longer spells the prefix this way"
    assert f'"{prefix}"' in LE_LUA.read_text(encoding="utf-8"), "letsencrypt.lua no longer spells the prefix this way"


def test_ssl_still_runs_before_letsencrypt():
    """The reason the exemption has to live in ssl.lua at all. If this ever reverses, letsencrypt's
    own whitelist would handle the challenge and this exemption becomes redundant rather than
    load-bearing -- worth knowing before someone deletes it as dead code."""
    order = json.loads(ORDER_JSON.read_text(encoding="utf-8"))
    access_order = order["access"] if isinstance(order, dict) else order

    assert access_order.index("ssl") < access_order.index("letsencrypt"), "ssl no longer precedes letsencrypt; re-read ssl.lua's exemption"
