-- Plain Lua 5.4: clusterstore:call retries a TRYAGAIN answer (multi-key command on a migrating Redis Cluster slot)
-- a few times with short sleeps, and leaves every other error and every other mode alone.
-- Run: lua tests/unit/test_lua_cluster_tryagain_retry.lua   (from the repo root)
local repo = (arg[0]:match("^(.*)/[^/]+$") or ".") .. "/../.."
package.path = repo .. "/src/bw/lua/?.lua;" .. package.path

local variables = {
	USE_REDIS = "yes",
	REDIS_HOST = "redis",
	REDIS_PORT = "6379",
	REDIS_DATABASE = "0",
	REDIS_TIMEOUT = "1000",
	REDIS_KEEPALIVE_IDLE = "1000",
	REDIS_KEEPALIVE_POOL = "10",
	REDIS_SENTINEL_HOSTS = "",
	REDIS_CLUSTER_NODES = "redis-1:6379",
}
local sleeps, cosocket = {}, true
_G.ngx = {
	ERR = 1,
	WARN = 2,
	INFO = 3,
	config = { subsystem = "http" },
	shared = {},
	sleep = function(seconds)
		sleeps[#sleeps + 1] = seconds
	end,
}
package.loaded["bunkerweb.utils"] = {
	get_variable = function(k)
		return variables[k] or ""
	end,
	parse_duration = function(v)
		return tonumber(v)
	end,
	is_cosocket_available = function()
		return cosocket
	end,
	is_connection_error = function(err)
		return err == "closed"
	end,
}
package.loaded["bunkerweb.logger"] = {
	new = function()
		return { log = function() end }
	end,
}
package.loaded["resty.redis.connector"] = {
	new = function()
		return {}
	end,
}
package.loaded["resty.redis"] = {}
local clusterstore = require "bunkerweb.clusterstore"

local TRYAGAIN = "TRYAGAIN Multiple keys request during rehashing of slot"
local failures = 0
local function it(name, fn)
	sleeps, cosocket = {}, true
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or ": " .. tostring(err)))
	if not ok then
		failures = failures + 1
	end
end

-- A client whose eval answers the given replies in turn, then repeats the last one
local function store_with(replies, cluster)
	variables.REDIS_CLUSTER_NODES = cluster == false and "" or "redis-1:6379"
	local store = clusterstore:new()
	store.calls = 0
	store.redis_client = {
		eval = function()
			store.calls = store.calls + 1
			local reply = replies[math.min(store.calls, #replies)]
			return reply[1], reply[2]
		end,
	}
	return store
end

it("TRYAGAIN is retried and the first good answer is returned", function()
	local store = store_with({ { nil, TRYAGAIN }, { nil, TRYAGAIN }, { 7 } })
	local res, err = store:call("eval", "script", 2, "a", "b")
	assert(res == 7 and err == nil, tostring(res) .. " " .. tostring(err))
	assert(store.calls == 3 and #sleeps == 2)
	assert(sleeps[1] == 0.02 and sleeps[2] == 0.05)
end)

it("the retries are bounded and the TRYAGAIN error comes back", function()
	local store = store_with({ { nil, TRYAGAIN } })
	local res, err = store:call("eval", "script", 2, "a", "b")
	assert(res == nil and err == TRYAGAIN)
	assert(store.calls == 4 and #sleeps == 3, "one call and three retries")
end)

it("tryagain_retries = 0 turns the retry off", function()
	local store = store_with({ { nil, TRYAGAIN } })
	store.tryagain_retries = 0
	local res, err = store:call("eval", "script", 2, "a", "b")
	assert(res == nil and err == TRYAGAIN and store.calls == 1 and #sleeps == 0)
end)

it("tryagain_retries above the delay table still stops at three", function()
	local store = store_with({ { nil, TRYAGAIN } })
	store.tryagain_retries = 10
	store:call("eval", "script", 2, "a", "b")
	assert(store.calls == 4 and #sleeps == 3)
end)

it("any other error is returned at once", function()
	local store = store_with({ { nil, "CROSSSLOT Keys in request don't hash to the same slot" } })
	local res, err = store:call("eval", "script", 2, "a", "b")
	assert(res == nil and err:find("^CROSSSLOT") and store.calls == 1 and #sleeps == 0)
end)

it("a phase that cannot yield does not retry", function()
	local store = store_with({ { nil, TRYAGAIN } })
	cosocket = false
	local res, err = store:call("eval", "script", 2, "a", "b")
	assert(res == nil and err == TRYAGAIN and store.calls == 1 and #sleeps == 0)
end)

it("a good answer on the first call sleeps never", function()
	local store = store_with({ { "OK" } })
	assert(store:call("eval", "script", 1, "a") == "OK")
	assert(store.calls == 1 and #sleeps == 0)
end)

it("outside cluster mode TRYAGAIN is not retried", function()
	local store = store_with({ { nil, TRYAGAIN } }, false)
	store.redis_client.eval = function()
		store.calls = store.calls + 1
		return nil, TRYAGAIN
	end
	local res, err = store:call("eval", "script", 1, "a")
	assert(res == nil and err == TRYAGAIN and store.calls == 1 and #sleeps == 0)
end)

os.exit(failures == 0 and 0 or 1)
