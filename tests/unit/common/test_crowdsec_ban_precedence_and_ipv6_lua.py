"""CrowdSec exclusions, captcha precedence and IP identity using shipped Lua bodies."""

import ipaddress
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from test_crowdsec_challenge_lua import ALLOW, CHALLENGE_PREFIX, field, run, to_lua

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")


@pytest.mark.parametrize("uri", ["/private", "/private/child", "/private/child/grandchild"])
def test_excluded_location_never_queries_lapi_or_appsec(uri):
    output = run(ALLOW, uri=uri, conf={"EXCLUDE_LOCATION": ["/private"]}, allowip_ok=False, allowip_remediation="ban")
    assert field(output, "ALLOWIP_CALLS") == "0"
    assert field(output, "SENT_URI") == "nil"
    assert "whitelisted /private" in field(output, "RET")


def test_exclusion_does_not_cover_sibling_prefix():
    output = run(ALLOW, uri="/private-other", conf={"EXCLUDE_LOCATION": ["/private"]}, allowip_ok=False, allowip_remediation="ban")
    assert field(output, "RET") == "true|denied|true|nil"


def test_expected_exclusion_is_debug_only():
    output = run(ALLOW, uri="/private/child", conf={"EXCLUDE_LOCATION": ["/private"]})
    assert "LOG=DEBUG whitelisted location: /private/" in output
    assert "LOG=ERR" not in output


SOLUTION = """
local validated, redirected = 0, nil
csmod.validateCaptcha = function() validated = validated + 1; return true end
ngx.req.get_post_args = function() return { ['g-recaptcha-response'] = 'valid-token' } end
ngx.req.set_method = function(method) assert(method == ngx.HTTP_GET) end
ngx.redirect = function(uri) redirected = uri; return true, uri end
local ok, msg, banned = csmod.Allow('1.2.3.4', false, nil, CHALLENGE_PREFIX)
print('RESULT=' .. tostring(ok) .. '|' .. tostring(msg) .. '|' .. tostring(banned))
print('VALIDATED=' .. validated)
print('REDIRECTED=' .. tostring(redirected))
dump()
"""


def test_appsec_only_captcha_solution_redirects():
    output = run(
        SOLUTION,
        cache={"captcha_1.2.3.4": ["/private", 6]},
        appsec_json={"action": "captcha"},
        request_body="g-recaptcha-response=valid-token",
        captcha_usable=True,
    )
    assert field(output, "REDIRECTED") == "/private"
    assert field(output, "VALIDATED") == "1"
    assert f"CACHE_KEY={CHALLENGE_PREFIX}captcha_1.2.3.4" not in output


@pytest.mark.parametrize("source", [1, 2])
def test_pending_captcha_solution_cannot_override_lapi_ban(source):
    output = run(
        SOLUTION,
        cache={"captcha_1.2.3.4": ["/private", source | 4]},
        request_body="g-recaptcha-response=valid-token",
        captcha_usable=True,
        allowip_ok=False,
        allowip_remediation="ban",
    )
    assert field(output, "RESULT") == "true|denied|true"
    assert field(output, "VALIDATED") == "0"
    assert field(output, "REDIRECTED") == "nil"


# The raw parser never collapses an IPv6 address onto its IPv4 tail. An IPv4-mapped address (::ffff:a.b.c.d) is the one
# address that IS its IPv4 address in the identity the core shares (ipaddr.key): bouncer.lua maps it before it parses,
# which test_crowdsec_ipv6_identity_lua.py pins (decisions, clients and ranges, every spelling).
@pytest.mark.parametrize(
    "address",
    ["2001:db8::192.0.2.1", "64:ff9b::192.0.2.1", "::192.0.2.1", "::ffff:192.0.2.1", "::FFFF:192.0.2.1", "::ffff:c000:201"],
)
def test_ipv6_tail_retains_full_ipv6_identity_in_the_raw_parser(address):
    words = struct.unpack("<4I", ipaddress.IPv6Address(address).packed)
    expected = [(int(ipaddress.IPv6Address(address)) >> (32 * i)) & 0xFFFFFFFF for i in range(4)]
    script = f"""
package.path = {to_lua(str(ROOT / 'src/common/core/?.lua') + ';')} .. package.path
local words = {to_lua(list(words))}
package.loaded.ffi = {{ cdef = function() end, new = function() return {{uint32={{}}}} end,
  C = {{inet_pton = function(_, text, dst)
    assert(text == {to_lua(address)})
    for i=0,3 do dst.uint32[i] = words[i+1] end
    return 1
  end}} }}
local ip = require 'crowdsec.lib.iputils'
local value, ipv4 = ip.parseIPAddress({to_lua(address)})
assert(ipv4 == false, 'IPv6 decision collapsed onto IPv4')
for i, word in ipairs({to_lua(expected)}) do assert(value.uint32[i-1] == word) end
local v4, is_v4 = ip.parseIPAddress('192.0.2.1')
assert(v4 == 0xc0000201 and is_v4 == true)
print('OK')
"""
    result = subprocess.run(["lua", "-"], input=script, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("address", ["prefix192.0.2.1", "192.0.2.1suffix", "-1.2.3.4"])
def test_ipv4_parser_rejects_surrounding_text(address):
    script = f"""
package.path = {to_lua(str(ROOT / 'src/common/core/?.lua') + ';')} .. package.path
package.loaded.ffi = {{ cdef=function() end }}
require 'crowdsec.lib.iputils'
assert(parseIP4Address({to_lua(address)}) == nil, 'IPv4 parser accepted surrounding text')
"""
    result = subprocess.run(["lua", "-"], input=script, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
