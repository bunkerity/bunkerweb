"""A cachestore failure must never turn reverse scan off, nor be retried once per port.

`reversescan:access()` had two exits that discarded enforcement whenever Redis misbehaved:

* a failed cache **read** aborted the whole scan with `ret(false, ...)`, which the plugin
  runner logs and steps over — so the request was served without ever being scanned;
* a failed cache **write** returned before the verdict block, throwing away a deny the scan
  had *already* reached.

Run 32834226362 fired **neither** of them: on the All-in-one arm all six
`[CACHESTORE] hit level for plugin_reverse_scan_10.20.30.30:<port> = 3` lines for connection
`*108` precede the crash, so every read succeeded, and the scan then found port 8000 open. What
killed the request is a *raise* on the write path — `add_to_cache` → `cachestore:set` →
`set_redis` → `clusterstore:call` — logged as `reversescan:access() failed :
.../resty/redis.lua:255: bad argument #1 to 'byte' (string expected, got boolean)`. It cannot
have come from the read path: mlcache `xpcall`s its get callback (`mlcache.lua:786`), so a raise
there is returned as `callback threw an error: ...`, which that message does not carry. The
request was served 200 where the spec asserts 403. The Docker arm passes because its reversescan
stack runs redis-less, so `cachestore` never reaches the code that can fail.

Two properties are asserted here:

1. **enforcement survives the cache.** Read failure, write failure, and a write that *raises*
   (case 5, which only passes because `clusterstore:call` contains the raise — the containment
   deliberately lives at the choke point, not in every caller).
2. **the cache is not retried per port.** Against a Redis that drops rather than refuses, every
   call pays `REDIS_TIMEOUT` in full (1000 ms default, `src/common/core/redis/plugin.json:62`).
   With the default six ports that was six timeouts in the read loop plus six in the write loop
   — ~12 s of held connection per new IP. One `cache_down` flag caps it at one.

The cache is an optimization. Losing it costs a round of connects, not the enforcement.

Runs through the ``lua`` binary with OpenResty stubbed.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "src" / "common" / "core" / "reversescan" / "reversescan.lua"
CLUSTERSTORE = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "clusterstore.lua"
LUA_DIR = ROOT / "src" / "bw" / "lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

HARNESS = """
package.path = "%s/?.lua;" .. package.path
-- reversescan.lua calls bare `unpack`, which LuaJIT has as a global and 5.4 does not.
unpack = unpack or table.unpack

local class = require "middleclass"

