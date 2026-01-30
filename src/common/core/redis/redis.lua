local class = require "middleclass"
local plugin = require "bunkerweb.plugin"

local redis = class("redis", plugin)

local ngx = ngx
local NOTICE = ngx.NOTICE
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local HTTP_OK = ngx.HTTP_OK

function redis:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "redis", ctx)
end

function redis:init_worker()
	-- Check if init_worker is needed
	if self.variables["USE_REDIS"] ~= "yes" or self.is_loading then
		return self:ret(true, "init_worker not needed")
	end
	-- Check redis connection
	local ok, err = self.clusterstore:connect(true)
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
	self.logger:log(NOTICE, "connectivity with redis server " .. self.variables["REDIS_HOST"] .. " is successful")
	return self:ret(true, "success")
end

-- function redis:timer()
-- 	-- Check if metrics is used
-- 	local is_needed, err = has_variable("USE_REDIS", "yes")
-- 	if is_needed == nil then
-- 		return self:ret(false, "can't check USE_REDIS variable : " .. err)
-- 	end
-- 	if not is_needed then
-- 		return self:ret(true, "redis not used")
-- 	end
-- 	-- Return values
-- 	local ret = true
-- 	local ret_err = "redis is working"
-- 	-- Check redis connection
-- 	local ok, err = self.clusterstore:connect(true)
-- 	if not ok then
-- 		self.
-- 		return self:ret(false, "redis connect error : " .. err)
-- 	end
-- 	-- Send ping
-- 	local ok, err = self.clusterstore:call("ping")
-- 	self.clusterstore:close()
-- 	if err then
-- 		return self:ret(false, "error while sending ping command to redis server : " .. err)
-- 	end
-- 	if not ok then
-- 		return self:ret(false, "redis ping command failed")
-- 	end
-- end

function redis:api()
	if self.ctx.bw.uri == "/redis/ping" and self.ctx.bw.request_method == "POST" then
		if self.variables["USE_REDIS"] ~= "yes" then
			return self:ret(true, "redis is not enabled", HTTP_OK)
		end
		-- Check redis connection
		local ok, err = self.clusterstore:connect(true)
		if not ok then
			return self:ret(true, "redis connect error : " .. err, HTTP_INTERNAL_SERVER_ERROR)
		end
		-- Send ping
		local ok, err = self.clusterstore:call("ping")
		self.clusterstore:close()
		if err then
			return self:ret(
				true,
				"error while sending ping command to redis server : " .. err,
				HTTP_INTERNAL_SERVER_ERROR
			)
		end
		if not ok then
			return self:ret(true, "redis ping command failed", HTTP_INTERNAL_SERVER_ERROR)
		end
		return self:ret(true, "success", HTTP_OK)
	end
	if self.ctx.bw.uri == "/redis/stats" and self.ctx.bw.request_method == "GET" then
		if self.variables["USE_REDIS"] ~= "yes" then
			return self:ret(true, "redis is not enabled", HTTP_OK)
		end
		-- Connect to redis
		local ok, err = self.clusterstore:connect(true)
		if not ok then
			return self:ret(true, "redis connect error : " .. err, HTTP_INTERNAL_SERVER_ERROR)
		end
		-- Get number of keys
		local nb_keys, err = self.clusterstore:call("dbsize")
		self.clusterstore:close()
		if err then
			return self:ret(
				true,
				"error while sending dbsize command to redis server : " .. err,
				HTTP_INTERNAL_SERVER_ERROR
			)
		end
		if not ok then
			return self:ret(true, "redis dbsize command failed", HTTP_INTERNAL_SERVER_ERROR)
		end
		-- Return data
		local data = {
			redis_nb_keys = nb_keys,
		}
		return self:ret(true, data, HTTP_OK)
	end
	return self:ret(false, "success")
end

return redis
