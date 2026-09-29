local ngx = ngx
local class = require "middleclass"
local clogger = require "bunkerweb.logger"
local rc = require "resty.redis.connector"
local rediskeys = require "bunkerweb.rediskeys"
local resty_redis = require "resty.redis"
local utils = require "bunkerweb.utils"

local clusterstore = class("clusterstore")

local logger = clogger:new("CLUSTERSTORE")

local get_variable = utils.get_variable
local parse_duration = utils.parse_duration
local is_cosocket_available = utils.is_cosocket_available
local is_connection_error = utils.is_connection_error
local ERR = ngx.ERR
local WARN = ngx.WARN
local INFO = ngx.INFO
local tonumber = tonumber
local tostring = tostring
local subsystem = ngx.config.subsystem
-- Loaded on first cluster use only, so a missing library never breaks standalone or Sentinel.
local rediscluster

-- Helper function to get timer log level with validation
local function get_timer_log_level()
	local level_name = utils.get_variable("TIMERS_LOG_LEVEL", false):upper()
	if ngx[level_name] then
		return ngx[level_name]
	else
		return INFO -- Default to INFO if invalid
	end
end

function clusterstore:initialize(pool)
	-- Get variables
	local variables = {
		["USE_REDIS"] = "",
		["REDIS_HOST"] = "",
		["REDIS_PORT"] = "",
		["REDIS_DATABASE"] = "",
		["REDIS_SSL"] = "",
		["REDIS_SSL_VERIFY"] = "",
		["REDIS_TIMEOUT"] = "",
		["REDIS_KEEPALIVE_IDLE"] = "",
		["REDIS_KEEPALIVE_POOL"] = "",
		["REDIS_USERNAME"] = "",
		["REDIS_PASSWORD"] = "",
		["REDIS_SENTINEL_HOSTS"] = "",
		["REDIS_SENTINEL_USERNAME"] = "",
		["REDIS_SENTINEL_PASSWORD"] = "",
		["REDIS_SENTINEL_MASTER"] = "",
		["REDIS_CLUSTER_NODES"] = "",
	}
	-- Set them for later use
	self.variables = {}
	for k, _ in pairs(variables) do
		local value, err = get_variable(k, false)
		if value == nil then
			logger:log(ERR, err)
		end
		self.variables[k] = value
	end
	-- Don't go further if redis is not used
	if self.variables["USE_REDIS"] ~= "yes" then
		return
	end
	self.config_error = rediskeys.cluster_config_error(
		self.variables["REDIS_CLUSTER_NODES"],
		self.variables["REDIS_SENTINEL_HOSTS"],
		self.variables["REDIS_DATABASE"]
	)
	if self.config_error then
		-- connect() reports it, so every caller takes its usual Redis-down fallback.
		return
	end
	if rediskeys.nodes_value(self.variables["REDIS_CLUSTER_NODES"]) then
		local timeout = parse_duration(self.variables["REDIS_TIMEOUT"], "ms")
		self.pool = pool == nil or pool
		self.cluster_mode = true
		self.options = {
			name = "bw",
			serv_list = rediskeys.parse_nodes(self.variables["REDIS_CLUSTER_NODES"]),
			dict_name = subsystem == "stream" and "redis_cluster_locks_stream" or "redis_cluster_locks",
			refresh_lock_key = "bw_refresh_",
			lock_timeout = timeout / 1000,
			connect_timeout = timeout,
			send_timeout = timeout,
			read_timeout = timeout,
			keepalive_timeout = parse_duration(self.variables["REDIS_KEEPALIVE_IDLE"], "ms"),
			keepalive_cons = tonumber(self.variables["REDIS_KEEPALIVE_POOL"]),
			max_redirection = 2,
			max_connection_attempts = 1,
			max_connection_timeout = timeout,
			enable_slave_read = false,
			-- The client sends AUTH for any string, an empty one included.
			username = self.variables["REDIS_USERNAME"] ~= "" and self.variables["REDIS_USERNAME"] or nil,
			password = self.variables["REDIS_PASSWORD"] ~= "" and self.variables["REDIS_PASSWORD"] or nil,
			connect_opts = {
				ssl = self.variables["REDIS_SSL"] == "yes",
				ssl_verify = self.variables["REDIS_SSL_VERIFY"] == "yes",
				pool_size = tonumber(self.variables["REDIS_KEEPALIVE_POOL"]),
			},
		}
		return
	end
	-- Compute options
	local options = {
		connect_timeout = parse_duration(self.variables["REDIS_TIMEOUT"], "ms"),
		read_timeout = parse_duration(self.variables["REDIS_TIMEOUT"], "ms"),
		send_timeout = parse_duration(self.variables["REDIS_TIMEOUT"], "ms"),
		keepalive_timeout = parse_duration(self.variables["REDIS_KEEPALIVE_IDLE"], "ms"),
		keepalive_poolsize = tonumber(self.variables["REDIS_KEEPALIVE_POOL"]),
		connection_options = {
			ssl = self.variables["REDIS_SSL"] == "yes",
			ssl_verify = self.variables["REDIS_SSL_VERIFY"] == "yes",
		},
		host = self.variables["REDIS_HOST"],
		port = tonumber(self.variables["REDIS_PORT"]),
		db = tonumber(self.variables["REDIS_DATABASE"]),
		username = self.variables["REDIS_USERNAME"],
		password = self.variables["REDIS_PASSWORD"],
		sentinel_username = self.variables["REDIS_SENTINEL_USERNAME"],
		sentinel_password = self.variables["REDIS_SENTINEL_PASSWORD"],
		master_name = self.variables["REDIS_SENTINEL_MASTER"],
		role = "master",
		sentinels = {},
	}
	self.pool = pool == nil or pool
	if self.pool then
		options.connection_options.pool_size = tonumber(self.variables["REDIS_KEEPALIVE_POOL"])
	end
	if self.variables["REDIS_SENTINEL_HOSTS"] ~= "" then
		for sentinel_host in self.variables["REDIS_SENTINEL_HOSTS"]:gmatch("%S+") do
			local shost, sport = sentinel_host:match("([^:]+):?(%d*)")
			if sport == "" then
				sport = 26379
			else
				sport = tonumber(sport)
			end
			local data = { host = shost, port = sport }
			if options.sentinel_username ~= "" then
				data.username = options.sentinel_username
			end
			if options.sentinel_password ~= "" then
				data.password = options.sentinel_password
			end
			table.insert(options.sentinels, data)
		end
	end
	self.options = options
	-- Instantiate object
	if is_cosocket_available() then
		local redis_connector, err = rc.new(self.options)
		self.redis_connector = redis_connector
		if self.redis_connector == nil then
			logger:log(ERR, "can't instantiate redis object : " .. err)
			return
		end
	end
