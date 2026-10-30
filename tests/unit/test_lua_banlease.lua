local root = arg[0]:match("^(.*)/tests/unit/") or "."
package.path = root .. "/src/bw/lua/?.lua;" .. package.path

local failures = 0
local function it(name, fn)
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. tostring(err))))
	if not ok then
		failures = failures + 1
	end
end

local function new_dict()
	local data = {}
	local dict = {}
	function dict.get(_, k)
		return data[k]
	end
	dict.full = false
	function dict.safe_set(_, k, v)
		if dict.full and data[k] == nil then
			return false, "no memory"
		end
		data[k] = v
		return true
	end
	function dict.safe_add(_, k, v)
		if data[k] ~= nil then
			return false, "exists"
		end
		if dict.full then
			return false, "no memory"
		end
		data[k] = v
		return true
	end
	function dict.incr(_, k, v)
		if data[k] == nil then
			return nil, "not found"
		end
		data[k] = data[k] + v
		return data[k]
	end
	function dict.delete(_, k)
		data[k] = nil
	end
	dict._data = data
	return dict
end

local now = 1700000000.123456
_G.ngx = {
	shared = { bans_meta = new_dict() },
	now = function()
		return now
	end,
	time = function()
		return math.floor(now)
	end,
	log = function() end,
	ERR = 4,
	WARN = 5,
	INFO = 7,
}
package.loaded["cjson"] = {
	encode = function(t)
		return string.format("%s|%s|%s", t.id, t.rank, t.epoch)
	end,
	decode = function(s)
		local id, rank, epoch = s:match("^(.-)|(%d+)|(%d+)$")
		return { id = id, rank = tonumber(rank), epoch = tonumber(epoch) }
	end,
}
package.loaded["resty.random"] = {
	bytes = function(n)
		return string.rep("\171", n)
	end,
}
package.loaded["resty.string"] = {
	to_hex = function(s)
		return (s:gsub(".", function(c)
			return string.format("%02x", c:byte())
		end))
	end,
}
local banlease = require("bunkerweb.banlease")

it("reason ids map stored reasons", function()
	assert(banlease.reason_id("bad behavior") == "bad_behavior")
	assert(banlease.reason_id("crowdsec") == "crowdsec")
	assert(banlease.reason_id("something else") == nil)
	assert(banlease.is_known_id("bad_behavior") and not banlease.is_known_id("bad behavior"))
	assert(not banlease.is_known_id("antiddos"))
end)

it("lease keys and detection", function()
	assert(banlease.lease_key("1.2.3.4") == "bans_cs_ip_1.2.3.4")
	assert(banlease.lease_key("1.2.3.4", "a_ip_b.example.com") == "bans_cs_service_a_ip_b.example.com_ip_1.2.3.4")
	assert(banlease.is_lease_key("bans_cs_ip_1.2.3.4") and not banlease.is_lease_key("bans_ip_1.2.3.4"))
end)

it("epochs never repeat and missing epochs stay missing without create", function()
	assert(banlease.lease_epoch("1.2.3.4", false) == nil)
	local e1 = banlease.lease_epoch("1.2.3.4", true)
	assert(type(e1) == "number")
	assert(banlease.lease_epoch("1.2.3.4", true) == e1)
	local e2 = banlease.bump_lease_epoch("1.2.3.4")
	assert(e2 ~= e1)
	assert(banlease.marker_epoch("1.2.3.4", false) == nil)
end)

it("a full dict fails writes instead of evicting, and a failed bump fences by deleting", function()
	local dict = ngx.shared.bans_meta
	local before = dict._data["epoch_seq"]
	dict.full = true
	assert(banlease.lease_epoch("9.9.9.9", true) == nil, "no new epoch when full")
	local e = banlease.bump_lease_epoch("1.2.3.4") -- existing key: safe_set succeeds
	assert(e and dict._data["epoch_seq"] > before)
	assert(banlease.bump_marker_epoch("8.8.8.8") == nil, "new key cannot be created")
	assert(dict._data["me_8.8.8.8"] == nil)
	assert(banlease.write_marker("", "8.8.8.8", "manual", 2, 1, 30) == false)
	assert(dict._data["epoch_seq"] ~= nil, "the sequence is never removed")
	dict.full = false
end)

it("markers round trip and are scoped by service", function()
	local me = banlease.marker_epoch("1.2.3.4", true)
	assert(banlease.write_marker("www.example.com", "1.2.3.4", "crowdsec", 4, me, 30))
	local m = banlease.read_marker("www.example.com", "1.2.3.4")
	assert(m and m.id == "crowdsec" and m.rank == 4 and m.epoch == me)
	assert(banlease.read_marker("", "1.2.3.4") == nil)
end)

it("format_raw_addr handles v4, v6 and v4-mapped (kept IPv6, as nginx prints it)", function()
	assert(banlease.format_raw_addr("\1\2\3\4", "inet") == "1.2.3.4")
	local v6 = "\32\1\13\184" .. string.rep("\0", 11) .. "\1"
	assert(banlease.format_raw_addr(v6, "inet6") == "2001:db8::1")
	local mapped = string.rep("\0", 10) .. "\255\255\1\2\3\4"
	assert(banlease.format_raw_addr(mapped, "inet6") == "::ffff:1.2.3.4")
	assert(banlease.format_raw_addr(nil, nil) == nil)
end)

it("incarnation is 32 hex chars", function()
	local inc = banlease.new_incarnation()
	assert(inc and #inc == 32 and inc:match("^%x+$"))
end)

it("no dict means no epochs and no markers", function()
	ngx.shared.bans_meta = nil
	assert(banlease.lease_epoch("1.2.3.4", true) == nil)
	assert(banlease.bump_marker_epoch("1.2.3.4") == nil)
	assert(banlease.read_marker("", "1.2.3.4") == nil)
end)

os.exit(failures == 0 and 0 or 1)
