"""An unban must also clear the Bad Behavior state that produced the ban (issue #3818).

`bwcli unban <ip>` used to lift the ban and nothing else: the counter that reached
`BAD_BEHAVIOR_THRESHOLD` stayed at the threshold, so the very next watched status code from that IP
incremented it to `threshold + 1` and re-banned instantly. The operator unbanned for one request.

The counters live under two spellings of the same state -- `plugin_badbehavior_count_*` in the local
datastore, `plugin_bad_behavior_*` in Redis -- so a fix that handles one shape leaves half the bug
alive, and which half depends on whether the deployment runs Redis. Both shapes are pinned here.

The Lua harness is `test_ban_sync.UTILS_PREAMBLE`: it `dofile`s `utils.lua` under stand-alone Lua
with `ngx`, the datastore, the clusterstore and `resty.lock` mocked, and exposes `main_store`,
`internal_store` and `redis_calls` as chunk-locals the test body can read.

Harness limit worth stating: the mock maps `ngx.shared.datastore` and `ngx.shared.datastore_stream`
onto the same `main_store` table, so no test here can tell the HTTP zone from the Stream one. That
distinction is not testable in-process anyway -- see
`test_a_stream_unban_still_forwards_and_writes_no_local_state`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_ban_sync import UTILS_LUA, _run_utils, needs_lua  # noqa: E402

IP = "192.0.2.1"


def _remove_ban_body() -> str:
    source = UTILS_LUA.read_text()
    return source.partition("utils.remove_ban = function")[2].partition("utils.new_cachestore = function")[0]


# ---------------------------------------------------------------- local datastore


@needs_lua
def test_the_reported_scenario_a_counter_at_the_threshold_does_not_survive_the_unban():
    # #3818 verbatim: BAD_BEHAVIOR_THRESHOLD=5, counter at 5 before the unban, still 5 after.
    _run_utils(
        "http",
        r"""
assert(utils.add_ban("192.0.2.1", "bad behavior", 60, "www.example.com", "FR", "service", {}))
main_store["plugin_badbehavior_count_www.example.com_192.0.2.1"] = 5

assert(utils.remove_ban("192.0.2.1", "www.example.com", "service"))

assert(main_store["bans_service_www.example.com_ip_192.0.2.1"] == nil, "ban survived")
assert(
    main_store["plugin_badbehavior_count_www.example.com_192.0.2.1"] == nil,
    "counter survived the unban: the next watched status re-bans immediately"
)
""",
    )


@needs_lua
def test_a_service_unban_clears_that_services_counter_and_no_other():
    _run_utils(
        "http",
        r"""
assert(utils.add_ban("192.0.2.1", "bad behavior", 60, "smtp", "FR", "service", {}))
main_store["plugin_badbehavior_count_smtp_192.0.2.1"] = 5
main_store["plugin_badbehavior_count_web_192.0.2.1"] = 3
main_store["plugin_badbehavior_count_192.0.2.1"] = 7
main_store["plugin_badbehavior_count_smtp_198.51.100.9"] = 4

assert(utils.remove_ban("192.0.2.1", "smtp", "service"))

assert(main_store["plugin_badbehavior_count_smtp_192.0.2.1"] == nil, "target counter survived")
-- Same scope semantics as the ban keys: a service unban is not a global one.
assert(main_store["plugin_badbehavior_count_web_192.0.2.1"] == 3, "other service's counter was cleared")
assert(main_store["plugin_badbehavior_count_192.0.2.1"] == 7, "global counter was cleared")
assert(main_store["plugin_badbehavior_count_smtp_198.51.100.9"] == 4, "another IP's counter was cleared")
""",
    )


@needs_lua
def test_a_global_unban_clears_the_global_counter_and_every_per_service_one():
    _run_utils(
        "http",
        r"""
assert(utils.add_ban("192.0.2.1", "bad behavior", 60, "smtp", "FR", "service", {}))
assert(utils.add_ban("192.0.2.1", "manual", 60, nil, "FR", "global", {}))
main_store["plugin_badbehavior_count_192.0.2.1"] = 9
main_store["plugin_badbehavior_count_smtp_192.0.2.1"] = 5
-- `web` never reached the threshold, so it has no ban key of its own. State is state: an unban
-- that leaves it behind still hands the IP a head start on that service.
main_store["plugin_badbehavior_count_web_192.0.2.1"] = 2
main_store["plugin_badbehavior_count_web_198.51.100.9"] = 6

