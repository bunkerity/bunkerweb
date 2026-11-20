"""Reserved-address classification with the real vendored matcher under LuaJIT."""

import ipaddress
import json

import pytest
from test_ipv6_ipmatcher_luajit import LUAJIT, ROOT, run

pytestmark = pytest.mark.skipif(not LUAJIT, reason="no LuaJIT on PATH (BW_LUAJIT)")

RESERVED = (
    "0.0.0.0/8",
    "10.0.0.0/8",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.0.0.0/24",
    "192.88.99.0/24",
    "192.168.0.0/16",
    "198.18.0.0/15",
    "198.51.100.0/24",
    "203.0.113.0/24",
    "224.0.0.0/4",
    "233.252.0.0/24",
    "240.0.0.0/4",
    "255.255.255.255/32",
    "::/128",
    "::1/128",
    "::ffff:0:0:0/96",
    "64:ff9b::/96",
    "64:ff9b:1::/48",
    "100::/64",
    "2001::/32",
    "2001:20::/28",
    "2001:db8::/32",
    "2002::/16",
    "fc00::/7",
    "fe80::/10",
    "ff00::/8",
)

HARNESS = r"""
ngx.re = {match = function() end}
ngx.thread = {kill = function() end}
ngx.shared = {internalstore = {}, internalstore_stream = {}}
package.loaded["bunkerweb.banlease"] = {}
package.loaded["bunkerweb.datastore"] = {new = function() return {} end}
package.loaded["bunkerweb.logger"] = {new = function() return {} end}
package.loaded["bunkerweb.mmdb"] = {}
package.loaded["cjson"] = {}
package.loaded["resty.random"] = {}
package.loaded["resty.dns.resolver"] = {}
package.loaded["resty.session"] = {}
local constructions = 0
local real_new = ipmatcher.new
ipmatcher.new = function(networks)
    constructions = constructions + 1
    if FAIL_CONSTRUCTION then return nil, "forced construction failure" end
    return real_new(networks)
end
package.loaded["resty.ipmatcher"] = ipmatcher
local utils = dofile(UTILS_PATH)
assert(constructions == 0, "matcher must be lazy")
"""


def run_utils(body, subsystem="http"):
    run(f"ngx.config.subsystem = {json.dumps(subsystem)}\nUTILS_PATH = {json.dumps(str(ROOT / 'src/bw/lua/bunkerweb/utils.lua'))}\n" + HARNESS + body)


@pytest.mark.parametrize("subsystem", ["http", "stream"])
def test_reserved_edges_preserve_results_and_build_once(subsystem):
    networks = [ipaddress.ip_network(cidr) for cidr in RESERVED]
    addresses = {
        ipaddress.ip_address(ip) for ip in ("8.8.8.8", "1.1.1.1", "192.0.2.1", "2606:4700:4700::1111", "::ffff:8.8.8.8", "::ffff:10.1.2.3", "::FFFF:C0A8:101")
    }
    for network in networks:
        for edge in (int(network.network_address), int(network.broadcast_address)):
            for offset in (-1, 0, 1):
                if 0 <= edge + offset < 2**network.max_prefixlen:
                    addresses.add(type(network.network_address)(edge + offset))
    assertions = []
    for address in sorted(addresses, key=lambda ip: (ip.version, int(ip))):
        effective = address.ipv4_mapped if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped else address
        expected = not any(effective.version == network.version and effective in network for network in networks)
        assertions.append(f"check({json.dumps(str(address))}, {str(expected).lower()})")
    run_utils(
        r"""
local function check(ip, expected)
    for _ = 1, 3 do
        local global, err = utils.ip_is_global(ip)
        assert(global == expected, ip .. ": " .. tostring(global))
        assert(err == "success", tostring(err))
    end
end
""" + "\n".join(assertions) + '\nassert(constructions == 1, "expected one construction, got " .. constructions)',
        subsystem,
    )


def test_constructor_failure_is_not_cached_and_later_call_retries():
    run_utils(r"""
FAIL_CONSTRUCTION = true
for attempt = 1, 2 do
    local global, err = utils.ip_is_global("8.8.8.8")
    assert(global == nil)
    assert(err == "can't instantiate ipmatcher : forced construction failure", tostring(err))
    assert(constructions == attempt)
end
FAIL_CONSTRUCTION = false
for _ = 1, 10 do
    local global, err = utils.ip_is_global("8.8.8.8")
    assert(global == true and err == "success")
end
assert(constructions == 3, "successful retry must be cached, got " .. constructions)
""")


def test_invalid_clients_keep_matcher_error_and_cached_matcher():
    run_utils(r"""
local reference = assert(real_new({}))
for _, ip in ipairs({"", "not-an-ip", "1.2.3.999", "2001:db8::xyz", "fe80::1%eth0"}) do
    local _, expected_error = reference:match(ip)
    assert(expected_error, "fixture must be invalid: " .. ip)
    local global, err = utils.ip_is_global(ip)
    assert(global == nil)
    assert(err == "can't check ip : " .. expected_error, tostring(err))
end
local global, err = utils.ip_is_global("8.8.8.8")
assert(global == true and err == "success")
assert(constructions == 1, "invalid clients must not discard matcher, got " .. constructions)
""")
