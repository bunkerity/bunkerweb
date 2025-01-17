local ngx = ngx
local class = require "middleclass"
local clogger = require "bunkerweb.logger"
local rc = require "resty.redis.connector"
local utils = require "bunkerweb.utils"

local clusterstore = class("clusterstore")

local logger = clogger:new("CLUSTERSTORE")

local get_variable = utils.get_variable
local is_cosocket_available = utils.is_cosocket_available
local ERR = ngx.ERR
local WARN = ngx.WARN
local INFO = ngx.INFO
local tonumber = tonumber
local tostring = tostring

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
	-- Compute options
	local options = {
		connect_timeout = tonumber(self.variables["REDIS_TIMEOUT"]),
		read_timeout = tonumber(self.variables["REDIS_TIMEOUT"]),
		send_timeout = tonumber(self.variables["REDIS_TIMEOUT"]),
		keepalive_timeout = tonumber(self.variables["REDIS_KEEPALIVE_IDLE"]),
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
		self:close()
		return false, "error while getting reused times : " .. err
	end
	logger:log(INFO, "redis reused times = " .. tostring(times))
	return true, "success", times
end

function clusterstore:close()
	-- Check if connected is created
	if not self.redis_connector then
		return false, "connector is not instantiated"
	end
	-- Check if client is created
	if not self.redis_client then
		return false, "client is not instantiated"
	end
	-- Pool case
	local ok, err
	if self.pool then
		ok, err = self.redis_connector:set_keepalive(self.redis_client)
		-- No pool
	else
		ok, err = self.redis_client:close()
	end
	self.redis_client = nil
	if err then
		logger:log(ERR, "error while closing redis_client : " .. err)
	end
	return ok ~= nil, err
end

function clusterstore:call(method, ...)
	-- Check if client is created
	if not self.redis_client then
		return false, "client is not instantiated"
	end
	-- Call method
	return self.redis_client[method](self.redis_client, ...)
end

function clusterstore:multi(calls)
	-- Check if client is created
	if not self.redis_client then
		return false, "client is not instantiated"
	end
	-- Start transaction
	local ok, err = self.redis_client:multi()
	if not ok then
		return false, "multi() failed : " .. err
	end
	-- Loop on calls
	for _, call in ipairs(calls) do
		local method = call[1]
		local args = unpack(call[2])
		ok, err = self.redis_client[method](self.redis_client, args)
		if not ok then
			return false, method .. "() failed : " .. err
		end
	end
	-- Exec transaction
	local exec, err = self.redis_client:exec()
	if not exec then
		return false, "exec() failed : " .. err
	end
	if type(exec) ~= "table" then
		return false, "exec() result is not a table"
	end
	return true, "success", exec
end

return clusterstore
