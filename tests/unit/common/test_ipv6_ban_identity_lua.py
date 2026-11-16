"""One client address, one ban: every spelling of an address reaches the same ban key (dev 93c91c40e on 1.7's storage).

NGINX prints `$remote_addr` as RFC 5952 text, while an operator, the API, the CLI or a feed may spell the same IPv6
address expanded or in upper case, and `::ffff:a.b.c.d` is the IPv4 address `a.b.c.d`. The ban keys of the shared dict
and of Redis are text, so a spelling that is not the canonical one is a ban that never matches (or an unban that misses).

The harness is `test_ban_lease_lua.LEASE_PREAMBLE`: the real `utils.lua`, a Redis that executes the scripts it is sent.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_ban_lease_lua import LUA, ROOT, needs_lua, run_lease  # noqa: E402

SPELLINGS = ["2001:db8::1", "2001:DB8::1", "2001:0db8:0:0:0:0:0:1", "2001:DB8:0:0:0:0:0:0001"]
MAPPED = ["::ffff:192.0.2.1", "::FFFF:192.0.2.1", "::ffff:c000:201", "0:0:0:0:0:ffff:192.0.2.1"]


def _lua_list(values):
    return "{" + ", ".join(f'"{value}"' for value in values) + "}"


@needs_lua
def test_a_ban_holds_for_every_spelling_of_an_ipv6_address():
    run_lease(r"""
for _, spelling in ipairs(%s) do
    assert(utils.add_ban(spelling, "manual", 300, nil, "FR", "global", {}), spelling)
