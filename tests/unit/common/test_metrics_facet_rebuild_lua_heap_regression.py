"""The request-facet rebuild and trim scripts must read the retained list in bounded slices.

``REBUILD_SCRIPT`` read the whole list with one ``LRANGE 0 -1`` and decoded every row inside one ``EVAL``. Redis counts the
Lua heap against ``maxmemory``, so on a memory-capped ``allkeys-lru`` Redis the first start after an upgrade evicted most of
the stored reports. This test runs the real script text from ``metrics.lua`` against an in-memory Redis stand-in that records
every ``LRANGE`` and asserts no call is wider than a slice while the rebuilt facets stay correct.
"""

import re

import pytest
from _lua_state_helpers import BASE_LUA  # type: ignore
from _t2_helpers import CORE, LUA, run_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

SOURCE = (CORE / "metrics" / "metrics.lua").read_text()
SCRIPTS = dict(re.findall(r"local (\w+_SCRIPT) = \[==\[(.*?)\]==\]", SOURCE, re.S))
FIELDS = ["ip", "country", "method", "url", "status", "reason", "server_name", "security_mode"]
SLICE_MAX = 256

FAKE_REDIS = r"""
STORE = { strings = {}, lists = {}, hashes = {} }
LRANGES = {}
local function fkey(k) return k end
local function call(cmd, key, ...)
    local a = { ... }
    if cmd == "GET" then return STORE.strings[key] or false
    elseif cmd == "SET" then
        for i = 1, #a do if a[i] == "NX" and STORE.strings[key] ~= nil then return false end end
        STORE.strings[key] = a[1] return { ok = "OK" }
    elseif cmd == "DEL" then STORE.strings[key], STORE.lists[key], STORE.hashes[key] = nil, nil, nil return 1
    elseif cmd == "LLEN" then return #(STORE.lists[key] or {})
    elseif cmd == "TYPE" then
        if STORE.lists[key] then return { ok = "list" } elseif STORE.hashes[key] then return { ok = "hash" } elseif STORE.strings[key] then return { ok = "string" } end
        return { ok = "none" }
    elseif cmd == "LRANGE" then
        local list, s, e = STORE.lists[key] or {}, a[1], a[2]
        LRANGES[#LRANGES + 1] = { s, e }
        if e < 0 then e = #list + e end
        local out = {}
        for i = s + 1, math.min(e + 1, #list) do out[#out + 1] = list[i] end
        return out
    elseif cmd == "LTRIM" then
        local list, s = STORE.lists[key] or {}, a[1]
        local out = {}
        for i = s + 1, #list do out[#out + 1] = list[i] end
        STORE.lists[key] = out return { ok = "OK" }
    elseif cmd == "HINCRBY" then
        local h = STORE.hashes[key] or {}
        STORE.hashes[key] = h
        h[a[1]] = (h[a[1]] or 0) + a[2]
        return h[a[1]]
    elseif cmd == "HDEL" then if STORE.hashes[key] then STORE.hashes[key][a[1]] = nil end return 1
    end
    error("unexpected redis command " .. tostring(cmd))
end
redis = { call = call, pcall = function(...) local ok, r = pcall(call, ...) if ok then return r end return { err = tostring(r) } end }
cjson = json
cjson.null = json.null
KEYS = { "requests", "requests:facets:initialized", "requests:facets:rebuilding", "requests:facets:oomprobe" }
for _, f in ipairs({ "ip", "country", "method", "url", "status", "reason", "server_name", "security_mode" }) do KEYS[#KEYS + 1] = "requests:facet:" .. f end
ARGV = {}
"""


def _rows(n):
    return ",".join(
        '"{\\"id\\":\\"id%d\\",\\"date\\":%d,\\"ip\\":\\"10.0.0.%d\\",\\"country\\":\\"FR\\",\\"method\\":\\"GET\\",\\"url\\":\\"/p%d\\",\\"status\\":403,'
        '\\"reason\\":\\"x\\",\\"server_name\\":\\"app\\",\\"security_mode\\":\\"block\\"}"' % (i, 1700000000 + i, i % 3, i % 2)
        for i in range(n)
    )


def run_script_text(name, rows, argv=""):
    body = FAKE_REDIS + f"""
STORE.lists.requests = {{ {_rows(rows)} }}
ARGV = {{ {argv} }}
local chunk = assert(load({SCRIPTS[name]!r}))
local result = chunk()
local widest, whole = 0, false
for _, r in ipairs(LRANGES) do
    if r[2] < 0 then whole = true else widest = math.max(widest, r[2] - r[1] + 1) end
end
emit({{ result = type(result) == "number" and result or "err", ranges = #LRANGES, widest = widest, whole = whole,
        list = #STORE.lists.requests, cert = STORE.strings["requests:facets:initialized"], ip = STORE.hashes["requests:facet:ip"] }})
"""
    return run_script(BASE_LUA + "\n" + body)


def test_rebuild_reads_a_large_list_in_bounded_slices_and_still_counts_every_row():
    assert "REBUILD_SCRIPT" in SCRIPTS
    out = run_script_text("REBUILD_SCRIPT", 1200, '"0"')
    assert out["result"] == 1200
    assert out["whole"] is False, "REBUILD_SCRIPT issued an unbounded LRANGE"
    assert out["widest"] <= SLICE_MAX
    assert out["ranges"] >= 1200 // SLICE_MAX
    assert out["ip"] == {"10.0.0.0": 400, "10.0.0.1": 400, "10.0.0.2": 400}
    assert '"valid":1200' in out["cert"].replace(" ", "")


def test_trim_removes_the_oldest_rows_in_bounded_slices_and_keeps_the_facets_consistent():
    out = run_script_text("REBUILD_SCRIPT", 900, '"0"')
    assert out["list"] == 900
    trim = FAKE_REDIS + f"""
STORE.lists.requests = {{ {_rows(900)} }}
ARGV = {{ "0" }}
assert(load({SCRIPTS["REBUILD_SCRIPT"]!r}))()
LRANGES = {{}}
ARGV = {{ "100" }}
redis.call("DEL", "requests:facets:oomprobe")
local removed = assert(load({SCRIPTS["TRIM_SCRIPT"]!r}))()
local widest, whole = 0, false
for _, r in ipairs(LRANGES) do
    if r[2] < 0 then whole = true else widest = math.max(widest, r[2] - r[1] + 1) end
end
local total = 0
for _, n in pairs(STORE.hashes["requests:facet:ip"]) do total = total + n end
emit({{ removed = removed, whole = whole, widest = widest, list = #STORE.lists.requests, facet_total = total }})
"""
    out = run_script(BASE_LUA + "\n" + trim)
    assert out["removed"] == 800
    assert out["whole"] is False
    assert out["widest"] <= SLICE_MAX
    assert out["list"] == 100
    assert out["facet_total"] == 100
