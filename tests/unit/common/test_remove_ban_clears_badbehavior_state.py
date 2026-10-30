"""An unban must also clear the Bad Behavior state that produced the ban (issue #3818).

``bwcli unban <ip>`` used to lift the ban and nothing else: the counter that reached ``BAD_BEHAVIOR_THRESHOLD`` stayed at
the threshold, so the next watched status code from that IP incremented it past the threshold and re-banned at once.

The counter has two spellings of the same state: ``plugin_badbehavior_count_*`` in the local datastore and
``plugin_bad_behavior_*`` in Redis (owned by ``rediskeys.badbehavior``, hash-tagged in cluster mode). A fix that handles
one shape leaves half the deployments broken, so both are pinned. Every unban path (``bwcli``, the API, the UI, the Lua
API endpoint) ends in ``utils.remove_ban``, which is what runs here: the real ``utils.lua`` and the real ``rediskeys.lua``
under plain Lua, with the datastores and the Redis client stubbed.

Harness limit: the metrics counters live in zones ``utils.lua`` never opens, so they are pinned as a scope guard only.
"""

import pytest
from _t2_helpers import BW_MODULES, LUA, lua_str, run_script, utils_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

UTILS_SOURCE = (BW_MODULES / "utils.lua").read_text()

# The real rediskeys functions replace the stubs the utils prelude installs; only ``cluster_mode`` stays scripted.
FAKE_REDIS = f"""
CALLS = {{}}
local real_rediskeys = dofile({lua_str(BW_MODULES / "rediskeys.lua")})
local stub_rediskeys = package.loaded["bunkerweb.rediskeys"]
for name, fn in pairs(real_rediskeys) do stub_rediskeys[name] = fn end
stub_rediskeys.cluster_mode = function() return CLUSTER end
package.loaded["bunkerweb.clusterstore"] = {{
    new = function()
        return {{
            connect = function() if CONNECT_ERR then return false, CONNECT_ERR end return true end,
            call = function(_, command, key) CALLS[#CALLS + 1] = command .. " " .. key return 1 end,
            close = function() end,
        }}
    end,
}}
"""


def unban(setup: str, call: str, *, use_redis: str = "no", cluster: bool = False, subsystem: str = "http") -> dict:
    body = f"""
VARIABLES = {{ global = {{ USE_REDIS = "{use_redis}" }} }}
CLUSTER = {"true" if cluster else "false"}
{FAKE_REDIS}
{setup}
local ok, msg = {call}
table.sort(CALLS)
emit({{ ok = ok, calls = CALLS, left = SHARED.datastore:get_keys(), left_other = SHARED.datastore_stream:get_keys() }})
"""
    return run_script(utils_script(body, subsystem=subsystem))


def _seed(*keys: str, zone: str = "datastore") -> str:
    return "".join(f'SHARED.{zone}.data["{key}"] = 5\n' for key in keys)


# ---------------------------------------------------------------- local datastore


def test_the_reported_scenario_a_counter_at_the_threshold_does_not_survive_the_unban():
    # #3818 verbatim: BAD_BEHAVIOR_THRESHOLD=5, counter at 5 before the unban, still 5 after.
    out = unban(
        _seed("bans_service_www.example.com_ip_192.0.2.1", "plugin_badbehavior_count_www.example.com_192.0.2.1"),
        'utils.remove_ban("192.0.2.1", "www.example.com", "service")',
    )
    assert out["ok"] is True
    assert out["left"] == []


def test_a_service_unban_clears_that_services_counter_and_no_other():
    out = unban(
        _seed(
            "plugin_badbehavior_count_smtp_192.0.2.1",
            "plugin_badbehavior_count_web_192.0.2.1",
            "plugin_badbehavior_count_192.0.2.1",
            "plugin_badbehavior_count_smtp_198.51.100.9",
        ),
        'utils.remove_ban("192.0.2.1", "smtp", "service")',
    )
    # Same scope semantics as the ban keys: a service unban is not a global one.
    assert out["left"] == [
        "plugin_badbehavior_count_192.0.2.1",
        "plugin_badbehavior_count_smtp_198.51.100.9",
        "plugin_badbehavior_count_web_192.0.2.1",
    ]


