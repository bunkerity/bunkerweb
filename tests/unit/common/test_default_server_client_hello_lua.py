"""The default server's `ssl_client_hello_by_lua_block`, rendered and EXECUTED (dev c5c0ab37e).

The core hook (`tlsdrop.hook`) now calls the plugins that export `client_hello(hello)` for the default server as well
as for every service. The legacy `ssl_client_hello_default()` loop of the default server must keep working for every
other plugin, and must not call a second time one the hook already served: a plugin that exports both would otherwise
see each handshake twice (PRO acme and antiddos export the legacy method today).

The block is run against stub plugins; a grep would pass on a loop that builds the skip list and never reads it.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_ban_lease_lua import LUA, needs_lua  # noqa: E402
from test_default_server_runners_lua import lua_block, render  # noqa: E402

DEFAULT_TEMPLATE = "default-server-http.conf"

HARNESS = r"""
local block_path = arg[1]

local calls, logs, hook_calls, exited = {}, {}, 0, nil
local legacy_ids = {}
local order = { ssl_client_hello_default = {} }
local plugins = {}
local hello_ids = {}
local hook_result = nil

package.loaded["bunkerweb.logger"] = { new = function() return { log = function(_, level, message) logs[#logs + 1] = message end } end }
package.loaded["bunkerweb.datastore"] = { new = function()
    return { get = function(_, key)
        if key == "plugins_order" then return order, "success" end
        return nil, "not found"
    end }
end }
package.loaded["bunkerweb.helpers"] = {
    require_plugin = function(id) return plugins[id], "ok" end,
    new_plugin = function(plugin_lua) return true, plugin_lua end,
    call_plugin = function(plugin_obj, phase)
        calls[#calls + 1] = phase .. ":" .. plugin_obj.id
        return true, { ret = true, msg = "ok" }
    end,
}
package.loaded["bunkerweb.tlsdrop"] = {
    hook = function() hook_calls = hook_calls + 1 return hook_result end,
    is_client_hello_plugin = function(id) return hello_ids[id] == true end,
}
ngx = { INFO = 6, ERR = 3, WARN = 4, HTTP_CLOSE = 444, shared = { internalstore = {} }, exit = function(status) exited = status return status end }

local function plugin(id, methods)
    local module = { id = id }
    for name, fn in pairs(methods) do module[name] = fn end
    plugins[id] = module
end

local file = assert(io.open(block_path))
local source = file:read("*a")
file:close()
local function run() return assert(load(source, "block"))() end
"""


def run_block(tmp_path: Path, body: str) -> None:
    assert LUA is not None
    (tmp_path / "block.lua").write_text(lua_block(render(DEFAULT_TEMPLATE), "ssl_client_hello_by_lua_block"), encoding="utf-8")
    result = subprocess.run([LUA, "-", str(tmp_path / "block.lua")], input=HARNESS + body, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr + result.stdout


@needs_lua
def test_a_plugin_the_hook_already_served_is_not_called_through_its_legacy_method(tmp_path):
    run_block(
        tmp_path,
        r"""
plugin("both", { ssl_client_hello_default = function() end })
plugin("legacy", { ssl_client_hello_default = function() end })
order.ssl_client_hello_default = { "both", "legacy" }
hello_ids.both = true
assert(run() == true)
assert(hook_calls == 1, "the core hook runs first, once")
assert(#calls == 1 and calls[1] == "ssl_client_hello_default:legacy", table.concat(calls, ","))
local skipped = false
for _, line in ipairs(logs) do if line:find("both", 1, true) and line:find("client_hello() hook", 1, true) then skipped = true end end
assert(skipped, "the skip is logged, like every skipped plugin")
""",
    )


@needs_lua
def test_without_hook_plugins_the_legacy_loop_runs_every_plugin_as_before(tmp_path):
    run_block(
        tmp_path,
        r"""
plugin("a", { ssl_client_hello_default = function() end })
plugin("b", { ssl_client_hello_default = function() end })
order.ssl_client_hello_default = { "a", "b" }
assert(run() == true)
assert(table.concat(calls, ",") == "ssl_client_hello_default:a,ssl_client_hello_default:b")
""",
    )


@needs_lua
def test_a_handshake_the_hook_closed_ends_the_phase_before_the_legacy_loop(tmp_path):
    run_block(
        tmp_path,
        r"""
plugin("a", { ssl_client_hello_default = function() end })
order.ssl_client_hello_default = { "a" }
hook_result = true
run()
assert(hook_calls == 1 and #calls == 0 and exited == nil)
""",
    )
