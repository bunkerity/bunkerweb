"""Real utils module: resolver decisions, canonical ban identity and scope precedence."""

import pytest
from _lua_core_helpers import BW_MODULES, LUA, run_core

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = BW_MODULES / "utils.lua"

HARNESS = r"""
ngx.re = {match = function() end}
ngx.thread = {kill = function() end}
ngx.now = function() return 1000 end
ngx.sleep = function() end
local locks = {}
ngx.shared = {internalstore = {}, datastore_stream = {}, datastore = {
    safe_add = function(_, k, v) if locks[k] then return false, "exists" end locks[k] = v return true end,
    get = function(_, k) return locks[k] end,
    delete = function(_, k) locks[k] = nil end}}
local ipaddr = require "bunkerweb.ipaddr"
local stores = {{}, {}, {}}
DATA, INTERNAL, OTHER = stores[1], stores[2], stores[3]
VARIABLES = {global = {USE_REDIS = "no", USE_IPV6 = "yes", CROWDSEC_BAN_REFRESH = "0",
    DNS_RESOLVERS = "127.0.0.1 2001:db8::53"}}
local ds = {}
function ds:new(dict)
    local data = dict == ngx.shared.internalstore and INTERNAL or
        (dict == ngx.shared.datastore_stream and OTHER or DATA)
    return setmetatable({data = data}, {__index = ds})
end
function ds:get(key)
    if GET_ERROR == key then return nil, "read failed" end
    if key == "variables" then return VARIABLES, "success" end
    if self.data[key] == nil then return nil, "not found" end
    return self.data[key], "success"
end
function ds:set(key, value, ttl)
    if SET_ERROR then return false, "write failed" end
    self.data[key] = value
    TTLS[key] = ttl
    return true
end
ds.set_with_retries = ds.set
function ds:ttl(key) return true, TTLS[key] or 60 end
function ds:delete(key) self.data[key] = nil return true end
function ds:keys() local out = {} for k in pairs(self.data) do out[#out+1] = k end return out end
TTLS = {}
package.loaded["bunkerweb.datastore"] = ds
local lease = {RANK = {explicit_service = 1, explicit_global = 2, lease_service = 3, lease_global = 4},
    new_incarnation = function() return "token" end,
    meta = function() return META end,
    lease_key = function(ip, service) return "lease_" .. (service or "global") .. "_" .. ip end,
    lease_epoch = function() return EPOCH end,
    marker_epoch = function() return nil end,
    reason_id = function() return nil end,
    bump_marker_epoch_if_present = function() end}
package.loaded["bunkerweb.banlease"] = lease
package.loaded["bunkerweb.mmdb"] = {}
package.loaded["resty.random"] = {bytes = function() end}
package.loaded["resty.session"] = {}
package.loaded["resty.ipmatcher"] = {
    parse_ipv4 = ipaddr.parse_ipv4, parse_ipv6 = ipaddr.parse_ipv6,
    new = function(networks)
        if MATCHER_ERROR then return nil, "invalid network" end
        return {match = function(_, ip)
            if MATCH_ERROR then return nil, "invalid client" end
            for _, net in ipairs(networks) do
                if ipaddr.normalize(net) == ipaddr.normalize(ip) then return true end
            end
            return false
        end}
    end}
CACHE, QUERIES = {}, {}
package.loaded["resty.dns.resolver"] = {new = function()
    if RESOLVER_ERROR then return nil, "resolver unavailable" end
    return {TYPE_A = 1, TYPE_AAAA = 28,
        query = function(_, name, options)
            QUERIES[#QUERIES+1] = options.qtype
            local answer = ANSWERS and ANSWERS[tostring(options.qtype)]
            if answer == nil or answer == false then return nil, "timeout" end
            return answer
        end,
        reverse_query = function(_, ip) REVERSE_IP = ip return PTRS, "reverse timeout" end}
end}
REDIS_CALLS = {}
package.loaded["bunkerweb.clusterstore"] = {new = function()
    return {config_error = CONFIG_ERROR,
        connect = function() return not CONNECT_ERROR, "connection failed" end,
        close = function() CLOSED = true end,
        call = function(_, command, ...)
            REDIS_CALLS[#REDIS_CALLS+1] = {command, ...}
            if REDIS_ERROR then return nil, "redis failed" end
            if command == "eval" then return REDIS_RESULT end
            return true
        end}
end}
local real_open = io.open
io.open = function(path, mode)
    if FILES and FILES[path] then return {read = function() return FILES[path] end, close = function() end} end
    if path == "/usr/share/bunkerweb/INTEGRATION" or path == "/usr/share/bunkerweb/VERSION" or path == "/etc/os-release" then
        return nil, "absent"
    end
    return real_open(path, mode)
end
local utils = dofile(MODULE)
utils.new_cachestore = function()
    return {get = function(_, key)
        if CACHE_GET_ERROR then return false, "cache read failed" end
        return true, CACHE[key]
    end, set = function(_, key, value, ttl)
        if CACHE_SET_ERROR then return false, "cache write failed" end
        CACHE[key] = value; CACHE_TTL = ttl; return true
    end}
end
"""