end

function clusterstore:connect(readonly)
	if self.config_error then
		return false, "invalid redis configuration : " .. self.config_error
	end
	if self.cluster_mode then
		-- Reads go to primaries in cluster mode, readonly is ignored.
		if not is_cosocket_available() then
			return false, "cosocket is not available"
		end
		rediscluster = rediscluster or require "resty.rediscluster"
		local client, err = rediscluster:new(self.options)
		self.redis_client = client
		self.healthy = client ~= nil
		if not client then
			return false, "error while getting redis cluster client : " .. tostring(err)
		end
		return true, "success", 1
	end
	-- Check if connector is created
	if not self.redis_connector then
		return false, "connector is not instantiated"
	end
	-- Disconnect if needed
	if self.redis_client then
		self:close()
	end
	-- Connect to sentinels if needed
	local redis_client, err, previous_errors
	if #self.options.sentinels > 0 and readonly then
		redis_client, err, previous_errors = self.redis_connector:connect({ role = "slave" })
		if not redis_client then
			if previous_errors then
				err = err .. " ( previous errors : "
				for _, e in ipairs(previous_errors) do
					err = err .. e .. ", "
				end
				err = err:sub(1, -3) .. " )"
			end
			logger:log(WARN, "error while getting redis slave client : " .. err .. ", fallback to master")
			redis_client, err, previous_errors = self.redis_connector:connect()
		end
	else
		redis_client, err, previous_errors = self.redis_connector:connect()
	end
	self.redis_client = redis_client
	self.healthy = redis_client ~= nil
	if not self.redis_client then
		if previous_errors then
			err = err .. " ( previous errors : "
			for _, e in ipairs(previous_errors) do
				err = err .. e .. ", "
			end
			err = err:sub(1, -3) .. " )"
		end
		return false, "error while getting redis client : " .. err
	end
	-- Everything went well
	local times
	times, err = self.redis_client:get_reused_times()
	if times == nil then
		self.healthy = false
		self:close()
		return false, "error while getting reused times : " .. err
	end
	local timers_log_level = get_timer_log_level()
	logger:log(timers_log_level, "redis reused times = " .. tostring(times))
	return true, "success", times
end

