"""Ban and lease routes through the complete API, real IP normalizer and real banlease."""

import json

import pytest

from _lua_core_helpers import BW_MODULES, LUA, run_core

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HARNESS = r"""
local F = dofile(BW_LUA .. "/../../../tests/unit/lua_lease_fakes.lua")(BW_LUA .. "/../../..")
F.reset()
-- Keep the shared, escape-aware codec; the lease fake's codec handles only simple strings.
F.json = json
package.loaded["cjson"] = json
LOGS = {}
package.loaded["bunkerweb.logger"] = {
    new = function() return { log = function(_, level, msg) LOGS[#LOGS + 1] = msg end } end,
}
ngx.req = {
    read_body = function() end,
    get_body_data = function() return BODY end,
    get_body_file = function() return BODY_FILE end,
}
for _, name in ipairs({ "bit", "ffi", "bunkerweb.helpers", "ngx.process",
                       "bunkerweb.pushswap", "resty.lock", "resty.signal", "resty.upload" }) do
    package.loaded[name] = {}
end
package.loaded["ffi"].cdef = function() end
local ds = package.loaded["bunkerweb.datastore"]:new()
local get, ttl = ds.get, ds.ttl
ds.get = function(self, key)
    if GET_ERROR then return nil, GET_ERROR end
    return get(self, key)
end
ds.ttl = function(self, key)
    if TTL_ERROR then return false, TTL_ERROR end
    return ttl(self, key)
end
local utils = package.loaded["bunkerweb.utils"]
local function ban_key(ip, service, scope)
    return scope == "service" and ("bans_service_" .. service .. "_ip_" .. ip) or ("bans_ip_" .. ip)
end
utils.get_country = function()
    if COUNTRY_ERROR then return nil, COUNTRY_ERROR end
    return "ZZ"
end
utils.add_ban = function(ip, reason, exp, service, country, scope)
    if WRITE_ERROR then return false, WRITE_ERROR end
    F.store[ban_key(ip, service, scope)] = {
        value = json.encode({ reason = reason, service = service, country = country, ban_scope = scope }), ttl = exp,
    }
    return true
end
utils.remove_ban = function(ip, service, scope)
    if WRITE_ERROR then return false, WRITE_ERROR end
    F.store[ban_key(ip, service, scope)] = nil
    return true
end
local api = dofile(MODULE)
local self = setmetatable({ ctx = { bw = {} } }, { __index = api })
local lease = require("bunkerweb.banlease")
for key, row in pairs(ROWS or {}) do F.store[key] = row end
for key, value in pairs(FLAGS or {}) do F.flags[key] = value end
if REDIS then F.vars.USE_REDIS = "yes" end
local function seed_lease(ip, service, epoch)
    local current = lease.lease_epoch(ip, true)
    local key = service and ("bans_cs_service_" .. service .. "_ip_" .. ip) or ("bans_cs_ip_" .. ip)
    F.store[key] = { value = json.encode({ reason = "crowdsec", lease_epoch = epoch or current }), ttl = 20 }
end
local function call(route, body)
    if body then BODY = json.encode(body) end
    local method = route == "/bans" and "GET" or "POST"
    local code, response = api.global[method]["^" .. route .. "$"](self)
    return { code = code, response = response, store = F.store, logs = LOGS }
end
"""


def run(route="/ban", body=None, *, setup="", raw=None, **env):
    return run_core(
        BW_MODULES / "api.lua",
        HARNESS + setup + "\nemit(call(ROUTE))",
        ROUTE=route,
        BODY=raw if raw is not None else json.dumps(body or {}),
        **env,
    )


@pytest.mark.parametrize("route", ["/ban", "/unban", "/lease_lookup", "/remove_lease"])
@pytest.mark.parametrize("body", [{}, {"ip": "invalid"}, {"ip": 7}, {"ip": "192.0.2.1/32"}, {"ip": "[::1]"}])
def test_rejects_missing_or_invalid_ip(route, body):
    result = run(route, body)
    assert result["code"] == 400
    assert result["response"] == {"status": "error", "msg": "invalid IP address"}
    assert result["store"] == {}


@pytest.mark.parametrize("route", ["/ban", "/unban", "/lease_lookup", "/remove_lease"])
def test_malformed_json(route):
    result = run(route, raw="not json")
    assert result["code"] == (500 if route in ("/ban", "/unban") else 400)
    assert result["response"]["status"] == "error"
    assert result["response"]["msg"].startswith("can't decode JSON")


