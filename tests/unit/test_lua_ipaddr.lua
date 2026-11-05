-- Plain Lua check of bunkerweb/ipaddr.lua: canonical IP text, IPv4-mapped IPv6 as IPv4, and nothing but the standard
-- library underneath (no ngx, no bunkerweb.* module, no ffi), so the file can live in a repository of its own.
-- Run: lua tests/unit/test_lua_ipaddr.lua   (from the repo root)
local root = arg[0]:match("^(.*)/tests/unit/") or "."
local path = root .. "/src/bw/lua/bunkerweb/ipaddr.lua"

local failures = 0
local function it(name, fn)
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. tostring(err))))
	if not ok then
		failures = failures + 1
	end
end
local function eq(a, b)
	assert(a == b, ("expected %s got %s"):format(tostring(b), tostring(a)))
end

-- Loaded with an empty environment apart from the standard library: any hidden dependency is a load error
local ipaddr =
	assert(loadfile(path, "t", { string = string, table = table, math = math, tonumber = tonumber, type = type }))()

it("a spelling of the same IPv6 address has one canonical text", function()
	for _, spelling in ipairs({
		"2001:0DB8:0:0:0:0:0:1",
		"2001:db8::1",
		"2001:DB8:0::1",
		"2001:db8:0:0:0:0:0:0001",
		"2001:db8::0:1",
	}) do
		eq(ipaddr.normalize(spelling), "2001:db8::1")
	end
end)

it("RFC 5952 compression: the first longest run of two or more zero groups", function()
	eq(ipaddr.normalize("2001:db8:0:0:1:0:0:1"), "2001:db8::1:0:0:1")
	eq(ipaddr.normalize("1:0:0:2:0:0:0:3"), "1:0:0:2::3")
	eq(ipaddr.normalize("1:2:3:4:5:6:7:0"), "1:2:3:4:5:6:7:0")
	eq(ipaddr.normalize("1:0:3:4:5:6:7:8"), "1:0:3:4:5:6:7:8")
	eq(ipaddr.normalize("0:0:0:0:0:0:0:0"), "::")
	eq(ipaddr.normalize("0:0:0:0:0:0:0:1"), "::1")
	eq(ipaddr.normalize("1::"), "1::")
end)

it("an IPv4-mapped IPv6 address is the IPv4 address, in every spelling", function()
	for _, spelling in ipairs({ "::ffff:192.0.2.1", "::FFFF:192.0.2.1", "::ffff:c000:201", "0:0:0:0:0:ffff:c000:0201" }) do
		eq(ipaddr.normalize(spelling), "192.0.2.1")
	end
	eq(ipaddr.normalize("::ffff:0:1"), "0.0.0.1")
	eq(ipaddr.normalize("::fffe:c000:201"), "::fffe:c000:201")
end)

it("the dotted tail follows ngx_inet6_ntop, so a $remote_addr is its own identity", function()
	eq(ipaddr.normalize("::1.2.3.4"), "::1.2.3.4")
	eq(ipaddr.normalize("::102:304"), "::1.2.3.4")
	eq(ipaddr.normalize("::1"), "::1")
	eq(ipaddr.normalize("::2"), "::2")
end)

it("IPv4 is kept, with no leading zero", function()
	eq(ipaddr.normalize("192.0.2.1"), "192.0.2.1")
	eq(ipaddr.normalize("0.0.0.0"), "0.0.0.0")
	eq(ipaddr.normalize("01.2.3.4"), nil)
	eq(ipaddr.normalize("1.2.3"), nil)
	eq(ipaddr.normalize("1.2.3.256"), nil)
end)

it("what is not a bare address is refused", function()
	for _, bad in ipairs({
		"fe80::1%eth0",
		"[2001:db8::1]",
		"2001:db8::1/64",
		"1::2::3",
		"1:2:3:4:5:6:7:8:9",
		"12345::1",
		"::ffff:1.2.3",
		"::ffff:1.2.3.4.5",
		"g::1",
		"",
		" 2001:db8::1",
		"example.com",
	}) do
		eq(ipaddr.normalize(bad), nil)
	end
	eq(ipaddr.normalize(nil), nil)
	eq(ipaddr.normalize(42), nil)
end)

it("key() canonicalizes IPv6 and leaves everything else as it came", function()
	eq(ipaddr.key("2001:0DB8::1"), "2001:db8::1")
	eq(ipaddr.key("2001:0DB8::1"), "2001:db8::1") -- memoized path
	eq(ipaddr.key("::ffff:192.0.2.1"), "192.0.2.1")
	eq(ipaddr.key("192.0.2.1"), "192.0.2.1")
	eq(ipaddr.key("fe80::1%eth0"), "fe80::1%eth0")
	eq(ipaddr.key("example.com"), "example.com")
	eq(ipaddr.key(nil), nil)
end)

it("the memo stays bounded", function()
	for i = 1, 5000 do
		eq(ipaddr.key(("2001:DB8::%x"):format(i)), ("2001:db8::%x"):format(i))
	end
end)

os.exit(failures == 0 and 0 or 1)
