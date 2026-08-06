"""Execute the Stream timer dispatcher with HTTP-only and Stream-capable plugins."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONF = ROOT / "src" / "common" / "confs" / "init-stream-lua.conf"
LUA = shutil.which("lua") or shutil.which("luajit")

pytestmark = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


def _lua_block(path: Path, directive: str) -> str:
    source = path.read_text(encoding="utf-8")
    start = source.index("{", source.index(f"{directive}_by_lua_block"))
    body_start, depth = start + 1, 0
    for index in range(start, len(source)):
        depth += source[index] == "{"
        depth -= source[index] == "}"
        if depth == 0:
            return source[body_start:index]
    raise AssertionError(f"unbalanced {directive}_by_lua_block")


PREAMBLE = r"""
local calls, scheduled = {}, {}
ngx = {
    ERR = "ERR", INFO = "INFO", WARN = "WARN",
    worker = { id = function() return 0 end, pid = function() return 1 end },
    timer = { at = function(delay, callback) scheduled[#scheduled + 1] = { delay, callback }; return true end },
    shared = { internalstore_stream = {} },
}

package.loaded["bunkerweb.ban_sync"] = { reconcile = function() return true end }
package.loaded["bunkerweb.logger"] = { new = function() return { log = function() end } end }
package.loaded["bunkerweb.utils"] = { get_variable = function(name) return name == "IS_LOADING" and "no" or "INFO" end }
package.loaded["bunkerweb.helpers"] = {
    require_plugin = function(id) return { id = id, timer = function() end } end,
    new_plugin = function(plugin) return true, plugin end,
    call_plugin = function(plugin) calls[#calls + 1] = plugin.id; return true, { ret = true, msg = "ok" } end,
}
package.loaded["bunkerweb.datastore"] = {
    new = function()
        return {
            get = function(_, key)
                if key == "plugins_order" then return { timer = { "http-only", "badbehavior", "metrics", "sessions" } } end
                if key == "plugin_http-only" then return { stream = "no" } end
                if key == "plugin_badbehavior" or key == "plugin_sessions" then return { stream = "yes" } end
                if key == "plugin_metrics" then return { stream = "partial" } end
                return nil, "not found"
            end,
        }
    end,
}
"""


def test_stream_timer_skips_http_only_plugins():
    script = (
        PREAMBLE
        + "\nlocal function run()\n"
        + _lua_block(CONF, "init_worker")
        + r"""
end
run()
assert(#scheduled == 1 and scheduled[1][1] == 0, "initial timer was not scheduled")
scheduled[1][2](false)
assert(table.concat(calls, ",") == "badbehavior,metrics,sessions", "only Stream-capable timers must run")
print("OK")
"""
    )
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
