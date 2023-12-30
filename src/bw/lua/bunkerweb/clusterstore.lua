local ngx = ngx
local class = require "middleclass"
local clogger = require "bunkerweb.logger"
local redis = require "resty.redis"
local utils = require "bunkerweb.utils"

local clusterstore = class("clusterstore")

local logger = clogger:new("CLUSTERSTORE")

local get_variable = utils.get_variable
local ERR = ngx.ERR
local tonumber = tonumber

function clusterstore:initialize(pool)
	-- Get variables
	local variables = {
		["REDIS_HOST"] = "",
		["REDIS_PORT"] = "",
		["REDIS_DATABASE"] = "",
		["REDIS_SSL"] = "",
		["REDIS_TIMEOUT"] = "",
		["REDIS_KEEPALIVE_IDLE"] = "",
		["REDIS_KEEPALIVE_POOL"] = "",
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
	-- Instantiate object
	self.pool = pool == nil or pool
	local redis_client, err = redis:new()
	self.redis_client = redis_client
	if self.redis_client == nil then
		logger:log(ERR, "can't instantiate redis object : " .. err)
		return
	end
	self.redis_client:set_timeout(tonumber(self.variables["REDIS_TIMEOUT"]))
end

function clusterstore:connect()
	-- Check if client is created
	if not self.redis_client then
		return false, "client is not instantiated"
	end
	-- Set options
	local options = {
		ssl = self.variables["REDIS_SSL"] == "yes",
	}
	if self.pool then
		options.pool = "bw-redis"
		options.pool_size = tonumber(self.variables["REDIS_KEEPALIVE_POOL"])
	end
	-- Connect
	local ok, err = self.redis_client:connect(self.variables["REDIS_HOST"], tonumber(self.variables["REDIS_PORT"]), options)
	if not ok then
		return false, err
	end
	-- Select database if needed
	local times, err = self.redis_client:get_reused_times()
	if err then
		self.redis_client:close()
		return false, err
	end
	if times < 2 then
		-- luacheck: ignore 421
		local _, err = self.redis_client:select(tonumber(self.variables["REDIS_DATABASE"]))
		if err then
			self.redis_client:close()
			return false, err
		end
	end
	return true, "success", times
end

function clusterstore:close()
	-- Check if client is created
	if not self.redis_client then
		return false, "client is not instantiated"
	end
	-- Pool case
	local ok, err
	if self.pool then
		ok, err = self.redis_client:set_keepalive(
			tonumber(self.variables["REDIS_KEEPALIVE_IDLE"]),
			tonumber(self.variables["REDIS_KEEPALIVE_POOL"])
		)
	-- No pool
	else
		ok, err = self.redis_client:close()
	end
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
