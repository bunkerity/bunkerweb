import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BAN_SYNC_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "ban_sync.lua"
UTILS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"
API_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "api.lua"
INIT_STREAM_CONF = ROOT / "src" / "common" / "confs" / "init-stream-lua.conf"
HTTP_CONF = ROOT / "src" / "common" / "confs" / "http.conf"
STREAM_CONF = ROOT / "src" / "common" / "confs" / "stream.conf"
BADBEHAVIOR_LUA = ROOT / "src" / "common" / "core" / "badbehavior" / "badbehavior.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


SYNC_PREAMBLE = r"""
local encoded, next_json = {}, 0
local json = {
    encode = function(value)
        next_json = next_json + 1
        local key = "json:" .. next_json
        encoded[key] = value
        return key
    end,
    decode = function(value)
        if encoded[value] == nil then error("invalid json") end
        return encoded[value]
    end,
}
package.preload["cjson"] = function() return json end

local sync_store = {}
local set_error = nil
package.preload["bunkerweb.datastore"] = function()
    return {
        new = function()
            return {
                get = function(_, key)
                    if sync_store[key] == nil then return nil, "not found" end
                    return sync_store[key]
                end,
                set = function(_, key, value)
                    if set_error then return false, set_error end
                    sync_store[key] = value
                    return true, "success"
                end,
            }
        end,
    }
end

local lock_held = false
package.preload["resty.lock"] = function()
    return {
        new = function()
            return {
                lock = function()
                    assert(not lock_held)
                    lock_held = true
                    return 0
                end,
                unlock = function()
                    assert(lock_held)
                    lock_held = false
                    return true
                end,
            }
        end,
    }
end

local now = 100
local response_status = 200
local response_payload = nil
local request_error = nil
local requested_timeout = nil
package.preload["bunkerweb.internal_api"] = function()
    return {
        request = function(path, options)
            assert(not lock_held, "network request made under commit lock")
            assert(path == "/bans")
            requested_timeout = options.timeout
            if request_error then return nil, request_error end
            return { status = response_status, body = json.encode(response_payload) }
        end,
    }
end

ngx = {
    shared = { ban_sync_stream = {} },
    worker = { id = function() return 0 end },
    now = function() return now end,
    time = function() return now end,
}

local ban_sync = dofile(arg[1])
"""