def run(body, **env):
    return run_core(MODULE, HARNESS + body, **env)


def test_forward_confirmation_requires_matching_address_and_skips_unmatched_suffix():
    out = run(r"""
ANSWERS = {['1'] = {{address = '192.0.2.9'}}, ['28'] = {}}
local spoof = utils.rdns_forward_confirmed({'evil.bot.example'}, {'.bot.example'}, nil, '192.0.2.1')
local no_match = utils.rdns_forward_confirmed({'evil.other'}, {'.bot.example'}, nil, '192.0.2.1')
ANSWERS['1'] = {{address = '192.0.2.1'}}; CACHE = {}
local suffix, name = utils.rdns_forward_confirmed({'real.bot.example'}, {'.bot.example'}, nil, '::ffff:192.0.2.1')
emit({spoof = spoof, no_match = no_match, suffix = suffix, name = name, queries = QUERIES})
""")
    assert "spoof" not in out and "no_match" not in out
    assert out["suffix"] == ".bot.example" and out["name"] == "real.bot.example"
    assert out["queries"] == [28, 1, 28, 1]


@pytest.mark.parametrize("setup", ["ANSWERS = {}", "MATCHER_ERROR = true", "MATCH_ERROR = true", "ANSWERS = {['1'] = {}, ['28'] = {}}"])
def test_forward_confirmation_fails_closed_on_empty_or_error(setup):
    out = run(
        r"""
ANSWERS = {['1'] = {{address = '192.0.2.1'}}, ['28'] = {}}
"""
        + setup
        + r"""
local logger = {log = function(_, level, msg) LOGS[#LOGS+1] = {level, msg} end}
local suffix = utils.rdns_forward_confirmed({'x.bot.example'}, {'.bot.example'}, nil, '192.0.2.1', logger)
assert(utils.rdns_forward_confirmed(nil, {}, nil, '192.0.2.1') == nil)
emit({suffix = suffix, logs = LOGS})
"""
    )
    assert "suffix" not in out
    assert out["logs"]


def test_ipv6_forward_confirmation_forces_aaaa_and_compares_canonical_identity():
    out = run(r"""
VARIABLES.global.USE_IPV6 = 'no'
ANSWERS = {['1'] = {}, ['28'] = {{address = '2001:db8::1'}}}
local suffix = utils.rdns_forward_confirmed({'x.bot.example'}, {'.bot.example'}, nil, '2001:0DB8:0:0:0:0:0:1')
emit({suffix = suffix, queries = QUERIES})
""")
    assert out == {"suffix": ".bot.example", "queries": [28, 1]}


@pytest.mark.parametrize(
    "failure", ["", "CACHE_GET_ERROR = true; CACHE_SET_ERROR = true", "PTRS = nil", "PTRS = {errcode = 3, errstr = 'NXDOMAIN'}", "RESOLVER_ERROR = true"]
)
def test_reverse_dns_cache_canonical_key_and_errors(failure):
    out = run(
        r"""
PTRS = {{ptrdname = 'bot.example'}, {address = 'ignored'}}
"""
        + failure
        + r"""
local result, err = utils.get_rdns('::ffff:192.0.2.1')
local second = utils.get_rdns('192.0.2.1')
emit({result = result, second = second, err = err, cache = CACHE, ip = REVERSE_IP, logs = LOGS})
"""
    )
    if "RESOLVER" in failure:
        assert out["result"] is False and out["err"] == "resolver unavailable"
    else:
        assert out["ip"] == "192.0.2.1"
        assert out["result"] == (["bot.example"] if not failure or "CACHE_GET" in failure else {})
        if "CACHE_GET" in failure:
            assert out["logs"] and out["cache"] == {}
        else:
            assert "rdns_192.0.2.1" in out["cache"]