def test_a_global_unban_clears_the_global_counter_and_every_per_service_one():
    out = unban(
        _seed(
            "bans_ip_192.0.2.1",
            "bans_service_smtp_ip_192.0.2.1",
            "plugin_badbehavior_count_192.0.2.1",
            "plugin_badbehavior_count_smtp_192.0.2.1",
            # Never reached the threshold, so it has no ban key of its own: an unban that leaves it behind still hands
            # the IP a head start on that service.
            "plugin_badbehavior_count_web_192.0.2.1",
            "plugin_badbehavior_count_web_198.51.100.9",
        ),
        'utils.remove_ban("192.0.2.1", nil, "global")',
    )
    assert out["left"] == ["plugin_badbehavior_count_web_198.51.100.9"]


def test_a_global_unban_also_sweeps_the_counters_of_the_other_zone():
    # delete_local walks both zones for the ban keys; the counters follow the same rule.
    out = unban(
        _seed("plugin_badbehavior_count_192.0.2.1", "plugin_badbehavior_count_smtp_192.0.2.1", zone="datastore_stream"),
        'utils.remove_ban("192.0.2.1", nil, "global")',
    )
    assert out["left_other"] == []


def test_a_service_unban_clears_the_counter_of_the_other_zone_too():
    out = unban(
        _seed("plugin_badbehavior_count_smtp_192.0.2.1", zone="datastore_stream"),
        'utils.remove_ban("192.0.2.1", "smtp", "service")',
    )
    assert out["left_other"] == []


def test_the_pending_increment_and_decrement_queues_are_left_alone():
    # They share the ``plugin_badbehavior_`` prefix with the counters but are work queues for every IP.
    out = unban(
        _seed("plugin_badbehavior_incr", "plugin_badbehavior_decr", "plugin_badbehavior_count_192.0.2.1"),
        'utils.remove_ban("192.0.2.1", nil, "global")',
    )
    assert out["left"] == ["plugin_badbehavior_decr", "plugin_badbehavior_incr"]


def test_an_ip_whose_text_ends_with_the_unbanned_one_is_not_swept():
    out = unban(
        _seed(
            "plugin_badbehavior_count_smtp_1.2.3.4",
            "plugin_badbehavior_count_smtp_11.2.3.4",
            "plugin_badbehavior_count_11.2.3.4",
        ),
        'utils.remove_ban("1.2.3.4", nil, "global")',
    )
    assert out["left"] == ["plugin_badbehavior_count_11.2.3.4", "plugin_badbehavior_count_smtp_11.2.3.4"]


def test_the_stream_subsystem_clears_its_own_counters():
    # A Stream VM unban acts on the Stream zone it owns (``datastore`` there), like it does for the ban keys.
    out = unban(
        _seed("bans_service_tcp_ip_192.0.2.1", "plugin_badbehavior_count_tcp_192.0.2.1", zone="datastore_stream"),
        'utils.remove_ban("192.0.2.1", "tcp", "service")',
        subsystem="stream",
    )
    assert out["left_other"] == []


# ------------------------------------------------------------------------- Redis


def test_a_service_unban_deletes_the_services_redis_counter_only():
    out = unban("", 'utils.remove_ban("192.0.2.1", "smtp", "service")', use_redis="yes")
    assert out["calls"] == [
        "del bans_service_smtp_ip_192.0.2.1",
        "del plugin_bad_behavior_smtp_192.0.2.1",
    ]


def test_a_global_unban_deletes_the_global_redis_counter_and_one_per_banned_service():
    out = unban(
        _seed("bans_service_smtp_ip_192.0.2.1") + _seed("bans_service_web_ip_192.0.2.1", zone="datastore_stream"),
        'utils.remove_ban("192.0.2.1", nil, "global")',
        use_redis="yes",
    )
    assert out["calls"] == [
        "del bans_ip_192.0.2.1",
        "del bans_service_smtp_ip_192.0.2.1",
        "del bans_service_web_ip_192.0.2.1",
        "del plugin_bad_behavior_192.0.2.1",
        "del plugin_bad_behavior_smtp_192.0.2.1",
        "del plugin_bad_behavior_web_192.0.2.1",
    ]


def test_a_service_banned_in_both_zones_has_its_redis_counter_deleted_once():
    out = unban(
        _seed("bans_service_smtp_ip_192.0.2.1") + _seed("bans_service_smtp_ip_192.0.2.1", zone="datastore_stream"),
        'utils.remove_ban("192.0.2.1", nil, "global")',
        use_redis="yes",
    )
    assert out["calls"].count("del plugin_bad_behavior_smtp_192.0.2.1") == 1


