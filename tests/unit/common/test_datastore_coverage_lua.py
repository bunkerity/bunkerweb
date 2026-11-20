"""Shared-dict errors, bounded eviction, TTL and per-worker cache behavior."""

import pytest
from _lua_core_helpers import BW_MODULES, LUA, run_core

pytestmark = pytest.mark.skipif(LUA is None, reason="no Lua interpreter")
MODULE = BW_MODULES / "datastore.lua"

SETUP = r"""
local function keys(values)
    local out = {} for k in pairs(values) do out[#out+1] = k end table.sort(out) return out
end
local values, expiry, list = {}, {}, {"old1", "old2", "old3", "old4", "old5", "old6"}
WRITES, ALLOCATIONS = 0, {}
local dict = {}
function dict:get(key)
    if GET_ERR then return nil, GET_ERR end
    if expiry[key] and expiry[key] <= NOW then return nil end
    return values[key]
end
function dict:safe_set(key, value, ttl)
    if WRITE_ERR then return nil, WRITE_ERR end
    values[key], expiry[key] = value, ttl and ttl > 0 and NOW + ttl or nil
    return true
end
function dict:set(key, value, ttl)
    WRITES = WRITES + 1
    if RETRY_ERR and WRITES <= (FAIL_WRITES or 99) then return nil, RETRY_ERR end
    self:safe_set(key, value, ttl) return true, nil, FORCIBLE
end
function dict:delete(key) values[key], expiry[key] = nil, nil end
function dict:get_keys() return keys(values) end
function dict:ttl(key)
    if TTL_ERR then return nil, TTL_ERR end
    if not values[key] then return nil end
    return expiry[key] and expiry[key] - NOW or 0
end
function dict:rpush(_, value)
    WRITES = WRITES + 1
    if PUSH_ERR and WRITES <= (FAIL_WRITES or 99) then return nil, PUSH_ERR end
    list[#list + 1] = value return #list
end
function dict:lpop()
    if POP_ERR then return nil, POP_ERR end
    if EMPTY then return nil end
    return table.remove(list, 1)
end
function dict:llen() return #list end
ngx.shared.datastore, ngx.shared.datastore_stream = dict, dict
ngx.shared.metrics_datastore, ngx.shared.internalstore = {}, {}
if ZONE then ngx.shared[ZONE] = dict end
local ready, setting = READY ~= false, SETTING or "1000"
package.loaded["bunkerweb.utils"] = {
    get_variable = function()
        if REENTER then store_class:new(dict):get("bootstrap", true) end
        if ready then return setting end
    end,
}
local lru_methods = {}
function lru_methods:set(key, value, ttl, flags)
    self.values[key] = {value=value, expires=ttl and NOW+ttl, flags=flags}
end
function lru_methods:get(key)
    local entry=self.values[key]
    if not entry then return nil end
    if entry.expires and entry.expires <= NOW then return nil, entry.value, entry.flags end
    return entry.value, nil, entry.flags
end
function lru_methods:get_keys() return keys(self.values) end
function lru_methods:delete(key) self.values[key] = nil end
function lru_methods:flush_all() self.values = {} end
package.loaded["resty.lrucache"] = {new = function(size)
    ALLOCATIONS[#ALLOCATIONS+1] = size
    if INITIAL_FAIL and #ALLOCATIONS == 1 or RESIZE_FAIL and #ALLOCATIONS > 1 then return nil, "allocation failed" end
    return setmetatable({values={}}, {__index=lru_methods})
end}
store_class = dofile(MODULE)
local store = store_class:new()
local function results(...)
    local out = {} for i=1,select("#", ...) do local v=select(i, ...) out[i]=v==nil and json.null or v end return out
end
"""


def run(body, **env):
    return run_core(MODULE, SETUP + body, **env)


@pytest.mark.parametrize("ttl", [None, -1, 0, 5])
def test_shared_values_and_ttl(ttl):
    out = run(
        'assert(store:set("key", "value", TTL)) local before=store:get("key") local ttl=results(store:ttl("key")) NOW=NOW+6 emit({before=before,after=results(store:get("key")),ttl=ttl})',
        TTL=ttl,
    )
    assert out == {"before": "value", "after": [None, "not found"] if ttl == 5 else ["value", None], "ttl": [True, 5 if ttl == 5 else 0]}


def test_shared_read_write_and_ttl_failures():
    assert run('emit(results(store:get("key")))', GET_ERR="read failed") == [None, "read failed"]
    assert run('emit(results(store:set("key", "value")))', WRITE_ERR="no memory") == [None, "no memory"]
    assert run('emit(results(store:ttl("key")))', TTL_ERR="bad key") == [False, "bad key"]
    assert run('emit(results(store:ttl("missing")))') == [True, 0]
    assert run('emit(results(store:ttl("key", true)))') == [False, "not supported by LRU"]


@pytest.mark.parametrize("ttl", [None, -1, 0, 5])
def test_worker_values_remain_private_and_expire(ttl):
    out = run(
        'assert(store:set("key", "worker", TTL, true)) assert(store:set("key", "shared")) local before=store:get("key", true) NOW=NOW+6 emit({before=before,after=results(store:get("key", true)),shared=store:get("key")})',
        TTL=ttl,
    )
    assert out == {"before": "worker", "after": [None, "not found"] if ttl == 5 else ["worker", "success"], "shared": "shared"}


