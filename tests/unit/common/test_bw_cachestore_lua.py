"""Behaviour of ``src/bw/lua/bunkerweb/cachestore.lua``, the real file run under plain Lua.

``cachestore`` is a two-level cache (worker LRU + shared dict, via ``resty.mlcache``) with an optional
Redis backing. ``resty.mlcache`` and the cluster store are the OpenResty/network boundary and are stood in
by small in-memory fakes driven by globals; ``middleclass``, ``bunkerweb.logger`` and
``bunkerweb.rediskeys`` are the real files. The fake mlcache keeps one store with a clock (``NOW``) and
implements what the module relies on: a miss runs the callback (``value, err, ttl``), ``nil, err`` is
returned without caching, a ttl of ``0`` never expires, a missing callback means "local levels only".
"""

import pytest
from _lua_core_helpers import BW_MODULES, LUA, module_path, run_core  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("CACHESTORE", BW_MODULES / "cachestore.lua")

SETUP = """
CALLS = {}               -- every mlcache call: { name, key, callback_given }
SET_CALLS = {}
REDIS = {}               -- every cluster store call: { command, args... }
CLOSED = 0
CONNECT = CONNECT or { true }            -- what clusterstore:connect() returns
EVAL_REPLY = EVAL_REPLY or { NULL, -2 }  -- what the GET + TTL script answers
STORE = {}
UPDATED = 0
CLUSTER_NODES = CLUSTER_NODES or ""

local function expired(entry) return entry.expires and entry.expires <= NOW end

local mlcache = {}
function mlcache:get(key, opts, callback, ...)
    CALLS[#CALLS + 1] = { "get", key, callback ~= nil }
    local entry = STORE[key]
    if entry and not expired(entry) then return entry.value, nil, 1 end
    if not callback then return nil, GET_ERR, nil end
    local value, err, ttl = callback(...)
    if err then return nil, err end
    if value ~= nil then
        local expires = NOW + 30
        if ttl == 0 then expires = nil elseif ttl and ttl > 0 then expires = NOW + ttl end
        STORE[key] = { value = value, expires = expires }
    end
    return value, nil, 3
end
function mlcache:set(key, opts, value)
    SET_CALLS[#SET_CALLS + 1] = { key, opts and opts.ttl, value }
    if SET_ERR then return nil, SET_ERR end
    local ttl = opts and opts.ttl or 30
    STORE[key] = { value = value, expires = NOW + ttl }
    return true
end
function mlcache:delete(key)
    CALLS[#CALLS + 1] = { "delete", key }
    if DELETE_ERR then return nil, DELETE_ERR end
    STORE[key] = nil
    return true
end
function mlcache:purge(flush) PURGED = flush return PURGE_RESULT end
function mlcache:update() UPDATED = UPDATED + 1 return UPDATE_RESULT end

package.loaded["resty.mlcache"] = { new = function(name, shm, opts)
    NEW_ARGS = { name, shm, opts }
    if NEW_FAIL then return nil, NEW_FAIL end
    return mlcache
end }

CLUSTERSTORE = {
    connect = function(_, ...)
        CONNECT_ARGS = { ... }
        return table.unpack(CONNECT, 1, 2)
    end,
    call = function(_, command, ...)
        REDIS[#REDIS + 1] = { command, ... }
        if command == "eval" then
            if EVAL_ERR then return nil, EVAL_ERR end
            return EVAL_REPLY
        end
        if command == "set" then return "OK", SET_REPLY_ERR end
        if command == "del" then return 1, DEL_REPLY_ERR end
    end,
    close = function() CLOSED = CLOSED + 1 end,
}
package.loaded["bunkerweb.clusterstore"] = { new = function(_, pool) POOL = pool or "default" return CLUSTERSTORE end }
package.loaded["bunkerweb.utils"] = {
    get_variable = function(name) if name == "REDIS_CLUSTER_NODES" then return CLUSTER_NODES end return nil end,
    get_ctx_obj = function(obj, ctx) return ctx and ctx.bw and ctx.bw[obj] or nil end,
    is_cosocket_available = function() return PHASE ~= "log" and PHASE ~= "set" end,
}
local cachestore = dofile(MODULE)
"""


def run(body, **env):
    return run_core(MODULE, SETUP + body, **env)


def calls_of(out, name):
    return [c for c in (out["calls"] or []) if c[0] == name]


