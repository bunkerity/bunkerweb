local ngx = ngx
local class = require "middleclass"
local clogger = require "bunkerweb.logger"
local rc = require "resty.redis.connector"
local rediskeys = require "bunkerweb.rediskeys"
local utils = require "bunkerweb.utils"
local rediscluster

local clusterstore = class("clusterstore")

local logger = clogger:new("CLUSTERSTORE")

local get_variable = utils.get_variable
local is_cosocket_available = utils.is_cosocket_available
local is_connection_error = utils.is_connection_error
local is_protocol_error = utils.is_protocol_error
local ERR = ngx.ERR
local WARN = ngx.WARN
local INFO = ngx.INFO
local tonumber = tonumber
local tostring = tostring

local REDIS_SETTINGS = {
	"USE_REDIS",
	"REDIS_HOST",
	"REDIS_PORT",
	"REDIS_DATABASE",
	"REDIS_SSL",
	"REDIS_SSL_VERIFY",
	"REDIS_TIMEOUT",
	"REDIS_KEEPALIVE_IDLE",
	"REDIS_KEEPALIVE_POOL",
	"REDIS_USERNAME",
	"REDIS_PASSWORD",
	"REDIS_SENTINEL_HOSTS",
	"REDIS_SENTINEL_USERNAME",
	"REDIS_SENTINEL_PASSWORD",
	"REDIS_SENTINEL_MASTER",
	"REDIS_CLUSTER_NODES",
}

-- Per-worker memo. clusterstore:new() runs at least four times per HTTP request (once
-- per phase, from fill_ctx) plus once per is_banned / add_ban / remove_ban, and every
-- call used to re-read fifteen settings and rebuild a connector config. None of those
-- values can change without a config regeneration and an NGINX reload, which restarts
-- the worker and takes this memo with it. Keyed by the pool flag -- the only input that
-- changes the options.
local cached_variables
local cached_options = {}
local cached_connectors = {}
local cached_timer_log_level

-- Helper function to get timer log level with validation
local function get_timer_log_level()
	if cached_timer_log_level then
		return cached_timer_log_level
	end
	local level_name = utils.get_variable("TIMERS_LOG_LEVEL", false):upper()
	cached_timer_log_level = ngx[level_name] or INFO -- Default to INFO if invalid
	return cached_timer_log_level
end

local function read_variables()
	if cached_variables then
		return cached_variables
	end
	local values = {}
	local complete = true
	for _, k in ipairs(REDIS_SETTINGS) do
		local value, err = get_variable(k, false)
		if value == nil then
			logger:log(ERR, err)
			complete = false
		end
		values[k] = value
	end
	-- Only memoize a complete read : a failure in an early phase, before the settings
	-- have landed in the datastore, must not poison the worker for its whole lifetime.
	if complete then
		cached_variables = values
	end
	return values
end

local function build_options(variables, pool)
	local options = {
		connect_timeout = tonumber(variables["REDIS_TIMEOUT"]),
		read_timeout = tonumber(variables["REDIS_TIMEOUT"]),
		send_timeout = tonumber(variables["REDIS_TIMEOUT"]),
		keepalive_timeout = tonumber(variables["REDIS_KEEPALIVE_IDLE"]),
		keepalive_poolsize = tonumber(variables["REDIS_KEEPALIVE_POOL"]),
		-- REDIS_SSL_CA is absent here because it cannot be passed per connection: the handshake
		-- ends in `sock:sslhandshake(false, server_name, ssl_verify)` (lua-resty-redis) and an
		-- OpenResty cosocket has no per-connection trust store -- it verifies against the one
		-- `lua_ssl_trusted_certificate` file of the surrounding NGINX config. It does reach this
		-- path all the same: when REDIS_SSL_CA is set, gen/main.py appends it onto that bundle
		-- (write_lua_trusted_ca_bundle) and src/common/confs/{http,stream}.conf point the
		-- directive at the result. Appended, never substituted -- antibot, bunkernet and crowdsec
		-- verify against the same store, so replacing it would break all three.
		connection_options = {
			ssl = variables["REDIS_SSL"] == "yes",
			ssl_verify = variables["REDIS_SSL_VERIFY"] == "yes",
		},
		host = variables["REDIS_HOST"],
		port = tonumber(variables["REDIS_PORT"]),
		db = tonumber(variables["REDIS_DATABASE"]),
		username = variables["REDIS_USERNAME"],
		password = variables["REDIS_PASSWORD"],
		sentinel_username = variables["REDIS_SENTINEL_USERNAME"],
		sentinel_password = variables["REDIS_SENTINEL_PASSWORD"],
		master_name = variables["REDIS_SENTINEL_MASTER"],
		role = "master",
		sentinels = {},
	}
	if pool then
		options.connection_options.pool_size = tonumber(variables["REDIS_KEEPALIVE_POOL"])
	end
	if variables["REDIS_SENTINEL_HOSTS"] ~= "" then
		for sentinel_host in variables["REDIS_SENTINEL_HOSTS"]:gmatch("%S+") do
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
	return options
end