@pytest.mark.parametrize("setup", ["", "CACHE_GET_ERROR = true; CACHE_SET_ERROR = true", "VARIABLES.global.USE_IPV6 = nil", "RESOLVER_ERROR = true"])
def test_forward_dns_family_cache_and_boundary_errors(setup):
    out = run(
        r"""
ANSWERS = {['1'] = {{address = '192.0.2.1'}, {cname = 'ignored'}}, ['28'] = {{address = '2001:db8::1'}}}
"""
        + setup
        + r"""
local ips, err = utils.get_ips('bot.example')
local v4 = utils.get_ips('bot.example', false)
local second = utils.get_ips('bot.example')
emit({ips = ips, v4 = v4, second = second, err = err, cache = CACHE, logs = LOGS})
"""
    )
    if "RESOLVER" in setup:
        assert out["ips"] is False
    else:
        assert out["v4"] == ["192.0.2.1"]
        assert out["ips"] == (["192.0.2.1"] if "USE_IPV6 = nil" in setup else ["2001:db8::1", "192.0.2.1"])
        assert out["second"] == out["ips"]
        if setup:
            assert out["logs"]


@pytest.mark.parametrize("kind", ["country", "asn"])
@pytest.mark.parametrize("mode", ["absent", "success", "missing", "throw"])
def test_mmdb_lookup_normalizes_mapped_addresses_and_preserves_failures(kind, mode):
    out = run(
        r"""
local db = package.loaded['bunkerweb.mmdb']
if MODE ~= 'absent' then db[KIND .. '_db'] = {lookup = function(_, ip)
    assert(ip == '192.0.2.1')
    if MODE == 'throw' then error('lookup exception') end
    if MODE == 'missing' then return nil, 'no record' end
    return {country = {iso_code = 'FR'}, autonomous_system_number = 64500}
end} end
local value, err = utils['get_' .. KIND]('::ffff:192.0.2.1')
emit({value = value, err = err})
""",
        KIND=kind,
        MODE=mode,
    )
    if mode == "success":
        assert out == {"value": "FR" if kind == "country" else 64500, "err": "success"}
    elif mode == "absent":
        assert out["value"] is False and "not loaded" in out["err"]
    else:
        assert "value" not in out
        assert ("no record" if mode == "missing" else "lookup exception") in out["err"]


@pytest.mark.parametrize("mode", ["SWARM_MODE", "KUBERNETES_MODE", "AUTOCONF_MODE", "file", "docker", "absent"])
def test_integration_version_and_resolver_metadata_caches(mode):
    out = run(
        r"""
FILES = {['/usr/share/bunkerweb/VERSION'] = '1.6.18\r\n'}
VARIABLES.global[MODE] = 'yes'
if MODE == 'file' then FILES['/usr/share/bunkerweb/INTEGRATION'] = 'linux\n' end
if MODE == 'docker' then FILES['/etc/os-release'] = 'Alpine Linux' end
local ctx = {bw = {}}
local integration = utils.get_integration(ctx)
local version = utils.get_version(ctx)
local resolvers = utils.get_resolvers()
emit({integration = integration, again = utils.get_integration(ctx), stored = utils.get_integration(),
    version = version, version2 = utils.get_version(ctx), version3 = utils.get_version(),
    resolvers = resolvers, resolvers2 = utils.get_resolvers()})
""",
        MODE=mode,
    )
    expected = {"SWARM_MODE": "swarm", "KUBERNETES_MODE": "kubernetes", "AUTOCONF_MODE": "autoconf", "file": "linux", "docker": "docker", "absent": "unknown"}[
        mode
    ]
    assert out["integration"] == out["again"] == out["stored"] == expected
    assert out["version"] == out["version2"] == out["version3"] == "1.6.18"
    assert out["resolvers"] == out["resolvers2"] == ["127.0.0.1", "2001:db8::53"]


def test_metadata_errors_are_logged():
    out = run(r"""
SET_ERROR = true
VARIABLES.global.SWARM_MODE = 'yes'
local integration = utils.get_integration()
local resolvers = utils.get_resolvers()
local version = utils.get_version()
GET_ERROR = 'variables'
local unavailable = utils.get_integration()
local unavailable_resolvers = utils.get_resolvers()
emit({integration = integration, resolvers = resolvers, version = version,
    unavailable = unavailable, unavailable_resolvers = unavailable_resolvers, logs = LOGS})
""")
    assert out["integration"] == "swarm"
    assert "version" not in out
    assert out["unavailable"] == out["unavailable_resolvers"] == "unknown"
    assert len(out["logs"]) == 5


