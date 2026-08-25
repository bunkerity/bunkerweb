"""``cors:self_origin`` — the origin the plugin compares an incoming ``Origin`` against.

Call site C2. The origin used to be built by concatenating the scheme and ``server_name``, so it
carried no port. That is right on a default install — ``misc/integrations/docker.yml:16-18``
publishes ``443:8443``, so the browser sends ``https://example.com`` and the rendered 8443 is not
the reachable port — and wrong the moment a service declares ports of its own: the emitted origin
then never matches the browser's and every same-site request looks cross-origin.

``tests/unit/common/test_lua_public_authority.py`` covers ``public_authority`` itself and asserts,
by source grep, that this file calls it. What was missing is the behaviour of the call site: a grep
cannot tell an origin built with the right authority from one built with the wrong argument order,
and the **equal** branch — every existing deployment — is the one that must not change. So
``cors.lua`` is loaded and ``self_origin`` is actually called here, with the real
``public_authority`` source lifted out of ``utils.lua`` rather than stubbed.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORS_LUA = ROOT / "src" / "common" / "core" / "cors" / "cors.lua"
UTILS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"
LUA_PATH = ROOT / "src" / "bw" / "lua"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")


def utils_source(*names: str) -> str:
    """The shipped source of the named helpers plus the ``port_list`` local they share.

    Same lift as ``test_ssl_acme_challenge_not_redirected.py``: ``utils.lua`` cannot be required
    outside OpenResty (its logger pulls in ``ngx.errlog``), and a stub that merely mimicked
    ``public_authority`` would keep passing while the real one broke.
    """
    text = UTILS_LUA.read_text(encoding="utf-8")
    chunks = [re.search(r"^local function port_list\(.*?^end$", text, re.S | re.M)]
    chunks += [re.search(rf"^utils\.{name} = function.*?^end$", text, re.S | re.M) for name in names]
    for name, chunk in zip(("port_list",) + names, chunks):
        assert chunk, f"{name} not found in utils.lua -- renamed?"
    return "\n".join(chunk.group(0) for chunk in chunks)


PREAMBLE = r"""
package.path = arg[2] .. "/?.lua;" .. package.path
_G.ngx = { HTTP_NO_CONTENT = 204 }

local class = require "middleclass"
local plugin = class("plugin")
function plugin:initialize(id, ctx)
    self.id, self.ctx, self.variables = id, ctx, {}
end
function plugin:ret(ret, msg, status, redirect, data)
    return { ret = ret, msg = msg, status = status, redirect = redirect, data = data }
end
package.preload["bunkerweb.plugin"] = function() return plugin end

local utils = {}
-- Only the three cors.lua binds at load time have to exist; regex_match and get_deny_status are
-- never reached by self_origin, but an absent key would be a nil upvalue at require time.
utils.regex_match = function() return nil end
utils.get_deny_status = function() return 403 end
package.preload["bunkerweb.utils"] = function() return utils end

local function self_origin(server_name, https_configured)
    local cors = dofile(arg[1])
    return cors:new({ bw = { server_name = server_name, https_configured = https_configured } }):self_origin()
end
"""


def run(body: str, variables_table: str) -> None:
    harness = (
        PREAMBLE
        + (
            "local internalstore = { get = function() return %s, nil end }\n%s\n"
            % (variables_table, utils_source("listen_port_override", "host_without_port", "public_authority"))
        )
        + body
    )
    result = subprocess.run([LUA, "-", str(CORS_LUA), str(LUA_PATH)], input=harness, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


SAME = '{ global = { MULTISITE = "yes", HTTP_PORT = "8080", HTTPS_PORT = "8443" }, ["a.example.com"] = { HTTPS_PORT = "8443" } }'
MOVED = '{ global = { MULTISITE = "yes", HTTP_PORT = "8080", HTTPS_PORT = "8443" }, ["a.example.com"] = { HTTP_PORT = "9080", HTTPS_PORT = "9443" } }'


class TestTheEqualBranch:
    """The half that carries the whole install base: an origin that gained a port here would stop
    matching the browser's and turn CORS from allow into deny on every existing deployment."""

    def test_a_service_that_did_not_move_gets_a_bare_https_origin(self):
        run(
            """
            local origin = self_origin("a.example.com", "yes")
            assert(origin == "https://a.example.com", "wrong self origin: " .. tostring(origin))
            """,
            SAME,
        )

    def test_a_service_that_did_not_move_gets_a_bare_http_origin(self):
        """``https_configured ~= "yes"`` picks the scheme AND the setting the port comes from, so
        the two branches are not interchangeable."""
        run(
            """
            local origin = self_origin("a.example.com", "no")
            assert(origin == "http://a.example.com", "wrong self origin: " .. tostring(origin))
            """,
            SAME,
        )


class TestTheMovedBranch:
    def test_the_https_origin_carries_the_service_https_port(self):
        run(
            """
            local origin = self_origin("a.example.com", "yes")
            assert(origin == "https://a.example.com:9443", "wrong self origin: " .. tostring(origin))
            """,
            MOVED,
        )

    def test_the_http_origin_carries_the_service_http_port(self):
        """Anti-swap: with both settings moved to different values, reading the wrong one is
        visible. HTTP must answer 9080, not 9443."""
        run(
            """
            local origin = self_origin("a.example.com", "no")
            assert(origin == "http://a.example.com:9080", "wrong self origin: " .. tostring(origin))
            """,
            MOVED,
        )

    def test_an_unknown_host_keeps_a_bare_origin(self):
        """The default server answers unknown Hosts; inventing a port for one would emit an origin
        that matches nothing."""
        run(
            """
            local origin = self_origin("other.example.com", "yes")
            assert(origin == "https://other.example.com", "wrong self origin: " .. tostring(origin))
            """,
            MOVED,
        )
