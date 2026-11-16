"""`utils.add_ban(..., { if_absent = true })`: the insert-only ban write of dev c5c0ab37e on 1.7's ban storage.

Plugins that ban from the ClientHello (PRO antiddos) must never replace or extend a ban an operator or another
instance holds. The contract is dev's: the first result is `"added"`, `"exists"` or `"error"` (not a boolean), then a
message. The write is `keep_existing` (CrowdSec leases) underneath, so it goes through the same snapshot lock and
advances the same ban epoch: `ban_sync` and `GET /bans` see it like any other ban. Where dev's contract is stricter than
`keep_existing`, a Redis failure leaves no local copy behind (the ban may exist in Redis, unseen).

The harness is `test_ban_lease_lua.LEASE_PREAMBLE`: the real `utils.lua`, a Redis that executes SET NX / EX.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_ban_lease_lua import needs_lua, run_lease  # noqa: E402

OPTS = "{ if_absent = true }"


@needs_lua
def test_a_free_key_is_added_with_the_normal_record_and_advances_the_ban_epoch():
    run_lease(r"""
local before = epoch_store["ban_snapshot_epoch"]
local status, msg = utils.add_ban("192.0.2.1", "antiddos", 300, "www", "FR", "global", { a = 1 }, { if_absent = true })
assert(status == "added" and msg == "success", tostring(status) .. " " .. tostring(msg))
local record = encoded[main_store["bans_ip_192.0.2.1"]]
assert(record.reason == "antiddos" and record.service == "www" and record.country == "FR" and record.permanent == false)
assert(record.expires_at == now + 300 and record.reason_data.a == 1 and main_ttls["bans_ip_192.0.2.1"] == 300)
assert(epoch_store["ban_snapshot_epoch"] ~= before, "ban_sync would never learn this ban: the snapshot epoch did not move")
local banned, reason = utils.is_banned("192.0.2.1", "www")
assert(banned == true and reason == "antiddos")
""")


@needs_lua
def test_an_existing_ban_is_never_replaced_or_extended_whatever_its_kind():
    run_lease(r"""
assert(utils.add_ban("192.0.2.1", "manual", 60, nil, "FR", "global", {}))
local original, ttl = main_store["bans_ip_192.0.2.1"], main_ttls["bans_ip_192.0.2.1"]
local epoch = epoch_store["ban_snapshot_epoch"]
for _, new_ttl in ipairs({ 0, 60, 86400 }) do
    local status = utils.add_ban("192.0.2.1", "antiddos", new_ttl, nil, "FR", "global", {}, { if_absent = true })
    assert(status == "exists", tostring(status))
    assert(main_store["bans_ip_192.0.2.1"] == original and main_ttls["bans_ip_192.0.2.1"] == ttl, "the ban was rewritten")
end
assert(epoch_store["ban_snapshot_epoch"] == epoch, "a refused write moved the epoch")

-- a permanent ban stays permanent
main_store["bans_ip_192.0.2.9"] = ban_value("manual", {}, { permanent = true, expires_at = 0 })
assert(utils.add_ban("192.0.2.9", "antiddos", 30, nil, "FR", "global", {}, { if_absent = true }) == "exists")
assert(main_ttls["bans_ip_192.0.2.9"] == nil)
""")


@needs_lua
def test_the_scopes_are_independent_keys():
    run_lease(r"""
assert(utils.add_ban("192.0.2.1", "manual", 60, nil, "FR", "global", {}))
assert(utils.add_ban("192.0.2.1", "antiddos", 60, "www", "FR", "service", {}, { if_absent = true }) == "added")
assert(main_store["bans_service_www_ip_192.0.2.1"] ~= nil)
assert(utils.add_ban("192.0.2.1", "antiddos", 60, "www", "FR", "service", {}, { if_absent = true }) == "exists")
""")


@needs_lua
def test_the_options_table_is_accepted_in_the_deadline_slot_and_after_it():
    run_lease(r"""
assert(utils.add_ban("192.0.2.1", "a", 60, nil, "FR", "global", {}, { if_absent = true }) == "added")
assert(utils.add_ban("192.0.2.1", "b", 60, nil, "FR", "global", {}, nil, { if_absent = true }) == "exists")
assert(utils.add_ban("192.0.2.2", "b", 60, nil, "FR", "global", {}, nil, { if_absent = true }) == "added")
""")


@needs_lua
def test_an_invalid_address_or_ttl_is_an_error_and_writes_nothing():
    run_lease(r"""
local status, msg = utils.add_ban("not an ip", "antiddos", 300, nil, nil, "global", {}, { if_absent = true })
assert(status == "error" and msg == "invalid IP address", tostring(status) .. " " .. tostring(msg))
status, msg = utils.add_ban("192.0.2.1", "antiddos", -5, nil, nil, "global", {}, { if_absent = true })
assert(status == "error" and msg == "invalid ban expiration", tostring(msg))
assert(next(main_store) == nil)
""")


@needs_lua
def test_without_the_option_the_return_values_are_the_historical_ones():
    run_lease(r"""