class TestLocalCache:
    def test_a_miss_is_a_successful_empty_answer(self):
        out = run('local store = cachestore:new() local ok, value = store:get("k") emit({ ok = ok, value = value })')
        assert out == {"ok": True}

    def test_a_stored_value_is_returned(self):
        out = run('local s = cachestore:new() assert(s:set("k", "v")) local ok, value = s:get("k") emit({ ok = ok, value = value })')
        assert out == {"ok": True, "value": "v"}

    def test_set_without_ex_leaves_the_ttl_to_the_cache_default(self):
        out = run('cachestore:new():set("k", "v") emit({ key = SET_CALLS[1][1], no_ttl = SET_CALLS[1][2] == nil, value = SET_CALLS[1][3] })')
        assert out == {"key": "k", "no_ttl": True, "value": "v"}

    def test_set_with_ex_passes_it_as_the_ttl(self):
        out = run('cachestore:new():set("k", "v", 5) emit({ ttl = SET_CALLS[1][2], value = SET_CALLS[1][3] })')
        assert out == {"ttl": 5, "value": "v"}

    def test_a_value_expires_after_its_ttl(self):
        out = run("""
local s = cachestore:new()
s:set("k", "v", 5)
NOW = NOW + 4
local _, before = s:get("k")
NOW = NOW + 1
local _, after = s:get("k")
emit({ before = before, after = after })
""")
        assert out == {"before": "v"}

    def test_delete_forgets_the_value(self):
        out = run('local s = cachestore:new() s:set("k", "v") local r = s:delete("k") local _, value = s:get("k") emit({ r = r, value = value })')
        assert out == {"r": True}

    def test_set_reports_a_cache_failure(self):
        out = run('local ok, err = cachestore:new():set("k", "v") emit({ ok = ok, err = err })', SET_ERR="no memory")
        assert out == {"ok": False, "err": "no memory"}

    def test_delete_reports_a_cache_failure(self):
        out = run('local ok, err = cachestore:new():delete("k") emit({ ok = ok, err = err })', DELETE_ERR="no memory")
        assert out == {"ok": False, "err": "no memory"}

    def test_a_cache_error_on_get_is_returned_as_a_failure(self):
        out = run('local ok, err = cachestore:new():get("k") emit({ ok = ok, err = err })', GET_ERR="shm error", phase="log")
        assert out == {"ok": False, "err": "shm error"}

    def test_a_hit_is_logged_with_its_level(self):
        out = run('local s = cachestore:new() s:set("k", "v") s:get("k") emit(LOGS)')
        assert out == [["INFO", "[CACHESTORE] hit level for k = 1"]]

    def test_a_local_get_runs_a_no_miss_callback_when_sockets_are_available(self):
        out = run('cachestore:new():get("k") emit({ calls = CALLS, redis = #REDIS })')
        assert out == {"calls": [["get", "k", True]], "redis": 0}

    def test_a_get_in_a_phase_without_sockets_passes_no_callback(self):
        out = run('cachestore:new(true):get("k") emit({ calls = CALLS, redis = #REDIS })', phase="log")
        assert out == {"calls": [["get", "k", False]], "redis": 0}

    def test_a_value_set_earlier_is_still_served_in_a_phase_without_sockets(self):
        out = run('local s = cachestore:new() s:set("k", "v") local _, value = s:get("k") emit(value)', phase="log")
        assert out == "v"

    def test_get_local_nolock_serves_stored_values_and_never_runs_a_callback(self):
        out = run(
            """
local s = cachestore:new(true)
s:set("k", "v")
local _, hit = s:get_local_nolock("k")
local ok, miss = s:get_local_nolock("absent")
emit({ hit = hit, ok = ok, miss = miss, gets = CALLS, redis = #REDIS })
""",
            phase="log",
        )
        assert out["hit"] == "v"
        assert out["ok"] is True
        assert "miss" not in out
        assert out["gets"] == [["get", "k", False], ["get", "absent", False]]
        assert out["redis"] == 0

    def test_get_local_nolock_reports_a_cache_error(self):
        out = run('local ok, err = cachestore:new():get_local_nolock("k") emit({ ok = ok, err = err })', GET_ERR="boom")
        assert out == {"ok": False, "err": "boom"}