UTILS_PREAMBLE = r"""
local subsystem = arg[2]
local encoded, next_json = {}, 0
local json = {
    encode = function(value)
        next_json = next_json + 1
        local key = "json:" .. next_json
        encoded[key] = value
        return key
    end,
    decode = function(value)
        if encoded[value] == nil then error("invalid json") end
        return encoded[value]
    end,
}
package.preload["cjson"] = function() return json end

local now, lock_now = 100, nil
local lock_held = false
local main_store, main_ttls = {}, {}
local sync_store, epoch_store = {}, {}
local internal_store = { variables = { global = { USE_REDIS = "no" } } }
local datastore_writes = 0

ngx = {
    var = {},
    ERR = 3,
    INFO = 6,
    WARN = 4,
    HTTP_FORBIDDEN = 403,
    HTTP_CLOSE = 444,
    null = {},
    re = { match = function() return nil end },
    config = { subsystem = subsystem },
    get_phase = function() return "timer" end,
    thread = { kill = function() return true end },
    shared = {
        datastore = {},
        datastore_stream = {},
        internalstore = {},
        internalstore_stream = {},
        ban_sync = {},
        ban_sync_stream = {},
    },
    now = function() return now end,
}

local function choose_store(dict)
    if dict == ngx.shared.ban_sync_stream then return sync_store, {} end
    if dict == ngx.shared.ban_sync then return epoch_store, {} end
    if dict == ngx.shared.internalstore or dict == ngx.shared.internalstore_stream then
        return internal_store, {}
    end
    return main_store, main_ttls
end

package.preload["bunkerweb.datastore"] = function()
    return {
        new = function(_, dict)
            local values, ttls = choose_store(dict)
            return {
                dict = {
                    safe_add = function(_, key, value)
                        if values[key] ~= nil then return false, "exists" end
                        values[key] = value
                        return true
                    end,
                    incr = function(_, key, amount)
                        if values[key] == nil then return nil, "not found" end
                        values[key] = values[key] + amount
                        return values[key]
                    end,
                },
                get = function(_, key)
                    if values[key] == nil then return nil, "not found" end
                    return values[key]
                end,
                set = function(_, key, value, ttl)
                    values[key], ttls[key] = value, ttl
                    if values == main_store then datastore_writes = datastore_writes + 1 end
                    return true, "success"
                end,
                set_with_retries = function(_, key, value, ttl)
                    values[key], ttls[key] = value, ttl
                    if values == main_store then datastore_writes = datastore_writes + 1 end
                    return true, "success"
                end,
                delete = function(_, key)
                    values[key], ttls[key] = nil, nil
                    if values == main_store then datastore_writes = datastore_writes + 1 end
                    return true, "success"
                end,
                keys = function()
                    local keys = {}
                    for key in pairs(values) do keys[#keys + 1] = key end
                    return keys
                end,
                ttl = function(_, key)
                    return true, ttls[key] or 0
                end,
            }
        end,
    }
end

local logs = {}
package.preload["bunkerweb.logger"] = function()
    return {
        new = function()
            return {
                log = function(_, _, message) logs[#logs + 1] = message end,
            }
        end,
    }
end
package.preload["bunkerweb.mmdb"] = function() return {} end
package.preload["resty.ipmatcher"] = function()
    return {
        new = function() return { match = function() return false end } end,
        parse_ipv4 = function(ip) return type(ip) == "string" and ip:find(".", 1, true) end,
        parse_ipv6 = function(ip) return type(ip) == "string" and ip:find(":", 1, true) end,
    }
end
package.preload["resty.random"] = function()
    return { bytes = function(size) return string.rep("x", size) end }
end
package.preload["resty.dns.resolver"] = function() return { new = function() return {} end } end
package.preload["resty.session"] = function() return { start = function() return {} end } end
package.preload["resty.lock"] = function()
    return {
        new = function()
            return {
                lock = function()
                    assert(not lock_held)
                    lock_held = true
                    if lock_now then now = lock_now end
                    return 0
                end,
                unlock = function()
                    assert(lock_held)
                    lock_held = false
                    return true
                end,
            }
        end,
    }
end

local api_status, api_error = 200, nil
local api_calls = {}
package.preload["bunkerweb.internal_api"] = function()
    return {
        request = function(path, options)
            assert(not lock_held)
            api_calls[#api_calls + 1] = {
                path = path,
                body = json.decode(options.body),
                timeout = options.timeout,
            }
            if api_error then return nil, api_error end
            return { status = api_status, body = "ok" }
        end,
    }
end

local redis_connect_ok, redis_connect_calls = true, 0
local redis_delete_error = nil
local redis_lookup_results, redis_scan_results = {}, {}
local redis_scan_error = nil
local redis_calls = {}
package.preload["bunkerweb.clusterstore"] = function()
    return {
        new = function()
            return {
                connect = function()
                    redis_connect_calls = redis_connect_calls + 1
                    if redis_connect_ok then return true end
                    return false, "redis unavailable"
                end,
                call = function(_, ...)
                    local arguments = { ... }
                    redis_calls[#redis_calls + 1] = arguments
                    if arguments[1] == "eval" then
                        return redis_lookup_results[arguments[4]] or { ngx.null, ngx.null }
                    end
                    if arguments[1] == "scan" then
                        if redis_scan_error then return nil, redis_scan_error end
                        return redis_scan_results[arguments[2]] or { "0", {} }
                    end
                    if arguments[1] == "del" and redis_delete_error then
                        return false, redis_delete_error
                    end
                    return true
                end,
                close = function() return true end,
            }
        end,
    }
end

local utils = dofile(arg[1])
"""