-- ---- OpenResty stubs -------------------------------------------------------------
-- spawn runs the scan inline and hands back a token; wait pops one token per call, in the
-- order they were spawned, and replays what the scan returned.
local spawned = {}
ngx = {
    WARN = 4,
    ERR = 1,
    INFO = 7,
    socket = { tcp = function() error("the scan function is stubbed, no socket expected") end },
    thread = {
        spawn = function(fn, ip, port, timeout)
            local open, ret_port = fn(ip, port, timeout)
            local token = { open = open, port = ret_port }
            spawned[#spawned + 1] = token
            return token
        end,
        wait = function(...)
            local first = select(1, ...)
            return true, first.open, first.port
        end,
        kill = function() return true end,
    },
}

-- ---- module stubs ----------------------------------------------------------------
local plugin = class("plugin")
function plugin:initialize(id, ctx)
    self.id = id
    self.ctx = ctx
end
function plugin:ret(ok, msg, status)
    return { ok = ok, msg = msg, status = status }
end
function plugin:set_metric(kind, key, value)
    self.metrics[#self.metrics + 1] = kind .. "/" .. key .. "=" .. tostring(value)
end
package.loaded["bunkerweb.plugin"] = plugin
package.loaded["bunkerweb.logger"] = { new = function(_, _) return { log = function() end } end }
package.loaded["resty.redis.connector"] = { new = function() return {}, nil end }
-- One table serves both modules: reversescan needs the first two, clusterstore the rest.
-- is_connection_error is the real predicate, verbatim, so case 5 cannot pass by weakening it.
package.loaded["bunkerweb.utils"] = {
    kill_all_threads = function() end,
    get_deny_status = function() return 403 end,
    get_variable = function() return "", nil end,
    is_cosocket_available = function() return false end,
    is_connection_error = function(err)
        return err
            and (
                err:find("closed", 1, true)
                or err:find("broken pipe", 1, true)
                or err:find("connection reset", 1, true)
                or err:find("timeout", 1, true)
            )
    end,
}

local reversescan = dofile("%s")
-- The real clusterstore, not a stub : case 5 asserts *where* the containment lives.
local clusterstore = dofile("%s")

-- The raise lua-resty-redis produced in run 32834226362, reached through the same chain
-- cachestore:set_redis uses (connect -> call -> close). Only clusterstore:call stops it.
local function raising_set(key, value)
    local store = clusterstore:allocate()
    store.healthy = true
    store.redis_client = {
        set = function()
            error("resty/redis.lua:255: bad argument #1 to 'byte' (string expected, got boolean)")
        end,
    }
    local _, err = store:call("set", key, value, "EX", 86400)
    if err then
        return false, "SET failed : " .. err
    end
    return true
end

-- ---- fixture ---------------------------------------------------------------------
-- `open_ports` decides what the stubbed scan reports; `get_err` / `set_err` / `set_raises`
-- inject the cachestore failures. Nothing else about the plugin changes between cases.
local function new_plugin(opts)
    local logged = {}
    local stored = {}
    local calls = { get = 0, set = 0 }
    local instance = reversescan:new({ bw = { remote_addr = "10.20.30.30" } })
    instance.variables = {
        USE_REVERSE_SCAN = "yes",
        REVERSE_SCAN_PORTS = opts.ports or "22 8000",
        REVERSE_SCAN_TIMEOUT = "500",
    }
    instance.logged = logged
    instance.stored = stored
    instance.calls = calls
    instance.metrics = {}
    instance.logger = { log = function(_, _, message) logged[#logged + 1] = message end }
    instance.cachestore = {
        get = function()
            calls.get = calls.get + 1
            if opts.get_err then
                return false, opts.get_err
            end
            return true, nil
        end,
        set = function(_, key, value)
            calls.set = calls.set + 1
            if opts.set_raises then
                return raising_set(key, value)
            end
            if opts.set_err then
                return false, opts.set_err
            end
            stored[key] = value
            return true
        end,
    }
    -- Replace the real socket scan: `open_ports` is the ground truth for this case.
    instance.scan = function(_, port)
        return opts.open_ports[port] == true, port
    end
    return instance
end

-- 1. Cache read failure: the scan still runs and an open port is still denied.
local p = new_plugin({ get_err = "redis is unreachable", open_ports = { [8000] = true } })
local ret = p:access()
assert(ret.status == 403, "a cache read failure must not skip the scan, got status " .. tostring(ret.status))
assert(#p.logged >= 1 and p.logged[1]:find("scanning anyway", 1, true), "the read failure must be logged, got: " .. tostring(p.logged[1]))

-- 2. Cache write failure: the verdict the scan already reached survives.
p = new_plugin({ set_err = "redis is unreachable", open_ports = { [8000] = true } })
ret = p:access()
assert(ret.status == 403, "a cache write failure must not discard the deny, got status " .. tostring(ret.status))

-- 3. Nothing open, cache healthy: allow, and both verdicts are persisted.
p = new_plugin({ open_ports = {} })
ret = p:access()
assert(ret.status == nil, "no open port must not deny, got status " .. tostring(ret.status))
assert(ret.ok == true, "no open port must be a success return")
assert(p.stored["plugin_reverse_scan_10.20.30.30:22"] == "close", "port 22 verdict was not cached")
assert(p.stored["plugin_reverse_scan_10.20.30.30:8000"] == "close", "port 8000 verdict was not cached")

-- 4. An open port is denied and counted when the cache works, too.
p = new_plugin({ open_ports = { [22] = true } })
ret = p:access()
assert(ret.status == 403, "an open port must deny, got status " .. tostring(ret.status))
assert(p.metrics[1] == "counters/failed_22=1", "the open port must be counted, got " .. tostring(p.metrics[1]))

-- 5. The write *raises*, exactly as in run 32834226362. access() must still deny -- which it
--    only does because clusterstore:call turns the raise into a returned error.
p = new_plugin({ set_raises = true, open_ports = { [8000] = true } })
local called, result = pcall(p.access, p)
assert(called, "a raising cachestore write must not propagate out of access(): " .. tostring(result))
assert(result.status == 403, "a raising cache write must not discard the deny, got status " .. tostring(result.status))

-- 6. Timeout amplification: one dead cachestore costs ONE call, not one per port and one more
--    per port in the write loop. With the six default ports that was 12 x REDIS_TIMEOUT.
p = new_plugin({ get_err = "timeout", ports = "22 80 443 3128 8000 8080", open_ports = {} })
ret = p:access()
assert(ret.ok == true and ret.status == nil, "nothing open must still allow, got status " .. tostring(ret.status))
assert(p.calls.get == 1, "a dead cachestore must be probed once, not once per port, got " .. tostring(p.calls.get) .. " reads")
assert(p.calls.set == 0, "a dead cachestore must not be written to at all, got " .. tostring(p.calls.set) .. " writes")

print("OK")
"""


def test_a_cachestore_failure_never_disables_the_scan():
    result = subprocess.run(
        ["lua", "-e", HARNESS % (LUA_DIR.as_posix(), MODULE.as_posix(), CLUSTERSTORE.as_posix())],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
