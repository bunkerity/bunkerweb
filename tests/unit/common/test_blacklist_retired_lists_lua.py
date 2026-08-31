"""``blacklist:init()`` must bind each ``<KIND>.list`` to the union of the settings that write it.

Sibling of ``test_whitelist_retired_lists_lua.py``, with one difference that is the whole point of
this file: blacklist has **two** producers. ``blacklist-download.py`` writes ``<KIND>.list`` from
``BLACKLIST_<KIND>_URLS`` *and* from ``BLACKLIST_COMMUNITY_LISTS``, whose default is non-empty
(``ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents``). A URLs-only guard — the verbatim port
of the whitelist fix — would therefore silently stop loading ``IP.list`` and ``USER_AGENT.list`` on
a **stock configuration**, i.e. quietly disable the default community blocklists for every user who
never set a URL. Case 1 below is that regression; the rest cover the retired-list behaviour the
guard exists for.

Runs under plain Lua with OpenResty stubbed.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "src" / "common" / "core" / "blacklist" / "blacklist.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

HARNESS = """
local MODULE = "%s"

-- Every kind blacklist:init() enumerates has a file on disk, so any kind the guard wrongly opens
-- shows up as a read rather than as a silent miss.
local KINDS = {
    "IP", "RDNS", "ASN", "USER_AGENT", "URI",
    "IGNORE_IP", "IGNORE_RDNS", "IGNORE_ASN", "IGNORE_USER_AGENT", "IGNORE_URI",
}
local SERVERS = { "www.example.com", "a.example.com", "b.example.com" }

-- ---- fake filesystem, installed before the module captures io.open ----------------
local FILES = {}
for _, server in ipairs(SERVERS) do
    for _, kind in ipairs(KINDS) do
        FILES["/var/cache/bunkerweb/blacklist/" .. server .. "/" .. kind .. ".list"] = { "192.168.0.254" }
    end
end
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
-- The plugin requires bunkerweb.rules at load time; this harness exercises init()'s
-- list reading only, so the composite-rule family is stubbed empty. A plugin-level
-- require with no stub here kills the harness at LOAD, not at an assertion.
package.loaded["bunkerweb.rules"] = {
    parse_family = function() return {}, {} end,
    warnings = function() return {} end,
    for_server = function() return {} end,
}
package.loaded["bunkerweb.plugin"] = {
    initialize = function() end,
    ret = function(_, ok, msg) return { ret = ok, msg = msg } end,
}
package.loaded["bunkerweb.utils"] = {
    has_variable = function() return true end,
    get_multiple_variables = function() return {} end,
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

local blacklist = dofile(MODULE)

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
    }, blacklist)
    local result = instance:init()
    assert(result.ret == true, "init() failed: " .. tostring(result.msg))
    return stored
end

local function opened_list(server, kind)
    for _, path in ipairs(opened) do
        if path == "/var/cache/bunkerweb/blacklist/" .. server .. "/" .. kind .. ".list" then return true end
    end
    return false
end

-- The default blacklist-download.py passes to getenv(), i.e. what a stock deployment runs with.
local STOCK_COMMUNITY = "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"

-- 1. THE REGRESSION A VERBATIM PORT WOULD SHIP. Stock configuration: not one BLACKLIST_*_URLS is
--    set, and BLACKLIST_COMMUNITY_LISTS is at its default. IP.list and USER_AGENT.list are
--    written by the community lists, so both MUST still be read; nothing else is produced.
local stored_lists = run({ SERVER_NAME = "www.example.com", BLACKLIST_COMMUNITY_LISTS = STOCK_COMMUNITY })
assert(opened_list("www.example.com", "IP"), "stock config: the ip: community list still writes IP.list, it must be read")
assert(opened_list("www.example.com", "USER_AGENT"), "stock config: the ua: community list still writes USER_AGENT.list, it must be read")
for _, kind in ipairs({ "RDNS", "ASN", "URI", "IGNORE_IP", "IGNORE_RDNS", "IGNORE_ASN", "IGNORE_USER_AGENT", "IGNORE_URI" }) do
    assert(not opened_list("www.example.com", kind), "stock config: nothing produces " .. kind .. ".list, it must not be read")
