"""Real bundled bit operations under Lua 5.4; IP parsing uses LuaJIT's real FFI/libc.

Set BW_LUAJIT when LuaJIT is outside PATH, as in test_ipv6_ipmatcher_luajit.py.
Neither library is stubbed; decimal IPv6 words follow iputils' exported representation.
"""

import ipaddress
import os
import shutil
import subprocess

import pytest
from _lua_state_helpers import CORE, LUA, run_lua, to_lua  # type: ignore

LIB = CORE / "crowdsec" / "lib"
LUAJIT = os.environ.get("BW_LUAJIT") or shutil.which("luajit")
needs_jit = pytest.mark.skipif(not LUAJIT, reason="iputils needs real LuaJIT FFI (BW_LUAJIT)")
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")


def run(body, *, iputils=False):
    script = f'package.path = {to_lua(str(CORE / "?.lua") + ";")} .. package.path\n'
    script += f'local bit = dofile({to_lua(str(LIB / "bitop.lua"))})\n'
    if iputils:
        script += f'local ip = dofile({to_lua(str(LIB / "iputils.lua"))})\n'
    script += body + '\nprint("OK")\n'
    if iputils:
        result = subprocess.run([LUAJIT, "-"], input=script, capture_output=True, text=True, check=False, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        output = result.stdout
    else:
        output = run_lua(script)
    assert output.strip().endswith("OK")


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("tobit(-1)", 0xFFFFFFFF),
        ("tobit(4294967297)", 1),
        ("bnot(0)", 0xFFFFFFFF),
        ("bnot(4294967295)", 0),
        ("band(0x12345678, 0xff00ff00)", 0x12005600),
        ("bor(0x12345678, 0xff00ff00)", 0xFF34FF78),
        ("bxor(0x12345678, 0xff00ff00)", 0xED34A978),
        ("bxor(0, 123)", 123),
        ("bxor(123, 0)", 123),
        ("lshift(0x80000001, 1)", 2),
        ("lshift(0x80000000, -31)", 1),
        ("rshift(8, -2)", 32),
        ("rshift(0xffffffff, 4)", 0x0FFFFFFF),
        ("tohex(0xabcdef)", "00abcdef"),
        ("tohex(0xabcdef, -4)", "CDEF"),
        ("tohex(123, 0)", ""),
        ("extract(0x12345678, 8, 8)", 0x56),
        ("extract(2, 1)", 1),
        ("replace(0x12345678, 0x1ab, 8, 8)", 0x1234AB78),
        ("replace(0, 1, 31)", 0x80000000),
        ("bswap(0x12345678)", 0x78563412),
        ("rrotate(0x12345678, 8)", 0x78123456),
        ("lrotate(0x12345678, 8)", 0x34567812),
        ("rol(0x12345678, 40)", 0x34567812),
        ("ror(0x12345678, 32)", 0x12345678),
        ("arshift(0x80000000, 4)", 0xF8000000),
        ("arshift(0x70000000, 4)", 0x07000000),
        ("btest(2, 3)", True),
        ("btest(2, 1)", False),
    ],
)
def test_pure_lua_bit_operations(expression, expected):
    run(f"assert(bit.{expression} == {to_lua(expected)}, {to_lua(expression)})")


@pytest.mark.parametrize("compat", ["bit32", "bit"])
def test_variadic_bit_operations_and_signed_normalization(compat):
    signed = compat == "bit"
    run(f"""
local b = bit.{compat}
assert(b.tobit == nil or b.tobit(0xffffffff) == -1)
assert(b.bnot(0) == {(-1 if signed else 0xFFFFFFFF)})
assert(b.bnot(-1) == 0)
assert(b.band(-1) == {(-1 if signed else 0xFFFFFFFF)})
assert(b.bor(4294967297) == 1)
assert(b.bxor(-1) == {(-1 if signed else 0xFFFFFFFF)})
assert(b.band(0xf7, 0x7f, 0x37, 0x17) == 0x17)
assert(b.bor(1, 2, 4, 8) == 15)
assert(b.bxor(1, 3, 7, 15) == 10)
assert(b.band(-1, 0xff) == 255)
assert(b.bor(-1, 0) == {(-1 if signed else 0xFFFFFFFF)})
assert(b.bxor(-1, 0) == {(-1 if signed else 0xFFFFFFFF)})
""")


