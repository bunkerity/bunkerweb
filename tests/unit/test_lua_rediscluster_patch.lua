-- Plain Lua 5.4 test for the BW patch on resty.rediscluster.
local script_dir = arg[0]:match("^(.*)/[^/]+$") or "."
local repo = script_dir .. "/../.."
package.path = repo .. "/src/deps/src/resty-redis-cluster/lib/?.lua;" .. package.path

-- LuaJIT bitop for xmodem (it does require("bit"))
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
-- Records the pool name resty.redis:connect() was called with, so the pool-stability test can
-- see what set_poolname() wrote without a real Redis Cluster. Connect always fails: none of the
-- tests need fetch_slots to succeed, only to reach set_poolname before it does.
local connect_pool_names = {}
package.loaded["resty.redis"] = {
	new = function()
		return {
			set_timeouts = function() end,
			connect = function(_, _, _, opts)
				connect_pool_names[#connect_pool_names + 1] = opts.pool
				return nil, "stub refuses connection"
			end,
			close = function()
				return true
			end,
		}
	end,
}
local lock_keys = {}
package.loaded["resty.lock"] = {
	new = function()
		return {
			lock = function(_, key)
				lock_keys[#lock_keys + 1] = key
				return 0
			end,
			unlock = function()
				return true
			end,
		}
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
_G.ngx = {
	re = {
		match = function()
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
		return 0
	end,
	config = { subsystem = "http" },
	shared = {},
}

local rc = require "resty.rediscluster"
local xmodem = require "resty.xmodem"

local failures = 0
local function it(name, fn)
	local ok, err = pcall(fn)
	if ok then
		print("PASS " .. name)
	else
		failures = failures + 1
		print("FAIL " .. name .. ": " .. tostring(err))
	end
end
local function slot(k)
	return xmodem.redis_crc(rc.parse_key(k))
end

it("zero keys routes to no_key", function()
	assert(rc.eval_route_key(0, "arg1") == "no_key")
end)
it("one key unchanged", function()
	assert(rc.eval_route_key(1, "bans_ip_1.2.3.4", "arg") == "bans_ip_1.2.3.4")
end)
it("same-slot multi-key accepted, routes by first key", function()
	local k1, k2 = "bans_service_app_ip_{1.2.3.4}", "bans_ip_{1.2.3.4}"
	assert(slot(k1) == slot(k2))
	assert(rc.eval_route_key(2, k1, k2, "argv") == k1)
end)
it("cross-slot rejected before sending", function()
	local k1, k2 = "bans_service_app_ip_1.2.3.4", "bans_ip_1.2.3.4"
	assert(slot(k1) ~= slot(k2))
	local key, err = rc.eval_route_key(2, k1, k2)
	assert(key == nil and err:find("CROSSSLOT", 1, true), tostring(err))
end)
it("fewer keys than keys_num rejected", function()
	local key, err = rc.eval_route_key(3, "{a}1", "{a}2")
	assert(key == nil and err, "expected an error")
end)
it("non-integer keys_num rejected", function()
	assert(rc.eval_route_key("2", "a", "b") == nil)
	assert(rc.eval_route_key(1.5, "a") == nil)
	assert(rc.eval_route_key(-1) == nil)
end)
it("masters() without cache returns error", function()
	local list, err = rc.masters({ config = { name = "none" } })
	assert(list == nil and err)
end)
it("base pool name is stable across repeated new() on one options table", function()
	connect_pool_names = {}
	-- lua-resty-session builds its storage once and calls redis:new(self.options) on every
	-- session operation: same options table, many new() calls. Without the BW patch,
	-- set_base_pool_name() reads the previous call's connect_opts.pool back as the base and
	-- prefixes it again, so the pool name grows by one "ip:port:" per call.
	local opts = {
		name = "bw_pool_stability_test",
		serv_list = { { ip = "10.0.0.1", port = 7000 } },
		max_connection_attempts = 1,
	}
	rc:new(opts)
	assert(#connect_pool_names >= 1, "connect stub was never reached")
	local first = connect_pool_names[1]
	rc:new(opts)
	local second = connect_pool_names[#connect_pool_names]
	assert(second == first, ("pool name grew across new(): %q then %q"):format(first, second))
end)
it("slot cache init lock is per worker", function()
	-- slot_cache lives in each worker, so a lock key shared across workers only makes
	-- every worker wait for the others after a reload.
	lock_keys = {}
	rc:new({
		name = "bw_lock_key_test",
		serv_list = { { ip = "10.0.0.1", port = 7000 } },
		max_connection_attempts = 1,
	})
	assert(#lock_keys >= 1, "init_slots never took the lock")
	assert(lock_keys[1] == "redis_cluster_slot_bw_lock_key_test4242", "lock key: " .. tostring(lock_keys[1]))
end)

os.exit(failures == 0 and 0 or 1)
