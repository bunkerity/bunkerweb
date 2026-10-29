"""The bad behavior timer builds a ban's evidence from the shared event ring and never reads a metric keyed by request data.

Each blocked request is recorded as one event of a single shared ``increments`` table; the client address and the URI are fields
of the event, not part of a metric key, because a key per attacker evicts every other plugin's metrics during a scan flood. The
timer therefore has to fetch that one table and pick the banned IP's events out of it: only that IP, and only the banned service
when the ban is service scoped, falling back to the counter that triggered the ban when the ring holds none of them. This runs
the real ``badbehavior.lua`` timer with stand-ins for the shared tables and the ban store and pins the events handed to
``add_ban``. Refs: #3475.
"""

import pytest
from _t2_helpers import LUA, run_plugin_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HEADER = r"""
VARIABLES = {
    USE_BAD_BEHAVIOR = "yes", BAD_BEHAVIOR_STATUS_CODES = "400 401 403 404 405 429 444",
    BAD_BEHAVIOR_BAN_SCOPE = "service", BAD_BEHAVIOR_BAN_TIME = "3600", BAD_BEHAVIOR_COUNT_TIME = "60", BAD_BEHAVIOR_THRESHOLD = "10",
}
ADD_BANS = {}
UTILS = {
    add_ban = function(ip, reason, ttl, service, country, ban_scope, reason_data)
        ADD_BANS[#ADD_BANS + 1] = { ip = ip, reason = reason, ttl = ttl, service = service, scope = ban_scope, summary = reason_data }
        return true, "ok"
    end,
}
EVIDENCE, FETCHED = {}, {}
package.loaded["metrics/metrics"] = {
    new = function()
        return {
            store_ban_evidence = function(_, events, meta)
                EVIDENCE[#EVIDENCE + 1] = { events = events, meta = meta }
                return { stored = #events }
            end,
        }
    end,
}
"""

SCENARIO = r"""
local RING = {
    { date = 100, ip = "203.0.113.9", server_name = "app.example.com", url = "/a", method = "GET" },
    { date = 105, ip = "198.51.100.7", server_name = "app.example.com", url = "/other-ip", method = "GET" },
    { date = 110, ip = "203.0.113.9", server_name = "app.example.com", url = "/b", method = "POST" },
    { date = 120, ip = "203.0.113.9", server_name = "api.example.com", url = "/other-service", method = "GET" },
}
local function queue(ip, scope, server)
    DICT.incr[#DICT.incr + 1] = json.encode({ ip = ip, count_time = 60, ban_time = 3600, threshold = 10, use_redis = false,
        server_name = server, security_mode = "block", country = "FR", status = "403", ban_scope = scope })
end
%(queued)s
local plugin = PLUGIN:new({ bw = {} })
-- A placed ban deletes its counter; the shared datastore stub predates that and has no delete.
plugin.datastore.delete = function() return true, "success" end
function plugin:increase() return 10 end
function plugin:get_metric(kind, key)
    FETCHED[#FETCHED + 1] = kind .. ":" .. key
    if kind == "tables" and key == "increments" then return RING end
    return nil
end
local r = plugin:timer()
local bans = {}
for i, ban in ipairs(ADD_BANS) do
    local events = {}
    for j, e in ipairs(EVIDENCE[i].events) do events[j] = e.ip .. "|" .. e.server_name .. "|" .. tostring(e.url) .. "|" .. tostring(e.counter) end
    bans[i] = { ip = ban.ip, reason = ban.reason, service = ban.service, scope = ban.scope, stored = ban.summary.stored, events = events }
end
emit({ ok = r.ret, msg = r.msg, bans = bans, fetched = FETCHED })
"""


def timer(queued: str):
    return run_plugin_script("badbehavior", SCENARIO % {"queued": queued}, header=HEADER)


def test_a_service_scoped_ban_carries_only_the_events_of_that_ip_on_that_service():
    out = timer('queue("203.0.113.9", "service", "app.example.com")')
    assert out["ok"] is True
    assert out["bans"] == [
        {
            "ip": "203.0.113.9",
            "reason": "bad behavior",
            "service": "app.example.com",
            "scope": "service",
            "stored": 2,
            # newest first, every event stamped with the counter that triggered the ban
            "events": ["203.0.113.9|app.example.com|/b|10", "203.0.113.9|app.example.com|/a|10"],
        }
    ]


def test_a_global_ban_carries_the_events_of_that_ip_on_every_service():
    out = timer('queue("203.0.113.9", "global", "app.example.com")')
    assert out["bans"][0]["scope"] == "global"
    assert out["bans"][0]["events"] == [
        "203.0.113.9|api.example.com|/other-service|10",
        "203.0.113.9|app.example.com|/b|10",
        "203.0.113.9|app.example.com|/a|10",
    ]


def test_an_ip_with_no_event_left_in_the_ring_is_banned_with_the_triggering_counter_as_evidence():
    out = timer('queue("192.0.2.77", "service", "app.example.com")')
    assert out["ok"] is True
    assert [ban["ip"] for ban in out["bans"]] == ["192.0.2.77"]
    assert out["bans"][0]["stored"] == 1
    assert out["bans"][0]["events"] == ["192.0.2.77|app.example.com|nil|10"]


def test_the_shared_event_table_is_fetched_once_for_all_bans_and_no_metric_key_embeds_an_ip():
    out = timer('queue("203.0.113.9", "service", "app.example.com")\nqueue("198.51.100.7", "service", "app.example.com")')
    assert sorted(ban["ip"] for ban in out["bans"]) == ["198.51.100.7", "203.0.113.9"]
    assert out["fetched"] == ["tables:increments"]
