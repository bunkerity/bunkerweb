"""Rejected init must raise before replacing the previous policy; logging is not rejection."""

import shutil
import subprocess
from pathlib import Path

import pytest

from test_load_plugin import HELPERS_LUA, RAW_PREAMBLE, _run_lua

ROOT = Path(__file__).resolve().parents[3]
LUA = shutil.which("lua") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


@pytest.mark.parametrize("failure", ["missing", "open", "read"])
def test_manifest_io_failures_keep_their_cause(failure):
    setup = {
        "missing": 'io.open = function() return nil, "No such file", 2 end',
        "open": 'io.open = function() return nil, "Permission denied", 13 end',
        "read": """io.open = function()
            return { read = function() return nil, "Input/output error" end,
                     close = function() closed = true end }
        end""",
    }[failure]
    preamble = RAW_PREAMBLE.replace("--[[DECODE_BODY]]", 'error("decode must not run after an I/O error")')
    preamble = preamble.replace("local helpers = dofile(arg[1])", "local closed = false\n" + setup + "\nlocal helpers = dofile(arg[1])")
    checks = {
        "missing": 'assert(ok == nil, "a directory without plugin.json must be skipped")',
        "open": 'assert(ok == false and plugin_or_err:find("Permission denied", 1, true), tostring(plugin_or_err))',
        "read": 'assert(ok == false and closed and plugin_or_err:find("Input/output error", 1, true), tostring(plugin_or_err))',
    }[failure]
    _run_lua(preamble + checks, str(HELPERS_LUA))


INIT_HARNESS = r"""
local failure, body_path = arg[1], arg[2]
local touched = false
local stored = {}
local store = {
    flush_lru = function()
        if failure == "flush" then return false, "no LRU" end
        touched = true
        return true
    end,
    delete_all = function() touched = true; return true end,
    set = function(_, key, value)
        if failure == "set:" .. key then return false, "write failed" end
        stored[key] = value
        return true
    end,
}
local helpers = {
    load_plugin = function()
        if failure == "manifest" then return false, "invalid JSON at /plugin/plugin.json" end
        if failure == "absent-manifest" then return nil, "no plugin.json" end
        return true, { id = "probe", version = "1.0" }
    end,
    load_variables = function()
        if failure == "variables" then return false, "invalid variables" end
        return true, { global = { IS_LOADING = "no" } }
    end,
    order_plugins = function()
        if failure == "order" then return false, "invalid order" end
        return true, { init = {} }, {}
    end,
}
package.preload["bunkerweb.helpers"] = function() return helpers end
package.preload["bunkerweb.datastore"] = function()
    return { new = function() return store end, seal = function() return true end }
end
package.preload["bunkerweb.logger"] = function() return { new = function() return { log = function() end } end } end
package.preload["bunkerweb.cachestore"] = function()
    if failure == "cache" then error("cache construction failed") end
    return { new = function() return { purge = function() return true end } end }
end
package.preload["cjson"] = function() return { encode = function() return "[]" end } end
package.preload["resty.random"] = function() return {} end
package.preload["resty.string"] = function() return {} end
ngx = { config = { subsystem = "http" }, shared = {}, INFO = 1, ERR = 2, NOTICE = 3, WARN = 4 }
local body = assert(loadfile(body_path))
io.open = function(path)
    if path == "/var/run/bunkerweb/api-internal.token" then
        return { read = function() return string.rep("a", 64) end, close = function() end }
    end
    if path == "/etc/nginx/variables.env" then
        if failure == "missing-variables" then return nil, "No such file", 2 end
        return { close = function() end }
    end
    return nil, "No such file", 2
end
io.lines = function() return function() return nil end end
io.popen = function()
    return {
        lines = function()
            local yielded = false
            return function()
                if not yielded then yielded = true; return "/plugin" end
            end
        end,
        close = function() return true end,
    }
end
os.execute = function() return true end
local ok, err = pcall(body)
if failure == "none" or failure == "absent-manifest" then
    assert(ok, tostring(err))
    assert(stored.variables and stored.plugins_order, "valid configuration did not reach the store")
    if failure == "absent-manifest" then assert(#stored.plugins == 0) end
else
    assert(not ok, "init returned normally after " .. failure .. "; nginx would accept it")
    if failure == "manifest" or failure == "variables" or failure == "missing-variables" or failure == "order" or failure == "cache" then
        assert(not touched, "rejected init mutated the previous policy")
    end
end
"""


@pytest.mark.parametrize("template", ["init-lua.conf", "init-stream-lua.conf"])
@pytest.mark.parametrize(
    "failure",
    ["manifest", "missing-variables", "variables", "order", "cache", "flush", "set:plugins", "set:variables", "set:plugins_order", "none", "absent-manifest"],
)
def test_init_rejects_invalid_configuration(tmp_path, template, failure):
    source = (ROOT / "src/common/confs" / template).read_text()
    block = source.split("init_by_lua_block {", 1)[1].split("\n}", 1)[0]
    body = tmp_path / "init.lua"
    body.write_text(block)
    result = subprocess.run([LUA, "-", failure, str(body)], input=INIT_HARNESS, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
