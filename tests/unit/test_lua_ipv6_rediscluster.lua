-- Plain Lua 5.4: real Cluster discovery and redirect paths, socket boundary stubbed.
local repo = (arg[0]:match("^(.*)/[^/]+$") or ".") .. "/../.."
package.path = repo .. "/src/deps/src/resty-redis-cluster/lib/?.lua;" .. package.path
_G.unpack = table.unpack -- luacheck: ignore 143
package.loaded.bit = {
	band = function(a, b)
		return a & b
	end,
	bxor = function(a, b)
		return a ~ b
	end,
	lshift = function(a, b)
		return a << b
	end,
	rshift = function(a, b)
		return a >> b
	end,
}
package.loaded["table.new"] = function()
	return {}
end
package.loaded["resty.openssl.digest"] = {
	new = function()
		return nil, "stub"
	end,
}
package.loaded["resty.string"] = {
	to_hex = function(s)
		return s
	end,
}
package.loaded["resty.lock"] = {
	new = function()
		return {
			lock = function()
				return 0
			end,
			unlock = function()
				return true
			end,
		}
	end,
}

local mode, redirected, advertised, seed, cluster_version
local connects, commands, nested_moved
local SOURCE, TARGET = "2001:db8::1", "2001:db8::2"
package.loaded["resty.redis"] = {
	new = function()
		local c = {}
		function c.set_timeouts() end
		function c:connect(host, port)
			connects[#connects + 1] = { host, port }
			if host:find(":", 1, true) and host:sub(1, 1) ~= "[" then
				return nil, "bare IPv6 rejected by cosocket"
			end
			self.host = host
			return true
		end
		function c.cluster(_, sub)
			if sub == "info" then
				return "cluster_state:ok\r\n"
			end
			if sub == "nodes" then
				return "id " .. advertised .. " master - 0 0 1 connected 0-16383"
			end
			local host = mode == "MOVED" and redirected and TARGET or SOURCE
			if mode and not redirected then
				host = "[" .. host .. "]"
			end
			if cluster_version == 7 then
				return { { 0, 16383, { "redis-node", 6379, "id", { "ip", host } } } }
			end
			return { { 0, 16383, { host, 6379, "id" } } }
		end
		function c.info()
			return "redis_version:" .. cluster_version .. ".2.0\r\n"
		end
		function c:asking()
			self.asked = true
			return true
		end
		function c:get()
			if self.pipeline_count then
				self.pipeline_count = self.pipeline_count + 1
				return
			end
			commands[#commands + 1] = { self.host, self.asked }
			if mode == "ASK" and self.host == "[" .. TARGET .. "]" then
				assert(self.asked, "redirect target must receive ASKING before GET")
				return "value"
			end
			if mode == "ASK" then
				return false, "ASK 1 " .. seed
			end
			if mode == "MOVED" and not redirected then
				redirected = true
				return false, "MOVED 1 " .. SOURCE .. ":6379"
			end
			return "value"
		end
		function c:init_pipeline()
			self.pipeline_count = 0
		end
		function c:commit_pipeline()
			local count = self.pipeline_count
			self.pipeline_count = nil
			local replies = {}
			for i = 1, count do
				local value, err = self:get()
				replies[i] = err and { false, err } or value
			end
			return replies
		end
		function c.close()
			return true
		end
		function c.set_keepalive()
			return true
		end
		function c.get_reused_times()
			return 0
		end
		return c
	end,
}
_G.ngx = {
	re = {
		match = function(s, pat)
			if pat:find("cluster_state", 1, true) then
				return { "ok" }
			end
			if pat:find("redis_version", 1, true) then
				return { tostring(cluster_version) .. ".2" }
			end
			-- Match the old PCRE faithfully: it splits an IPv6 target at its first colon.
			if pat:find("ASK", 1, true) then
				local h, p = s:match("^ASK [^ ]+ ([^:]+):([^ ]+)")
				return h and { h, p } or nil
			end
		end,
	},
	log = function(_, msg)
		if msg == "nested moved redirection detected, refreshing slots ..." then
			nested_moved = true
		end
	end,
	ERR = 1,
	WARN = 2,
	NOTICE = 3,
	INFO = 4,
	DEBUG = 5,
	worker = {
		id = function()
			return 0
		end,
		pid = function()
			return 4242
		end,
	},
	now = function()
		return 0
	end,
	config = { subsystem = "http" },
	shared = {},
}
local rc = require "resty.rediscluster"
local function upvalue(fn, name)
	for i = 1, math.huge do
		local key, value = debug.getupvalue(fn, i)
		if not key then
			break
		end
		if key == name then
			return value
		end
	end
	error("missing upvalue " .. name)
end
local parse_masters = upvalue(upvalue(rc.fetch_slots, "try_hosts_slots"), "parse_masters")
local failures, serial = 0, 0
local function it(name, fn)
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or ": " .. tostring(err)))
	if not ok then
		failures = failures + 1
	end
end
local function client(action, addr, version)
	mode, redirected, advertised, cluster_version =
		action, false, addr or SOURCE .. ":6379@16379,redis-node", version or 6
	connects, commands, nested_moved = {}, {}, false
	serial = serial + 1
	return assert(rc:new({
		name = "ipv6_" .. serial,
		serv_list = { { ip = "seed", port = 6379 } },
		max_redirection = 2,
		max_connection_attempts = 1,
	}))
end
local node_addresses = {
	SOURCE .. ":6379@16379,redis-node",
	"[" .. SOURCE .. "]:6379@16379",
	"192.0.2.1:6380@16380",
	":0@0",
}
for _, addr in ipairs(node_addresses) do
	it("CLUSTER NODES parses " .. addr, function()
		advertised = addr
		local red = { config = { name = "nodes_test" } }
		assert(parse_masters(red, package.loaded["resty.redis"].new()))
		local master = assert(rc.masters(red))[1]
		local expected = addr == ":0@0" and "" or (addr:sub(1, 3) == "192" and "192.0.2.1" or SOURCE)
		local port = addr == ":0@0" and 0 or (expected == SOURCE and 6379 or 6380)
		assert(master.ip == expected and master.port == port, tostring(master.ip) .. ":" .. tostring(master.port))
	end)
end
for _, version in ipairs({ 6, 7 }) do
	it("CLUSTER SLOTS IPv6 sockets, Redis " .. version, function()
		local red = client(nil, nil, version)
		assert(red:get("key") == "value")
		assert(connects[#connects][1] == "[" .. SOURCE .. "]", connects[#connects][1])
	end)
end
for _, target in ipairs({ TARGET .. ":6380", "[" .. TARGET .. "]:6380" }) do
	it("ASK follows " .. target, function()
		local red = client("ASK")
		seed = target
		local value, err = red:get("key")
		assert(value == "value", tostring(err))
		assert(connects[#connects][1] == "[" .. TARGET .. "]" and tonumber(connects[#connects][2]) == 6380)
	end)
end
it("MOVED refreshes and recognizes an IPv6 target", function()
	local red = client("MOVED")
	local value, err = red:get("key")
	assert(value == "value", tostring(err))
	assert(commands[#commands][1] == "[" .. TARGET .. "]")
	assert(nested_moved, "IPv6 MOVED target was not recognized")
end)
it("pipeline ASK follows an IPv6 target", function()
	local red = client("ASK")
	seed = TARGET .. ":6380"
	red:init_pipeline()
	red:get("key")
	local replies, err = red:commit_pipeline()
	assert(replies and replies[1] == "value", tostring(err))
end)
os.exit(failures == 0 and 0 or 1)
