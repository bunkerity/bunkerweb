"""``limit`` local counters: the read-prune-append-write of one key is serialized across workers.

Runs the real ``limit.lua`` under plain Lua (see ``_lua_request_helpers``). Workers are modelled as
coroutines: the fake shared-dict ``get`` yields right after it has taken its snapshot (the point where
another worker can be scheduled before the ``set``), and the fake ``resty.lock`` makes a loser yield
until the winner unlocks. Without a lock the interleaving below admits more than the rate.
"""

import pytest
from _lua_request_helpers import requires_lua, run

pytestmark = requires_lua

SETUP = r"""
VARIABLES = { USE_LIMIT_REQ = "yes", USE_LIMIT_REQ_GLOBAL = "yes" }
STORE["plugin_limit_rules"] = { global = RULES }
STORE["plugin_limit_global_rules"] = { global = GLOBAL_RATE }

-- Is this code running inside a worker coroutine (and so can be descheduled)?
local function in_task()
    local co, ismain = coroutine.running()
    return co ~= nil and ismain ~= true
end

HELD, LOCK_CALLS, UNLOCK_CALLS, LOCK_OPTS, LOCK_FAIL, NEW_FAIL = {}, 0, 0, {}, nil, nil
if WITH_LOCK then
    package.loaded["resty.lock"] = {
        new = function(_, zone, opts)
            if NEW_FAIL then return nil, NEW_FAIL end
            LOCK_OPTS[#LOCK_OPTS + 1] = { zone = zone, timeout = opts.timeout, exptime = opts.exptime }
            local obj = {}
            function obj:lock(key)
                LOCK_CALLS = LOCK_CALLS + 1
                if LOCK_FAIL then return nil, LOCK_FAIL end
                while HELD[key] do
                    if not in_task() then return nil, "timeout" end
                    coroutine.yield("lock wait")
                end
                HELD[key] = true
                self.key = key
                return 0
            end
            function obj:unlock()
                if not self.key then return nil, "unlocked" end
                HELD[self.key] = nil
                self.key = nil
                UNLOCK_CALLS = UNLOCK_CALLS + 1
                return 1
            end
            return obj
        end,
    }
end

THROTTLED = {}
PLUGIN.log_throttled = function(_, level, key, msg) THROTTLED[#THROTTLED + 1] = level .. "|" .. key .. "|" .. msg end

-- One request of one client; every datastore read is a preemption point after the snapshot.
function request(uri)
    local p = PLUGIN:new(ctx({ uri = uri or "/" }))
    local get = p.datastore.get
    p.datastore.get = function(...)
        local value, err = get(...)
        if in_task() then coroutine.yield("snapshot read") end
        return value, err
    end
    local r = p:access()
    return r
end

-- Round-robin the workers until all of them are done; return how many requests were admitted.
function schedule(workers, per_worker)
    local admitted, tasks = 0, {}
    for w = 1, workers do
        tasks[w] = coroutine.create(function()
            for _ = 1, per_worker do
                local r = request()
                if r.status == nil then admitted = admitted + 1 end
            end
        end)
    end
    for _ = 1, 100000 do
        local alive = false
        for _, t in ipairs(tasks) do
            if coroutine.status(t) == "suspended" then
                alive = true
                assert(coroutine.resume(t))
            end
        end
        if not alive then return admitted end
    end
    error("workers never finished")
end
"""


def scenario(body, *, rules='{ ["/"] = "2r/s" }', global_rate="nil", lock=True, subsystem="http"):
    return run(
        "limit",
        f"""
RULES = {rules}
GLOBAL_RATE = {global_rate}
WITH_LOCK = {"true" if lock else "false"}
{SETUP}
{body}
""",
        subsystem=subsystem,
    )


class TestConcurrentWorkers:
    @pytest.mark.parametrize("rate", [1, 2, 5])
    @pytest.mark.parametrize("workers", [2, 4])
    def test_the_per_url_rate_holds_across_workers(self, rate, workers):
        out = scenario(
            f'emit("admitted", schedule({workers}, {rate + 2}))',
            rules=f'{{ ["/"] = "{rate}r/s" }}',
        )
        assert out["admitted"] == str(rate)

    @pytest.mark.parametrize("workers", [2, 4])
    def test_the_global_rate_holds_across_workers(self, workers):
        out = scenario(f'emit("admitted", schedule({workers}, 4))', rules="{}", global_rate='"3r/s"')
        assert out["admitted"] == "3"

    def test_clients_do_not_wait_for_each_others_lock(self):
        out = scenario(
            r"""
local held_keys = {}
local t = coroutine.create(function() request("/a") end)
assert(coroutine.resume(t))              -- parked inside its critical section on /a
for k in pairs(HELD) do held_keys[#held_keys + 1] = k end
local r = request("/b")                  -- main thread: a different key must not need /a's lock
emit("held", #held_keys) emit("other_status", r.status) emit("other_waits", LOCK_FAIL)
""",
        )
        assert out["held"] == "1"
        assert out["other_status"] == "nil"