@pytest.mark.parametrize("route", ["/ban", "/lease_lookup", "/remove_lease", "/unban"])
@pytest.mark.parametrize("raw", ["false", "7", '"text"'])
def test_non_object_json_rejected(route, raw):
    result = run(route, raw=raw)
    assert result["code"] == 400
    assert result["response"]["status"] == "error"


@pytest.mark.parametrize("raw", ["false", "7"])
def test_ban_scalar_json_returns_bad_request(raw):
    assert run(raw=raw)["code"] == 400


@pytest.mark.parametrize("route", ["/ban", "/unban", "/lease_lookup", "/remove_lease"])
@pytest.mark.parametrize(("ip", "canonical"), [("192.0.2.1", "192.0.2.1"), ("::ffff:192.0.2.1", "192.0.2.1"), ("2001:0DB8:0:0:0:0:0:1", "2001:db8::1")])
def test_canonical_identity_and_service_isolation(route, ip, canonical):
    service = "a_ip_b.example.com"
    result = run(
        route,
        {"ip": ip, "service": service, "ban_scope": "service"},
        setup=f'seed_lease("{canonical}"); seed_lease("{canonical}", "{service}")',
        ROWS={f"bans_ip_{canonical}": {"value": "manual", "ttl": 60}, f"bans_service_{service}_ip_{canonical}": {"value": "old", "ttl": 60}},
    )
    assert result["code"] == 200
    assert result["store"][f"bans_ip_{canonical}"]["value"] == "manual"
    scoped = f"bans_service_{service}_ip_{canonical}"
    if route == "/ban":
        assert json.loads(result["store"][scoped]["value"])["ban_scope"] == "service"
        assert result["response"]["msg"] == f"ip {canonical} banned for service {service} for 86400 seconds"
    elif route == "/unban":
        assert scoped not in result["store"]
        assert result["response"]["msg"] == f"ip {canonical} unbanned for service {service}"
    elif route == "/lease_lookup":
        row = result["response"]["data"]["row"]
        assert (row["ip"], row["service"], row["ban_scope"]) == (canonical, service, "service")
    else:
        assert f"bans_cs_service_{service}_ip_{canonical}" not in result["store"]
        assert f"bans_cs_ip_{canonical}" in result["store"]


@pytest.mark.parametrize("route", ["/ban", "/unban", "/lease_lookup", "/remove_lease"])
@pytest.mark.parametrize("service", ["unknown", "Web UI", "bwcli", "default server", ""])
def test_reserved_service_falls_back_to_global(route, service):
    result = run(route, {"ip": "192.0.2.1", "ban_scope": "service", "service": service}, setup='seed_lease("192.0.2.1")')
    assert result["code"] == 200
    if route == "/ban":
        row = json.loads(result["store"]["bans_ip_192.0.2.1"]["value"])
        assert (row["ban_scope"], row["service"]) == ("global", "unknown")
    elif route == "/unban":
        assert result["response"]["msg"] == "ip 192.0.2.1 unbanned"
    elif route == "/lease_lookup":
        assert result["response"]["data"]["row"]["ban_scope"] == "global"
    else:
        assert "bans_cs_ip_192.0.2.1" not in result["store"]


@pytest.mark.parametrize("route", ["/ban", "/unban", "/lease_lookup", "/remove_lease"])
def test_invalid_scope_is_rejected_for_leases_and_logged_for_bans(route):
    result = run(route, {"ip": "192.0.2.1", "ban_scope": "invalid"})
    assert result["code"] == (200 if route in ("/ban", "/unban") else 400)
    if route in ("/ban", "/unban"):
        assert "Invalid ban scope: invalid, defaulting to global" in result["logs"]
    else:
        assert result["response"]["msg"] == "invalid ban scope"


@pytest.mark.parametrize("route", ["/lease_lookup", "/remove_lease"])
@pytest.mark.parametrize("service", [None, 7, False])
def test_lease_service_required(route, service):
    result = run(route, {"ip": "192.0.2.1", "ban_scope": "service", "service": service})
    assert result["code"] == 400
    assert result["response"]["msg"] == "service is required for a service ban scope"


