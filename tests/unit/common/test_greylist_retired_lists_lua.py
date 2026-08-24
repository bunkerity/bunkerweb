"""``greylist:init()`` must read ``<KIND>.list`` only while ``GREYLIST_<KIND>_URLS`` is set.

Sibling of ``test_whitelist_retired_lists_lua.py`` — greylist carries the same unconditional read
and therefore the same defect: ``<KIND>.list`` is written by ``greylist-download.py`` out of
``GREYLIST_<KIND>_URLS`` and by nothing else, so a list withdrawn from the configuration stayed
enforced once a `push-configs` run tarred ``/var/cache/bunkerweb`` while the download job was still
retiring the file. Greylisting is a *bypass* of the later plugins, so the stale entry lets traffic
through checks the operator has re-enabled.

Runs under plain Lua with OpenResty stubbed.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "src" / "common" / "core" / "greylist" / "greylist.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

HARNESS = """
local MODULE = "%s"

-- ---- fake filesystem, installed before the module captures io.open ----------------
local FILES = {
    ["/var/cache/bunkerweb/greylist/www.example.com/IP.list"] = { "192.168.0.254", "10.0.0.0/8" },
    ["/var/cache/bunkerweb/greylist/www.example.com/RDNS.list"] = { ".bw-services" },
    -- Both multisite services carry the file; only one of them still configures the URLs.
    ["/var/cache/bunkerweb/greylist/a.example.com/IP.list"] = { "192.168.0.254", "10.0.0.0/8" },
    ["/var/cache/bunkerweb/greylist/b.example.com/IP.list"] = { "192.168.0.254", "10.0.0.0/8" },
}
local opened = {}
io.open = function(path)
    opened[#opened + 1] = path
    local lines = FILES[path]
    if not lines then
        return nil, "no such file"
    end
    local index = 0
    return {
        lines = function()
            return function()
                index = index + 1
                return lines[index]
            end
        end,
        close = function() end,
    }
end

-- ---- OpenResty and BunkerWeb stubs -----------------------------------------------
-- ngx.var carries no server name during init_by_lua, which is what makes dropping the ctx
-- argument fall back to the global value.
ngx = { ERR = "ERR", INFO = "INFO", var = {}, get_phase = function() return "init" end }

VARIABLES = {}
local stored = {}

package.loaded["middleclass"] = function(_, parent)
    local klass = {}
    klass.__index = klass
    setmetatable(klass, { __index = parent })
    return klass
end
package.loaded["resty.ipmatcher"] = { new = function() return { match = function() return false end } end }
package.loaded["bunkerweb.plugin"] = {
    initialize = function() end,
    ret = function(_, ok, msg) return { ret = ok, msg = msg } end,
}
package.loaded["bunkerweb.utils"] = {
    has_variable = function() return true end,
    get_deny_status = function() return 403 end,
    get_rdns = function() return {} end,
    rdns_forward_confirmed = function() return false end,
    regex_match = function() return false end,
    -- Faithful to utils.get_variable: a global table, an optional per-service override that only
    -- applies when site_search is on AND MULTISITE is "yes", and a server name taken from ctx.bw
    -- when there is a ctx and from ngx.var otherwise.
    get_variable = function(name, site_search, ctx)
        if site_search == nil then
            site_search = true
        end
        local value = VARIABLES.global[name]
        if site_search and VARIABLES.global.MULTISITE == "yes" then
            local server = ctx and ctx.bw and ctx.bw.server_name or ngx.var.server_name
            if server and VARIABLES[server] and VARIABLES[server][name] ~= nil then
                value = VARIABLES[server][name]
            end
        end
        if value == nil then
            return nil, "not found"
        end
        return value, "success"
    end,
    deduplicate_list = function(list)
        local seen, out = {}, {}
        for _, item in ipairs(list) do
            if not seen[item] then
                seen[item] = true
                out[#out + 1] = item
            end
        end
        return out
    end,
}

local greylist = dofile(MODULE)

local function run(globals, per_service)
    VARIABLES = per_service or {}
    VARIABLES.global = globals
    opened = {}
    stored = {}
    local instance = setmetatable({
        is_loading = false,
        is_request = false,
        logger = { log = function() end },
        internalstore = {
            set = function(_, key, value)
                stored[key] = value
                return true
            end,
        },
    }, greylist)
    local result = instance:init()
    assert(result.ret == true, "init() failed: " .. tostring(result.msg))
    return stored
end

local function contains(list, wanted)
    for _, item in ipairs(list) do
        if item == wanted then return true end
    end
    return false
end

local function opened_list(server, kind)
    for _, path in ipairs(opened) do
        if path == "/var/cache/bunkerweb/greylist/" .. server .. "/" .. kind .. ".list" then return true end
    end
    return false
end

-- 1. The URL setting is configured: the downloaded list is loaded.
local stored_lists = run({ SERVER_NAME = "www.example.com", GREYLIST_IP_URLS = "http://custom-api:8000/list/ip" })
assert(opened_list("www.example.com", "IP"), "IP.list must be read while GREYLIST_IP_URLS is configured")
assert(contains(stored_lists["plugin_greylist_lists_www.example.com"]["IP"], "192.168.0.254"), "the downloaded entry is missing")

-- 2. The URL setting is gone but the file is still on disk: it must NOT be read, while a kind
--    whose setting IS configured still loads.
stored_lists = run({ SERVER_NAME = "www.example.com", GREYLIST_RDNS_URLS = "http://custom-api:8000/list/rdns" })
local lists = stored_lists["plugin_greylist_lists_www.example.com"]
assert(not opened_list("www.example.com", "IP"), "a retired IP.list must not be read once GREYLIST_IP_URLS is gone")
assert(#lists["IP"] == 0, "the retired entries are still enforced")
assert(contains(lists["RDNS"], ".bw-services"), "the kind whose URL setting IS configured must still load")

-- 3. A setting present but blank is not a configured URL.
stored_lists = run({ SERVER_NAME = "www.example.com", GREYLIST_IP_URLS = "   " })
assert(not opened_list("www.example.com", "IP"), "a blank GREYLIST_IP_URLS must not resurrect the file")
assert(#stored_lists["plugin_greylist_lists_www.example.com"]["IP"] == 0, "nothing should have been loaded for IP")

-- 4. Multisite: the guard reads the setting THROUGH the service it is iterating. Dropping the ctx
--    (or passing site_search = false) collapses both services onto the empty global value.
stored_lists = run({
    SERVER_NAME = "a.example.com b.example.com",
    MULTISITE = "yes",
    GREYLIST_IP_URLS = "",
}, {
    ["a.example.com"] = { GREYLIST_IP_URLS = "http://custom-api:8000/list/ip" },
    ["b.example.com"] = { GREYLIST_IP_URLS = "" },
})
assert(opened_list("a.example.com", "IP"), "service A configures the URLs, so its IP.list must be read")
assert(not opened_list("b.example.com", "IP"), "service B has no URLs, so its retired IP.list must be ignored")
assert(contains(stored_lists["plugin_greylist_lists_a.example.com"]["IP"], "192.168.0.254"), "service A lost its downloaded entries")
assert(#stored_lists["plugin_greylist_lists_b.example.com"]["IP"] == 0, "service B is still enforcing a retired list")

print("OK")
"""


def test_a_retired_greylist_file_is_not_loaded_without_its_url_setting():
    result = subprocess.run(["lua", "-e", HARNESS % MODULE.as_posix()], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