class TestLockContract:
    def test_the_lock_covers_the_read_and_the_write(self):
        out = scenario(
            r"""
local p = PLUGIN:new(ctx())
local key = "plugin_limit_lock_" .. p:counter_key()
local seen = {}
p.datastore.get = function(_, k) seen[#seen + 1] = "get:" .. tostring(HELD[key] == true); return nil, "not found" end
p.datastore.set_with_retries = function(_, k, v) seen[#seen + 1] = "set:" .. tostring(HELD[key] == true); return true end
p:limit_req_local(2, "s")
emit("seen", table.concat(seen, ",")) emit("after", tostring(HELD[key])) emit("lock_calls", LOCK_CALLS)
""",
        )
        assert out["seen"] == "get:true,set:true"
        assert out["after"] == "nil"
        assert out["lock_calls"] == "1"

    @pytest.mark.parametrize(("subsystem", "zone"), [("http", "cachestore_locks"), ("stream", "cachestore_locks_stream")])
    def test_the_wait_is_short_and_the_entry_expires_on_its_own(self, subsystem, zone):
        out = scenario(
            r"""
request()
local o = LOCK_OPTS[1]
emit("zone", o.zone) emit("timeout", o.timeout) emit("exptime", o.exptime)
""",
            subsystem=subsystem,
        )
        assert out["zone"] == zone
        assert 0 < float(out["timeout"]) <= 0.05
        assert float(out["timeout"]) < float(out["exptime"]) <= 5

    def test_the_redis_path_takes_no_lock(self):
        out = scenario(
            r"""
local p = PLUGIN:new(ctx())
p.use_redis = true
p.clusterstore = { connect = function() return true end, close = function() end, call = function() return { NOW } end }
p.limit_req_redis = function() return { NOW } end
local r = p:access()
emit("status", r.status) emit("lock_calls", LOCK_CALLS)
""",
        )
        assert out == {"status": "nil", "lock_calls": "0"}

    def test_a_redis_failure_falls_back_to_the_locked_local_counter(self):
        out = scenario(
            r"""
local p = PLUGIN:new(ctx())
p.use_redis = true
p.clusterstore = { connect = function() return nil, "down" end, close = function() end }
local r = p:access()
emit("status", r.status) emit("lock_calls", LOCK_CALLS) emit("unlock_calls", UNLOCK_CALLS)
""",
        )
        assert out == {"status": "nil", "lock_calls": "1", "unlock_calls": "1"}


# The lock only pays for itself while the timestamp list is short: above this many requests per window the
# counters keep their unlocked read-modify-write (the bound is limit.lua's LOCK_MAX_RATE).
LOCK_BOUND = 100


