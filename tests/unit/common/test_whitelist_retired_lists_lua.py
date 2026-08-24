"""``whitelist:init()`` must read ``<KIND>.list`` only while ``WHITELIST_<KIND>_URLS`` is set.

``<KIND>.list`` is written by ``whitelist-download.py`` out of ``WHITELIST_<KIND>_URLS`` and by
nothing else, so the setting -- not the file's presence on disk -- is what makes it meaningful.
``init()`` used to load the file whenever it existed, and that kept a *withdrawn* list enforced:
``push-configs`` and the download jobs are dispatched in the same batch, share
``/var/cache/bunkerweb`` (a persistent volume in every container integration), and a push that
tars the directory while the download job is still retiring the file ships the retired list to
every instance. Seen live in CI run 32508782608: after ``WHITELIST_IP_URLS`` was replaced by
``WHITELIST_RDNS_URLS`` the instance still answered ``IP is whitelisted (info : ip)`` for the
address the withdrawn ``IP.list`` carried.

Runs under plain Lua with OpenResty stubbed -- ``init()`` is pure decision-making around
``io.open`` and ``get_variable``, which is exactly what regressed.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "src" / "common" / "core" / "whitelist" / "whitelist.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

HARNESS = """
local MODULE = "%s"

-- ---- fake filesystem, installed before the module captures io.open ----------------
local FILES = {
    ["/var/cache/bunkerweb/whitelist/www.example.com/IP.list"] = { "192.168.0.254", "10.0.0.0/8" },
    ["/var/cache/bunkerweb/whitelist/www.example.com/RDNS.list"] = { ".bw-services" },
    -- Both multisite services carry the file; only one of them still configures the URLs.
    ["/var/cache/bunkerweb/whitelist/a.example.com/IP.list"] = { "192.168.0.254", "10.0.0.0/8" },
    ["/var/cache/bunkerweb/whitelist/b.example.com/IP.list"] = { "192.168.0.254", "10.0.0.0/8" },
}
local opened = {}
io.open = function(path, mode)
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
-- ngx.var carries no server name during init_by_lua, which is exactly what makes dropping
-- the ctx argument fall back to the global value.
ngx = { ERR = "ERR", INFO = "INFO", OK = "OK", WARN = "WARN", var = {}, get_phase = function() return "init" end }

VARIABLES = {}
local stored = {}

package.loaded["middleclass"] = function(_, parent)
    local klass = {}
    klass.__index = klass
    setmetatable(klass, { __index = parent })
    return klass
end
package.loaded["resty.env"] = { set = function() end }
package.loaded["resty.ipmatcher"] = { new = function() return { match = function() return false end } end }
package.loaded["bunkerweb.plugin"] = {
    initialize = function() end,
    ret = function(_, ok, msg) return { ret = ok, msg = msg } end,
}
package.loaded["bunkerweb.utils"] = {
    has_variable = function() return true end,
    get_ips = function() return {} end,
    get_rdns = function() return {} end,
    regex_match = function() return false end,
    -- Faithful to utils.get_variable: a global table, an optional per-service override that
    -- only applies when site_search is on AND MULTISITE is "yes", and a server name taken from
    -- ctx.bw when there is a ctx and from ngx.var otherwise. Stubbing the first argument alone
    -- let a caller drop `ctx` -- or pass site_search = false -- with no test noticing.
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

local whitelist = dofile(MODULE)

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
    }, whitelist)
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
        if path == "/var/cache/bunkerweb/whitelist/" .. server .. "/" .. kind .. ".list" then return true end
    end
    return false
end

local function opened_ip_list()
    return opened_list("www.example.com", "IP")
end

-- 1. The URL setting is configured: the downloaded list is loaded and merged with the
--    manually configured entries.
local stored_lists = run({ SERVER_NAME = "www.example.com", WHITELIST_IP_URLS = "http://custom-api:8000/list/ip", WHITELIST_IP = "1.2.3.4" })
local lists = stored_lists["plugin_whitelist_lists_www.example.com"]
assert(opened_ip_list(), "IP.list must be read while WHITELIST_IP_URLS is configured")
assert(contains(lists["IP"], "192.168.0.254"), "the downloaded entry is missing")
assert(contains(lists["IP"], "1.2.3.4"), "the manually configured entry is missing")

-- 2. The URL setting is gone but the file is still on disk (a retired list the shared cache
--    directory shipped anyway): the file must NOT be read, and the manual entries must still be.
stored_lists = run({ SERVER_NAME = "www.example.com", WHITELIST_IP = "1.2.3.4", WHITELIST_RDNS_URLS = "http://custom-api:8000/list/rdns" })
lists = stored_lists["plugin_whitelist_lists_www.example.com"]
assert(not opened_ip_list(), "a retired IP.list must not be read once WHITELIST_IP_URLS is gone")
assert(not contains(lists["IP"], "192.168.0.254"), "the retired entry is still enforced")
assert(contains(lists["IP"], "1.2.3.4"), "the manually configured entry must survive the guard")
assert(contains(lists["RDNS"], ".bw-services"), "the kind whose URL setting IS configured must still load")

-- 3. A setting present but blank is not a configured URL.
stored_lists = run({ SERVER_NAME = "www.example.com", WHITELIST_IP_URLS = "   " })
lists = stored_lists["plugin_whitelist_lists_www.example.com"]
assert(not opened_ip_list(), "a blank WHITELIST_IP_URLS must not resurrect the file")
assert(#lists["IP"] == 0, "nothing should have been loaded for IP")

-- 4. Multisite: the guard is per service, so it has to read the setting THROUGH the service it
--    is currently iterating. Service A configures WHITELIST_IP_URLS, service B does not, and
--    both have an IP.list on disk. Only A's may be opened.
--    This is what pins the two arguments the stub used to ignore: dropping the ctx (or passing
--    site_search = false) collapses both services onto the empty global value, and A's list
--    stops being read.
stored_lists = run({
    SERVER_NAME = "a.example.com b.example.com",
    MULTISITE = "yes",
    WHITELIST_IP_URLS = "",
    WHITELIST_IP = "",
}, {
    ["a.example.com"] = { WHITELIST_IP_URLS = "http://custom-api:8000/list/ip" },
    ["b.example.com"] = { WHITELIST_IP_URLS = "" },
})
assert(opened_list("a.example.com", "IP"), "service A configures the URLs, so its IP.list must be read")
assert(not opened_list("b.example.com", "IP"), "service B has no URLs, so its retired IP.list must be ignored")
assert(contains(stored_lists["plugin_whitelist_lists_a.example.com"]["IP"], "192.168.0.254"), "service A lost its downloaded entries")
assert(#stored_lists["plugin_whitelist_lists_b.example.com"]["IP"] == 0, "service B is still enforcing a retired list")

print("OK")
"""


def test_a_retired_list_file_is_not_loaded_without_its_url_setting():
    result = subprocess.run(["lua", "-e", HARNESS % MODULE.as_posix()], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