@pytest.mark.parametrize("setup, expected", [("", False), ("MATCH_ERROR = true", None), ("MATCHER_ERROR = true", None)])
def test_network_boundary_errors_and_global_classification(setup, expected):
    out = run(setup + r"""
local match, err = utils.is_ip_in_networks('192.0.2.1', {'192.0.2.2'})
local global, global_err = utils.ip_is_global('::ffff:192.0.2.1')
emit({match = match, err = err, global = global, global_err = global_err})
""")
    assert out.get("match") == expected
    if expected is None:
        assert "can't" in out["err"] and "can't" in out["global_err"]
    else:
        assert out["global"] is True


@pytest.mark.parametrize("scope", ["global", "service"])
@pytest.mark.parametrize("ttl", [0, 120])
def test_ban_scope_and_unban_preserve_other_service_and_ip(scope, ttl):
    out = run(
        r"""
assert(utils.add_ban('192.0.2.2', 'other IP', 60))
assert(utils.add_ban('192.0.2.1', 'other service', 60, 'other.example', nil, 'service'))
assert(utils.add_ban('::ffff:192.0.2.1', 'manual', TTL, 'app.example', 'FR', SCOPE, {rule = 42}))
local key = SCOPE == 'service' and 'bans_service_app.example_ip_192.0.2.1' or 'bans_ip_192.0.2.1'
local data = json.decode(DATA[key])
local other_data = json.decode(OTHER[key])
local ok, reason, ttl, details = utils.is_banned('192.0.2.1', 'app.example')
assert(utils.remove_ban('::ffff:192.0.2.1', 'app.example', SCOPE))
emit({data = data, other_data = other_data, ok = ok, reason = reason, ttl = ttl, details = details,
    other_service = DATA['bans_service_other.example_ip_192.0.2.1'] ~= nil,
    other_ip = DATA['bans_ip_192.0.2.2'] ~= nil, removed = DATA[key] == nil and OTHER[key] == nil})
""",
        SCOPE=scope,
        TTL=ttl,
    )
    assert out["data"] == out["other_data"]
    assert out["data"]["ban_scope"] == scope
    assert out["data"]["permanent"] == (ttl == 0)
    assert out["ok"] is True and out["reason"] == "manual" and out["details"] == {"rule": 42}
    assert out["ttl"] == ttl
    assert out["removed"] and out["other_ip"]
    assert out["other_service"] == (scope == "service")


def test_ban_lookup_order_explicit_service_global_then_leases():
    out = run(r"""
VARIABLES.global.CROWDSEC_BAN_REFRESH = '60'
DATA['bans_service_app.example_ip_192.0.2.1'] = json.encode({reason = 'service'})
DATA['bans_ip_192.0.2.1'] = json.encode({reason = 'global'})
DATA['lease_app.example_192.0.2.1'] = json.encode({reason = 'lease service'})
DATA['lease_global_192.0.2.1'] = json.encode({reason = 'lease global'})
local reasons, local_reasons = {}, {}
for _, key in ipairs({'bans_service_app.example_ip_192.0.2.1', 'bans_ip_192.0.2.1',
    'lease_app.example_192.0.2.1', 'lease_global_192.0.2.1'}) do
    local ok, reason = utils.is_banned('192.0.2.1', 'app.example')
    local local_ok, local_reason = utils.is_banned_local('192.0.2.1', 'app.example')
    assert(ok and local_ok)
    reasons[#reasons+1] = reason; local_reasons[#local_reasons+1] = local_reason
    DATA[key] = nil
end
local empty, why = utils.is_banned('192.0.2.1', 'app.example')
emit({reasons = reasons, local_reasons = local_reasons, empty = empty, why = why})
""")
    assert out["reasons"] == out["local_reasons"] == ["service", "global", "lease service", "lease global"]
    assert out["empty"] is False and out["why"] == "not banned"