local ok, msg = utils.add_ban("192.0.2.1", "manual", 120, nil, nil, "global", { a = 1 })
assert(ok == true and msg == "success", tostring(ok) .. " " .. tostring(msg))
ok, msg = utils.add_ban("192.0.2.1", "manual", 120, nil, nil, "global", { a = 2 }, { if_absent = false })
assert(ok == true and msg == "success", "if_absent=false must overwrite as before")
assert(encoded[main_store["bans_ip_192.0.2.1"]].reason_data.a == 2)
assert(utils.ADD_BAN_IF_ABSENT == 1, "plugins detect the option through this flag")
""")


# ----------------------------------------------------------------------------------------------------- Redis


@needs_lua
def test_redis_gets_the_same_record_with_set_nx_and_the_ttl():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
local status = utils.add_ban("192.0.2.1", "antiddos", 30, nil, "FR", "global", {}, { if_absent = true })
assert(status == "added", tostring(status))
local call = redis_calls[1]
assert(call[1] == "set" and call[2] == "bans_ip_192.0.2.1" and table.concat({ table.unpack(call, 4) }, " "):find("NX EX 30", 1, true))
assert(redis_kv["bans_ip_192.0.2.1"] == main_store["bans_ip_192.0.2.1"])
""")


@needs_lua
def test_a_ban_only_redis_knows_stands_and_leaves_no_local_copy():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_kv["bans_ip_192.0.2.1"] = ban_value("manual", {}, { permanent = true, expires_at = 0 })
local explicit = redis_kv["bans_ip_192.0.2.1"]
local status = utils.add_ban("192.0.2.1", "antiddos", 30, nil, "FR", "global", {}, { if_absent = true })
assert(status == "exists", tostring(status))
assert(redis_kv["bans_ip_192.0.2.1"] == explicit and redis_ttl["bans_ip_192.0.2.1"] == nil, "the Redis ban was replaced or given a ttl")
assert(main_store["bans_ip_192.0.2.1"] == nil, "a local copy stayed next to the Redis ban")
""")


@needs_lua
def test_redis_unreachable_is_an_error_and_no_local_copy_stays():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_connect_ok = false
local status, msg = utils.add_ban("192.0.2.1", "antiddos", 30, nil, "FR", "global", {}, { if_absent = true })
assert(status == "error" and msg:find("redis"), tostring(status) .. " " .. tostring(msg))
assert(main_store["bans_ip_192.0.2.1"] == nil, "Redis may hold a ban we could not see: nothing may stay local")
""")


@needs_lua
def test_a_failing_redis_set_is_an_error_and_no_local_copy_stays():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_fail_command = "set"
local status, msg = utils.add_ban("192.0.2.1", "antiddos", 30, nil, "FR", "global", {}, { if_absent = true })
assert(status == "error" and msg:find("redis SET failed", 1, true), tostring(status) .. " " .. tostring(msg))
assert(main_store["bans_ip_192.0.2.1"] == nil)
""")


@needs_lua
def test_the_rollback_leaves_a_ban_an_administrator_wrote_meanwhile():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_fail_command = "set"
-- the administrator's overwrite lands between our local add and the Redis failure
local clusterstore = require("bunkerweb.clusterstore")
local new = clusterstore.new
clusterstore.new = function(...)
    local object = new(...)
    local call = object.call
    object.call = function(self, ...)
        main_store["bans_ip_192.0.2.1"] = ban_value("manual", {}, { permanent = true, expires_at = 0 })
        return call(self, ...)
    end
    return object
end
local status = utils.add_ban("192.0.2.1", "antiddos", 30, nil, "FR", "global", {}, { if_absent = true })
assert(status == "error", tostring(status))
assert(encoded[main_store["bans_ip_192.0.2.1"]].reason == "manual", "the rollback removed the administrator's ban")
""")


# ---------------------------------------------------------------------------------------------------- stream


@needs_lua
def test_from_the_stream_subsystem_it_refuses_instead_of_overwriting_through_the_api():
    run_lease(
        r"""
local requests = 0
package.loaded["bunkerweb.internal_api"].request = function() requests = requests + 1 return { status = 200 } end
local status, msg = utils.add_ban("192.0.2.1", "antiddos", 30, nil, "FR", "global", {}, { if_absent = true })
assert(status == "error" and msg:find("stream", 1, true), tostring(status) .. " " .. tostring(msg))
assert(requests == 0, "the ban was forwarded to the API, where it would overwrite an existing one")
""",
        subsystem="stream",
    )
