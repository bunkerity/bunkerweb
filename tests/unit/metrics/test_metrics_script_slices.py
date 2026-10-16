"""Execute the shipped Redis scripts with bounded list reads and mutable history."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

LUA = shutil.which("lua") or shutil.which("luajit")
SOURCE = Path(__file__).resolve().parents[3] / "src/common/core/metrics/metrics.lua"


@pytest.mark.skipif(LUA is None, reason="no Lua interpreter")
@pytest.mark.parametrize("script_name", ["TRIM_SCRIPT", "REBUILD_SCRIPT"])
def test_request_scripts_read_slices_without_skipping_rows(script_name):
    script = re.search(r"local " + script_name + r" = \[==\[(.*?)\]==\]", SOURCE.read_text(), re.S).group(1)
    preamble = r"""
local list, ids, facets = {}, {}, {}
local reads, collections, marker = 0, 0, nil
for i = 1, 1030 do list[i] = tostring(i); ids[tostring(i)] = true end
local rebuilding = SCRIPT_NAME == 'REBUILD_SCRIPT'
if rebuilding then
    list[256] = 'bad'; list[257] = 'duplicate'; list[513] = 'missing'
    ids = {}
else
    facets['requests:facet:ip|N/A'] = #list
end
cjson = {null = {}, decode = function(raw)
    if raw == 'bad' then error('invalid json') end
    if raw == 'missing' then return {} end
    return {id = raw == 'duplicate' and '1' or raw}
end}
collectgarbage = function(mode)
    assert(mode == 'collect'); collections = collections + 1
end
redis = {}
function redis.call(command, key, a, b)
    if command == 'LLEN' then return #list end
    if command == 'LRANGE' then
        assert(b >= 0 and b - a + 1 <= 256, 'unbounded LRANGE: ' .. a .. ':' .. b)
        reads = reads + 1
        local slice = {}
        for i = a + 1, math.min(b + 1, #list) do slice[#slice + 1] = list[i] end
        return slice
    end
    if command == 'DEL' then
        if key == 'requests:ids' then ids = {} end
        if key == 'requests:facets:initialized' then marker = nil end
        return 1
    end
    if command == 'SET' then
        if key == 'requests:facets:initialized' then marker = a end
        return 'OK'
    end
    if command == 'SADD' then
        if ids[a] then return 0 end
        ids[a] = true; return 1
    end
    if command == 'SREM' then ids[a] = nil; return 1 end
    if command == 'LREM' then
        for i, raw in ipairs(list) do
            if raw == b then table.remove(list, i); return 1 end
        end
        return 0
    end
    if command == 'LTRIM' then
        local kept = {}
        for i = a + 1, #list do kept[#kept + 1] = list[i] end
        list = kept; return 'OK'
    end
    if command == 'HINCRBY' then
        local field = key .. '|' .. a
        facets[field] = (facets[field] or (rebuilding and 0 or 1030)) + b
        return facets[field]
    end
    if command == 'HDEL' then facets[key .. '|' .. a] = nil; return 1 end
    error('unexpected command ' .. command)
end
redis.pcall = redis.call
KEYS = {'requests', 'requests:ids'}
ARGV = {'7'}
"""
    checks = r"""
local count = run()
assert(reads >= 4 and collections >= 4, 'slices must release temporary payloads')
assert(marker == '1')
if rebuilding then
    assert(count == 1027 and #list == 1027)
    assert(list[1] == '1' and list[#list] == '1030')
    assert(facets['requests:facet:ip|N/A'] == 1027)
    for _, raw in ipairs(list) do assert(ids[raw]) end
else
    assert(count == 1023 and #list == 7 and list[1] == '1024')
    assert(facets['requests:facet:ip|N/A'] == 7)
    for i = 1, 1030 do assert((ids[tostring(i)] == true) == (i > 1023)) end
end
"""
    program = "SCRIPT_NAME = '" + script_name + "'\n" + preamble
    program += "\nlocal run = assert((loadstring or load)([====[" + script + "]====]))\n" + checks
    result = subprocess.run([LUA, "-"], input=program, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