def test_stale_lease_epoch_cannot_ban_and_datastore_errors_propagate():
    out = run(r"""
META = {}; EPOCH = 'new'
VARIABLES.global.CROWDSEC_BAN_REFRESH = '60'
DATA['lease_global_192.0.2.1'] = json.encode({reason = 'stale', lease_epoch = 'old'})
local stale = utils.is_banned('192.0.2.1')
local local_stale = utils.is_banned_local('192.0.2.1')
DATA['lease_global_192.0.2.1'] = json.encode({reason = 'fresh', lease_epoch = 'new'})
local fresh = utils.is_banned('192.0.2.1')
GET_ERROR = 'bans_ip_192.0.2.1'
local ok, err = utils.is_banned('192.0.2.1')
local local_ok, local_err = utils.is_banned_local('192.0.2.1')
emit({stale = stale, local_stale = local_stale, fresh = fresh, ok = ok, err = err, local_ok = local_ok, local_err = local_err})
""")
    assert out["stale"] is False and out["local_stale"] is False and out["fresh"] is True
    assert "ok" not in out and "local_ok" not in out
    assert "read failed" in out["err"] and out["local_err"] == out["err"]


@pytest.mark.parametrize("failure", ["", "CONNECT_ERROR = true", "REDIS_ERROR = true", "REDIS_RESULT = {err = 'script failed'}"])
def test_higher_priority_redis_ban_wins_and_local_ban_survives_redis_failure(failure):
    out = run(
        r"""
VARIABLES.global.USE_REDIS = 'yes'
DATA['bans_ip_192.0.2.1'] = json.encode({reason = 'local global'})
REDIS_RESULT = {json.encode({reason = 'redis service', reason_data = {source = 'manual'}}), 100, 1}
"""
        + failure
        + r"""
local ok, reason, ttl = utils.is_banned('192.0.2.1', 'app.example')
emit({ok = ok, reason = reason, ttl = ttl, cached = DATA['bans_service_app.example_ip_192.0.2.1'],
    cache_ttl = TTLS['bans_service_app.example_ip_192.0.2.1']})
"""
    )
    assert out["ok"] is True
    assert out["reason"] == ("local global" if failure else "redis service")
    if not failure:
        assert out["ttl"] == 100 and out["cache_ttl"] == 30


@pytest.mark.parametrize("failure", ["CONNECT_ERROR = true", "REDIS_ERROR = true", "REDIS_RESULT = {err = 'script failed'}"])
def test_redis_failure_without_local_ban_is_error(failure):
    out = run("VARIABLES.global.USE_REDIS = 'yes'\n" + failure + r"""
local ok, err = utils.is_banned('192.0.2.1')
emit({ok = ok, err = err})
""")
    assert "ok" not in out and "redis" in out["err"]


@pytest.mark.parametrize("ttl", [-1, 12])
def test_redis_permanent_ttl_normalized_and_missing_result_not_banned(ttl):
    out = run(
        r"""
VARIABLES.global.USE_REDIS = 'yes'
REDIS_RESULT = {json.encode({reason = 'redis'}), TTL, 1}
local ok, reason, ttl = utils.is_banned('192.0.2.1')
local cache_ttl = TTLS['bans_ip_192.0.2.1']
DATA['bans_ip_192.0.2.1'] = nil
REDIS_RESULT = {ngx.null, -2, 0}
local absent = utils.is_banned('192.0.2.1')
emit({ok = ok, reason = reason, ttl = ttl, cache_ttl = cache_ttl, absent = absent})
""",
        TTL=ttl,
    )
    assert out == {"ok": True, "reason": "redis", "ttl": max(ttl, 0), "cache_ttl": 30 if ttl < 0 else ttl, "absent": False}


@pytest.mark.parametrize(
    "setup, expected",
    [("SET_ERROR = true", False), ("CONNECT_ERROR = true", False), ("REDIS_ERROR = true", False), ("CONNECT_ERROR = true; CONFIG_ERROR = true", True)],
)
def test_add_ban_failures_keep_local_enforcement_when_written(setup, expected):
    out = run("VARIABLES.global.USE_REDIS = 'yes'\n" + setup + r"""
local ok, err = utils.add_ban('192.0.2.1', 'manual', 10)
emit({ok = ok, err = err, local_ban = DATA['bans_ip_192.0.2.1'] ~= nil})
""")
    assert out["ok"] is expected
    assert out["local_ban"] == ("SET_ERROR" not in setup)


@pytest.mark.parametrize("address", ["bad", "fe80::1%eth0", "[2001:db8::1]"])
def test_ban_mutations_reject_invalid_addresses(address):
    out = run(
        r"""
local added, add_err = utils.add_ban(ADDRESS, 'manual', 1)
local removed, remove_err = utils.remove_ban(ADDRESS)
emit({added = added, removed = removed, add_err = add_err, remove_err = remove_err, data = DATA})
""",
        ADDRESS=address,
    )
    assert out == {"added": False, "removed": False, "add_err": "invalid IP address", "remove_err": "invalid IP address", "data": {}}