class TestLockIsBoundedToSmallRates:
    @pytest.mark.parametrize("workers", [2, 4])
    def test_a_huge_per_url_rate_takes_no_lock(self, workers):
        out = scenario(
            f'emit("admitted", schedule({workers}, 5)) emit("locks", LOCK_CALLS) emit("opts", #LOCK_OPTS)',
            rules='{ ["/"] = "1000000r/s" }',
        )
        assert out == {"admitted": str(workers * 5), "locks": "0", "opts": "0"}

    @pytest.mark.parametrize("workers", [2, 4])
    def test_a_huge_global_rate_takes_no_lock(self, workers):
        out = scenario(
            f'emit("admitted", schedule({workers}, 5)) emit("locks", LOCK_CALLS) emit("opts", #LOCK_OPTS)',
            rules="{}",
            global_rate='"1000000r/s"',
        )
        assert out == {"admitted": str(workers * 5), "locks": "0", "opts": "0"}

    @pytest.mark.parametrize("scope", ["uri", "global"])
    @pytest.mark.parametrize(("rate", "locked"), [(LOCK_BOUND, 1), (LOCK_BOUND + 1, 0)])
    def test_the_bound_is_inclusive(self, scope, rate, locked):
        rules, global_rate = ("{}", f'"{rate}r/s"') if scope == "global" else (f'{{ ["/"] = "{rate}r/s" }}', "nil")
        out = scenario('request() emit("locks", LOCK_CALLS)', rules=rules, global_rate=global_rate)
        assert out["locks"] == str(locked)

    @pytest.mark.parametrize("scope", ["uri", "global"])
    def test_the_rate_holds_across_workers_up_to_the_bound(self, scope):
        rules, global_rate = ("{}", f'"{LOCK_BOUND}r/s"') if scope == "global" else (f'{{ ["/"] = "{LOCK_BOUND}r/s" }}', "nil")
        out = scenario(f'emit("admitted", schedule(4, {LOCK_BOUND // 4 + 3}))', rules=rules, global_rate=global_rate)
        assert out["admitted"] == str(LOCK_BOUND)

    @pytest.mark.parametrize("failure", ["LOCK_FAIL", "NEW_FAIL"])
    def test_above_the_bound_a_broken_lock_is_neither_tried_nor_logged(self, failure):
        out = scenario(
            f"""
{failure} = "timeout"
for _ = 1, 3 do request() end
emit("throttled", #THROTTLED) emit("locks", LOCK_CALLS) emit("opts", #LOCK_OPTS)
""",
            rules=f'{{ ["/"] = "{LOCK_BOUND + 1}r/s" }}',
        )
        assert out == {"throttled": "0", "locks": "0", "opts": "0"}

    def test_above_the_bound_the_decisions_are_rc3s(self):
        out = scenario(
            r"""
local p = PLUGIN:new(ctx())
p.datastore.set_with_retries = function(_, k, v, d) DS[k] = v; return true end
for _ = 1, 4 do p:limit_req_local(2000, "s") end
emit("stored", DS[p:counter_key()]) emit("locks", LOCK_CALLS)
""",
            rules='{ ["/"] = "2000r/s" }',
        )
        assert out["stored"] == "[" + ",".join(["1000000"] * 4) + "]"
        assert out["locks"] == "0"

    @pytest.mark.parametrize("scope", ["uri", "global"])
    def test_the_lock_call_gets_the_same_function_every_request(self, scope):
        """A closure built per request is an FNEW on the hot path: the method and its arguments are passed instead."""
        rules, global_rate = ("{}", '"5r/s"') if scope == "global" else ('{ ["/"] = "5r/s" }', "nil")
        out = scenario(
            r"""
local seen = {}
local orig = PLUGIN.with_counter_lock
PLUGIN.with_counter_lock = function(self, key, fn, ...)
    seen[#seen + 1] = fn
    return orig(self, key, fn, ...)
end
for _ = 1, 3 do request() end
emit("calls", #seen) emit("kind", type(seen[1]))
emit("same", seen[1] == seen[2] and seen[2] == seen[3])
""",
            rules=rules,
            global_rate=global_rate,
        )
        assert out == {"calls": "3", "kind": "function", "same": "true"}


class TestFallbackWhenTheLockIsUnavailable:
    @pytest.mark.parametrize("failure", ["LOCK_FAIL", "NEW_FAIL"])
    @pytest.mark.parametrize("scope", ["uri", "global"])
    def test_the_request_is_counted_as_before_and_the_problem_is_logged_throttled(self, failure, scope):
        rules, global_rate = ("{}", '"2r/s"') if scope == "global" else ('{ ["/"] = "2r/s" }', "nil")
        out = scenario(
            f"""
{failure} = "timeout"
local statuses = {{}}
for i = 1, 4 do statuses[i] = tostring(request().status) end
emit("statuses", table.concat(statuses, ","))
emit("throttled", #THROTTLED) emit("first", THROTTLED[1])
local keys = {{}}
for _, line in ipairs(THROTTLED) do keys[line:match("^[^|]*|([^|]*)|")] = true end
local n = 0 for _ in pairs(keys) do n = n + 1 end
emit("distinct_keys", n) emit("held", next(HELD) == nil)
""",
            rules=rules,
            global_rate=global_rate,
        )
        assert out["statuses"] == "nil,nil,429,429"
        assert out["distinct_keys"] == "1"
        assert out["throttled"] == "4"  # one call per request; the base plugin throttles to one line per interval
        assert out["first"].startswith("WARN|counter_lock|")
        assert "timeout" in out["first"]
        assert out["held"] == "true"

    def test_a_missing_lock_library_still_counts(self):
        out = scenario(
            r"""
local statuses = {}
for i = 1, 4 do statuses[i] = tostring(request().status) end
emit("statuses", table.concat(statuses, ","))
""",
            lock=False,
        )
        assert out["statuses"] == "nil,nil,429,429"