function clusterstore:close()
	if self.cluster_mode then
		-- The cluster client returns every socket to its pool after each command.
		self.redis_client = nil
		return true
	end
	-- Check if connected is created
	if not self.redis_connector then
		return false, "connector is not instantiated"
	end
	-- Check if client is created
	if not self.redis_client then
		return false, "client is not instantiated"
	end
	-- Only return healthy connections to the keepalive pool.
	-- Unhealthy connections (or non-pooled) are closed directly to avoid
	-- the unnecessary DISCARD command that the connector sends before keepalive.
	local ok, err
	if self.pool and self.healthy then
		ok, err = self.redis_connector:set_keepalive(self.redis_client)
		-- If keepalive fails (e.g., socket already closed at the C level),
		-- fall back to a hard close so the socket is fully released.
		if not ok then
			logger:log(WARN, "set_keepalive failed: " .. (err or "unknown") .. ", closing connection")
			self.redis_client:close()
		end
	else
		ok, err = self.redis_client:close()
	end
	self.redis_client = nil
	if not ok and err then
		logger:log(ERR, "error while closing redis_client : " .. err)
	end
	return ok ~= nil, err
end

local function node_client(self, host, port)
	local red = resty_redis:new()
	red:set_timeouts(self.options.connect_timeout, self.options.send_timeout, self.options.read_timeout)
	-- No keepalive pool: DBSIZE is rare, and a pooled socket would skip AUTH after a
	-- credential or TLS change.
	local ok, err = red:connect(host, port, {
		ssl = self.options.connect_opts.ssl,
		ssl_verify = self.options.connect_opts.ssl_verify,
	})
	if not ok then
		return nil, err
	end
	if self.options.password then
		if self.options.username then
			ok, err = red:auth(self.options.username, self.options.password)
		else
			ok, err = red:auth(self.options.password)
		end
		if not ok then
			red:close()
			return nil, err
		end
	end
	return red
end

-- Keyless commands have no slot to route by: PING means "every slot is served",
-- DBSIZE is summed over primaries.
local function cluster_keyless(self, method)
	if method == "ping" then
		local info, err = self.redis_client:cluster("info")
		if not info then
			return nil, err
		end
		if not info:find("cluster_state:ok", 1, true) then
			return nil, "cluster_state is not ok"
		end
		return "PONG"
	end
	local masters, err = self.redis_client:masters()
	if not masters then
		return nil, err
	end
	local total = 0
	for _, master in ipairs(masters) do
		local red, conn_err = node_client(self, master.ip, master.port)
		if not red then
			return nil, master.ip .. ":" .. tostring(master.port) .. " " .. tostring(conn_err)
		end
		local count, cmd_err = red:dbsize()
		if not count then
			red:close()
			return nil, cmd_err
		end
		red:close()
		total = total + count
	end
	return total
end

-- Cluster only: up to limit keys matching pattern, from every primary. SCAN walks a single node,
-- so each primary gets its own connection. The walk per primary is bounded like a plain SCAN loop.
function clusterstore:scan_primaries(pattern, limit)
	if not self.cluster_mode or not self.redis_client then
		return nil, "not connected to a cluster"
	end
	local masters, err = self.redis_client:masters()
	if not masters then
		return nil, err
	end
	local keys = {}
	for _, master in ipairs(masters) do
		local red, conn_err = node_client(self, master.ip, master.port)
		if not red then
			return nil, master.ip .. ":" .. tostring(master.port) .. " " .. tostring(conn_err)
		end
		local cursor, scanned = "0", 0
		repeat
			local page, scan_err = red:scan(cursor, "MATCH", pattern, "COUNT", 100)
			if type(page) ~= "table" or type(page[2]) ~= "table" then
				red:close()
				return nil, scan_err or "unexpected SCAN reply"
			end
			cursor = page[1]
			scanned = scanned + math.max(100, #page[2])
			for _, key in ipairs(page[2]) do
				keys[#keys + 1] = key
				if #keys >= limit then
					red:close()
					return keys
				end
			end
		until cursor == "0" or scanned >= limit
		red:close()
	end
	return keys
end

function clusterstore:call(method, ...)
	-- Check if client is created
	if not self.redis_client then
		return false, "client is not instantiated"
	end
	if self.cluster_mode then
		if method == "ping" or method == "dbsize" then
			return cluster_keyless(self, method)
		end
		return self.redis_client[method](self.redis_client, ...)
	end
	-- Call method (res is nil for socket errors, false for Redis RESP errors)
	local res, err = self.redis_client[method](self.redis_client, ...)
	if res == nil and is_connection_error(err) then
		self.healthy = false
	end
	return res, err
end

return clusterstore
