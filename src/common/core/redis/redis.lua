local class  = require "middleclass"
local plugin = require "bunkerweb.plugin"

local redis  = class("redis", plugin)

function redis:initialize()
	-- Call parent initialize
	plugin.initialize(self, "redis")
end

function redis:init_worker()
	-- Check if init_worker is needed
	if self.variables["USE_REDIS"] ~= "yes" or self.is_loading then
		return self:ret(true, "init_worker not needed")
	end
	-- Check redis connection
	local ok, err = self.clusterstore:connect()
	if not ok then
		return self:ret(false, "redis connect error : " .. err)
	end
	-- Send ping
	local ok, err = self.clusterstore:call("ping")
	self.clusterstore:close()
	if err then
		return self:ret(false, "error while sending ping command to redis server : " .. err)
	end
	if not ok then
		return self:ret(false, "redis ping command failed")
	end
	self.logger:log(ngx.NOTICE, "connectivity with redis server " .. self.variables["REDIS_HOST"] .. " is successful")
	return self:ret(true, "success")
end

return redis