assert(utils.remove_ban("192.0.2.1", nil, "global"))

assert(main_store["bans_ip_192.0.2.1"] == nil)
assert(main_store["bans_service_smtp_ip_192.0.2.1"] == nil)
assert(main_store["plugin_badbehavior_count_192.0.2.1"] == nil, "global counter survived")
assert(main_store["plugin_badbehavior_count_smtp_192.0.2.1"] == nil, "service counter survived")
assert(main_store["plugin_badbehavior_count_web_192.0.2.1"] == nil, "sub-threshold service counter survived")
assert(main_store["plugin_badbehavior_count_web_198.51.100.9"] == 6, "another IP's counter was cleared")
""",
    )


@needs_lua
def test_the_pending_increment_and_decrement_queues_are_left_alone():
    # These share the `plugin_badbehavior_` prefix with the counters but are shared work queues for
    # every IP; sweeping them would drop other clients' pending operations on the floor.
    _run_utils(
        "http",
        r"""
main_store["plugin_badbehavior_incr"] = "queued-incr"
main_store["plugin_badbehavior_decr"] = "queued-decr"
main_store["plugin_badbehavior_count_192.0.2.1"] = 5

assert(utils.remove_ban("192.0.2.1", nil, "global"))

assert(main_store["plugin_badbehavior_count_192.0.2.1"] == nil)
assert(main_store["plugin_badbehavior_incr"] == "queued-incr", "incr queue was swept")
assert(main_store["plugin_badbehavior_decr"] == "queued-decr", "decr queue was swept")
""",
    )


@needs_lua
def test_an_ip_whose_text_ends_with_the_unbanned_one_is_not_swept():
    # The sweep matches on "_" .. ip, so 11.2.3.4 must not be caught by an unban of 1.2.3.4.
    _run_utils(
        "http",
        r"""
main_store["plugin_badbehavior_count_smtp_1.2.3.4"] = 5
main_store["plugin_badbehavior_count_smtp_11.2.3.4"] = 5
main_store["plugin_badbehavior_count_11.2.3.4"] = 5

assert(utils.remove_ban("1.2.3.4", nil, "global"))

assert(main_store["plugin_badbehavior_count_smtp_1.2.3.4"] == nil, "target counter survived")
assert(main_store["plugin_badbehavior_count_smtp_11.2.3.4"] == 5, "neighbouring IP was swept")
assert(main_store["plugin_badbehavior_count_11.2.3.4"] == 5, "neighbouring IP was swept")
""",
    )


# ------------------------------------------------------------------------- Redis


@needs_lua
def test_a_service_unban_deletes_the_services_redis_counter_only():
    _run_utils(
        "http",
        r"""
internal_store.variables.global.USE_REDIS = "yes"
assert(utils.remove_ban("192.0.2.1", "smtp", "service"))

local deleted = {}
local del_calls = 0
for _, call in ipairs(redis_calls) do
    if call[1] == "del" then
        del_calls = del_calls + 1
        for index = 2, #call do deleted[call[index]] = true end
    end
end
assert(del_calls == 1, "counter keys must ride the ban keys' DEL, not a second round trip")
assert(deleted["bans_service_smtp_ip_192.0.2.1"], "ban key not deleted")
assert(deleted["plugin_bad_behavior_smtp_192.0.2.1"], "Redis counter not deleted")
assert(not deleted["plugin_bad_behavior_192.0.2.1"], "a service unban cleared the global counter")
""",
    )


@needs_lua
def test_a_global_unban_deletes_the_global_redis_counter_and_one_per_banned_service():
    # No second SCAN: the service names come from the `bans_service_*` keys already collected, both
    # the locally swept ones (smtp) and the ones SCANned out of Redis (web).
    _run_utils(
        "http",
        r"""
assert(utils.add_ban("192.0.2.1", "bad behavior", 60, "smtp", "FR", "service", {}))
internal_store.variables.global.USE_REDIS = "yes"
redis_scan_results["0"] = { "0", { "bans_service_web_ip_192.0.2.1" } }

assert(utils.remove_ban("192.0.2.1", nil, "global"))

