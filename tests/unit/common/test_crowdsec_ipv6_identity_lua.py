"""CrowdSec decisions and clients share one IP identity with the rest of the core (``ipaddr.key``).

An IPv4-mapped IPv6 address is its IPv4 address and every spelling of an IPv6 address is one address: a decision for
``192.0.2.1`` blocks a client that arrives as ``::ffff:192.0.2.1`` (and the reverse), and an IPv6 decision matches every
spelling of it. The real ``lib/bouncer.lua`` runs through the harness of ``test_crowdsec_bouncer_stream_coverage_lua.py``;
only OpenResty, libc and the Local API are faked. The FFI ``inet_pton`` fake knows the spellings registered below.
"""

import ipaddress
import struct

import pytest
from _crowdsec_lua_helpers import BASE_LUA, LUA, last_json, run_lua, to_lua  # type: ignore
from test_crowdsec_bouncer_stream_coverage_lua import HARNESS, ROOT  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

SPELLINGS = [
    "2001:db8::1",
    "2001:DB8::1",
    "2001:db8:0:0:0:0:0:1",
    "2001:DB8:0:0:0:0:0:1",
    "::ffff:192.0.2.1",
    "::FFFF:192.0.2.1",
    "::ffff:c000:201",
    "::ffff:192.0.2.0",
    "::ffff:0:0",
    "::192.0.2.1",
    "::c000:201",
    "64:ff9b::192.0.2.1",
    "64:ff9b::c000:201",
    "::1",
]


def run(tmp_path, body, *, conf=None):
    config = {
        "API_URL": "https://lapi.example",
        "API_KEY": "unit-key",
        "BOUNCING_ON_TYPE": "all",
        "FALLBACK_REMEDIATION": "ban",
        "CAPTCHA_PROVIDER": "",
        "CACHE_EXPIRATION": 30,
        **(conf or {}),
    }
    path = tmp_path / "bouncer.conf"
    path.write_text("".join(f"{key}={value}\n" for key, value in config.items()))
    ip6 = {text: struct.unpack("<4I", ipaddress.ip_address(text).packed) for text in SPELLINGS}
    prelude = f"ROOT={to_lua(str(ROOT))}\nDIR={to_lua(str(tmp_path))}\nCONF={to_lua(str(path))}\nIP6={to_lua(ip6)}\n"
    return last_json(run_lua(BASE_LUA + prelude + HARNESS + "\n" + body))


def verdicts(tmp_path, decisions, clients):
    """Stream the decisions in, then ask about each client address: {client: allowed?}."""
    out = run(
        tmp_path,
        f"""
assert(boot()); stream({to_lua(decisions)}); poll()
local out = {{}}
for _, ip in ipairs({to_lua(clients)}) do out[ip] = allowed(ip).allowed end
emit(out)
""",
    )
    return out


def lua_decision(value, scope="Ip"):
    return {"id": 1, "scope": scope, "value": value, "type": "ban", "duration": "3600s"}


MAPPED_CLIENTS = ["192.0.2.1", "::ffff:192.0.2.1", "::FFFF:192.0.2.1", "::ffff:c000:201"]


def test_an_ipv4_decision_blocks_every_spelling_of_the_mapped_client(tmp_path):
    result = verdicts(tmp_path, [lua_decision("192.0.2.1")], MAPPED_CLIENTS)
    assert result == {client: False for client in MAPPED_CLIENTS}


@pytest.mark.parametrize("decision", ["::ffff:192.0.2.1", "::FFFF:192.0.2.1", "::ffff:c000:201"])
def test_a_mapped_decision_blocks_the_ipv4_client_and_every_mapped_spelling(tmp_path, decision):
    result = verdicts(tmp_path, [lua_decision(decision)], MAPPED_CLIENTS)
    assert result == {client: False for client in MAPPED_CLIENTS}


@pytest.mark.parametrize("decision", ["2001:db8::1", "2001:DB8::1", "2001:db8:0:0:0:0:0:1", "2001:DB8:0:0:0:0:0:1"])
def test_an_ipv6_decision_matches_every_spelling(tmp_path, decision):
    clients = ["2001:db8::1", "2001:DB8::1", "2001:db8:0:0:0:0:0:1", "2001:DB8:0:0:0:0:0:1"]
    assert verdicts(tmp_path, [lua_decision(decision)], clients) == {client: False for client in clients}