def test_bit32_empty_arguments_rotations_and_shift_boundaries():
    run("""
local b = bit.bit32
assert(b.band() == 0xffffffff and b.bor() == 0 and b.bxor() == 0)
assert(b.btest(3, 2) and not b.btest(1, 2))
assert(b.lrotate(-1, 17) == 0xffffffff)
assert(b.rrotate(4294967297, 1) == 0x80000000)
assert(b.lshift(1, 31) == 0x80000000)
assert(b.rshift(-1, 31) == 1)
assert(b.lshift(8, -1) == 4 and b.rshift(8, -1) == 16)
for _, n in ipairs({-33, -32, 32, 33}) do
    assert(b.lshift(-1, n) == 0 and b.rshift(-1, n) == 0)
end
assert(b.arshift(-1, 32) == 0xffffffff)
assert(b.arshift(1, 32) == 0)
assert(b.arshift(0x80000000, 4) == 0xf8000000)
assert(b.arshift(0x70000000, 4) == 0x07000000)
assert(b.arshift(1, -1) == 2)
assert(b.extract(-1, 8, 8) == 255 and b.extract(2, 1) == 1)
assert(b.replace(-1, 0, 8, 8) == 0xffff00ff and b.replace(0, 1, 1) == 2)
""")


@pytest.mark.parametrize(("field", "width"), [(-1, 1), (32, 1), (0, -1), (31, 2)])
@pytest.mark.parametrize("operation", ["extract", "replace"])
def test_bit32_rejects_out_of_range_fields(operation, field, width):
    args = f"0, {field}, {width}" if operation == "extract" else f"0, 1, {field}, {width}"
    run(f"local ok, err = pcall(bit.bit32.{operation}, {args}); assert(not ok and err:find('out of range', 1, true))")


def test_bitop_signed_api_wraps_shifts_rotates_and_bytes():
    run("""
local b = bit.bit
assert(b.tobit(1) == 1 and b.tobit(-1) == -1)
assert(b.tohex(-1) == 'ffffffff')
assert(b.lshift(1, 33) == 2 and b.rshift(-1, 33) == 0x7fffffff)
assert(b.arshift(-2147483648, 1) == -1073741824)
assert(b.rol(0x40000000, 1) == -2147483648)
assert(b.ror(1, 1) == -2147483648)
assert(b.bswap(0x12345680) == -2141834222)
""")


@needs_jit
@pytest.mark.parametrize("address", ["0.0.0.0", "192.0.2.255", "255.255.255.255"])
def test_ipv4_parsing_and_integer_conversion(address):
    value = int(ipaddress.IPv4Address(address))
    run(
        f"""
assert(parseIP4Address({to_lua(address)}) == {value})
local value, v4 = ip.parseIPAddress({to_lua(address)})
assert(value == {value} and v4 == true)
assert(ip.ipToInt({to_lua(address)}) == {value})
""",
        iputils=True,
    )


@needs_jit
@pytest.mark.parametrize("address", ["", "garbage", "1.2.3", "256.1.2.3", "1.2.3.999", "2001:db8:::1"])
def test_invalid_addresses_return_nil(address):
    run(
        f"""
assert(parseIP4Address({to_lua(address)}) == nil)
local value, v4 = ip.parseIPAddress({to_lua(address)})
assert(value == nil and v4 == false)
""",
        iputils=True,
    )


@needs_jit
@pytest.mark.parametrize(
    "address",
    ["::", "::1", "2001:db8::1234", "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff", "::ffff:c000:201", "2001:db8::192.0.2.1", "64:ff9b::192.0.2.1"],
)
def test_ipv6_parsing_preserves_all_network_order_words(address):
    value = int(ipaddress.IPv6Address(address))
    words = [(value >> (32 * i)) & 0xFFFFFFFF for i in range(4)]
    run(
        f"""
local value, v4 = ip.parseIPAddress({to_lua(address)})
assert(value ~= nil and v4 == false)
for i, expected in ipairs({to_lua(words)}) do assert(tonumber(value.uint32[i-1]) == expected) end
""",
        iputils=True,
    )