@pytest.mark.parametrize("worker", [True, False])
def test_keys_pattern_delete_single_delete_and_flush(worker):
    out = run(
        'store:set("ban:1", "x", nil, WORKER) store:set("keep", "y", nil, WORKER) local before=store:keys(WORKER) assert(store:delete_all("^ban:", WORKER)) local after=store:keys(WORKER) assert(store:delete("keep", WORKER)) emit({before=before,after=after,missing=results(store:get("keep", WORKER))})',
        WORKER=worker,
    )
    assert out == {"before": ["ban:1", "keep"], "after": ["keep"], "missing": [None, "not found"]}
    assert run('store:set("key", "x", nil, true) local result=results(store:flush_lru()) emit({result=result,count=#store:keys(true)})') == {
        "result": [True, "success"],
        "count": 0,
    }


@pytest.mark.parametrize(
    "operation", ['get("key", true)', 'set("key", "v", nil, true)', 'delete("key", true)', "keys(true)", 'delete_all(".*", true)', "flush_lru()"]
)
def test_missing_worker_lru_reports_error(operation):
    out = run(f"emit({{result=results(store:{operation}),logs=LOGS}})", INITIAL_FAIL=True)
    assert out["result"] == [None if operation.startswith("get(") else False, "lru is not instantiated"]
    assert ["ERR", "[DATASTORE] failed to instantiate LRU cache : allocation failed"] in out["logs"]


@pytest.mark.parametrize("setting,size", [("2k", 2000), ("2K", 2000), ("1m", 1000000), ("1M", 1000000), ("2001", 2001), ("bad", None), ("", None), ("0", None)])
def test_lru_size_parsing_and_bootstrap_migration(setting, size):
    out = run(
        'assert(store:set("bootstrap", "metadata", nil, true)) ready=true local value=store:get("bootstrap", true) emit({value=value,sizes=ALLOCATIONS})',
        READY=False,
        SETTING=setting,
    )
    assert out == {"value": "metadata", "sizes": [1000, size] if size else [1000]}


def test_resize_failure_keeps_existing_worker_entries():
    out = run(
        'store:set("bootstrap", "metadata", nil, true) ready=true local value=store:get("bootstrap", true) emit({value=value,logs=LOGS})',
        READY=False,
        SETTING="2000",
        RESIZE_FAIL=True,
    )
    assert out["value"] == "metadata"
    assert ["ERR", "[DATASTORE] failed to resize datastore LRU to 2000 : allocation failed"] in out["logs"]


def test_reentrant_setting_lookup_does_not_recurse():
    assert run('store:set("key", "value", nil, true) emit(store:get("key", true))', REENTER=True, SETTING="2000") == "value"


@pytest.mark.parametrize("ttl", [None, -1, 5])
def test_set_retries_only_memory_failures_and_preserves_ttl(ttl):
    out = run(
        'local result=results(store:set_with_retries("key", "value", TTL)) local before=store:get("key") NOW=NOW+6 emit({result=result,before=before,after=results(store:get("key")),writes=WRITES})',
        RETRY_ERR="no memory",
        FAIL_WRITES=2,
        TTL=ttl,
    )
    assert out == {"result": [True, "success"], "before": "value", "after": [None, "not found"] if ttl == 5 else ["value", None], "writes": 3}


@pytest.mark.parametrize("error,retries,writes", [("no memory", None, 5), ("no memory", 2, 2), ("bad key", 5, 1)])
def test_set_retry_limit_and_nonmemory_error(error, retries, writes):
    assert run(
        'local result=results(store:set_with_retries("key", "v", nil, RETRIES)) emit({result=result,writes=WRITES})', RETRY_ERR=error, RETRIES=retries
    ) == {"result": [False, error], "writes": writes}


@pytest.mark.parametrize(
    "zone,setting", [("datastore", "DATASTORE_MEMORY_SIZE"), ("metrics_datastore", "METRICS_MEMORY_SIZE"), ("internalstore", "INTERNALSTORE_MEMORY_SIZE")]
)
def test_forced_eviction_warning_is_throttled_per_zone(zone, setting):
    out = run(
        'assert(store:set_with_retries("ban:1", "v")) assert(store:set_with_retries("ban:2", "v")) NOW=NOW+60 assert(store:set_with_retries("ban:3", "v")) emit(LOGS)',
        FORCIBLE=True,
        ZONE=zone,
    )
    assert out == [["WARN", f"[DATASTORE] shared dict is full : writing ban:{key} evicted an unexpired entry, raise {setting}"] for key in (1, 3)]


def test_stream_default_dict_and_explicit_dict():
    assert run("emit(store.dict == ngx.shared.datastore_stream)", subsystem="stream") is True
    assert run("local explicit={} emit(store_class:new(explicit).dict == explicit)") is True


def test_list_push_evicts_oldest_entries_until_write_succeeds():
    out = run(
        'local result=results(store:safe_rpush("list", "new")) emit({result=result,head=store:lpop("list"),length=store:llen("list"),writes=WRITES})',
        PUSH_ERR="no memory",
        FAIL_WRITES=2,
    )
    assert out == {"result": [5, None], "head": "old3", "length": 4, "writes": 3}


@pytest.mark.parametrize(
    "env,error,writes",
    [
        ({"PUSH_ERR": "no memory"}, "no memory", 6),
        ({"PUSH_ERR": "bad type"}, "bad type", 1),
        ({"PUSH_ERR": "no memory", "EMPTY": True}, "no memory (dict is full and key has nothing to evict)", 1),
        ({"PUSH_ERR": "no memory", "POP_ERR": "bad type"}, "bad type", 1),
    ],
)
def test_list_errors_and_eviction_bound(env, error, writes):
    assert run('local result=results(store:safe_rpush("list", "new")) emit({result=result,writes=WRITES})', **env) == {
        "result": [None, error],
        "writes": writes,
    }
