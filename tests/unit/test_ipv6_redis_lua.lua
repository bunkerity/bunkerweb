-- Plain Lua 5.4: real clusterstore and sessions endpoint configuration.
local repo = (arg[0]:match("^(.*)/[^/]+$") or ".") .. "/../.."
package.path = repo .. "/src/bw/lua/?.lua;" .. package.path
local variables = {
	USE_REDIS = "yes",
	REDIS_HOST = "2001:db8::1",
	REDIS_PORT = "6379",
	REDIS_DATABASE = "0",
	REDIS_TIMEOUT = "1000",
	REDIS_KEEPALIVE_IDLE = "1000",
	REDIS_KEEPALIVE_POOL = "10",
	REDIS_SENTINEL_HOSTS = "",
	REDIS_CLUSTER_NODES = "",
	REDIS_SSL = "yes",
	REDIS_SSL_VERIFY = "yes",
	REDIS_USERNAME = "user",
	REDIS_PASSWORD = "pass",
	REDIS_SENTINEL_USERNAME = "sent-user",
	REDIS_SENTINEL_PASSWORD = "sent-pass",
}
_G.ngx = { ERR = 1, WARN = 2, INFO = 3, config = { subsystem = "http" }, shared = {} }
package.loaded["bunkerweb.utils"] = {
	get_variable = function(k)
		return variables[k] or ""
	end,
	parse_duration = function(v)
		return tonumber(v)
	end,
	is_cosocket_available = function()
		return false
	end,
}
package.loaded["bunkerweb.logger"] = {
	new = function()
		return { log = function() end }
	end,
}
package.loaded["resty.redis.connector"] = {}
package.loaded["resty.redis"] = {}
local plugin = require("middleclass")("plugin")
plugin.initialize = function() end
package.loaded["bunkerweb.plugin"] = plugin
package.loaded.cjson = {
	encode = function()
		return "{}"
	end,
}
local config
package.loaded["resty.session"] = {
	init = function(c)
		config = c
	end,
}
local clusterstore = require "bunkerweb.clusterstore"
local sessions = dofile(repo .. "/src/common/core/sessions/sessions.lua")
local session = setmetatable({
	kind = "http",
	variables = { SESSIONS_SECRET = "secret", SESSIONS_NAME = "session" },
	internalstore = {
		set = function()
			return true
		end,
	},
	logger = { log = function() end },
	ret = function(_, ok, msg)
		return ok, msg
	end,
}, { __index = sessions })
local failures = 0
local function it(name, fn)
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or ": " .. tostring(err)))
	if not ok then
		failures = failures + 1
	end
end
for _, host in ipairs({ "2001:db8::1", "[2001:db8::1]", "redis", "192.0.2.1" }) do
	it("standalone store and sessions " .. host, function()
		variables.REDIS_HOST, variables.REDIS_SENTINEL_HOSTS = host, ""
		local store = clusterstore:new()
		assert(session:init())
		local expected = host:find(":", 1, true) and "[2001:db8::1]" or host
		assert(store.options.host == expected, tostring(store.options.host))
		assert(config.redis.host == expected, tostring(config.redis.host))
		assert(store.options.password == "pass" and config.redis.password == "pass")
		assert(store.options.connection_options.ssl_verify and config.redis.ssl_verify)
	end)
end
for _, host in ipairs({ "[2001:db8::1]:26380", "[2001:db8::1]", "2001:db8::1" }) do
	it("Sentinel store and sessions " .. host, function()
		variables.REDIS_SENTINEL_HOSTS = host .. " redis:26381"
		local store = clusterstore:new()
		assert(session:init())
		for _, nodes in ipairs({ store.options.sentinels, config.redis.sentinels }) do
			assert(nodes[1].host == "[2001:db8::1]", tostring(nodes[1].host))
			assert(nodes[1].port == (host:find("26380", 1, true) and 26380 or 26379))
			assert(nodes[2].host == "redis" and nodes[2].port == 26381)
		end
		assert(store.options.sentinels[1].username == "sent-user")
	end)
end
it("Cluster primary commands bracket discovered IPv6", function()
	variables.REDIS_SENTINEL_HOSTS, variables.REDIS_CLUSTER_NODES = "", "[2001:db8::1]"
	local store = clusterstore:new()
	store.redis_client = {
		masters = function()
			return { { ip = "2001:db8::1", port = 6379 } }
		end,
	}
	package.loaded["resty.redis"].new = function()
		return {
			set_timeouts = function() end,
			connect = function(_, host)
				assert(host == "[2001:db8::1]", host)
				return true
			end,
			auth = function()
				return true
			end,
			dbsize = function()
				return 3
			end,
			close = function()
				return true
			end,
		}
	end
	assert(store:call("dbsize") == 3)
end)
os.exit(failures == 0 and 0 or 1)