end
local keys = {}
for key in pairs(main_store) do keys[#keys + 1] = key end
assert(#keys == 1 and keys[1] == "bans_ip_2001:db8::1", "one address, one key: " .. table.concat(keys, ","))
for _, spelling in ipairs(%s) do
    local banned = utils.is_banned(spelling, "www")
    assert(banned == true, "not banned under " .. spelling)
end
assert(utils.is_banned("2001:db8::2", "www") == false, "another address must never collide")
""" % (_lua_list(SPELLINGS), _lua_list(SPELLINGS)))


@needs_lua
def test_an_ipv4_mapped_address_is_its_ipv4_address():
    run_lease(r"""
assert(utils.add_ban("::ffff:192.0.2.1", "manual", 300, nil, "FR", "global", {}))
assert(main_store["bans_ip_192.0.2.1"] ~= nil and main_store["bans_ip_::ffff:192.0.2.1"] == nil)
for _, spelling in ipairs(%s) do
    assert(utils.is_banned(spelling, "www") == true, "mapped client not banned under " .. spelling)
end
assert(utils.is_banned("192.0.2.1", "www") == true)
assert(utils.is_banned("192.0.2.2", "www") == false)
-- and the other way round: an IPv4 ban holds for the mapped spelling of its client
assert(utils.add_ban("198.51.100.7", "manual", 300, nil, "FR", "global", {}))
assert(utils.is_banned("::ffff:198.51.100.7", "www") == true)
""" % _lua_list(MAPPED))


@needs_lua
def test_a_service_ban_and_its_local_view_follow_the_same_identity():
    run_lease(r"""
assert(utils.add_ban("2001:DB8::1", "manual", 300, "www", "FR", "service", {}))
assert(main_store["bans_service_www_ip_2001:db8::1"] ~= nil)
assert(utils.is_banned("2001:db8:0:0:0:0:0:1", "www") == true)
assert(utils.is_banned("2001:db8::1", "other") == false)
local banned = utils.is_banned_local("2001:0DB8::1", "www")
assert(banned == true, "the ClientHello lookup must read the same key")
""")


@needs_lua
def test_an_unban_under_another_spelling_removes_the_ban_locally_and_in_redis():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
assert(utils.add_ban("2001:db8::1", "manual", 300, nil, "FR", "global", {}))
assert(utils.add_ban("2001:db8::1", "manual", 300, "www", "FR", "service", {}))
assert(redis_kv["bans_ip_2001:db8::1"] and redis_kv["bans_service_www_ip_2001:db8::1"])
local ok, msg = utils.remove_ban("2001:0DB8:0:0:0:0:0:1")
assert(ok == true, tostring(msg))
assert(next(main_store) == nil, "a local key survived the unban")
assert(redis_kv["bans_ip_2001:db8::1"] == nil and redis_kv["bans_service_www_ip_2001:db8::1"] == nil, "a Redis key survived")
assert(utils.is_banned("2001:db8::1", "www") == false)
""")


@needs_lua
def test_a_ban_stored_under_a_raw_spelling_by_an_older_version_still_unbans():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
local legacy = ban_value("manual", {}, { permanent = true, expires_at = 0 })
-- what 1.7 wrote when the key was whatever spelling reached it
for _, key in ipairs({ "bans_ip_::ffff:192.0.2.1", "bans_ip_2001:DB8::1", "bans_service_www_ip_::ffff:192.0.2.1" }) do
    main_store[key] = legacy
    redis_kv[key] = legacy
end
assert(utils.remove_ban("192.0.2.1"))
assert(main_store["bans_ip_::ffff:192.0.2.1"] == nil and main_store["bans_service_www_ip_::ffff:192.0.2.1"] == nil, "mapped legacy key left locally")
assert(redis_kv["bans_ip_::ffff:192.0.2.1"] == nil and redis_kv["bans_service_www_ip_::ffff:192.0.2.1"] == nil, "mapped legacy key left in Redis")
assert(utils.remove_ban("2001:db8::1"))
assert(main_store["bans_ip_2001:DB8::1"] == nil, "upper case legacy key left locally")
assert(redis_kv["bans_ip_2001:DB8::1"] == nil, "upper case legacy key left in Redis")
""")


@needs_lua
def test_an_invalid_address_is_refused_with_the_historical_message():
    run_lease(r"""
for _, bad in ipairs({ "fe80::1%eth0", "[2001:db8::1]", "2001:db8::1/64", "example.com", "1::2::3" }) do
    local ok, msg = utils.add_ban(bad, "manual", 60, nil, nil, "global", {})
    assert(ok == false and msg == "invalid IP address", bad .. " " .. tostring(msg))
end
assert(next(main_store) == nil)
""")


@needs_lua
def test_a_stream_snapshot_built_from_the_database_keys_a_legacy_row_by_its_identity():
    """ban_sync reads GET /bans (the database): a row stored under a raw spelling must land on the canonical key."""
    result = subprocess.run(
        [
            LUA,
            "-",
            str(ROOT / "src/bw/lua"),
        ],
        input=r"""
package.path = arg[1] .. "/?.lua;" .. package.path
local registry = {}
package.preload["cjson"] = function()
    return { encode = function(v) registry[#registry + 1] = v return "json:" .. #registry end, decode = function(t) return registry[tonumber(t:match("%d+"))] end }
end
local store = {}
package.preload["bunkerweb.datastore"] = function()
    return { new = function() return { get = function(_, k) return store[k], store[k] and "ok" or "not found" end, set = function(_, k, v) store[k] = v return true end } end }
end
package.preload["bunkerweb.internal_api"] = function() return { request = function() end } end
package.preload["bunkerweb.rediskeys"] = function() return { ban = function(key) return key end } end
package.preload["resty.lock"] = function() return { new = function() return { lock = function() return 0 end, unlock = function() return true end } end } end
_G.ngx = { shared = { ban_sync_stream = {} }, worker = { id = function() return 0 end }, now = function() return 1000 end, time = function() return 1000 end }
local ban_sync = require "bunkerweb.ban_sync"
local snapshot, count = ban_sync._build_snapshot or nil, nil
assert(ban_sync._build_snapshot, "ban_sync must expose its snapshot builder to be tested")
local snap, n = ban_sync._build_snapshot({
    status = "success", generation_epoch = 1, snapshot_time = 1000,
    data = {
        { ip = "2001:DB8:0:0:0:0:0:1", ban_scope = "global", reason = "x", permanent = true, expires_at = 0 },
        { ip = "::ffff:192.0.2.1", ban_scope = "service", service = "www", reason = "x", permanent = true, expires_at = 0 },
    },
})
assert(snap and n == 2, tostring(snap))
assert(snap.bans["bans_ip_2001:db8::1"] and snap.bans["bans_service_www_ip_192.0.2.1"])
-- two spellings of one address in one payload are one ban, never a refused snapshot
local dup, derr = ban_sync._build_snapshot({
    status = "success", generation_epoch = 1, snapshot_time = 1000,
    data = {
        { ip = "2001:db8::1", ban_scope = "global", reason = "x", permanent = true, expires_at = 0 },
        { ip = "2001:DB8:0:0:0:0:0:1", ban_scope = "global", reason = "x", permanent = true, expires_at = 0 },
    },
})
assert(dup and dup.bans["bans_ip_2001:db8::1"], tostring(derr))
""",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout


@needs_lua
def test_the_standalone_ipaddr_script_passes():
    """`ipaddr.lua` depends on the standard library only: its own plain-Lua script runs it with an empty environment."""
    result = subprocess.run([LUA, str(ROOT / "tests/unit/test_lua_ipaddr.lua")], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0 and "FAIL" not in result.stdout, result.stdout + result.stderr