def test_a_mapped_range_covers_the_ipv4_hosts_it_names(tmp_path):
    # ::ffff:192.0.2.0/120 is 192.0.2.0/24
    out = run(
        tmp_path,
        f"""
assert(boot()); stream({to_lua([lua_decision("::ffff:192.0.2.0/120", "Range")])}); poll()
emit({{inside=allowed('192.0.2.77').allowed, mapped=allowed('::ffff:192.0.2.77').allowed, outside=allowed('192.0.3.1').allowed}})
""",
    )
    assert out == {"inside": False, "mapped": False, "outside": True}


def test_an_ipv4_range_covers_the_mapped_clients_inside_it(tmp_path):
    out = run(
        tmp_path,
        f"""
assert(boot()); stream({to_lua([lua_decision("192.0.2.0/24", "Range")])}); poll()
emit({{inside=allowed('::ffff:192.0.2.77').allowed, outside=allowed('::ffff:192.0.3.1').allowed}})
""",
    )
    assert out == {"inside": False, "outside": True}


@pytest.mark.parametrize("decision", ["::192.0.2.1", "64:ff9b::192.0.2.1"])
def test_an_ipv6_address_with_an_ipv4_tail_stays_off_that_ipv4_address(tmp_path, decision):
    """Only ::ffff:a.b.c.d is an IPv4 address; every other dotted tail is a real IPv6 address."""
    result = verdicts(tmp_path, [lua_decision(decision)], ["192.0.2.1", decision])
    assert result == {"192.0.2.1": True, decision: False}


def test_the_decision_for_a_mapped_client_is_looked_up_under_its_ipv4_text(tmp_path):
    """The Local API is asked about the identity the rest of the core uses, never the mapped spelling."""
    out = run(
        tmp_path,
        """
assert(boot())
RESPONSE = {status=200, body=json.encode(setmetatable({{id=1,scope='Ip',value='192.0.2.1',type='ban',duration='3600s'}}, json.array_mt))}
local first = allowed('::ffff:192.0.2.1')
local second = allowed('192.0.2.1')
emit({first=first.allowed, second=second.allowed, link=REQUESTS[1].link, requests=#REQUESTS})
""",
        conf={"MODE": "live"},
    )
    assert out["first"] is False and out["second"] is False
    assert out["link"].endswith("/v1/decisions?ip=192.0.2.1")
    # one answer serves both spellings
    assert out["requests"] == 1


def test_refresh_ip_of_a_mapped_spelling_refreshes_the_ipv4_identity(tmp_path):
    out = run(
        tmp_path,
        """
assert(boot())
RESPONSE = {status=200, body=json.encode(setmetatable({{id=1,scope='Ip',value='192.0.2.1',type='ban',duration='3600s'}}, json.array_mt))}
local result, err, status = b.RefreshIp({ip='::ffff:192.0.2.1'})
emit({ok=result ~= nil, err=err, status=status, link=REQUESTS[1] and REQUESTS[1].link, epochs=(function() local keys={} for k in pairs(CACHE.data) do if k:find('refresh_epoch|',1,true) then keys[#keys+1]=k end end table.sort(keys) return keys end)()})
""",
        conf={"MODE": "live"},
    )
    assert out["ok"] is True, out
    assert out["link"].endswith("/v1/decisions?ip=192.0.2.1&contains=true")
    # the fence is keyed on the IPv4 identity, whatever the spelling of the unban
    assert len(out["epochs"]) == 1 and out["epochs"][0].split("refresh_epoch|")[1].startswith("ipv4_4294967295_3221225985")


def test_an_invalid_address_is_still_refused(tmp_path):
    out = run(tmp_path, "assert(boot()); local r, e, s = b.RefreshIp({ip='fe80::1%eth0'}); emit({r=r, e=e, s=s})")
    assert out == {"e": "invalid ip", "s": 400}
