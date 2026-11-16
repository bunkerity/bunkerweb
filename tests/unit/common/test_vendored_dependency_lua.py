"""Exercise dependency patches through real Lua, stubbing only OpenResty boundaries."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
LUA = shutil.which("lua")
pytestmark = pytest.mark.skipif(not LUA, reason="Lua 5.4 is required")


@pytest.mark.parametrize(
    "script",
    [
        "test_ipv6_dns_arpa.lua",
        "test_ipv6_redis_connector.lua",
        "test_lua_rediscluster_patch.lua",
        "test_lua_rediscluster_retry.lua",
        "test_lua_ipv6_rediscluster.lua",
    ],
)
def test_vendored_dependency(script):
    result = subprocess.run([LUA, str(ROOT / "tests/unit" / script)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


IPC_PRELUDE = r"""
local clock, sleeps = 1000, 0
local values, expires = {}, {}
local dict = {}
function dict:get(key)
    if expires[key] and expires[key] <= clock then values[key] = nil end
    return values[key]
end
function dict:set(key, value, ttl)
    values[key] = value
    expires[key] = ttl and ttl > 0 and clock + ttl or nil
    return true
end
function dict:incr(key, delta, initial)
    values[key] = (values[key] or initial) + delta
    return values[key]
end
ngx = {
    ERR = 1, WARN = 2, INFO = 3, log = function() end,
    now = function() return clock end, update_time = function() end,
    sleep = function(dt) sleeps = sleeps + 1; clock = clock + dt end,
    shared = {ipc = dict, cache = dict},
    worker = {pid = function() return 10 end, count = function() return 2 end},
    thread = {spawn = function() end, wait = function() end},
}
local ipc_module = require "resty.mlcache.ipc"
local ipc = assert(ipc_module.new("ipc", true))
"""


def run_ipc(body):
    path = ROOT / "src/deps/src/lua-resty-mlcache/lib/?.lua"
    result = subprocess.run(
        [LUA, "-"], input=f"package.path = {str(path)!r} .. ';' .. package.path\n" + IPC_PRELUDE + body, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_mlcache_events_expire_after_five_minutes():
    run_ipc(r"""
assert(ipc:broadcast("invalidate", "key"))
clock = clock + 301
assert(dict:get(1) == nil, "event never expires")
assert(ipc:poll())
assert(sleeps == 0, "expired event stalled request")
assert(ipc.events_lost, "lost invalidation must be reported")
""")


def test_mlcache_idle_holes_deliver_surviving_event_without_sleep():
    run_ipc(r"""
values["lua-resty-ipc:index"] = 4
values["lua-resty-ipc:last_broadcast"] = clock - 1
values[4] = "20:3:invalidatekey"
local delivered
ipc:subscribe("invalidate", function(key) delivered = key end)
assert(ipc:poll())
assert(delivered == "key", "surviving invalidation lost")
assert(sleeps == 0, "idle hole stalled request")
assert(ipc.events_lost)
""")


def test_mlcache_hole_scan_is_bounded():
    run_ipc(r"""
values["lua-resty-ipc:index"] = 5000
values["lua-resty-ipc:last_broadcast"] = clock - 1
assert(ipc:poll())
assert(ipc.idx == 1000, "hole scan exceeded budget")
assert(sleeps == 0)
""")


def test_mlcache_recent_writer_still_gets_timeout_budget():
    run_ipc(r"""
values["lua-resty-ipc:index"] = 1
values["lua-resty-ipc:last_broadcast"] = clock
local ok, err = ipc:poll(0.01)
assert(ok == nil and err == "timeout")
assert(sleeps > 0, "recent writer must get a chance to finish")
assert(ipc.events_lost, "timeout lost an invalidation")
""")


@pytest.mark.parametrize("loss", ["idle", "timeout", "forcible"])
def test_mlcache_lost_invalidations_flush_l1(loss):
    run_ipc(f'local loss = "{loss}"\n' + r"""
package.preload["table.new"] = function() return function() return {} end end
package.preload["resty.lrucache"] = function() return {} end
package.preload["resty.lock"] = function() return {} end
package.preload["cjson"] = function() return {} end
local cache = assert(require("resty.mlcache").new("test", "cache", {
    ipc_shm = "ipc",
    lru = {stale = true, flush_all = function(self) self.stale = nil end},
}))
values["lua-resty-ipc:index"] = loss == "forcible" and 3 or 1
values["lua-resty-ipc:last_broadcast"] = loss == "timeout" and clock or clock - 1
if loss == "forcible" then
    values["lua-resty-ipc:forcible"] = true
    values[3] = "20:0:unused"
end
local ok, err = cache.poll(0.01)
if loss == "timeout" then assert(ok == nil and err == "timeout") else assert(ok, err) end
assert(cache.lru.stale == nil, "lost invalidation left stale L1 entry")
assert(cache.ipc.events_lost == nil, "loss marker must be consumed")
""")
