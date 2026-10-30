-- Plain Lua 5.4 test: a command whose slot owner is down must pay one connect timeout, not
-- one per retry and per announced address.
local script_dir = arg[0]:match("^(.*)/[^/]+$") or "."
local repo = script_dir .. "/../.."
package.path = repo .. "/src/deps/src/resty-redis-cluster/lib/?.lua;" .. package.path

package.loaded["bit"] = {
	band = function(a, b)
		return a & b
	end,
	bxor = function(a, b)
		return a ~ b
	end,
	lshift = function(a, n)
		return a << n
	end,
	rshift = function(a, n)
		return a >> n
	end,
}

-- One live seed answers the cluster commands; every slot belongs to a dead primary announced
-- as both an IP and a hostname (Redis 7 CLUSTER SLOTS form).
local DEAD_IP, DEAD_HOST = "10.0.0.9", "rc-node-1"
local LIVE_IP, LIVE_HOST = "10.0.0.8", "rc-node-2"
local dead_connects = 0
-- Set once the dead primary was tried: CLUSTER SLOTS then reports the promoted replica.
local promote_on_failure = false
local promoted = false
local function new_client()
	local c = {}
	function c.set_timeouts() end
	function c.connect(_, ip)
		if ip == DEAD_IP or ip == DEAD_HOST then
			dead_connects = dead_connects + 1
			promoted = promote_on_failure
			return nil, "timeout"
		end
		return true
	end
	function c.cluster(_, sub)
		if sub == "info" then
			return "cluster_state:ok\r\n"
		elseif sub == "nodes" then
			return "id1 " .. DEAD_IP .. ":6379@16379 master - 0 0 1 connected 0-16383"
		end
		if promoted then
			return { { 0, 16383, { LIVE_HOST, 6379, "id2", { "ip", LIVE_IP } } } }
		end
		return { { 0, 16383, { DEAD_HOST, 6379, "id1", { "ip", DEAD_IP } } } }
	end
	function c.get()
		return "v"
	end
	function c.info()
		return "redis_version:7.2.4\r\n"
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
end
package.loaded["resty.redis"] = { new = new_client }
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
local now_ts = 0
_G.ngx = {
	re = {
		match = function(s, pat)
			if pat:find("cluster_state", 1, true) then
				local m = s:match("cluster_state:(%a+)")
				return m and { m } or nil
			elseif pat:find("redis_version", 1, true) then
				local m = s:match("redis_version:(%d+%.%d+)")
				return m and { m } or nil
			end
			return nil
		end,
	},
	log = function() end,
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
		return now_ts
	end,
	config = { subsystem = "http" },
	shared = {},
}
-- Shared dict stub with TTLs on the test clock.
local store = {}
ngx.shared.redis_cluster_slot_locks = {
	get = function(_, k)
		local e = store[k]
		return e and e.exp > now_ts and e.v or nil
	end,
	set = function(_, k, v, ttl)
		store[k] = { v = v, exp = now_ts + ttl }
		return true
	end,
}

local rc = require "resty.rediscluster"

local red, err = rc:new({
	name = "bw_retry_test",
	serv_list = { { ip = "seed", port = 6379 } },
	max_redirection = 2,
	max_connection_attempts = 1,
})
assert(red, "new() failed: " .. tostring(err))

dead_connects = 0
local res, cmd_err = red:get("bans_ip_{1.2.3.4}")
assert(res == nil and cmd_err, "command against a dead primary must fail")
if dead_connects ~= 1 then
	print(("FAIL dead primary costs one connect per command: got %d connects (%s)"):format(dead_connects, cmd_err))
	os.exit(1)
end
print("PASS dead primary costs one connect per command")

-- Inside the down window the next command fails fast, without another connect timeout.
dead_connects = 0
local res_again, err_again = red:get("bans_ip_{1.2.3.4}")
if res_again ~= nil or dead_connects ~= 0 then
	print(("FAIL marked-down node is skipped: got %d connects (%s)"):format(dead_connects, tostring(err_again)))
	os.exit(1)
end
print("PASS marked-down node is skipped")

-- The window has passed: the node gets tried again.
now_ts = 10

-- Failover finished between the cached map and the refresh: the retry must reach the new owner.
promote_on_failure = true
local red2 = assert(rc:new({
	name = "bw_retry_failover_test",
	serv_list = { { ip = "seed", port = 6379 } },
	max_redirection = 2,
	max_connection_attempts = 1,
}))
dead_connects = 0
local res2, err2 = red2:get("bans_ip_{1.2.3.4}")
if res2 ~= "v" or dead_connects ~= 1 then
	print(
		("FAIL retry reaches the promoted node: res=%s err=%s connects=%d"):format(
			tostring(res2),
			tostring(err2),
			dead_connects
		)
	)
	os.exit(1)
end
print("PASS retry reaches the promoted node")