def _run_lua(preamble: str, body: str, *args: str) -> None:
    assert LUA is not None
    result = subprocess.run(
        [LUA, "-", *args],
        input=preamble + body,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _run_sync(body: str) -> None:
    _run_lua(SYNC_PREAMBLE, body, str(BAN_SYNC_LUA))


def _run_utils(subsystem: str, body: str) -> None:
    _run_lua(UTILS_PREAMBLE, body, str(UTILS_LUA), subsystem)


def test_old_queue_fence_and_cross_datastore_protocol_is_removed():
    sources = (BAN_SYNC_LUA.read_text() + UTILS_LUA.read_text() + API_LUA.read_text()).lower()
    for obsolete in (
        "ban_sync_pending_",
        "ban_sync_version_",
        "ban_sync_reset_",
        "x-bunkerweb-ban-generation",
        "acknowledge_ban_authority",
        "pending ban operation",
        "other_datastore",
    ):
        assert obsolete not in sources

    assert 'local internal_api = subsystem == "stream"' in UTILS_LUA.read_text()
    assert "not queued for retry" in UTILS_LUA.read_text()


def test_snapshot_zones_and_recurrent_timer_are_wired():
    http = HTTP_CONF.read_text()
    stream = STREAM_CONF.read_text()
    timer = INIT_STREAM_CONF.read_text()

    assert "lua_shared_dict ban_sync " in http
    assert "lua_shared_dict ban_sync_stream {{ normalize_memory_size(DATASTORE_MEMORY_SIZE) }};" in stream
    assert "local hdl, err = timer_at(0, recurrent_timer)" in timer
    loading = timer.index('elseif is_loading == "yes" then')
    assert loading < timer.index("reconcile_bans(logger)", loading)
    reconcile = timer.index("pcall(ban_sync.reconcile)")
    assert reconcile < timer.index("timer_at(5, recurrent_timer)", reconcile)


def test_http_snapshot_contract_is_locked_absolute_and_monotonic():
    source = API_LUA.read_text()
    route = source.partition('api.global.GET["^/bans$"]')[2].partition('api.global.GET["^/variables$"]')[0]

    assert "utils.with_ban_snapshot_lock" in route
    assert "utils.next_ban_snapshot_epoch()" in route
    assert "snapshot_response.snapshot_time" in route
    assert "expires_at = expires_at" in route
    assert "reason_data" in route
    assert "utils.acknowledge_ban_authority" not in route


def test_internal_deadline_validation_is_finite_and_passed_to_locked_mutations():
    api = API_LUA.read_text()
    utils = UTILS_LUA.read_text()

    assert api.count('self.ctx.bw.remote_addr == "unix:" and ip["not_after"] ~= nil') == 2
    assert api.count("not_after == math.huge") == 2
    assert api.count("not_after ~= not_after") == 2
    assert 'utils.remove_ban(ip["ip"], service, ban_scope, not_after)' in api
    assert "ban.reason_data, not_after" in api

    add_ban = utils.partition("utils.add_ban = function")[2].partition("utils.remove_ban = function")[0]
    remove_ban = utils.partition("utils.remove_ban = function")[2].partition("utils.new_cachestore = function")[0]
    assert add_ban.index("with_ban_snapshot_lock(function()") < add_ban.index("wall_time() > not_after")
    assert remove_ban.index("with_ban_snapshot_lock(function()") < remove_ban.index("wall_time() > not_after")


def test_badbehavior_redis_path_only_updates_the_counter():
    source = BADBEHAVIOR_LUA.read_text()
    match = re.search(
        r"function badbehavior:redis_increase\(.*?\nend\n\nfunction badbehavior:redis_decrease",
        source,
        re.S,
    )
    assert match
    function = match.group(0)

    assert 'redis.pcall("INCR", KEYS[1])' in function
    assert 'redis.pcall("EXPIRE", KEYS[1], ARGV[1])' in function
    assert '"eval", redis_script, 1, counter_key, count_time' in function
    assert 'redis.pcall("SET"' not in function
    assert "bans_ip_" not in function
    assert source.count("add_ban(") == 1


@needs_lua
def test_snapshot_publish_preserves_global_service_metadata_and_reason_data():
    _run_sync(r"""
response_payload = {
    status = "success",
    generation_epoch = 7,
    snapshot_time = 90,
    data = {
        {
            ip = "192.0.2.1", reason = "manual", service = "unknown",
            country = "FR", ban_scope = "global", permanent = true,
            expires_at = 0, reason_data = { source = "api" }, date = 80,
        },
        {
            ip = "2001:db8::1", reason = "bad behavior", service = "smtp",
            country = "DE", ban_scope = "service", permanent = false,
            expires_at = 140, reason_data = { status = "500" }, date = 85,
        },
    },
}
local ok, err = ban_sync.reconcile()
assert(ok, err)
assert(requested_timeout == 1000)
local record = json.decode(assert(sync_store.ban_snapshot))
assert(record.generation_epoch == 7)
assert(record.source_snapshot_time == 90)
local global = assert(record.bans["bans_ip_192.0.2.1"])
assert(global.permanent and global.reason_data.source == "api" and global.country == "FR")
local service = assert(record.bans["bans_service_smtp_ip_2001:db8::1"])
assert(service.expires_at == 140 and service.reason_data.status == "500")
""")


@needs_lua
def test_absolute_expiry_consumes_transport_delay():
    _run_sync(r"""
now = 151
response_payload = {
    status = "success", generation_epoch = 1, snapshot_time = 100,
    data = {
        {
            ip = "192.0.2.10", reason = "expired", service = "unknown",
            country = "FR", ban_scope = "global", permanent = false,
            expires_at = 150, reason_data = {},
        },
        {
            ip = "192.0.2.11", reason = "permanent", service = "unknown",
            country = "FR", ban_scope = "global", permanent = true,
            expires_at = 0, reason_data = {},
        },
    },
}
assert(ban_sync.reconcile())
local record = json.decode(assert(sync_store.ban_snapshot))
assert(record.bans["bans_ip_192.0.2.10"] == nil)
assert(record.bans["bans_ip_192.0.2.11"] ~= nil)
""")


@needs_lua
def test_older_snapshot_cannot_overwrite_newer_snapshot():
    _run_sync(r"""
response_payload = {
    status = "success", generation_epoch = 5, snapshot_time = 90,
    data = {
        {
            ip = "192.0.2.5", reason = "new", service = "unknown",
            country = "FR", ban_scope = "global", permanent = false,
            expires_at = 150, reason_data = {},
        },
    },
}
assert(ban_sync.reconcile())
local committed = assert(sync_store.ban_snapshot)

response_payload = {
    status = "success", generation_epoch = 4, snapshot_time = 80,
    data = {
        {
            ip = "192.0.2.4", reason = "stale", service = "unknown",
            country = "FR", ban_scope = "global", permanent = true,
            expires_at = 0, reason_data = {},
        },
    },
}
assert(ban_sync.reconcile())
assert(sync_store.ban_snapshot == committed)

response_payload.generation_epoch = 5
response_payload.data[1].permanent = false
response_payload.data[1].expires_at = 9999
assert(ban_sync.reconcile())
assert(sync_store.ban_snapshot == committed)
""")


@needs_lua
def test_malformed_and_duplicate_snapshots_preserve_committed_state():
    _run_sync(r"""
response_payload = {
    status = "success", generation_epoch = 1, snapshot_time = 90,
    data = {
        {
            ip = "192.0.2.1", reason = "old", service = "unknown",
            country = "FR", ban_scope = "global", permanent = true,
            expires_at = 0, reason_data = {},
        },
    },
}
assert(ban_sync.reconcile())
local committed = assert(sync_store.ban_snapshot)

response_payload = {
    status = "success", generation_epoch = 2, snapshot_time = 91,
    data = {
        {
            ip = "192.0.2.2", reason = "first", service = "unknown",
            country = "FR", ban_scope = "global", permanent = true,
            expires_at = 0, reason_data = {},
        },
        {
            ip = "192.0.2.2", reason = "duplicate", service = "unknown",
            country = "FR", ban_scope = "global", permanent = true,
            expires_at = 0, reason_data = {},
        },
    },
}
local ok, err = ban_sync.reconcile()
assert(not ok and err == "duplicate ban in /bans response")
assert(sync_store.ban_snapshot == committed)

response_payload.data = {
    {
        ip = "192.0.2.3", reason = "missing expiry", service = "unknown",
        country = "FR", ban_scope = "global", permanent = false,
        reason_data = {},
    },
}
ok, err = ban_sync.reconcile()
assert(not ok and err == "invalid absolute ban expiry in /bans response")
assert(sync_store.ban_snapshot == committed)
""")


@needs_lua
def test_failed_atomic_publish_retains_previous_snapshot():
    _run_sync(r"""
response_payload = {
    status = "success", generation_epoch = 1, snapshot_time = 90,
    data = {
        {
            ip = "192.0.2.1", reason = "old", service = "unknown",
            country = "FR", ban_scope = "global", permanent = true,
            expires_at = 0, reason_data = {},
        },
    },
}
assert(ban_sync.reconcile())
local committed = assert(sync_store.ban_snapshot)

response_payload.generation_epoch = 2
response_payload.data[1].reason = "new"
set_error = "no memory"
local ok, err = ban_sync.reconcile()
assert(not ok and err:find("without eviction", 1, true))
assert(sync_store.ban_snapshot == committed)
""")


@needs_lua
def test_snapshot_transport_failure_is_explicit_and_keeps_state():
    _run_sync(r"""
response_payload = {
    status = "success", generation_epoch = 1, snapshot_time = 90, data = {},
}
assert(ban_sync.reconcile())
local committed = sync_store.ban_snapshot

response_status = 503
local ok, err = ban_sync.reconcile()
assert(not ok and err == "internal API returned HTTP 503")
assert(sync_store.ban_snapshot == committed)

response_status = 200
request_error = "unavailable"
ok, err = ban_sync.reconcile()
assert(not ok and err == "unavailable")
assert(sync_store.ban_snapshot == committed)
""")


@needs_lua
def test_stream_mutations_forward_once_without_local_state_or_retry():
    _run_utils(
        "stream",
        r"""
local ok, err = utils.add_ban(
    "192.0.2.1", "bad behavior", 30, "smtp", "FR", "service", { status = "500" }
)
assert(ok, err)
assert(#api_calls == 1 and api_calls[1].path == "/ban" and api_calls[1].timeout == 1000)
local body = api_calls[1].body
assert(body.ip == "192.0.2.1" and body.exp == 30 and body.ban_scope == "service")
assert(body.reason_data.status == "500" and body.not_after == 101)
assert(datastore_writes == 0 and next(main_store) == nil)

api_status = 503
ok, err = utils.remove_ban("192.0.2.1", "smtp", "service")
assert(not ok and err == "internal API returned HTTP 503")
assert(#api_calls == 2 and datastore_writes == 0 and next(main_store) == nil)

api_status = 200
api_error = "unavailable"
ok, err = utils.add_ban("192.0.2.2", "manual", 0, nil, "FR", "global", {})
assert(not ok and err == "unavailable")
assert(#api_calls == 3 and datastore_writes == 0 and next(main_store) == nil)
assert(#logs >= 2 and logs[#logs]:find("not queued for retry", 1, true))
""",
    )


@needs_lua
def test_stream_enforcement_prefers_service_and_recomputes_absolute_ttl():
    _run_utils(
        "stream",
        r"""
sync_store.ban_snapshot = json.encode({
    generation_epoch = 1,
    bans = {
        ["bans_ip_192.0.2.1"] = {
            reason = "global", permanent = true, expires_at = 0,
            reason_data = { source = "global" },
        },
        ["bans_service_smtp_ip_192.0.2.1"] = {
            reason = "service", permanent = false, expires_at = 110,
            reason_data = { source = "service" },
        },
    },
})
local banned, reason, ttl, reason_data = utils.is_banned("192.0.2.1", "smtp")
assert(banned and reason == "service" and ttl == 10 and reason_data.source == "service")

now = 111
banned, reason, ttl, reason_data = utils.is_banned("192.0.2.1", "smtp")
assert(banned and reason == "global" and ttl == 0 and reason_data.source == "global")

sync_store.ban_snapshot = json.encode({
    generation_epoch = 2,
    bans = {
        ["bans_ip_192.0.2.1"] = {
            reason = "expired", permanent = false, expires_at = 105, reason_data = {},
        },
    },
})
banned, reason = utils.is_banned("192.0.2.1", "smtp")
assert(not banned and reason == "not banned")
""",
    )


@needs_lua
def test_stream_snapshot_miss_uses_redis_but_ignores_legacy_local_bans():
    _run_utils(
        "stream",
        r"""
internal_store.variables.global.USE_REDIS = "yes"
sync_store.ban_snapshot = json.encode({ generation_epoch = 1, bans = {} })

local service_raw = json.encode({
    reason = "redis service", permanent = false,
    reason_data = { source = "redis-service" },
})
redis_lookup_results["bans_service_smtp_ip_192.0.2.20"] = { service_raw, 45 }
local banned, reason, ttl, reason_data = utils.is_banned("192.0.2.20", "smtp")
assert(banned and reason == "redis service" and ttl == 45)
assert(reason_data.source == "redis-service")
assert(main_store["ban_redis_cache_bans_service_smtp_ip_192.0.2.20"] == service_raw)

local global_raw = json.encode({
    reason = "redis global", permanent = true,
    reason_data = { source = "redis-global" },
})
redis_lookup_results["bans_ip_192.0.2.21"] = { global_raw, -1 }
banned, reason, ttl, reason_data = utils.is_banned("192.0.2.21", "smtp")
assert(banned and reason == "redis global" and ttl == 0)
assert(reason_data.source == "redis-global")
assert(main_store["ban_redis_cache_bans_ip_192.0.2.21"] == global_raw)

-- A live upgrade can leave old permanent bans_* entries in datastore_stream.
-- Snapshot misses must never consult that legacy namespace.
main_store["bans_ip_192.0.2.22"] = json.encode({ reason = "stale", permanent = true })
banned, reason = utils.is_banned("192.0.2.22", "smtp")
assert(not banned and reason == "not banned")
""",
    )


@needs_lua
def test_http_deadline_is_checked_after_lock_and_mutations_advance_epoch():
    _run_utils(
        "http",
        r"""
lock_now = 102
local ok, err = utils.add_ban("192.0.2.1", "late", 30, nil, "FR", "global", {}, 101)
assert(not ok and err == "ban mutation deadline expired")
assert(next(main_store) == nil and epoch_store.ban_snapshot_epoch == nil)

lock_now = nil
now = 100
ok, err = utils.add_ban("192.0.2.1", "manual", 30, nil, "FR", "global", { source = "api" })
assert(ok, err)
assert(epoch_store.ban_snapshot_epoch == 1)
local data = json.decode(assert(main_store["bans_ip_192.0.2.1"]))
assert(data.expires_at == 130 and data.reason_data.source == "api")

ok, err = utils.remove_ban("192.0.2.1", nil, "global")
assert(ok, err)
assert(main_store["bans_ip_192.0.2.1"] == nil)
assert(epoch_store.ban_snapshot_epoch == 2)
""",
    )


@needs_lua
def test_http_retains_local_first_redis_outage_behavior():
    _run_utils(
        "http",
        r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_connect_ok = false

local ok, err = utils.add_ban("192.0.2.10", "manual", 30, nil, "FR", "global", {})
assert(not ok and err:find("redis unavailable", 1, true))
assert(main_store["bans_ip_192.0.2.10"] ~= nil)
assert(epoch_store.ban_snapshot_epoch == 1)

-- UDS callers get a truthful failure after the local-first removal; there is
-- no Stream-local retry and Redis fallback continues cluster enforcement.
ok, err = utils.remove_ban("192.0.2.10", nil, "global", 101)
assert(not ok and err:find("redis unavailable", 1, true))
assert(main_store["bans_ip_192.0.2.10"] == nil)
assert(epoch_store.ban_snapshot_epoch == 2)

ok, err = utils.add_ban("192.0.2.11", "manual", 30, nil, "FR", "global", {})
assert(not ok and main_store["bans_ip_192.0.2.11"] ~= nil)
assert(epoch_store.ban_snapshot_epoch == 3)

-- Redis failures are explicit so a removed ban cannot silently reappear from another instance.
ok, err = utils.remove_ban("192.0.2.11", nil, "global")
assert(not ok and err:find("redis unavailable", 1, true))
assert(main_store["bans_ip_192.0.2.11"] == nil)
assert(epoch_store.ban_snapshot_epoch == 4)
""",
    )


@needs_lua
def test_global_unban_reports_redis_delete_failure_after_local_removal():
    _run_utils(
        "http",
        r"""
assert(utils.add_ban("192.0.2.30", "manual", 30, nil, "FR", "global", {}))
assert(main_store["bans_ip_192.0.2.30"] ~= nil)

internal_store.variables.global.USE_REDIS = "yes"
redis_delete_error = "write failed"
local ok, err = utils.remove_ban("192.0.2.30", nil, "global")
assert(not ok and err:find("redis DEL failed", 1, true))
assert(main_store["bans_ip_192.0.2.30"] == nil)
assert(epoch_store.ban_snapshot_epoch == 2)
""",
    )


@needs_lua
def test_ban_lookup_uses_local_cache_before_redis_outage():
    _run_utils(
        "http",
        r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_connect_ok = false
local raw = json.encode({ reason = "local", permanent = true, reason_data = { source = "http" } })
main_store["bans_service_smtp_ip_192.0.2.40"] = raw

local banned, reason, ttl, reason_data = utils.is_banned("192.0.2.40", "smtp")
assert(banned and reason == "local" and ttl == 0 and reason_data.source == "http")
assert(redis_connect_calls == 0)

banned, reason = utils.is_banned("192.0.2.41", "smtp")
assert(banned == nil and reason:find("redis unavailable", 1, true))
assert(redis_connect_calls == 1)
""",
    )

    _run_utils(
        "stream",
        r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_connect_ok = false
sync_store.ban_snapshot = json.encode({ generation_epoch = 1, bans = {} })
local cached = json.encode({ reason = "cached", permanent = true, reason_data = { source = "cache" } })
main_store["ban_redis_cache_bans_ip_192.0.2.42"] = cached

local banned, reason, ttl, reason_data = utils.is_banned("192.0.2.42", "smtp")
assert(banned and reason == "cached" and ttl == 0 and reason_data.source == "cache")
assert(redis_connect_calls == 0)

sync_store.ban_snapshot = json.encode({
    generation_epoch = 2,
    bans = {
        ["bans_ip_192.0.2.43"] = { reason = "snapshot", permanent = true, expires_at = 0, reason_data = {} },
    },
})
banned, reason, ttl = utils.is_banned("192.0.2.43", "smtp")
assert(banned and reason == "snapshot" and ttl == 0)
assert(redis_connect_calls == 0)

banned, reason = utils.is_banned("192.0.2.44", "smtp")
assert(banned == nil and reason:find("redis unavailable", 1, true))
assert(redis_connect_calls == 1)
""",
    )


@needs_lua
def test_global_unban_discovers_redis_only_service_bans_with_scan():
    _run_utils(
        "http",
        r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_scan_results["0"] = { "1", { "bans_service_smtp_ip_192.0.2.50" } }
redis_scan_results["1"] = { "0", { "bans_service_imap_ip_192.0.2.50" } }

local ok, err = utils.remove_ban("192.0.2.50", nil, "global", 101)
assert(ok, err)
assert(next(main_store) == nil)

-- DEL is batched : one call carries every key it found, instead of one round-trip per
-- key. Look for each key anywhere in the argument list rather than assuming its position.
local scan_count, deleted_global, deleted_smtp, deleted_imap = 0, false, false, false
for _, arguments in ipairs(redis_calls) do
    if arguments[1] == "scan" then
        assert(arguments[4] == "bans_service_*_ip_192.0.2.50")
        scan_count = scan_count + 1
    elseif arguments[1] == "del" then
        for i = 2, #arguments do
            if arguments[i] == "bans_ip_192.0.2.50" then
                deleted_global = true
            elseif arguments[i] == "bans_service_smtp_ip_192.0.2.50" then
                deleted_smtp = true
            elseif arguments[i] == "bans_service_imap_ip_192.0.2.50" then
                deleted_imap = true
            end
        end
    end
end
assert(scan_count == 2 and deleted_global and deleted_smtp and deleted_imap)
""",
    )


@needs_lua
def test_global_unban_fails_on_redis_scan_error_or_non_progress():
    _run_utils(
        "http",
        r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_scan_error = "read failed"
local ok, err = utils.remove_ban("192.0.2.51", nil, "global")
assert(not ok and err == "redis SCAN failed : read failed")
""",
    )

    _run_utils(
        "http",
        r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_scan_results["0"] = { nil, {} }
local ok, err = utils.remove_ban("192.0.2.53", nil, "global")
assert(not ok and err == "redis SCAN failed : nil")
""",
    )

    _run_utils(
        "http",
        r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_scan_results["0"] = { "1", {} }
redis_scan_results["1"] = { "1", {} }
local ok, err = utils.remove_ban("192.0.2.52", nil, "global")
assert(not ok and err == "redis SCAN cursor did not advance")
""",
    )