@pytest.mark.parametrize(("exp", "status"), [(-1, 400), ("60", 400), (0, 200), (0.5, 200), (86400, 200), (2147483647, 200)])
def test_expiration_bounds(exp, status):
    result = run(body={"ip": "192.0.2.1", "exp": exp, "reason": "operator"}, COUNTRY_ERROR="geo unavailable")
    assert result["code"] == status
    if status == 400:
        assert result["response"]["msg"] == "exp must be a non-negative number"
        assert result["store"] == {}
    else:
        row = result["store"]["bans_ip_192.0.2.1"]
        assert row["ttl"] == exp
        assert json.loads(row["value"]) == {"reason": "operator", "country": "unknown", "service": "unknown", "ban_scope": "global"}
        assert "can't get country code geo unavailable" in result["logs"]


@pytest.mark.parametrize("route", ["/ban", "/unban", "/lease_lookup", "/remove_lease"])
@pytest.mark.parametrize("exists", [True, False])
def test_file_backed_body(tmp_path, route, exists):
    path = tmp_path / "body.json"
    if exists:
        path.write_text('{"ip":"192.0.2.1"}')
    result = run(route, raw="", setup="BODY = nil", BODY_FILE=str(path))
    assert result["code"] == (200 if exists else 500 if route in ("/ban", "/unban") else 400)
    assert result["response"]["status"] == ("success" if exists else "error")


@pytest.mark.parametrize("route", ["/ban", "/unban", "/lease_lookup", "/remove_lease"])
def test_write_or_redis_error_is_reported(route):
    result = run(route, {"ip": "192.0.2.1"}, WRITE_ERROR="write failed", REDIS=True, FLAGS={"redis_down": True})
    assert result["code"] == (500 if route in ("/ban", "/unban") else 502)
    assert result["response"]["status"] == "error"
    assert ("write failed" if route in ("/ban", "/unban") else "connection refused") in result["response"]["msg"]
    assert "data" not in result["response"]


@pytest.mark.parametrize("redis", [False, True])
def test_lease_not_found_reports_redis_check(redis):
    result = run("/lease_lookup", {"ip": "192.0.2.1", "service": "ignored"}, REDIS=redis)
    assert result["code"] == 200
    assert result["response"]["data"] == {"found": False, "redis_checked": redis}


def test_bans_parses_keys_legacy_values_and_lease_epochs():
    result = run(
        "/bans",
        setup='seed_lease("192.0.2.1"); seed_lease("192.0.2.2", "a_ip_b.example.com"); seed_lease("192.0.2.3", nil, "stale")',
        ROWS={
            "unrelated": {"value": "ignored", "ttl": 10},
            "bans_ip_192.0.2.4": {"value": "legacy", "ttl": 0},
            "bans_ip_192.0.2.5": {"value": "7", "ttl": 10},
            "bans_service_a_ip_b.example.com_ip_192.0.2.6": {"value": '{"reason":"operator","ban_scope":"global"}', "ttl": 90},
            "bans_cs_ip_192.0.2.7": {"value": '{"lease_epoch":"absent"}', "ttl": 10},
        },
        FLAGS={"ghost_keys": ["bans_ip_192.0.2.8"]},
    )
    assert result["code"] == 200
    rows = {row["ip"]: row for row in result["response"]["msg"]}
    assert set(rows) == {f"192.0.2.{i}" for i in (1, 2, 4, 5, 6)}
    assert (rows["192.0.2.2"]["service"], rows["192.0.2.2"]["kind"]) == ("a_ip_b.example.com", "crowdsec_lease")
    assert (rows["192.0.2.4"]["reason"], rows["192.0.2.4"]["date"], rows["192.0.2.4"]["exp"]) == ("legacy", 0, 0)
    assert rows["192.0.2.5"]["reason"] == "7"
    assert (rows["192.0.2.6"]["service"], rows["192.0.2.6"]["ban_scope"], rows["192.0.2.6"]["exp"]) == ("a_ip_b.example.com", "service", 90)


@pytest.mark.parametrize(("error", "status"), [("not found", 200), ("read failed", 500)])
@pytest.mark.parametrize("boundary", ["GET_ERROR", "TTL_ERROR"])
def test_bans_handles_disappearing_keys_and_storage_errors(boundary, error, status):
    result = run("/bans", ROWS={"bans_ip_192.0.2.1": {"value": "manual", "ttl": 30}}, **{boundary: error})
    assert result["code"] == status
    if status == 200:
        assert result["response"]["msg"] == {}
    else:
        assert result["response"]["msg"] == "can't access bans_ip_192.0.2.1 from datastore : read failed"
