-- Plain Lua check: one IPv6 address is one ban, lease and epoch, whatever its spelling (expanded, upper case,
-- IPv4-mapped), in the local datastore and in Redis (standalone keys and Cluster tagged keys).
-- Run: lua tests/unit/test_lua_ipv6_ban_identity.lua   (from the repo root)
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
local function eq(a, b, what)
	assert(a == b, (what or "value") .. ": expected " .. tostring(b) .. " got " .. tostring(a))
end

-- JSON stand-in: values are kept in a registry, the "encoded" string is its key
local registry = {}
package.loaded["cjson"] = {
	encode = function(value)
		registry[#registry + 1] = value
		return "json:" .. #registry
	end,
	decode = function(text)
		local value = registry[tonumber(text:match("^json:(%d+)$"))]
		assert(value, "unknown json " .. tostring(text))
		return value
	end,
}

local function new_dict()
	local data = {}
	local dict = {}
	function dict.get(_, k)
		return data[k]
	end
	function dict.safe_set(_, k, v)
		data[k] = v
		return true
	end
	function dict.safe_add(_, k, v)
		if data[k] ~= nil then
			return false, "exists"
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
	return dict
end

_G.ngx = {
	null = setmetatable({}, {}),
	shared = { bans_meta = new_dict(), datastore = new_dict(), internalstore = {} },
	config = { subsystem = "http" },
	thread = { kill = function() end },
	re = { match = function() end },
	var = {},
	now = function()
		return 1700000000
	end,
	time = function()
		return 1700000000
	end,
	log = function() end,
	get_phase = function()
		return "access"
	end,
	ERR = 4,
	WARN = 5,
	INFO = 7,
	HTTP_FORBIDDEN = 403,
	HTTP_CLOSE = 444,
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
package.loaded["bunkerweb.logger"] = {
	new = function()
		return { log = function() end }
	end,
}
package.loaded["bunkerweb.mmdb"] = {}
package.loaded["resty.dns.resolver"] = {}
package.loaded["resty.session"] = { start = function() end }
package.loaded["resty.ipmatcher"] = {
	parse_ipv4 = function(ip)
		return ip:match("^%d+%.%d+%.%d+%.%d+$") ~= nil
	end,
	parse_ipv6 = function(ip)
		return ip:find(":", 1, true) ~= nil
	end,
	new = function()
		return {
			match = function()
				return false
			end,
		}
	end,
}

local rows, internal = {}, {}
local function make_datastore(store)
	local obj = {}
	function obj.get(_, key)
		if store[key] == nil then
			return nil, "not found"
		end
		return store[key].value
	end
	function obj.set_with_retries(_, key, value, ttl)
		store[key] = { value = value, ttl = ttl or 0 }
		return true, "success"
	end
	function obj.delete(_, key)
		store[key] = nil
		return true, "success"
	end
	function obj.keys()
		local keys = {}
		for k in pairs(store) do
			keys[#keys + 1] = k
		end
		return keys
	end
	function obj.ttl(_, key)
		return true, store[key] and store[key].ttl or 0
	end
	return obj
end
local main_ds, internal_ds = make_datastore(rows), make_datastore(internal)
package.loaded["bunkerweb.datastore"] = {
	new = function(_, dict)
		return dict == ngx.shared.internalstore and internal_ds or main_ds
	end,
}

-- Redis: every key the code SETs or DELs is recorded
local redis_set, redis_del = {}, {}
package.loaded["bunkerweb.clusterstore"] = {
	new = function()
		local cs = {}
		function cs.connect()
			return true
		end
		function cs.close() end
		function cs.call(_, cmd, key)
			if cmd == "set" then
				redis_set[#redis_set + 1] = key
			elseif cmd == "del" then
				redis_del[#redis_del + 1] = key
			end
			return true
		end
		return cs
	end,
}

local function set_variables(vars)
	internal["variables"] = { value = { global = vars } }
end
local function reset(vars)
	for k in pairs(rows) do
		rows[k] = nil
	end
	redis_set, redis_del = {}, {}
	set_variables(vars or { USE_REDIS = "no", REDIS_CLUSTER_NODES = "" })
end

local banlease = require "bunkerweb.banlease"
local utils = require "bunkerweb.utils"
local function has(list, key)
	for _, k in ipairs(list) do
		if k == key then
			return true
		end
	end
	return false
end

it("a ban on the expanded upper case spelling is found by the compressed one", function()
	reset()
	assert(utils.add_ban("2001:0DB8:0:0:0:0:0:1", "manual", 300))
	assert(rows["bans_ip_2001:db8::1"], "stored under the canonical key")
	assert(not rows["bans_ip_2001:0DB8:0:0:0:0:0:1"], "no alias key")
	assert(utils.is_banned_local("2001:db8::1") == true)
	assert(utils.is_banned_local("2001:DB8::0:1") == true)
end)

it("an IPv4-mapped IPv6 ban is the IPv4 ban", function()
	reset()
	assert(utils.add_ban("::ffff:192.0.2.1", "manual", 300))
	assert(rows["bans_ip_192.0.2.1"])
	assert(utils.is_banned_local("192.0.2.1") == true)
	assert(utils.is_banned_local("::ffff:192.0.2.1") == true)
	assert(utils.is_banned_local("::FFFF:C000:201") == true)
end)

it("a zone id or a bracketed literal is not an address to ban", function()
	reset()
	assert(utils.add_ban("fe80::1%eth0", "manual", 300) == false)
	assert(utils.add_ban("[2001:db8::1]", "manual", 300) == false)
	assert(next(rows) == nil)
end)

it("unban by the compressed spelling removes the canonical ban and the legacy spellings", function()
	reset()
	rows["bans_ip_2001:db8::1"] = { value = "x", ttl = 0 }
	rows["bans_ip_2001:0DB8:0:0:0:0:0:1"] = { value = "x", ttl = 0 }
	rows["bans_ip_::ffff:192.0.2.1"] = { value = "x", ttl = 0 }
	rows["bans_service_my_ip_app_ip_2001:DB8::1"] = { value = "x", ttl = 0 }
	rows["bans_ip_2001:db8::2"] = { value = "x", ttl = 0 }
	assert(utils.remove_ban("2001:db8::1"))
	assert(not rows["bans_ip_2001:db8::1"])
	assert(not rows["bans_ip_2001:0DB8:0:0:0:0:0:1"], "legacy expanded spelling is gone")
	assert(not rows["bans_service_my_ip_app_ip_2001:DB8::1"], "legacy service spelling is gone")
	assert(rows["bans_ip_2001:db8::2"], "another address is untouched")
	assert(rows["bans_ip_::ffff:192.0.2.1"], "the mapped address is a different identity from this IPv6 address")
	assert(utils.remove_ban("192.0.2.1"))
	assert(not rows["bans_ip_::ffff:192.0.2.1"], "a legacy mapped ban goes with the IPv4 unban")
end)

it("a service unban removes the legacy spelling of that service only", function()
	reset()
	rows["bans_service_a_ip_2001:0DB8::1"] = { value = "x", ttl = 0 }
	rows["bans_service_b_ip_2001:0DB8::1"] = { value = "x", ttl = 0 }
	assert(utils.remove_ban("2001:db8::1", "a", "service"))
	assert(not rows["bans_service_a_ip_2001:0DB8::1"])
	assert(rows["bans_service_b_ip_2001:0DB8::1"])
end)

it("Redis standalone keys use the canonical spelling", function()
	reset({ USE_REDIS = "yes", REDIS_CLUSTER_NODES = "" })
	assert(utils.add_ban("2001:0DB8:0:0:0:0:0:1", "manual", 300))
	assert(has(redis_set, "bans_ip_2001:db8::1"), table.concat(redis_set, ","))
	rows["bans_ip_2001:0DB8:0:0:0:0:0:1"] = { value = "x", ttl = 0 }
	assert(utils.remove_ban("2001:DB8::1"))
	assert(has(redis_del, "bans_ip_2001:db8::1"), table.concat(redis_del, ","))
	assert(has(redis_del, "bans_ip_2001:0DB8:0:0:0:0:0:1"), "the legacy key is deleted in Redis too")
end)

it("Redis Cluster tagged keys use the canonical spelling", function()
	reset({ USE_REDIS = "yes", REDIS_CLUSTER_NODES = "redis-a:6379" })
	assert(utils.add_ban("2001:0DB8:0:0:0:0:0:1", "manual", 300))
	assert(has(redis_set, "bans_ip_{2001:db8::1}"), table.concat(redis_set, ","))
	assert(utils.add_ban("::ffff:192.0.2.1", "manual", 300))
	assert(has(redis_set, "bans_ip_{192.0.2.1}"), table.concat(redis_set, ","))
end)

it("leases and epochs of the same address are one lease and one epoch", function()
	reset()
	eq(banlease.lease_key("2001:0DB8::1"), banlease.lease_key("2001:db8::1"))
	eq(banlease.lease_key("2001:DB8::1", "svc"), "bans_cs_service_svc_ip_2001:db8::1")
	eq(banlease.lease_key("::ffff:192.0.2.1"), "bans_cs_ip_192.0.2.1")
	local epoch = banlease.bump_lease_epoch("2001:db8::1")
	assert(epoch)
	eq(banlease.lease_epoch("2001:0DB8:0:0:0:0:0:1", false), epoch, "epoch read through another spelling")
	local marker_epoch = banlease.bump_marker_epoch("::ffff:192.0.2.1")
	eq(banlease.marker_epoch("192.0.2.1", false), marker_epoch, "marker epoch of a mapped address")
	banlease.write_marker("svc", "2001:0DB8::1", "id", 2, marker_epoch, 10)
	assert(banlease.read_marker("svc", "2001:db8::1"), "marker read through another spelling")
end)

os.exit(failures == 0 and 0 or 1)