@needs_jit
def test_endian_aliases_ipv6_concatenation_and_table_merge():
    run(
        """
assert(bswap16(0x1234) == 0x3412)
assert(hton16(0xabcd) == 0xcdab and ntoh16(0xcdab) == 0xabcd)
assert(hton(0x12345678) == 0x78563412 and ntoh(0x78563412) == 0x12345678)
assert(bswap == hton and hton == ntoh)
assert(ip.concatIPv6({0, 0, 0, 1}) == 1)
assert(ip.concatIPv6({1, 0, 0, 0}) == 2^96)
assert(ip.concatIPv6({1, 2}) == nil and ip.concatIPv6('bad') == nil)
assert(ip.ipToInt(nil) == 0 and ip.ipToInt(123) == 0)
local empty = mergeTables(); assert(next(empty) == nil)
local first = {keep=1, override=2}
local merged = mergeTables(first, {override=3}, {last=4})
assert(merged == first and merged.keep == 1 and merged.override == 3 and merged.last == 4)
""",
        iputils=True,
    )


@needs_jit
@pytest.mark.parametrize("version", [4, 6])
def test_every_cidr_mask_and_membership_boundary(version):
    bits = 32 if version == 4 else 128
    # Python ipaddress supplies independent masks and addresses at either side of each prefix.
    cases = []
    for prefix in range(bits + 1):
        network = ipaddress.ip_network(f"{'192.0.2.129' if version == 4 else '2001:db8:1234:5678:9abc:def0:1234:5678'}/{prefix}", strict=False)
        mask = int(network.netmask)
        base = int(network.network_address)
        last = int(network.broadcast_address)
        if version == 4:
            cases.append(f"assert(ip.cidrToInt({prefix}, 'ipv4') == '{mask}')")
            for address, expected in [(base, base), (last, base)]:
                cases.append(f"assert(ip.ipv4_band({address}, {mask}) == {expected})")
            if last < (1 << bits) - 1:
                cases.append(f"assert(ip.ipv4_band({last + 1}, {mask}) ~= {base})")
        else:
            words = [(mask >> shift) & 0xFFFFFFFF for shift in (96, 64, 32, 0)]
            base_words = ":".join(str((base >> shift) & 0xFFFFFFFF) for shift in (96, 64, 32, 0))
            cases.append(f"assert(ip.cidrToInt({prefix}, 'ipv6') == {to_lua(':'.join(map(str, words)))})")
            for address, equal in [(base, True), (last, True)] + ([(last + 1, False)] if last < (1 << bits) - 1 else []):
                address_words = ":".join(str((address >> shift) & 0xFFFFFFFF) for shift in (96, 64, 32, 0))
                cases.append(f"assert(ip.ipv6_band({to_lua(address_words)}, {to_lua(words)}) {'==' if equal else '~='} {to_lua(base_words)})")
    run("\n".join(cases), iputils=True)


@needs_jit
def test_split_ranges_and_cidr_type_guard():
    run(
        """
for _, range in ipairs({'192.0.2.1/24', '2001:db8::1/128'}) do
    local addr, prefix = ip.splitRange(range)
    assert(addr .. '/' .. prefix == range)
end
for _, input in ipairs({false, 123, '', '192.0.2.1', '192.0.2.1/no'}) do
    local addr, prefix = ip.splitRange(input); assert(addr == nil and prefix == nil)
end
local addr, prefix = ip.splitRange(nil); assert(addr == nil and prefix == nil)
assert(ip.cidrToInt('bad', {}) == nil)
assert(ip.cidrToInt(1, 'unknown') == nil)
assert(#ip.netmasks_by_key_type.ipv4 == 33 and #ip.netmasks_by_key_type.ipv6 == 129)
""",
        iputils=True,
    )


@needs_jit
@pytest.mark.parametrize("address", ["prefix192.0.2.1", "192.0.2.1suffix", "-1.2.3.4"])
def test_ipv4_parser_rejects_surrounding_text(address):
    run(f"assert(parseIP4Address({to_lua(address)}) == nil)", iputils=True)


@needs_jit
def test_ipv6_parser_accepts_dotted_mapped_addresses_directly():
    run(
        """
local value = parseIP6Address('::ffff:192.0.2.1')
assert(value ~= nil and tonumber(value.uint32[0]) == 0xc0000201 and tonumber(value.uint32[1]) == 0xffff)
""",
        iputils=True,
    )


@needs_jit
@pytest.mark.parametrize("address", ["::ffff:192.0.2.1", "::FFFF:192.0.2.1"])
def test_dispatch_preserves_mapped_ipv6_address_family(address):
    # IPv6 policy: mapped addresses share the IPv4 client's decision identity.
    run(f"local value, v4 = ip.parseIPAddress({to_lua(address)}); assert(value == 0xc0000201 and v4 == true)", iputils=True)
