"""``dnsbl:init()`` must read ``IGNORE_IP.list`` only while ``DNSBL_IGNORE_IP_URLS`` is set.

Sibling of ``test_whitelist_retired_lists_lua.py``. ``IGNORE_IP.list`` is written by
``dnsbl-download.py`` out of ``DNSBL_IGNORE_IP_URLS`` and by nothing else, so the file is debris
once the setting is withdrawn — and here the debris **fails open**: the list is an *exemption*
from the DNSBL check, so a stale entry keeps letting an address through a check the operator has
deliberately re-armed. The file survives on the instance because ``push-configs`` tars
``/var/cache/bunkerweb`` while the download job is still retiring it.

Runs under plain Lua with OpenResty stubbed.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "src" / "common" / "core" / "dnsbl" / "dnsbl.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

HARNESS = """
local MODULE = "%s"

-- ---- fake filesystem -------------------------------------------------------------
local FILES = {
    ["/var/cache/bunkerweb/dnsbl/www.example.com/IGNORE_IP.list"] = { "192.168.0.254", "10.0.0.0/8" },
    -- Both multisite services carry the file; only one of them still configures the URLs.
    ["/var/cache/bunkerweb/dnsbl/a.example.com/IGNORE_IP.list"] = { "192.168.0.254" },
    ["/var/cache/bunkerweb/dnsbl/b.example.com/IGNORE_IP.list"] = { "192.168.0.254" },
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
ngx = {
    ERR = "ERR",
    INFO = "INFO",
    NOTICE = "NOTICE",
    var = {},
    get_phase = function() return "init" end,
    thread = { spawn = function() end, wait = function() end },
}

VARIABLES = {}
local stored = {}

package.loaded["middleclass"] = function(_, parent)
    local klass = {}
    klass.__index = klass
    setmetatable(klass, { __index = parent })
    return klass
end
package.loaded["resty.ipmatcher"] = { new = function() return { match = function() return false end } end }
package.loaded["resty.dns.resolver"] = { arpa_str = function(addr) return addr .. ".in-addr.arpa" end }
package.loaded["bunkerweb.plugin"] = {
    initialize = function() end,
    ret = function(_, ok, msg) return { ret = ok, msg = msg } end,
}
package.loaded["bunkerweb.utils"] = {
    has_variable = function() return true end,
    get_deny_status = function() return 403 end,
    get_ips = function() return {} end,
    kill_all_threads = function() end,
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

local dnsbl = dofile(MODULE)

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
    }, dnsbl)
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

local function opened_list(server)
    for _, path in ipairs(opened) do
        if path == "/var/cache/bunkerweb/dnsbl/" .. server .. "/IGNORE_IP.list" then return true end
    end
    return false
end

-- 1. The URL setting is configured: the downloaded exemption list is loaded.
local stored_lists = run({ SERVER_NAME = "www.example.com", DNSBL_IGNORE_IP_URLS = "http://custom-api:8000/list/ip" })
assert(opened_list("www.example.com"), "IGNORE_IP.list must be read while DNSBL_IGNORE_IP_URLS is configured")
assert(contains(stored_lists["plugin_dnsbl_lists_www.example.com"]["IGNORE_IP"], "192.168.0.254"), "the downloaded entry is missing")

-- 2. The URL setting is gone but the file is still on disk: it must NOT be read. This is the
--    fail-open case -- a stale exemption silently un-arms the DNSBL for that address.
stored_lists = run({ SERVER_NAME = "www.example.com" })
assert(not opened_list("www.example.com"), "a retired IGNORE_IP.list must not be read once DNSBL_IGNORE_IP_URLS is gone")
assert(#stored_lists["plugin_dnsbl_lists_www.example.com"]["IGNORE_IP"] == 0, "the retired exemption is still live")

-- 3. A setting present but blank is not a configured URL.
stored_lists = run({ SERVER_NAME = "www.example.com", DNSBL_IGNORE_IP_URLS = "   " })
assert(not opened_list("www.example.com"), "a blank DNSBL_IGNORE_IP_URLS must not resurrect the file")
assert(#stored_lists["plugin_dnsbl_lists_www.example.com"]["IGNORE_IP"] == 0, "nothing should have been loaded")

-- 4. Multisite: the guard reads the setting THROUGH the service it is iterating.
stored_lists = run({
    SERVER_NAME = "a.example.com b.example.com",
    MULTISITE = "yes",
    DNSBL_IGNORE_IP_URLS = "",
}, {
    ["a.example.com"] = { DNSBL_IGNORE_IP_URLS = "http://custom-api:8000/list/ip" },
    ["b.example.com"] = { DNSBL_IGNORE_IP_URLS = "" },
})
assert(opened_list("a.example.com"), "service A configures the URLs, so its IGNORE_IP.list must be read")
assert(not opened_list("b.example.com"), "service B has no URLs, so its retired IGNORE_IP.list must be ignored")
assert(contains(stored_lists["plugin_dnsbl_lists_a.example.com"]["IGNORE_IP"], "192.168.0.254"), "service A lost its exemptions")
assert(#stored_lists["plugin_dnsbl_lists_b.example.com"]["IGNORE_IP"] == 0, "service B is still exempting on a retired list")

print("OK")
"""


def test_a_retired_dnsbl_ignore_list_is_not_loaded_without_its_url_setting():
    result = subprocess.run(["lua", "-e", HARNESS % MODULE.as_posix()], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