def test_a_global_unban_deletes_the_redis_counter_of_a_service_that_only_has_a_local_counter():
    # ``web`` never reached the threshold, so no ban key names it. The local counter does (increase() always writes it).
    out = unban(
        _seed("plugin_badbehavior_count_web_192.0.2.1", "plugin_badbehavior_count_smtp_198.51.100.9"),
        'utils.remove_ban("192.0.2.1", nil, "global")',
        use_redis="yes",
    )
    assert out["calls"] == [
        "del bans_ip_192.0.2.1",
        "del plugin_bad_behavior_192.0.2.1",
        "del plugin_bad_behavior_web_192.0.2.1",
    ]


def test_a_service_named_by_a_ban_key_and_a_local_counter_is_deleted_once_in_redis():
    out = unban(
        _seed("bans_service_smtp_ip_192.0.2.1", "plugin_badbehavior_count_smtp_192.0.2.1")
        + _seed("plugin_badbehavior_count_smtp_192.0.2.1", "plugin_badbehavior_count_tcp_192.0.2.1", zone="datastore_stream"),
        'utils.remove_ban("192.0.2.1", nil, "global")',
        use_redis="yes",
    )
    assert out["calls"].count("del plugin_bad_behavior_smtp_192.0.2.1") == 1
    assert "del plugin_bad_behavior_tcp_192.0.2.1" in out["calls"]


def test_the_global_local_counter_is_not_taken_for_a_service_name():
    out = unban(_seed("plugin_badbehavior_count_192.0.2.1"), 'utils.remove_ban("192.0.2.1", nil, "global")', use_redis="yes")
    assert out["calls"] == ["del bans_ip_192.0.2.1", "del plugin_bad_behavior_192.0.2.1"]


def test_a_service_name_holding_ip_text_is_taken_whole():
    # Greedy like rediskeys.ban: the IP never contains "_ip_", a service name might.
    out = unban(
        _seed("bans_service_my_ip_app_ip_192.0.2.1"),
        'utils.remove_ban("192.0.2.1", nil, "global")',
        use_redis="yes",
    )
    assert "del plugin_bad_behavior_my_ip_app_192.0.2.1" in out["calls"]


def test_redis_cluster_mode_deletes_the_hash_tagged_counter_keys():
    # The counter key must share its slot with the ban key (rediskeys.badbehavior), or the cluster rejects the pair.
    out = unban(
        _seed("bans_service_smtp_ip_192.0.2.1"),
        'utils.remove_ban("192.0.2.1", nil, "global")',
        use_redis="yes",
        cluster=True,
    )
    assert out["calls"] == [
        "del bans_ip_{192.0.2.1}",
        "del bans_service_smtp_ip_{192.0.2.1}",
        "del plugin_bad_behavior_smtp_{192.0.2.1}",
        "del plugin_bad_behavior_{192.0.2.1}",
    ]


def test_an_unreachable_redis_still_clears_the_local_counters():
    out = unban(
        "CONNECT_ERR = 'connection refused'\n" + _seed("plugin_badbehavior_count_192.0.2.1"),
        'utils.remove_ban("192.0.2.1", nil, "global")',
        use_redis="yes",
    )
    assert out["ok"] is True
    assert out["calls"] == []
    assert out["left"] == []


def test_no_counter_key_is_sent_to_redis_when_redis_is_off():
    out = unban(_seed("plugin_badbehavior_count_192.0.2.1"), 'utils.remove_ban("192.0.2.1", nil, "global")', use_redis="no")
    assert out["calls"] == []
    assert out["left"] == []


# ----------------------------------------------------------------------- scope


def test_metrics_are_history_and_remove_ban_never_opens_the_metrics_zone():
    # The ``badbehavior_*`` metrics are history, not state, and live in zones utils.lua never instantiates.
    body = UTILS_SOURCE.partition("local function remove_ban")[2].partition("utils.new_cachestore = function")[0]
    assert body
    assert "metrics" not in body
    assert "metrics_datastore" not in UTILS_SOURCE


def test_the_redis_counter_key_shape_is_owned_by_rediskeys_alone():
    # One spelling per store: the local prefix lives in utils, the Redis one only in rediskeys.badbehavior.
    assert UTILS_SOURCE.count('"plugin_badbehavior_count_"') == 1
    assert "plugin_bad_behavior_" not in UTILS_SOURCE
