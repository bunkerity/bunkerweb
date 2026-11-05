-- Plain Lua 5.4: real Sentinel discovery, failover and replica connection paths.
local repo = (arg[0]:match("^(.*)/[^/]+$") or ".") .. "/../.."
package.path = repo .. "/src/deps/src/lua-resty-redis-connector/lib/?.lua;" .. package.path
_G.ngx = { log = function() end, ERR = 1, re = { match = function() end }, null = {} }
local master, reused = "2001:db8::1", 0
local connects, auths, selects = {}, {}, {}
package.loaded["resty.redis"] = {
	add_commands = function() end,
	new = function()
		local c = {}
		function c.set_timeouts() end
		function c:connect(host, port, options)
			connects[#connects + 1] = { host, port, options }
			if host:find(":", 1, true) and host:sub(1, 1) ~= "[" and host ~= "/tmp/redis.sock" then
				return nil, "bare IPv6 rejected by cosocket"
			end
			self.host = host
			return true
		end
		function c:auth(user, password)
			auths[#auths + 1] = { self.host, user, password }
			return true
		end
		function c:select(db)
			selects[#selects + 1] = { self.host, db }
			return true
		end
		function c.get_reused_times()
			return reused
		end
		function c.set_keepalive()
			return true
		end
		function c.sentinel(_, command)
			if command == "get-master-addr-by-name" then
				return { master, "6380" }
			end
			return { { "ip", "2001:db8::3", "port", "6381", "master-link-status", "ok", "flags", "slave" } }
		end
		return c
	end,
}
local connector = require "resty.redis.connector"
local failures = 0
local function it(name, fn)
	connects, auths, selects, reused = {}, {}, {}, 0
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or ": " .. tostring(err)))
	if not ok then
		failures = failures + 1
	end
end
local options = {
	sentinels = { { host = "[2001:db8::10]", port = 26379 } },
	master_name = "master",
	username = "user",
	password = "pass",
	sentinel_username = "sent-user",
	sentinel_password = "sent-pass",
	db = 2,
	connection_options = { ssl = true, ssl_verify = true },
}
it("discovered IPv6 master keeps TLS and separate credentials", function()
	master = "2001:db8::1"
	local red = assert(connector.new(options)):connect()
	assert(red and red.host == "[2001:db8::1]")
	assert(connects[2][2] == "6380" and connects[2][3].ssl and connects[2][3].ssl_verify)
	assert(auths[1][2] == "sent-user" and auths[1][3] == "sent-pass")
	assert(auths[2][2] == "user" and auths[2][3] == "pass")
	assert(selects[1][2] == 2)
end)
it("Sentinel failover connects to the new IPv6 master", function()
	local rc = assert(connector.new(options))
	master = "2001:db8::1"
	assert(rc:connect())
	master = "2001:db8::2"
	local red = assert(rc:connect())
	assert(red.host == "[2001:db8::2]")
end)
it("discovered IPv6 replica", function()
	local red = assert(assert(connector.new(options)):connect({ role = "slave" }))
	assert(red.host == "[2001:db8::3]")
end)
it("already bracketed hosts stay bracketed once", function()
	local red = assert(assert(connector.new({ host = "[2001:db8::1]" })):connect())
	assert(red.host == "[2001:db8::1]")
end)
it("pooled sockets still skip AUTH and SELECT", function()
	reused = 1
	assert(assert(connector.new(options)):connect())
	assert(#auths == 0 and #selects == 0)
end)
it("Unix socket path stays unchanged", function()
	assert(assert(connector.new({ path = "/tmp/redis.sock" })):connect())
	assert(connects[1][1] == "/tmp/redis.sock")
end)
os.exit(failures == 0 and 0 or 1)