function clusterstore:initialize(pool)
	self.pool = pool == nil or pool
	self.variables = read_variables()
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
		local timeout = tonumber(self.variables["REDIS_TIMEOUT"])
		self.pool = pool == nil or pool
		self.cluster_mode = true
		self.options = {
			name = "bw",
			serv_list = rediskeys.parse_nodes(self.variables["REDIS_CLUSTER_NODES"]),
			dict_name = ngx.config.subsystem == "stream" and "redis_cluster_locks_stream" or "redis_cluster_locks",
			refresh_lock_key = "bw_refresh_",
			lock_timeout = timeout / 1000,
			connect_timeout = timeout,
			send_timeout = timeout,
			read_timeout = timeout,
			keepalive_timeout = tonumber(self.variables["REDIS_KEEPALIVE_IDLE"]),
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

	-- Only reuse across instances once the settings read succeeded at least once.
	local memoize = cached_variables ~= nil
	local key = self.pool and "pooled" or "direct"

	local options = memoize and cached_options[key] or nil
	if not options then
		options = build_options(self.variables, self.pool)
		if memoize then
			cached_options[key] = options
		end
	end
	self.options = options

	-- The cosocket gate is a phase guard, not an optimization : in set / header_filter /
	-- log there are no cosockets, so the connector must stay nil and connect() degrades
	-- to a clean "connector is not instantiated". Handing those phases a live connector
	-- would make them attempt a real cosocket connect, which raises rather than returning
	-- an error -- and badbehavior:log() -> is_banned takes that path on every blocked
	-- request. The connector itself holds no socket (sockets are created per connect),
	-- so one instance per worker is safe to share.
	if is_cosocket_available() then
		local connector = memoize and cached_connectors[key] or nil
		if not connector then
			local redis_connector, err = rc.new(options)
			if redis_connector == nil then
				logger:log(ERR, "can't instantiate redis object : " .. err)
				return
			end
			connector = redis_connector
			if memoize then
				cached_connectors[key] = connector
			end
		end
		self.redis_connector = connector
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
	local red = require("resty.redis"):new()
	red:set_timeouts(self.options.connect_timeout, self.options.send_timeout, self.options.read_timeout)
	-- No keepalive pool: DBSIZE is rare, and a pooled socket would skip AUTH after a
	-- credential or TLS change.
	local ok, err = red:connect(host, port, {
		ssl = self.options.connect_opts.ssl,
		ssl_verify = self.options.connect_opts.ssl_verify,
		server_name = host:gsub("^%[(.*)%]$", "%1"),
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
local function cluster_keyless(self, method, cursor, ...)
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
	if method == "scan" then
		-- Keep SCAN incremental: one primary page per call, including empty pages.
		table.sort(masters, function(a, b)
			return a.ip .. ":" .. a.port < b.ip .. ":" .. b.port
		end)
		local index, node_cursor = tostring(cursor):match("^(%d+):(%d+)$")
		index, node_cursor = tonumber(index) or 1, node_cursor or "0"
		local master = masters[index]
		if not master then
			return { "0", {} }
		end
		local red, conn_err = node_client(self, master.ip, master.port)
		if not red then
			return nil, conn_err
		end
		local page, scan_err = red:scan(node_cursor, ...)
		red:close()
		if type(page) ~= "table" or type(page[2]) ~= "table" then
			return nil, scan_err or "unexpected SCAN reply"
		end
		if tostring(page[1]) == "0" then
			page[1] = index == #masters and "0" or (index + 1) .. ":0"
		else
			page[1] = index .. ":" .. page[1]
		end
		return page
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
-- limit caps keys globally and scan work per primary; total scan work can reach limit times primary count.
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
					return nil, "cluster SCAN key limit exceeded"
				end
			end
		until cursor == "0" or scanned >= limit
		red:close()
		if cursor ~= "0" then
			return nil, "cluster SCAN work limit exceeded"
		end
	end
	return keys
end

-- The client can also *raise* : reading a reply off a desynced stream reached string.byte
-- with a non-string and killed the whole access phase (reversescan, run 32834226362), leaving
-- `healthy` true and the poisoned socket eligible for the keepalive pool. A redis call is I/O,
-- not control flow -- it reports failures, it does not abort its caller's phase.
function clusterstore:call(method, ...)
	-- Check if client is created
	if not self.redis_client then
		return false, "client is not instantiated"
	end
	-- Contain failures in both adapters, including keyless cluster commands.
	local command = self.redis_client[method]
	local target = self.redis_client
	if self.cluster_mode and (method == "ping" or method == "dbsize" or method == "scan") then
		command = function(store, ...)
			return cluster_keyless(store, method, ...)
		end
		target = self
	end
	local ok, res, err = pcall(command, target, ...)
	if not ok then
		self.healthy = false
		return nil, "redis client raised : " .. tostring(res)
	end
	if res == nil and (is_connection_error(err) or is_protocol_error(err)) then
		self.healthy = false
	end
	return res, err
end

-- multi() was removed : it had zero callers and was not a pipeline anyway (each
-- queued command still cost its own round-trip before EXEC). Its absence is what
-- lets the connector skip the DISCARD on every keepalive return -- nothing can
-- leave a socket parked inside an open transaction. Batch with
-- init_pipeline/commit_pipeline instead; reinstate the DISCARD if MULTI comes back.

return clusterstore
