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
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SSL_LUA = ROOT / "src" / "common" / "core" / "ssl" / "ssl.lua"
LE_LUA = ROOT / "src" / "common" / "core" / "letsencrypt" / "letsencrypt.lua"
ORDER_JSON = ROOT / "src" / "common" / "core" / "order.json"
LUA_PATH = ROOT / "src" / "bw" / "lua"

UTILS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")


def utils_source(*names: str) -> str:
    """The shipped source of the named utils helpers, plus the `port_list` local they share.

    Lifted rather than reimplemented: a stub that merely mimics `public_authority` would keep
    passing while the real one broke. Same technique as
    ``tests/unit/common/test_lua_request_path_ports.py``, for the same reason -- utils.lua cannot
    be loaded outside OpenResty.
    """
    text = UTILS_LUA.read_text(encoding="utf-8")
    chunks = [re.search(r"^local function port_list\(.*?^end$", text, re.S | re.M)]
    chunks += [re.search(rf"^utils\.{name} = function.*?^end$", text, re.S | re.M) for name in names]
    for name, chunk in zip(("port_list",) + names, chunks):
        assert chunk, f"{name} not found in utils.lua -- renamed?"
    return "\n".join(chunk.group(0) for chunk in chunks)


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

-- `bunkerweb.utils` pulls in ngx.errlog through the logger, so it cannot be loaded outside
-- OpenResty. Only `public_authority` is used here, and its REAL source is lifted from utils.lua
-- below rather than reimplemented, so this stub cannot drift from the shipped behaviour: the
-- per-service port lookup it calls is what the fake internalstore drives.
local utils = {}
package.preload["bunkerweb.utils"] = function() return utils end

local function access(uri, request_uri, variables, ctx_extra)
    _G.VARIABLES = variables
    local bw = { uri = uri, request_uri = request_uri or uri, scheme = "http", http_host = "example.com", https_configured = "yes" }
    for key, value in pairs(ctx_extra or {}) do
        bw[key] = value
    end
    local ssl = dofile(arg[1])
    return ssl:new({ bw = bw }):access()
end
"""

REDIRECT_ON = '{ AUTO_REDIRECT_HTTP_TO_HTTPS = "yes" }'


def _run(body: str, variables_table: str = '{ global = { MULTISITE = "no" } }') -> None:
    harness = (
        PREAMBLE
        + (
            "local internalstore = { get = function() return %s, nil end }\n%s\n"
            % (variables_table, utils_source("listen_port_override", "host_without_port", "public_authority"))
        )
        + body
    )
    result = subprocess.run([LUA, "-", str(SSL_LUA), str(LUA_PATH)], input=harness, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_harness_itself_redirects_an_ordinary_request():
    """Anti-vacuity. If the stub were wrong and `access` never redirected anything, every
    assertion about the challenge *not* redirecting would pass for the wrong reason."""
    _run(f"""
        local r = access("/index.html", "/index.html", {REDIRECT_ON})
        assert(r.status == 301, "an ordinary request must still be redirected, got " .. tostring(r.status))
        assert(r.redirect == "https://example.com/index.html", "wrong redirect target: " .. tostring(r.redirect))
        """)


MULTISITE_SAME = '{ global = { MULTISITE = "yes", HTTPS_PORT = "8443" }, ["example.com"] = { HTTPS_PORT = "8443" } }'
MULTISITE_MOVED = '{ global = { MULTISITE = "yes", HTTPS_PORT = "8443" }, ["example.com"] = { HTTPS_PORT = "9443" } }'


class TestTheRedirectCarriesTheServicePort:
    """Lot C / call site C1. ``HTTPS_PORT`` became multisite, so the port a service listens on is
    no longer necessarily the global one -- and this redirect is an absolute URL, so a wrong
    authority sends the client to a socket nothing is listening on.

    The rule is per-service-list-differs-from-global. Equal (every deployment that overrides
    nothing) means the published-port contract still holds: ``docker.yml:16-18`` publishes 80:8080
    and 443:8443, so the *rendered* port is not the reachable one and the redirect must keep
    carrying no port at all. Different means the operator deliberately moved this service off the
    published port, and the rendered port is then the only port anyone can reach it on."""

    def test_a_service_that_overrides_nothing_redirects_exactly_as_before(self):
        """The byte-identity half. This is what every existing install renders."""
        _run(
            f"""
            local r = access("/index.html", nil, {REDIRECT_ON}, {{ server_name = "example.com" }})
            assert(r.redirect == "https://example.com/index.html", "wrong redirect target: " .. tostring(r.redirect))
            """,
            MULTISITE_SAME,
        )

    def test_a_service_on_its_own_port_redirects_to_that_port(self):
        _run(
            f"""
            local r = access("/index.html", nil, {REDIRECT_ON}, {{ server_name = "example.com" }})
            assert(r.redirect == "https://example.com:9443/index.html", "wrong redirect target: " .. tostring(r.redirect))
            """,
            MULTISITE_MOVED,
        )

    def test_a_host_header_that_already_carries_a_port_does_not_gain_a_second_one(self):
        """``http_host`` is client-supplied and routinely carries the port it was reached on. A
        naive concatenation would emit ``example.com:8080:9443``, which is not a URL."""
        _run(
            f"""
            local r = access("/index.html", nil, {REDIRECT_ON}, {{ server_name = "example.com", http_host = "example.com:8080" }})
            assert(r.redirect == "https://example.com:9443/index.html", "wrong redirect target: " .. tostring(r.redirect))
            """,
            MULTISITE_MOVED,
        )

    def test_an_ipv6_literal_host_keeps_its_brackets(self):
        """``[::1]:8080`` -- stripping ``:%d+$`` off a bare IPv6 literal would eat part of the
        address itself, so the bracketed form is matched first."""
        _run(
            f"""
            local r = access("/index.html", nil, {REDIRECT_ON}, {{ server_name = "example.com", http_host = "[::1]:8080" }})
            assert(r.redirect == "https://[::1]:9443/index.html", "wrong redirect target: " .. tostring(r.redirect))
            """,
            MULTISITE_MOVED,
        )


def test_the_acme_challenge_is_not_redirected():
    _run(f"""
        local r = access("/.well-known/acme-challenge/tok3n", "/.well-known/acme-challenge/tok3n", {REDIRECT_ON})
        assert(r.status == nil, "the challenge was answered with status " .. tostring(r.status))
        assert(r.redirect == nil, "the challenge was redirected to " .. tostring(r.redirect))
        """)


def test_the_challenge_is_allowed_on_rather_than_terminated():
    """The distinction that keeps this from being a fail-open: `ssl` declines to redirect, it does
    not answer the request. A status of OK here would end the access chain and skip `whitelist`,
    `blacklist` and the rest for any URL under the challenge prefix."""
    _run(f"""
        local r = access("/.well-known/acme-challenge/tok3n", nil, {REDIRECT_ON})
        assert(r.ret == true, "expected a successful, non-terminating return")
        assert(r.status == nil, "a status here would terminate the access chain at plugin 0")
        """)


def test_the_prefix_is_anchored_and_not_merely_contained():
    """`sub(uri, 1, #prefix)`, not `find`. A path that mentions the challenge further along is an
    ordinary request and must still be redirected."""
    _run(f"""
        local r = access("/redir?next=/.well-known/acme-challenge/tok3n", nil, {REDIRECT_ON})
        assert(r.status == 301, "a path merely containing the prefix must still redirect")
        """)


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