class TestRelease:
    @pytest.mark.parametrize("scope", ["uri", "global"])
    @pytest.mark.parametrize("failure", ["raise", "read_error", "write_error"])
    def test_the_lock_is_released_on_every_path(self, scope, failure):
        rules, global_rate = ("{}", '"2r/s"') if scope == "global" else ('{ ["/"] = "2r/s" }', "nil")
        broken = {
            "raise": 'p.datastore.get = function() error("boom", 0) end',
            "read_error": 'p.datastore.get = function() return nil, "broken" end',
            "write_error": 'p.datastore.set_with_retries = function() return nil, "broken" end',
        }[failure]
        out = scenario(
            f"""
local p = PLUGIN:new(ctx())
{broken}
local ok, r = pcall(p.access, p)
emit("raised", not ok) emit("ret", ok and tostring(r.ret) or r)
emit("locks", LOCK_CALLS) emit("unlocks", UNLOCK_CALLS) emit("held", next(HELD) == nil)
local again = request()          -- a later request is not stuck behind a leaked lock
emit("again", again.status)
""",
            rules=rules,
            global_rate=global_rate,
        )
        assert out["locks"] == out["unlocks"] == "1"
        assert out["held"] == "true"
        assert out["raised"] == ("true" if failure == "raise" else "false")
        assert out["again"] == "nil"


# The decisions of one client, one request at a time, recorded on rc3 (no lock) and required unchanged.
SERIAL = r"""
function serial(rate, unit, steps)
    local out = {}
    for _, step in ipairs(steps) do
        NOW = NOW + step
        local r = request()
        out[#out + 1] = (r.status or "ok") .. ":" .. tostring(r.data and r.data.current_rate or "-")
    end
    return table.concat(out, " ")
end
"""

WINDOWS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def serial(rate, unit, steps, *, lock):
    return scenario(
        f"""
{SERIAL}
local ttl = {{}}
-- ttl of every write of the counter (the first denied marker and the TTL refresh are part of the behaviour)
DS_SET = {{}}
PLUGIN.new = (function(orig) return function(cls, c)
    local p = orig(cls, c)
    p.datastore.set_with_retries = function(_, k, v, d) DS[k] = v; DS_SET[#DS_SET + 1] = tostring(d) .. "=" .. v; return true end
    return p
end end)(PLUGIN.new)
emit("decisions", serial({rate}, "{unit}", {{ {", ".join(map(str, steps))} }}))
emit("writes", table.concat(DS_SET, ";"))
""",
        rules=f'{{ ["/"] = "{rate}r/{unit}" }}',
        lock=lock,
    )


@pytest.mark.parametrize("lock", [True, False])
@pytest.mark.parametrize("unit", sorted(WINDOWS))
@pytest.mark.parametrize("rate", [0, 2, 10])
def test_serial_decisions_are_those_of_the_unlocked_counter(rate, unit, lock):
    """Expected values were recorded on rc3, whose counter takes no lock."""
    delay = WINDOWS[unit]
    # rate+3 requests in one second, then one at +delay (age == delay is still inside the window: the denied
    # marker survives), three more, then one at +delay+1 (everything pruned) and one more.
    steps = [0] * (rate + 3) + [delay, 0, 0, 0, delay + 1, 0]
    t0, t2 = 1000000, 1000000 + 2 * delay + 1
    if rate == 0:
        decisions = ["429:1"] * 9
        writes = [f"{delay}=[{t0}]", f"{delay}=[{t2}]"]
    else:
        decisions = ["ok:-"] * rate + [f"429:{rate + 1}"] * 7 + ["ok:-"] * 2
        writes = [f"{delay}=[{','.join([str(t0)] * k)}]" for k in range(1, rate + 2)]
        writes += [f"{delay}=[{t2}]", f"{delay}=[{t2},{t2}]"]
    out = serial(rate, unit, steps, lock=lock)
    assert out["decisions"].split() == decisions
    assert out["writes"].split(";") == writes