class TestRedisBacking:
    def test_a_miss_reads_redis_once_and_caches_the_answer(self):
        out = run("""
EVAL_REPLY = { "from redis", 100 }
local s = cachestore:new(true)
local _, first = s:get("k")
local _, second = s:get("k")
emit({ first = first, second = second, evals = #REDIS, key = REDIS[1][4], keys = REDIS[1][3], closed = CLOSED, connect = CONNECT_ARGS })
""")
        assert out == {"first": "from redis", "second": "from redis", "evals": 1, "key": "k", "keys": 1, "closed": 1, "connect": [True]}

    def test_the_redis_ttl_bounds_how_long_the_answer_is_cached(self):
        out = run("""
EVAL_REPLY = { "v", 10 }
local s = cachestore:new(true)
s:get("k")
NOW = NOW + 9
s:get("k")
local before = #REDIS
NOW = NOW + 2
s:get("k")
emit({ before = before, after = #REDIS })
""")
        assert out == {"before": 1, "after": 2}

    def test_a_key_without_expiry_in_redis_is_cached_without_expiry(self):
        out = run("""
EVAL_REPLY = { "v", -1 }
local s = cachestore:new(true)
s:get("k")
NOW = NOW + 100000
local _, value = s:get("k")
emit({ value = value, evals = #REDIS })
""")
        assert out == {"value": "v", "evals": 1}

    def test_a_key_absent_from_redis_is_a_clean_miss(self):
        out = run('local ok, value = cachestore:new(true):get("k") emit({ ok = ok, value = value, closed = CLOSED })')
        assert out == {"ok": True, "closed": 1}

    def test_a_redis_connection_failure_is_reported(self):
        out = run('local ok, err = cachestore:new(true):get("k") emit({ ok = ok, err = err, redis = #REDIS })', CONNECT=[None, "refused"])
        assert out == {"ok": False, "err": "can't connect to redis : refused", "redis": 0}

    def test_a_redis_script_error_is_reported_and_the_connection_closed(self):
        out = run('local ok, err = cachestore:new(true):get("k") emit({ ok = ok, err = err, closed = CLOSED })', EVAL_ERR="OOM")
        assert out == {"ok": False, "err": "OOM", "closed": 1}

    def test_redis_is_not_asked_when_the_store_was_built_without_it(self):
        out = run('cachestore:new(false):get("k") emit(#REDIS)')
        assert out == 0

    def test_redis_is_not_asked_in_a_phase_without_sockets(self):
        out = run('cachestore:new(true):get("k") emit(#REDIS)', phase="log")
        assert out == 0

    def test_set_writes_through_to_redis_with_the_given_expiry(self):
        out = run('local ok = cachestore:new(true):set("k", "v", 12) emit({ ok = ok, redis = REDIS, closed = CLOSED })')
        assert out == {"ok": True, "redis": [["set", "k", "v", "EX", 12]], "closed": 1}

    def test_set_without_ex_defaults_the_redis_expiry_to_thirty_seconds(self):
        out = run('cachestore:new(true):set("k", "v") emit(REDIS)')
        assert out == [["set", "k", "v", "EX", 30]]

    def test_a_redis_connection_failure_on_set_is_logged_but_the_local_copy_is_kept(self):
        out = run(
            'local s = cachestore:new(true) local ok = s:set("k", "v") local _, value = s:get("k") emit({ ok = ok, value = value, logs = LOGS })',
            CONNECT=[None, "refused"],
        )
        assert out["ok"] is True
        assert out["value"] == "v"
        assert ["ERR", "[CACHESTORE] can't connect to redis : refused"] in out["logs"]

    def test_a_redis_set_error_is_logged_and_the_connection_closed(self):
        out = run('local ok = cachestore:new(true):set("k", "v") emit({ ok = ok, logs = LOGS, closed = CLOSED })', SET_REPLY_ERR="READONLY")
        assert out["ok"] is True
        assert ["ERR", "[CACHESTORE] SET failed : READONLY"] in out["logs"]
        assert out["closed"] == 1

    def test_set_does_not_touch_redis_in_a_phase_without_sockets(self):
        out = run('local ok = cachestore:new(true):set("k", "v") emit({ ok = ok, redis = #REDIS })', phase="log")
        assert out == {"ok": True, "redis": 0}

    def test_delete_removes_the_key_from_redis_and_locally(self):
        out = run(
            'local s = cachestore:new(true) s:set("k", "v") REDIS = {} local ok = s:delete("k") local sent = { REDIS[1] } local _, value = s:get("k") emit({ ok = ok, value = value, redis = sent })'
        )
        assert out == {"ok": True, "redis": [["del", "k"]]}

    def test_a_redis_delete_failure_is_logged_but_the_local_copy_is_removed(self):
        out = run(
            'local s = cachestore:new(true) s:set("k", "v") local ok = s:delete("k") local _, value = s:get("k") emit({ ok = ok, value = value, logs = LOGS })',
            DEL_REPLY_ERR="READONLY",
        )
        assert out["ok"] is True
        assert "value" not in out
        assert ["ERR", "[CACHESTORE] DEL failed : READONLY"] in out["logs"]

    def test_a_redis_connection_failure_on_delete_is_logged(self):
        out = run('local ok = cachestore:new(true):delete("k") emit({ ok = ok, logs = LOGS })', CONNECT=[None, "refused"])
        assert out["ok"] is True
        assert ["ERR", "[CACHESTORE] can't connect to redis : refused"] in out["logs"]


