"""Real 1.7 ban lookup and Cluster retry adapter under migrating-slot replies."""

from pathlib import Path

import pytest

from test_ban_sync import LUA, UTILS_LUA, UTILS_PREAMBLE, _run_lua

pytestmark = pytest.mark.skipif(LUA is None, reason="Lua interpreter required")
ROOT = Path(__file__).resolve().parents[3]

HARNESS = r"""
package.loaded["bunkerweb.utils"] = utils
package.loaded["resty.redis.connector"] = {}
local adapter = dofile(arg[3])
local TRYAGAIN = "TRYAGAIN Multiple keys request during rehashing of slot"
local records, ttls, calls, sleeps = {}, {}, {}, {}
local failure, expire_on_ttl, transient_get = nil, false, false
ngx.sleep = function(delay) sleeps[#sleeps + 1] = delay end
internal_store.variables.global.USE_REDIS = "yes"
internal_store.variables.global.REDIS_CLUSTER_NODES = "redis:6379"
local closed = false
package.loaded["bunkerweb.clusterstore"] = {
    new = function()
        local store = adapter:allocate()
        store.cluster_mode = true
        store.healthy = true
        store.connect = function() return true end
        store.close = function() closed = true return true end
        store.redis_client = {
            eval = function() calls.eval = (calls.eval or 0) + 1 return false, TRYAGAIN end,
            get = function(_, key)
                calls.get = (calls.get or 0) + 1
                if failure then return false, failure end
                if transient_get and calls.get == 1 then return false, TRYAGAIN end
                return records[key] or ngx.null
            end,
            ttl = function(_, key)
                calls.ttl = (calls.ttl or 0) + 1
                if expire_on_ttl then return -2 end
                return ttls[key] or -1
            end,
        }
        return store
    end,
}
local function put(scope, reason, ttl, data)
    local key = scope == "service" and "bans_service_www_ip_{192.0.2.1}" or "bans_ip_{192.0.2.1}"
    records[key] = json.encode({reason = reason, reason_data = data, permanent = ttl == -1})
    ttls[key] = ttl
end
"""


@pytest.mark.parametrize("scope", ["global", "service"])
@pytest.mark.parametrize("ttl", [120, -1])
def test_migrating_slot_keeps_redis_only_ban(scope, ttl):
    check = f'put("{scope}", "manual", {ttl})\n' + r"""
local banned, reason, ttl = utils.is_banned("192.0.2.1", "www")
assert(banned == true and reason == "manual", tostring(banned) .. " " .. tostring(reason))
assert(ttl == math.max(TTL, 0), tostring(ttl))
assert(calls.eval == 1 and calls.get == 2 and #sleeps == 0)
assert(closed)
""".replace("TTL", str(ttl))
    run(check)


def run(check):
    _run_lua(UTILS_PREAMBLE, HARNESS + check, str(UTILS_LUA), "http", str(ROOT / "src/bw/lua/bunkerweb/clusterstore.lua"))


def test_explicit_global_ban_outranks_service_lease():
    run(r"""
put("service", "crowdsec", 20, {lease = true})
put("global", "manual", 120)
local banned, reason = utils.is_banned("192.0.2.1", "www")
assert(banned == true and reason == "manual", tostring(reason))
""")


def test_missing_and_expired_keys_remain_misses():
    run(r"""
put("global", "manual", 120)
expire_on_ttl = true
local banned, reason = utils.is_banned("192.0.2.1", "www")
assert(banned == false and reason == "not banned", tostring(banned) .. " " .. tostring(reason))
assert(closed)
""")


def test_transient_single_key_tryagain_retries_and_finds_ban():
    run(r"""
put("global", "manual", 120)
transient_get = true
local banned, reason = utils.is_banned("192.0.2.1", "www")
assert(banned == true and reason == "manual")
assert(calls.eval == 1 and calls.get == 3 and #sleeps == 1 and sleeps[1] == 0.02)
""")


@pytest.mark.parametrize("error", ["TRYAGAIN Multiple keys request during rehashing of slot", "ERR denied"])
def test_exhaustion_reports_redis_error_instead_of_clean_miss(error):
    run(f'failure = "{error}"\n' + r"""
local banned, reason = utils.is_banned("192.0.2.1", "www")
assert(banned == nil and reason:find(failure, 1, true), tostring(banned) .. " " .. tostring(reason))
assert(calls.eval == 1 and calls.get == (failure:find("^TRYAGAIN") and 4 or 1))
assert(closed)
""")
