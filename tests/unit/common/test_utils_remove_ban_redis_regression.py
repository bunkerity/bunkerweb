"""Removing a ban must delete every ban key it collected from Redis, not only from the local datastores.

``utils.remove_ban`` clears the local shared dicts first and then deletes the same keys from Redis, so an unban reaches the
other instances of a cluster. This runs the real ``utils.lua`` with a recording stand-in for the Redis client and pins the
``del`` commands it issues: the global key and every service key of the IP for a global unban, only the service key for a
service-scoped one, nothing for other IPs, and no Redis call at all when Redis is off or unreachable.
"""

import pytest
from _t2_helpers import BW_MODULES, LUA, lua_str, run_script, utils_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

FAKE_REDIS = (
    r"""
CALLS, CLOSES = {}, 0
package.loaded["bunkerweb.rediskeys"].ban = function(key, cluster) return "ban:" .. key end
package.loaded["bunkerweb.rediskeys"].badbehavior = dofile("""
    + lua_str(BW_MODULES / "rediskeys.lua")
    + r""").badbehavior
package.loaded["bunkerweb.clusterstore"] = {
    new = function()
        return {
            connect = function() if CONNECT_ERR then return false, CONNECT_ERR end return true end,
            call = function(_, command, key) CALLS[#CALLS + 1] = command .. " " .. key return 1 end,
            close = function() CLOSES = CLOSES + 1 end,
        }
    end,
}
"""
)


def unban(setup: str, call: str, *, use_redis: str = "yes", subsystem: str = "http") -> dict:
    body = f"""
VARIABLES = {{ global = {{ USE_REDIS = "{use_redis}" }} }}
{FAKE_REDIS}
{setup}
local ok, msg = {call}
table.sort(CALLS)
emit({{ ok = ok, msg = msg, calls = CALLS, closes = CLOSES, left = SHARED.datastore:get_keys(), left_other = SHARED.datastore_stream:get_keys() }})
"""
    return run_script(utils_script(body, subsystem=subsystem))


SEEDED_BANS = """
SHARED.datastore.data["bans_ip_1.2.3.4"] = "global"
SHARED.datastore.data["bans_service_app.example.com_ip_1.2.3.4"] = "service"
SHARED.datastore_stream.data["bans_service_tcp.example.com_ip_1.2.3.4"] = "stream service"
SHARED.datastore.data["bans_ip_5.6.7.8"] = "other ip"
SHARED.datastore.data["bans_service_app.example.com_ip_5.6.7.8"] = "other ip service"
"""


def test_a_global_unban_deletes_the_global_and_every_service_key_of_the_ip_from_redis():
    out = unban(SEEDED_BANS, 'utils.remove_ban("1.2.3.4")')
    assert out["ok"] is True
    assert out["calls"] == [
        "del ban:bans_ip_1.2.3.4",
        "del ban:bans_service_app.example.com_ip_1.2.3.4",
        "del ban:bans_service_tcp.example.com_ip_1.2.3.4",
        "del plugin_bad_behavior_1.2.3.4",
        "del plugin_bad_behavior_app.example.com_1.2.3.4",
        "del plugin_bad_behavior_tcp.example.com_1.2.3.4",
    ]
    assert out["closes"] == 1
    assert out["left"] == ["bans_ip_5.6.7.8", "bans_service_app.example.com_ip_5.6.7.8"]
    assert out["left_other"] == []


def test_a_service_scoped_unban_deletes_only_that_service_key_from_redis():
    out = unban(SEEDED_BANS, 'utils.remove_ban("1.2.3.4", "app.example.com", "service")')
    assert out["ok"] is True
    assert out["calls"] == [
        "del ban:bans_service_app.example.com_ip_1.2.3.4",
        "del plugin_bad_behavior_app.example.com_1.2.3.4",
    ]
    assert "bans_ip_1.2.3.4" in out["left"]


def test_the_stream_subsystem_collects_the_same_keys():
    out = unban(SEEDED_BANS, 'utils.remove_ban("1.2.3.4")', subsystem="stream")
    assert out["calls"] == [
        "del ban:bans_ip_1.2.3.4",
        "del ban:bans_service_app.example.com_ip_1.2.3.4",
        "del ban:bans_service_tcp.example.com_ip_1.2.3.4",
        "del plugin_bad_behavior_1.2.3.4",
        "del plugin_bad_behavior_app.example.com_1.2.3.4",
        "del plugin_bad_behavior_tcp.example.com_1.2.3.4",
    ]


def test_no_redis_call_is_made_when_redis_is_disabled():
    out = unban(SEEDED_BANS, 'utils.remove_ban("1.2.3.4")', use_redis="no")
    assert out["ok"] is True
    assert out["calls"] == []
    assert out["left"] == ["bans_ip_5.6.7.8", "bans_service_app.example.com_ip_5.6.7.8"]


def test_an_unreachable_redis_still_clears_the_local_datastores_and_deletes_nothing():
    out = unban("CONNECT_ERR = 'connection refused'\n" + SEEDED_BANS, 'utils.remove_ban("1.2.3.4")')
    assert out["ok"] is True
    assert out["calls"] == []
    assert out["left"] == ["bans_ip_5.6.7.8", "bans_service_app.example.com_ip_5.6.7.8"]
    assert out["left_other"] == []
