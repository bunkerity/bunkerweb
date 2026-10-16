"""TLS ClientHello drop (CrowdSec port, lane C): the decision and the hook of `tlsdrop.lua`.

A banned client whose ban reason is listed in `BANS_TLS_DROP_REASONS` gets its handshake closed in
`ssl_client_hello_by_lua*` instead of the 403 page. The hook runs before any certificate work, in a
phase where nothing may yield (no Redis, no lock, no `ngx.var`), so the contract is a decision
function that fails OPEN on every unknown: the access phase stays authoritative.

The harness is `test_ban_lease_lua.LEASE_PREAMBLE`, i.e. the real `utils.lua` (so `is_banned_local`,
`get_variable` and the local-only whitelist are the shipped ones) with `ngx.ssl` stubbed.

`canonical_addr` is checked against golden values produced by nginx's own `ngx_inet_addr`,
`ngx_inet6_addr` and `ngx_inet6_ntop` (`src/deps/src/nginx/src/core/ngx_inet.c`, compiled verbatim,
log `proofs/W25-X1C/nginx-golden.tsv`), because the PROXY address must be spelled exactly as
nginx spells `$remote_addr` or the ban key does not match.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_ban_lease_lua import needs_lua, run_lease  # noqa: E402

TLS_EXTRA = r"""
local exits = {}
ngx.exit = function(code) exits[#exits + 1] = code end
ngx.ERROR = -1
local clock = 1000
ngx.time = function() return clock end

-- Stand-in for libc inet_pton as resty.ipmatcher uses it: RFC 4291 text to four 32-bit words.
local function parse_ipv6(text)
    if type(text) ~= "string" then return false end
    if text:sub(1, 1) == "[" and text:sub(-1) == "]" then text = text:sub(2, -2) end
    if text:find("[^%x:.]") or text == "" then return false end
    local head, tail = text, nil
    local dc = text:find("::", 1, true)
    if dc then
        if text:find("::", dc + 1, true) then return false end
        head, tail = text:sub(1, dc - 1), text:sub(dc + 2)
    end
    local function groups(part)
        local out = {}
        if part == "" then return out end
        local items = {}
        for item in (part .. ":"):gmatch("(.-):") do items[#items + 1] = item end
        for i, item in ipairs(items) do
            if item:find(".", 1, true) then
                if i ~= #items then return nil end
                local a, b, c, d = item:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")
                if not a then return nil end
                for _, o in ipairs({ a, b, c, d }) do
                    if #o > 1 and o:sub(1, 1) == "0" then return nil end
                    if tonumber(o) > 255 then return nil end
                end
                out[#out + 1] = tonumber(a) * 256 + tonumber(b)
                out[#out + 1] = tonumber(c) * 256 + tonumber(d)
            else
                if #item < 1 or #item > 4 then return nil end
                out[#out + 1] = tonumber(item, 16)
            end
        end
        return out
    end
    local h = groups(head)
    local t = {}
    if tail then t = groups(tail) end
    if not h or not t then return false end
    local words = {}
    for _, w in ipairs(h) do words[#words + 1] = w end
    if dc then
        if #h + #t > 7 then return false end
        for _ = 1, 8 - #h - #t do words[#words + 1] = 0 end
        for _, w in ipairs(t) do words[#words + 1] = w end
    elseif #words ~= 8 then
        return false
    end
    local out = {}
    for i = 1, 4 do out[i] = words[2 * i - 1] * 65536 + words[2 * i] end
    return out
end

local function ip4(text)
    local a, b, c, d = text:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")
    return (tonumber(a) << 24) | (tonumber(b) << 16) | (tonumber(c) << 8) | tonumber(d)
end
-- exact addresses and IPv4 CIDRs: enough to tell a trusted proxy from a stranger
package.loaded["resty.ipmatcher"] = {
    parse_ipv6 = parse_ipv6,
    parse_ipv4 = function(ip) return ip:match("^%d+%.%d+%.%d+%.%d+$") and ip4(ip) end,
    new = function(networks)
        return {
            match = function(_, ip)
                for _, network in ipairs(networks) do
                    local base, bits = network:match("^(.-)/(%d+)$")
                    if not base then base, bits = network, "32" end
                    if base:match("^%d+%.%d+%.%d+%.%d+$") and ip:match("^%d+%.%d+%.%d+%.%d+$") then
                        local mask = bits == "0" and 0 or ((0xffffffff << (32 - tonumber(bits))) & 0xffffffff)
                        if (ip4(base) & mask) == (ip4(ip) & mask) then return true end
                    elseif base == ip then
                        return true
                    end
                end
                return false
            end,
        }
    end,
}

local client = { addr = "\192\0\2\1", family = "inet", quic = false, quic_err = nil, pp = nil, pp_err = nil }
local ssl_mod = {
    raw_client_addr = function() return client.addr, client.family end,
    proxy_protocol_addr = function() return client.pp, client.pp_err end,
}
package.loaded["ngx.ssl"] = ssl_mod
package.loaded["ngx.ssl.clienthello"] = {
    get_client_hello_ext = function(ext)
        assert(ext == 57, "only the QUIC transport parameters extension is looked at")
        return client.quic, client.quic_err
    end,
}

internal_store.variables.global.BANS_TLS_DROP_REASONS = "crowdsec bad_behavior manual ui api"
internal_store.variables.global.SECURITY_MODE = "block"
internal_store.variables.global.MULTISITE = "no"

package.loaded["bunkerweb.utils"] = utils
local tlsdrop = require("bunkerweb.tlsdrop")

local function ban(key, reason, reason_data, extra)
    main_store[key] = ban_value(reason, reason_data, extra)
end
local IP = "192.0.2.1"
"""


def run_tls(body: str) -> None:
    run_lease(TLS_EXTRA + body)


# ---------------------------------------------------------------------------------- decision matrix


@needs_lua
def test_a_banned_ip_with_a_listed_reason_is_dropped():
    run_tls(r"""
ban("bans_ip_192.0.2.1", "manual", {})
local verdict, id, ip = tlsdrop.decide("www", false, false, nil)
assert(verdict == "drop" and id == "manual" and ip == IP, tostring(verdict))
""")


@needs_lua
def test_setting_empty_missing_or_unreadable_never_drops():
    run_tls(r"""
ban("bans_ip_192.0.2.1", "manual", {})
internal_store.variables.global.BANS_TLS_DROP_REASONS = ""
assert(tlsdrop.decide("www", false, false, nil) == nil, "empty setting")
internal_store.variables.global.BANS_TLS_DROP_REASONS = nil
assert(tlsdrop.decide("www", false, false, nil) == nil, "setting absent from variables")
internal_store.variables = nil
assert(tlsdrop.decide("www", false, false, nil) == nil, "variables unreadable: fail open")
""")


@needs_lua
def test_not_banned_expired_or_unlisted_reason_does_not_drop():
    run_tls(r"""
assert(tlsdrop.decide("www", false, false, nil) == nil, "not banned")
ban("bans_ip_192.0.2.1", "antibot", {})
assert(tlsdrop.decide("www", false, false, nil) == nil, "a reason outside the five cannot be listed")
internal_store.variables.global.BANS_TLS_DROP_REASONS = "crowdsec"
ban("bans_ip_192.0.2.1", "manual", {})
assert(tlsdrop.decide("www", false, false, nil) == nil, "manual ban, only crowdsec listed")
main_store["bans_ip_192.0.2.1"] = nil -- expiry removes the shm key
internal_store.variables.global.BANS_TLS_DROP_REASONS = "manual"
assert(tlsdrop.decide("www", false, false, nil) == nil, "expired")
""")


@needs_lua
def test_each_of_the_five_reasons_maps_to_its_id_and_nothing_else_does():
    run_tls(r"""
local cases = { crowdsec = "crowdsec", ["bad behavior"] = "bad_behavior", manual = "manual", ui = "ui", api = "api" }
for reason, id in pairs(cases) do
    ban("bans_ip_192.0.2.1", reason, {})
    local verdict, got = tlsdrop.decide("www", false, false, nil)
    assert(verdict == "drop" and got == id, reason)
end
for _, reason in ipairs({ "bad_behavior", "Manual", "antibot", "blacklist", "", "crowdsec " }) do
    ban("bans_ip_192.0.2.1", reason, {})
    assert(tlsdrop.decide("www", false, false, nil) == nil, "dropped on reason '" .. reason .. "'")
end
""")


@needs_lua
def test_a_service_ban_beats_the_global_one_and_each_scope_is_judged_on_its_own_reason():
    run_tls(r"""
internal_store.variables.global.BANS_TLS_DROP_REASONS = "manual"
ban("bans_ip_192.0.2.1", "manual", {})
ban("bans_service_www_ip_192.0.2.1", "bad behavior", {}, { ban_scope = "service" })
-- the service ban is the one that applies: its reason is not listed, so no drop
assert(tlsdrop.decide("www", false, false, nil) == nil)
-- another service has no ban of its own: the global one applies
local verdict, id = tlsdrop.decide("other", false, false, nil)
assert(verdict == "drop" and id == "manual")
""")


@needs_lua
def test_permanent_bans_drop():
    run_tls(r"""
ban("bans_ip_192.0.2.1", "ui", {}, { permanent = true, expires_at = 0 })
assert(main_ttls["bans_ip_192.0.2.1"] == nil)
assert(tlsdrop.decide("www", false, false, nil) == "drop")
""")


@needs_lua
def test_a_service_lease_does_not_make_the_drop_follow_the_lease_when_an_explicit_global_ban_exists():
    run_tls(r"""
-- amendment 1 M1: the explicit global ban ranks first, so its reason is the one judged
internal_store.variables.global.BANS_TLS_DROP_REASONS = "crowdsec"
ban("bans_service_www_ip_192.0.2.1", "crowdsec", lease_data("aaaa1111aaaa1111"), { ban_scope = "service" })
ban("bans_ip_192.0.2.1", "manual", {})
assert(tlsdrop.decide("www", false, false, nil) == nil, "dropped on the lease although the explicit ban applies")

internal_store.variables.global.BANS_TLS_DROP_REASONS = "manual"
local verdict, id = tlsdrop.decide("www", false, false, nil)
assert(verdict == "drop" and id == "manual", tostring(id))
""")


@needs_lua
def test_a_lease_alone_drops_as_crowdsec():
    run_tls(r"""
internal_store.variables.global.BANS_TLS_DROP_REASONS = "crowdsec"
ban("bans_service_www_ip_192.0.2.1", "crowdsec", lease_data("aaaa1111aaaa1111"), { ban_scope = "service" })
local verdict, id = tlsdrop.decide("www", false, false, nil)
assert(verdict == "drop" and id == "crowdsec")
""")


@needs_lua
def test_the_default_server_reads_the_global_setting_and_only_the_global_ban():
    run_tls(r"""
ban("bans_service_www_ip_192.0.2.1", "manual", {}, { ban_scope = "service" })
assert(tlsdrop.decide(nil, false, false, nil) == nil, "a service ban must not apply to the default server")
ban("bans_ip_192.0.2.1", "manual", {})
assert(tlsdrop.decide(nil, false, false, nil) == "drop")
""")


@needs_lua
def test_multisite_reads_the_setting_of_the_service():
    run_tls(r"""
internal_store.variables.global.MULTISITE = "yes"
internal_store.variables.global.BANS_TLS_DROP_REASONS = ""
internal_store.variables.www = { BANS_TLS_DROP_REASONS = "manual" }
ban("bans_ip_192.0.2.1", "manual", {})
assert(tlsdrop.decide("www", false, false, nil) == "drop", "per-service setting ignored")
assert(tlsdrop.decide("other", false, false, nil) == nil, "another service must not inherit it")
""")


@needs_lua
def test_whitelisted_ip_is_not_dropped_and_a_whitelist_error_fails_open():
    run_tls(r"""
local cache_calls = { get = 0, get_local_nolock = 0 }
package.loaded["bunkerweb.cachestore"] = {
    new = function()
        return {
            get = function() cache_calls.get = cache_calls.get + 1 return true, nil end,
            get_local_nolock = function() cache_calls.get_local_nolock = cache_calls.get_local_nolock + 1 return true, nil end,
        }
    end,
}
internal_store.variables.global.USE_WHITELIST = "yes"
internal_store.variables.www = { USE_WHITELIST = "yes" }
ban("bans_ip_192.0.2.1", "manual", {})

internal_store.plugin_whitelist_lists_www = { IP = { IP } }
assert(tlsdrop.decide("www", false, false, nil) == nil, "whitelisted IP dropped")

internal_store.plugin_whitelist_lists_www = { IP = { "203.0.113.9" } }
assert(tlsdrop.decide("www", false, false, nil) == "drop", "not whitelisted")

internal_store.plugin_whitelist_lists_www = nil -- list unreadable
assert(tlsdrop.decide("www", false, false, nil) == nil, "whitelist error must fail open")
assert(cache_calls.get == 0, "the handshake used the locking cachestore read")
""")


@needs_lua
def test_detect_mode_reports_but_never_drops():
    run_tls(r"""
ban("bans_ip_192.0.2.1", "manual", {})
internal_store.variables.global.SECURITY_MODE = "detect"
local verdict, id, ip = tlsdrop.decide("www", false, false, nil)
assert(verdict == "detect" and id == "manual" and ip == IP)

assert(tlsdrop.hook("www", false, false, nil) == nil, "the hook must not report a drop")
assert(#exits == 0, "ngx.exit called in detect mode")
local found = false
for _, entry in ipairs(logs) do if entry[2]:find("would drop") and entry[2]:find(IP, 1, true) then found = true end end
assert(found, "detect mode must log the would-be drop")

internal_store.variables.global.SECURITY_MODE = nil
assert(tlsdrop.decide("www", false, false, nil) == nil, "an unreadable security mode must fail open")
""")


@needs_lua
def test_quic_handshakes_are_never_dropped():
    run_tls(r"""
ban("bans_ip_192.0.2.1", "manual", {})
client.quic = "params"
assert(tlsdrop.decide("www", false, false, nil) == nil)
client.quic, client.quic_err = nil, "no such extension API"
assert(tlsdrop.decide("www", false, false, nil) == nil, "an error reading the extension fails open")
""")


@needs_lua
def test_unknown_client_address_fails_open():
    run_tls(r"""
ban("bans_ip_192.0.2.1", "manual", {})
client.addr, client.family = nil, nil
assert(tlsdrop.decide("www", false, false, nil) == nil, "no address")
client.addr, client.family = "/run/sock", "unix"
assert(tlsdrop.decide("www", false, false, nil) == nil, "unix socket")
client.addr, client.family = "\192\0\2", "inet"
assert(tlsdrop.decide("www", false, false, nil) == nil, "truncated address")
""")


@needs_lua
def test_ipv6_client_is_judged_on_its_nginx_spelling_and_mapped_ipv4_on_the_v4_text():
    run_tls(r"""
ban("bans_ip_2001:db8::1", "manual", {})
client.addr, client.family = "\32\1\13\184" .. string.rep("\0", 11) .. "\1", "inet6"
local verdict, _, ip = tlsdrop.decide("www", false, false, nil)
assert(verdict == "drop" and ip == "2001:db8::1", tostring(ip))

-- a dual-stack listener reports an IPv4 client as ::ffff:a.b.c.d: the ban key is the dotted text
ban("bans_ip_192.0.2.1", "manual", {})
client.addr, client.family = string.rep("\0", 10) .. "\255\255\192\0\2\1", "inet6"
local v2, _, ip2 = tlsdrop.decide("www", false, false, nil)
assert(v2 == "drop" and ip2 == IP, tostring(ip2))
""")


@needs_lua
def test_with_redis_only_a_local_hit_drops_and_nothing_is_ever_sent_to_redis():
    run_tls(r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_kv["bans_ip_192.0.2.1"] = ban_value("manual", {})
assert(tlsdrop.decide("www", false, false, nil) == nil, "a ban only Redis knows cannot drop: the 403 page caches it")
ban("bans_ip_192.0.2.1", "manual", {})
assert(tlsdrop.decide("www", false, false, nil) == "drop", "a local copy is authoritative for the access phase too")
assert(#redis_calls == 0 and lock_calls == 0)
""")


@needs_lua
def test_nothing_in_the_decision_reads_ngx_var_or_takes_a_lock():
    run_tls(r"""
ngx.var = setmetatable({}, { __index = function(_, key) error("ngx.var." .. key .. " read in ssl_client_hello") end })
ban("bans_ip_192.0.2.1", "manual", {})
assert(tlsdrop.decide("www", false, false, nil) == "drop")
assert(tlsdrop.decide(nil, false, false, nil) == "drop")
assert(lock_calls == 0)
""")


@needs_lua
def test_any_error_inside_the_decision_is_swallowed():
    run_tls(r"""
ban("bans_ip_192.0.2.1", "manual", {})
ssl_mod.raw_client_addr = function() error("boom") end
assert(tlsdrop.decide("www", false, false, nil) == nil)
assert(tlsdrop.hook("www", false, false, nil) == nil and #exits == 0)
""")


# ------------------------------------------------------------------------------ PROXY protocol


@needs_lua
def test_header_based_real_ip_or_proxy_protocol_without_a_trusted_list_skips():
    run_tls(r"""
ban("bans_ip_192.0.2.1", "manual", {})
assert(tlsdrop.decide("www", true, false, nil) == nil, "PROXY protocol without realip: the client IP is unknown")
assert(tlsdrop.decide("www", false, true, nil) == nil, "header based real IP: the client IP is unknown")
assert(tlsdrop.decide("www", true, true, nil) == nil)
""")


@needs_lua
def test_trusted_proxy_peer_is_judged_on_the_proxy_protocol_source_address():
    run_tls(r"""
ban("bans_ip_198.51.100.7", "manual", {})
client.addr = "\10\0\0\5"  -- the peer, a load balancer
client.pp = "198.51.100.7"
local verdict, _, ip = tlsdrop.decide("www", true, true, "10.0.0.0/8 172.16.0.0/12")
assert(verdict == "drop" and ip == "198.51.100.7", tostring(ip))
""")


@needs_lua
def test_untrusted_peer_cannot_choose_its_own_address():
    run_tls(r"""
ban("bans_ip_198.51.100.7", "manual", {})
client.addr = "\192\0\2\1" -- not in the trusted list
client.pp = "198.51.100.7"
assert(tlsdrop.decide("www", true, true, "10.0.0.0/8") == nil, "the PROXY header of an untrusted peer was believed")
-- and its own address is the one judged
ban("bans_ip_192.0.2.1", "manual", {})
local verdict, _, ip = tlsdrop.decide("www", true, true, "10.0.0.0/8")
assert(verdict == "drop" and ip == "192.0.2.1")
""")


@needs_lua
def test_no_proxy_header_or_empty_trusted_list_judges_the_peer():
    run_tls(r"""
ban("bans_ip_10.0.0.5", "manual", {})
client.addr = "\10\0\0\5"
client.pp = nil
local verdict, _, ip = tlsdrop.decide("www", true, true, "10.0.0.0/8")
assert(verdict == "drop" and ip == "10.0.0.5")
client.pp = "198.51.100.7"
local v2, _, ip2 = tlsdrop.decide("www", true, true, "")
assert(v2 == "drop" and ip2 == "10.0.0.5", "an empty trusted list trusts nobody")
""")


@needs_lua
def test_proxy_address_is_taken_in_nginx_spelling():
    run_tls(r"""
ban("bans_ip_2001:db8::1", "manual", {})
client.addr = "\10\0\0\5"
client.pp = "2001:0DB8:0000:0000:0000:0000:0000:0001"
local verdict, _, ip = tlsdrop.decide("www", true, true, "10.0.0.0/8")
assert(verdict == "drop" and ip == "2001:db8::1", tostring(ip))
""")


@needs_lua
def test_a_proxy_protocol_api_that_is_missing_or_failing_fails_open():
    run_tls(r"""
ban("bans_ip_10.0.0.5", "manual", {})
client.addr = "\10\0\0\5"
ssl_mod.proxy_protocol_addr = nil  -- the vendored patch is not in this build
assert(tlsdrop.decide("www", true, true, "10.0.0.0/8") == nil)
ssl_mod.proxy_protocol_addr = function() return nil, "not supported" end
assert(tlsdrop.decide("www", true, true, "10.0.0.0/8") == nil)
ssl_mod.proxy_protocol_addr = function() return "not an address", nil end
assert(tlsdrop.decide("www", true, true, "10.0.0.0/8") == nil, "an unparsable PROXY address must not fall back to the peer")
""")


# --------------------------------------------------------------------------------- canonical_addr

# nginx's own answers (ngx_inet_addr, then ngx_inet6_addr + ngx_inet6_ntop), from
# proofs/W25-X1C/nginx-golden.tsv. "NIL" is a refusal.
GOLDEN = [
    ("192.0.2.1", "192.0.2.1"),
    ("010.001.002.003", "10.1.2.3"),  # decimal, leading zeros accepted
    ("1..2.3", "1.0.2.3"),  # empty octet accepted
    ("1.2.3", "NIL"),
    ("1.2.3.4.5", "NIL"),
    ("255.255.255.255", "NIL"),  # INADDR_NONE
    ("256.1.1.1", "NIL"),
    ("0.0.0.0", "0.0.0.0"),
    ("2001:db8::1", "2001:db8::1"),
    ("2001:0db8:0000:0000:0000:0000:0000:0001", "2001:db8::1"),
    ("2001:DB8::A", "2001:db8::a"),
    ("::1", "::1"),
    ("::", "::"),
    ("1::", "1::"),
    ("::ffff:192.0.2.1", "::ffff:192.0.2.1"),  # stays IPv6
    ("::ffff:c000:201", "::ffff:192.0.2.1"),
    ("::192.0.2.1", "::192.0.2.1"),
    ("::1.2.3.4", "::1.2.3.4"),
    ("::ffff:0.0.0.1", "::ffff:0.0.0.1"),
    ("64:ff9b::192.0.2.33", "64:ff9b::c000:221"),
    ("2001:db8:0:1:0:0:0:1", "2001:db8:0:1::1"),
    ("2001:0:0:1:0:0:0:1", "2001:0:0:1::1"),
    ("1:0:0:2:0:0:3:4", "1::2:0:0:3:4"),  # the first of two equal runs
    ("1:0:2:3:4:5:6:7", "1:0:2:3:4:5:6:7"),  # a single zero word is not compressed
    ("0:0:0:0:0:0:0:0", "::"),
    ("0:0:0:0:0:0:0:1", "::1"),
    ("0:0:0:0:0:0:1:1", "::0.1.0.1"),
    ("fe80::1", "fe80::1"),
    ("fe80::1%eth0", "NIL"),
    ("[2001:db8::1]", "NIL"),  # brackets: resty.ipmatcher strips them, nginx does not
    ("1:2:3:4:5:6:7:8:9", "NIL"),
    ("12345::1", "NIL"),
    ("2001:db8::1.2.3.4", "2001:db8::102:304"),
    ("1:2:3:4:5:6:1.2.3.4", "1:2:3:4:5:6:102:304"),
    ("1:2:3:4:5:6:7:1.2.3.4", "NIL"),
    ("::ffff:1.2.3", "NIL"),
    ("not-an-ip", "NIL"),
    ("", "NIL"),
    (":::", "NIL"),
    ("1::2::3", "NIL"),
]

# Where nginx and libc inet_pton (what resty.ipmatcher calls) disagree, from the same run. Left out of
# the table above because the harness stand-in cannot pin libc:
#   "1:2:3:4:5:6:7::"            nginx refuses; inet_pton takes it (canonical_addr answers 1:2:3:4:5:6:7:0)
#   "::2:3:4:5:6:7:8"            nginx answers 0:2:3:4:5:6:7:8 (no compression of a lone leading zero word)
#   "::ffff:010.001.002.003"     nginx answers ::ffff:10.1.2.3; inet_pton refuses leading zeros (nil, fail open)
# None can come from a PROXY protocol sender (proxies write the canonical form), and each ends in a
# fail-open or a ban lookup on an address that is not the client's.


def _lua_table(rows) -> str:
    return "{" + ",".join('{"%s","%s"}' % (a, b) for a, b in rows) + "}"


@needs_lua
def test_canonical_addr_matches_nginx_on_the_golden_table():
    run_tls("local GOLDEN = " + _lua_table(GOLDEN) + r"""
for _, row in ipairs(GOLDEN) do
    local got = tlsdrop.canonical_addr(row[1])
    local want = row[2] ~= "NIL" and row[2] or nil
    assert(got == want, "canonical_addr('" .. row[1] .. "') = " .. tostring(got) .. ", nginx says " .. tostring(row[2]))
end
""")


@needs_lua
def test_inet6_ntop_and_raw_address_formatting_follow_nginx():
    run_tls(r"""
local function packed(words)
    local out = {}
    for i, w in ipairs(words) do out[i] = string.char(w >> 8, w & 255) end
    return table.concat(out)
end
assert(tlsdrop.inet6_ntop(packed({ 0x2001, 0xdb8, 0, 0, 0, 0, 0, 1 })) == "2001:db8::1")
assert(tlsdrop.inet6_ntop(packed({ 0, 0, 0, 0, 0, 0xffff, 0xc000, 0x201 })) == "::ffff:192.0.2.1")
assert(tlsdrop.inet6_ntop(packed({ 0, 0, 0, 0, 0, 0, 0, 0 })) == "::")
assert(tlsdrop.format_raw_addr("\1\2\3\4", "inet") == "1.2.3.4")
assert(tlsdrop.format_raw_addr(string.rep("\0", 10) .. "\255\255\1\2\3\4", "inet6") == "1.2.3.4")
assert(tlsdrop.format_raw_addr(packed({ 0xfe80, 0, 0, 0, 0, 0, 0, 1 }), "inet6") == "fe80::1")
assert(tlsdrop.format_raw_addr("\1\2\3", "inet") == nil)
assert(tlsdrop.format_raw_addr(nil, nil) == nil)
assert(tlsdrop.format_raw_addr("x", "unix") == nil)
""")


# ------------------------------------------------------------------------------------------ hook


@needs_lua
def test_hook_closes_the_handshake_once_and_returns_true():
    run_tls(r"""
ban("bans_ip_192.0.2.1", "manual", {})
assert(tlsdrop.hook("www", false, false, nil) == true)
assert(#exits == 1 and exits[1] == ngx.ERROR)
assert(tlsdrop.hook("other-but-global-ban", false, false, nil) == true)
ban("bans_ip_192.0.2.1", "manual", {})
main_store["bans_ip_192.0.2.1"] = nil
assert(tlsdrop.hook("www", false, false, nil) == nil, "a client that is not banned must go on")
assert(#exits == 2)
""")


@needs_lua
def test_the_drop_warning_is_throttled_per_ip_and_per_minute():
    run_tls(r"""
ban("bans_ip_192.0.2.1", "manual", {})
local function warnings()
    local n = 0
    for _, entry in ipairs(logs) do if entry[2]:find("dropped banned IP") then n = n + 1 end end
    return n
end
for _ = 1, 5 do tlsdrop.hook("www", false, false, nil) end
assert(#exits == 5, "every handshake is still closed")
assert(warnings() == 1, "expected one warning, got " .. warnings())
clock = clock + 59
tlsdrop.hook("www", false, false, nil)
assert(warnings() == 1)
clock = clock + 2
tlsdrop.hook("www", false, false, nil)
assert(warnings() == 2, "the warning must come back after a minute")
""")


@needs_lua
def test_the_throttle_table_is_bounded():
    run_tls(r"""
-- 3000 distinct banned addresses inside one minute: all dropped, memory bounded, warnings still logged
for i = 0, 2999 do
    local ip = string.format("10.%d.%d.%d", i // 65536, (i // 256) % 256, i % 256)
    main_store["bans_ip_" .. ip] = ban_value("manual", {})
    client.addr = string.char(10, i // 65536, (i // 256) % 256, i % 256)
    assert(tlsdrop.hook("www", false, false, nil) == true)
end
assert(#exits == 3000)
local count = 0
for _, entry in ipairs(logs) do if entry[2]:find("dropped banned IP") then count = count + 1 end end
assert(count == 3000, "every distinct address gets its first warning, got " .. count)
""")