local deleted, order = {}, {}
local scan_calls = 0
for _, call in ipairs(redis_calls) do
    if call[1] == "scan" then scan_calls = scan_calls + 1 end
    if call[1] == "del" then
        for index = 2, #call do
            order[#order + 1] = call[index]
            deleted[call[index]] = (deleted[call[index]] or 0) + 1
        end
    end
end
assert(#order >= 5, "expected at least the 3 ban keys and 2 counter keys, got " .. #order)
assert(scan_calls == 1, "a second SCAN was issued for the counter keys")
assert(deleted["plugin_bad_behavior_192.0.2.1"] == 1, "global Redis counter not deleted exactly once")
assert(deleted["plugin_bad_behavior_smtp_192.0.2.1"] == 1, "locally-known service counter missing")
assert(deleted["plugin_bad_behavior_web_192.0.2.1"] == 1, "SCANned service counter missing")
""",
    )


@needs_lua
def test_a_service_named_in_both_the_local_sweep_and_the_redis_scan_is_deleted_once():
    _run_utils(
        "http",
        r"""
assert(utils.add_ban("192.0.2.1", "bad behavior", 60, "smtp", "FR", "service", {}))
internal_store.variables.global.USE_REDIS = "yes"
redis_scan_results["0"] = { "0", { "bans_service_smtp_ip_192.0.2.1" } }

assert(utils.remove_ban("192.0.2.1", nil, "global"))

local counted = 0
for _, call in ipairs(redis_calls) do
    if call[1] == "del" then
        for index = 2, #call do
            if call[index] == "plugin_bad_behavior_smtp_192.0.2.1" then counted = counted + 1 end
        end
    end
end
assert(counted == 1, "duplicate counter key in the DEL argument list: " .. counted)
""",
    )


@needs_lua
def test_the_local_purge_happens_even_when_redis_is_unreachable():
    # Same local-first contract the ban keys already have: the local state is gone and the caller
    # gets a truthful failure, rather than the counter surviving because Redis was down.
    _run_utils(
        "http",
        r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_connect_ok = false
main_store["plugin_badbehavior_count_192.0.2.1"] = 5

local ok, err = utils.remove_ban("192.0.2.1", nil, "global")
assert(not ok and err:find("redis unavailable", 1, true))
assert(main_store["plugin_badbehavior_count_192.0.2.1"] == nil, "counter survived a Redis outage")
""",
    )


@needs_lua
def test_no_counter_key_is_sent_to_redis_when_redis_is_off():
    _run_utils(
        "http",
        r"""
-- Set rather than inherited from the preamble: the harness happens to default it to "no", and a
-- test that reads the answer out of its own fixture proves nothing.
internal_store.variables.global.USE_REDIS = "no"
main_store["plugin_badbehavior_count_192.0.2.1"] = 5
assert(utils.remove_ban("192.0.2.1", nil, "global"))
assert(#redis_calls == 0, "Redis was contacted with USE_REDIS=no")
assert(main_store["plugin_badbehavior_count_192.0.2.1"] == nil)
""",
    )


# ------------------------------------------------------------------- Stream / scope


@needs_lua
def test_a_stream_unban_still_forwards_and_writes_no_local_state():
    # The Stream VM cannot mutate the HTTP zone (separate `lua_shared_dict` namespaces), so it
    # forwards to the internal API and holds no ban state of its own. Purging counters here would
    # break that contract; the Stream VM's own counters are covered in the results file's
    # "not verified / known gap" section.
    _run_utils(
        "stream",
        r"""
assert(utils.remove_ban("192.0.2.1", "smtp", "service"))
assert(#api_calls == 1 and api_calls[1].path == "/unban")
assert(datastore_writes == 0 and next(main_store) == nil)
""",
    )


def test_metrics_are_history_and_remove_ban_never_opens_the_metrics_zone():
    # Issue #3818 also asks for the `badbehavior_*` metrics to be reset. They are history, not
    # state (conception 2UuqIAeeha), and they live in `shared.metrics_datastore(_stream)`, a zone
    # `utils.lua` never instantiates -- so this is a scope guard, not a behaviour claim.
    assert "metrics" not in _remove_ban_body()
    assert "metrics_datastore" not in UTILS_LUA.read_text()


def test_both_counter_key_shapes_are_named_in_one_place():
    # The naming drift between the two stores is the trap this row exists for: handling one shape
    # only fixes half the deployments. Both must be reachable from `remove_ban`.
    source = UTILS_LUA.read_text()
    assert source.count('"plugin_badbehavior_count_"') == 1
    assert source.count('"plugin_bad_behavior_"') == 1
