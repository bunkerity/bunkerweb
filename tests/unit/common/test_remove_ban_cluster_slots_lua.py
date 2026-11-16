"""A service unban on Redis Cluster never sends one DEL across two hash slots.

Every IPv4 service unban also names the IPv4-mapped spelling an older version stored
(``{::ffff:192.0.2.1}``). Batched with the canonical ``{192.0.2.1}`` ban and counter keys in one
``DEL``, the two tags live on different slots (11134 and 15765): Redis Cluster answers CROSSSLOT, even
when the legacy key does not exist, and the canonical ban survives.

The harness is ``test_ban_sync.UTILS_PREAMBLE``. It has no Cluster client, so the test computes the
CRC16 slot of every key of every ``DEL`` the unban sent and requires one slot per ``DEL``, which is
exactly what a real Cluster enforces.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_ban_sync import _run_utils, needs_lua  # noqa: E402

SLOT_HELPERS = r"""
local function crc16(s)
    local crc = 0
    for i = 1, #s do
        crc = crc ~ (s:byte(i) << 8)
        for _ = 1, 8 do
            if crc & 0x8000 ~= 0 then crc = ((crc << 1) ~ 0x1021) & 0xFFFF else crc = (crc << 1) & 0xFFFF end
        end
    end
    return crc
end
local function slot(key)
    local tag = key:match("{([^}]+)}")
    return crc16(tag or key) % 16384
end
local function del_calls()
    local calls = {}
    for _, call in ipairs(redis_calls) do
        if call[1] == "del" then calls[#calls + 1] = call end
    end
    return calls
end
"""


@needs_lua
def test_the_two_spellings_really_sit_on_different_slots():
    _run_utils(
        "http",
        SLOT_HELPERS + r"""
assert(slot("bans_service_www_ip_{192.0.2.1}") == 15765)
assert(slot("bans_service_www_ip_{::ffff:192.0.2.1}") == 11134)
""",
    )


@needs_lua
def test_a_cluster_service_unban_sends_one_slot_per_del_and_removes_the_canonical_ban():
    _run_utils(
        "http",
        SLOT_HELPERS + r"""
internal_store.variables.global.USE_REDIS = "yes"
internal_store.variables.global.REDIS_CLUSTER_NODES = "127.0.0.1:7000"
assert(utils.remove_ban("192.0.2.1", "www.example.com", "service"))

local calls = del_calls()
assert(#calls >= 1)
local deleted = {}
for n, call in ipairs(calls) do
    local first = slot(call[2])
    for index = 2, #call do
        assert(slot(call[index]) == first, "DEL " .. n .. " spans slots: " .. call[2] .. " and " .. call[index])
        deleted[call[index]] = true
    end
end
assert(deleted["bans_service_www.example.com_ip_{192.0.2.1}"], "canonical ban key not deleted")
assert(deleted["bans_service_www.example.com_ip_{::ffff:192.0.2.1}"], "mapped legacy key not deleted")
assert(deleted["plugin_bad_behavior_www.example.com_{192.0.2.1}"], "counter key not deleted")
""",
    )


@needs_lua
def test_a_cluster_unban_fails_when_one_slot_group_fails_and_stops():
    _run_utils(
        "http",
        SLOT_HELPERS + r"""
internal_store.variables.global.USE_REDIS = "yes"
internal_store.variables.global.REDIS_CLUSTER_NODES = "127.0.0.1:7000"
redis_delete_error = "CROSSSLOT"
local ok, err = utils.remove_ban("192.0.2.1", "www.example.com", "service")
assert(ok == false and err:find("redis DEL failed", 1, true), tostring(err))
assert(#del_calls() == 1, "a failed DEL must stop the sweep")
""",
    )


@needs_lua
def test_standalone_redis_keeps_one_del_for_the_whole_key_set():
    _run_utils(
        "http",
        SLOT_HELPERS + r"""
internal_store.variables.global.USE_REDIS = "yes"
assert(utils.remove_ban("192.0.2.1", "www.example.com", "service"))
local calls = del_calls()
assert(#calls == 1, "standalone Redis must keep a single DEL, got " .. #calls)
local deleted = {}
for index = 2, #calls[1] do deleted[calls[1][index]] = true end
assert(deleted["bans_service_www.example.com_ip_192.0.2.1"])
assert(deleted["bans_service_www.example.com_ip_::ffff:192.0.2.1"])
assert(deleted["plugin_bad_behavior_www.example.com_192.0.2.1"])
""",
    )