end
assert(#stored_lists["plugin_blacklist_lists_www.example.com"]["IP"] == 1, "the community IP entries are missing")

-- 2. The setting is absent from variables.env entirely. The job would still use its getenv()
--    default, so "absent" must mean "the default is in force", never "no producer".
stored_lists = run({ SERVER_NAME = "www.example.com" })
assert(opened_list("www.example.com", "IP"), "an absent BLACKLIST_COMMUNITY_LISTS must fall back to the job's default")
assert(opened_list("www.example.com", "USER_AGENT"), "an absent BLACKLIST_COMMUNITY_LISTS must fall back to the job's default")

-- 3. Community lists explicitly emptied and no URLs: now nothing produces the files, so a list
--    left on disk is debris and must not be enforced.
stored_lists = run({ SERVER_NAME = "www.example.com", BLACKLIST_COMMUNITY_LISTS = "" })
for _, kind in ipairs(KINDS) do
    assert(not opened_list("www.example.com", kind), "with no producer at all, " .. kind .. ".list is retired and must not be read")
end
assert(#stored_lists["plugin_blacklist_lists_www.example.com"]["IP"] == 0, "a retired IP.list is still enforced")

-- 4. A URL setting alone is enough, community lists emptied -- including for an IGNORE_* kind,
--    which has no community producer at all.
run({
    SERVER_NAME = "www.example.com",
    BLACKLIST_COMMUNITY_LISTS = "",
    BLACKLIST_RDNS_URLS = "http://custom-api:8000/list/rdns",
    BLACKLIST_IGNORE_IP_URLS = "http://custom-api:8000/list/ip",
})
assert(opened_list("www.example.com", "RDNS"), "a configured BLACKLIST_RDNS_URLS must load RDNS.list")
assert(opened_list("www.example.com", "IGNORE_IP"), "a configured BLACKLIST_IGNORE_IP_URLS must load IGNORE_IP.list")
assert(not opened_list("www.example.com", "IP"), "IP.list has no producer here and must stay unread")
assert(not opened_list("www.example.com", "IGNORE_RDNS"), "IGNORE_RDNS.list has no producer here and must stay unread")

-- 5. A blank setting is not a configured producer, on either side of the union.
run({ SERVER_NAME = "www.example.com", BLACKLIST_COMMUNITY_LISTS = "   ", BLACKLIST_IP_URLS = "   " })
assert(not opened_list("www.example.com", "IP"), "blank URLs and blank community lists must not resurrect IP.list")

-- 6. The community prefix decides the kind, exactly as blacklist-download.py maps it.
run({ SERVER_NAME = "www.example.com", BLACKLIST_COMMUNITY_LISTS = "rdns:something" })
assert(opened_list("www.example.com", "RDNS"), "an rdns: community entry produces RDNS.list")
assert(not opened_list("www.example.com", "USER_AGENT"), "an rdns: entry must not enable USER_AGENT.list")

-- 6b. An id the job does not recognise produces NOTHING. The job gates the whole mapping on
--     `community_id in COMMUNITY_LISTS` (blacklist-download.py:100) and only warns otherwise, so
--     its `else: kind = "IP"` is reachable only for a KNOWN id with an unmapped prefix -- it is
--     not a fallback for garbage. Treating garbage as "IP is produced" would keep a retired
--     IP.list enforced for the price of one typo, which is the hole the guard exists to close.
-- ("ip:typo" is deliberately absent: it carries a RECOGNISED prefix, and matching on the prefix
--  rather than on the full id is a stated limit of this guard -- see the note in blacklist.lua.)
for _, garbage in ipairs({ "typo", "nope:whatever", "ip", ":leading" }) do
    run({ SERVER_NAME = "www.example.com", BLACKLIST_COMMUNITY_LISTS = garbage })
    for _, kind in ipairs(KINDS) do
        assert(not opened_list("www.example.com", kind), "community id " .. garbage .. " produces nothing, yet " .. kind .. ".list was read")
    end
end

-- 7. Multisite: BOTH halves of the union are per-service settings, so BOTH have to be read
--    THROUGH the service being iterated. Service A keeps the community default AND sets
--    BLACKLIST_RDNS_URLS; service B has emptied the community lists and sets no URLs; both carry
--    every file on disk. Varying only the community half here left the ctx on the URLs lookup
--    unpinned -- dropping it there collapses every service onto the global value and nothing
--    noticed.
run({
    SERVER_NAME = "a.example.com b.example.com",
    MULTISITE = "yes",
    BLACKLIST_COMMUNITY_LISTS = "",
    BLACKLIST_RDNS_URLS = "",
}, {
    ["a.example.com"] = { BLACKLIST_COMMUNITY_LISTS = STOCK_COMMUNITY, BLACKLIST_RDNS_URLS = "http://custom-api:8000/list/rdns" },
    ["b.example.com"] = { BLACKLIST_COMMUNITY_LISTS = "", BLACKLIST_RDNS_URLS = "" },
})
assert(opened_list("a.example.com", "IP"), "service A keeps the community lists, so its IP.list must be read")
assert(opened_list("a.example.com", "USER_AGENT"), "service A keeps the community lists, so its USER_AGENT.list must be read")
assert(opened_list("a.example.com", "RDNS"), "service A sets BLACKLIST_RDNS_URLS, so its RDNS.list must be read")
assert(not opened_list("b.example.com", "IP"), "service B has no producer, so its retired IP.list must be ignored")
assert(not opened_list("b.example.com", "USER_AGENT"), "service B has no producer, so its retired USER_AGENT.list must be ignored")
assert(not opened_list("b.example.com", "RDNS"), "service B sets no URLs, so its retired RDNS.list must be ignored")

print("OK")
"""


def test_blacklist_binds_each_list_to_the_union_of_its_producers():
    result = subprocess.run(["lua", "-e", HARNESS % MODULE.as_posix()], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
