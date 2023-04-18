local class			= require "middleclass"
local plugin		= require "bunkerweb.plugin"
local logger		= require "bunkerweb.logger"
local utils			= require "bunkerweb.utils"
local clusterstore	= require "bunkerweb.clusterstore"

local redis = class("redis", plugin)

function redis:initialize()
	-- Call parent initialize
	plugin.initialize(self, "redis")
end

function redis:init()
	-- Check if init is needed
	if self.variables["USE_REDIS"] then
		return self:ret(true, "redis not used")
	end
	-- Check redis connection
	local ok, err = clusterstore:connect()
	if not ok then
		return self:ret(false, "redis connect error : " .. err)
	end
	local ok, err = clusterstore:call("ping")
	clusterstore:close()
	if err then
		return self:ret(false, "error while sending ping command : " .. err)
	end
	if not ok then
		return self:ret(false, "ping command failed")
	end
	return self:ret(true, "redis ping successful")
end

return redis