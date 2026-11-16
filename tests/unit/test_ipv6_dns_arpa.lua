-- Plain Lua 5.4; only OpenResty socket/regex and LuaJIT bit boundaries are stubbed.
-- luacheck: std lua54
local script_dir = arg[0]:match("^(.*)/[^/]+$") or "."
local repo = script_dir .. "/../.."
package.path = repo .. "/src/deps/src/lua-resty-dns/lib/?.lua;" .. package.path
_G.unpack = table.unpack
package.loaded.bit = {
	band = function(a, b)
		return a & b
	end,
	rshift = function(a, b)
		return a >> b
	end,
	lshift = function(a, b)
		return a << b
	end,
}
_G.ngx = {
	socket = { tcp = function() end, udp = function() end },
	log = function() end,
	DEBUG = 8,
	re = {
		sub = function(subject, pattern, replacement)
			if pattern == "::" then
				return subject:gsub("::", replacement, 1)
			end
			assert(pattern == [[(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})]])
			assert(replacement == "$4.$3.$2.$1.in-addr.arpa")
			return subject:gsub("(%d+)%.(%d+)%.(%d+)%.(%d+)", "%4.%3.%2.%1.in-addr.arpa", 1)
		end,
	},
}
local dns = require "resty.dns.resolver"
local failures, checks = 0, 0
local function check(address, expected)
	checks = checks + 1
	local ok, actual = pcall(dns.arpa_str, address)
	print(address .. " -> " .. actual)
	if not ok or actual ~= expected then
		failures = failures + 1
		print("FAIL expected " .. expected)
	end
end
local function ipv6(hex)
	assert(#hex == 32)
	return hex:reverse():gsub("(.)", "%1.") .. "ip6.arpa"
end

local ordinary = ipv6("20010db8000000000000000000000001")
check("2001:db8::1", ordinary)
check("2001:0DB8:0:0:0:0:0:1", ipv6("20010DB8000000000000000000000001"))
check("2001:0db8:0000:0000:0000:0000:0000:0001", ordinary)
-- Keep this order: mapped lookup must not damage the next IPv6 or IPv4 lookup.
check("::ffff:192.0.2.1", ipv6("00000000000000000000ffffc0000201"))
check("2001:db8::1", ordinary)
check("192.0.2.1", "1.2.0.192.in-addr.arpa")
check("0:0:0:0:0:FFFF:192.0.2.1", ipv6("00000000000000000000FFFFc0000201"))
check("::ffff:0.0.0.0", ipv6("00000000000000000000ffff00000000"))
check("::ffff:255.255.255.255", ipv6("00000000000000000000ffffffffffff"))
check("2001:db8::192.0.2.1", ipv6("20010db80000000000000000c0000201"))
check("::", ipv6(string.rep("0", 32)))
check("::1", ipv6(string.rep("0", 31) .. "1"))
check("2001:db8::", ipv6("20010db8000000000000000000000000"))
check("ABCD:EF01:2345:6789:ABCD:EF01:2345:6789", ipv6("ABCDEF0123456789ABCDEF0123456789"))
check("::ffff:c000:201", ipv6("00000000000000000000ffffc0000201"))
check("2001:db8::1", ordinary)
print(checks .. " checks, " .. failures .. " failures")
os.exit(failures == 0 and 0 or 1)