class TestClusterKeys:
    KEY = "a{b}%c"
    ESCAPED = "a%7Bb%7D%25c"

    def test_cluster_mode_escapes_the_key_for_every_redis_command(self):
        out = run(
            f"""
local s = cachestore:new(true)
s:get("{self.KEY}")
s:set("{self.KEY}", "v")
s:delete("{self.KEY}")
local keys = {{}}
for _, call in ipairs(REDIS) do keys[#keys + 1] = call[1] == "eval" and call[4] or call[2] end
emit(keys)
""",
            CLUSTER_NODES="redis1:7000",
        )
        assert out == [self.ESCAPED] * 3

    def test_other_modes_send_the_key_as_is(self):
        out = run(f"""
local s = cachestore:new(true)
s:set("{self.KEY}", "v")
emit(REDIS[1][2])
""")
        assert out == self.KEY

    def test_the_local_cache_always_uses_the_raw_key(self):
        out = run(
            f"""
local s = cachestore:new(true)
s:set("{self.KEY}", "v")
emit({{ local_key = SET_CALLS[1][1] }})
""",
            CLUSTER_NODES="redis1:7000",
        )
        assert out == {"local_key": self.KEY}


class TestLifecycle:
    def test_the_cluster_store_comes_from_the_request_context_when_given(self):
        out = run("local mine = {} local s = cachestore:new(true, { bw = { clusterstore = mine } }) emit({ pool = POOL, same = s.clusterstore == mine })")
        assert out == {"same": True}

    def test_without_a_context_a_cluster_store_is_built_with_the_pool(self):
        out = run('local s = cachestore:new(true, nil, "pool-1") emit({ pool = POOL, same = s.clusterstore == CLUSTERSTORE })')
        assert out == {"pool": "pool-1", "same": True}

    def test_no_cluster_store_is_built_when_redis_is_off(self):
        out = run("local s = cachestore:new() emit({ pool = POOL, use_redis = s.use_redis, store = s.clusterstore ~= nil })")
        assert out == {"use_redis": False, "store": False}

    def test_a_context_store_is_the_one_used_for_redis(self):
        out = run("""
local mine = setmetatable({}, { __index = CLUSTERSTORE })
mine.call = function(_, ...) REDIS[#REDIS + 1] = { "ctx", ... } return "OK" end
cachestore:new(true, { bw = { clusterstore = mine } }):set("k", "v")
emit(REDIS)
""")
        assert out == [["ctx", "set", "k", "v", "EX", 30]]

    def test_update_polls_the_shared_dict_when_sockets_are_available(self):
        out = run("emit({ r = cachestore:new():update(), updated = UPDATED })", UPDATE_RESULT=True)
        assert out == {"r": True, "updated": 1}

    def test_update_is_a_no_op_in_a_phase_without_sockets(self):
        out = run("emit({ r = cachestore:new():update(), updated = UPDATED })", phase="log", UPDATE_RESULT=False)
        assert out == {"r": True, "updated": 0}

    def test_purge_flushes_everything_and_returns_the_cache_answer(self):
        out = run("emit({ r = cachestore:new():purge(), flush = PURGED })", PURGE_RESULT="purged")
        assert out == {"r": "purged", "flush": True}

    @pytest.mark.parametrize(
        ("subsystem", "shm", "ipc", "miss", "locks"),
        [
            ("http", "cachestore", "cachestore_ipc", "cachestore_miss", "cachestore_locks"),
            ("stream", "cachestore_stream", "cachestore_ipc_stream", "cachestore_miss_stream", "cachestore_locks_stream"),
        ],
    )
    def test_each_subsystem_gets_its_own_shared_dicts(self, subsystem, shm, ipc, miss, locks):
        out = run(
            "emit({ name = NEW_ARGS[1], shm = NEW_ARGS[2], ipc = NEW_ARGS[3].ipc_shm, miss = NEW_ARGS[3].shm_miss, locks = NEW_ARGS[3].shm_locks })",
            subsystem=subsystem,
        )
        assert out == {"name": "cachestore", "shm": shm, "ipc": ipc, "miss": miss, "locks": locks}

    def test_the_cache_is_built_with_a_short_negative_ttl_and_a_thirty_second_ttl(self):
        out = run("emit({ ttl = NEW_ARGS[3].ttl, neg = NEW_ARGS[3].neg_ttl, lru = NEW_ARGS[3].lru_size })")
        assert out == {"ttl": 30, "neg": 0.1, "lru": 100}

    def test_a_cache_that_cannot_be_built_is_logged_at_load(self):
        out = run("emit(LOGS)", NEW_FAIL="no such dict")
        assert out == [["ERR", "[CACHESTORE] can't instantiate mlcache : no such dict"]]
