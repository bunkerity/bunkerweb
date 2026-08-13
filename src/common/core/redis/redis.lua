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
		if err then
			self.clusterstore:close()
			return self:ret(
				true,
				"error while sending dbsize command to redis server : " .. err,
				HTTP_INTERNAL_SERVER_ERROR
			)
		end
		if not ok then
			self.clusterstore:close()
			return self:ret(true, "redis dbsize command failed", HTTP_INTERNAL_SERVER_ERROR)
		end
		-- Memory posture, on the same checkout. A key count alone cannot tell an operator whether
		-- the datastore is silently evicting: `evicted_keys` climbing means bans and rate-limit
		-- counters are being dropped to make room, which is invisible everywhere else.
		-- Best-effort — INFO must never turn a working stats call into a 500.
		local info = self.clusterstore:call("info", "memory")
		local stats_info = self.clusterstore:call("info", "stats")
		self.clusterstore:close()
		local data = {
			redis_nb_keys = nb_keys,
		}
		local function info_field(payload, field)
			if type(payload) ~= "string" then
				return nil
			end
			-- INFO lines are CRLF-terminated `field:value`.
			return payload:match("[\r\n]" .. field .. ":([^\r\n]*)") or payload:match("^" .. field .. ":([^\r\n]*)")
		end
		data.redis_used_memory = tonumber(info_field(info, "used_memory"))
		data.redis_maxmemory = tonumber(info_field(info, "maxmemory"))
		data.redis_maxmemory_policy = info_field(info, "maxmemory_policy")
		data.redis_evicted_keys = tonumber(info_field(stats_info, "evicted_keys"))
		return self:ret(true, data, HTTP_OK)
	end
	return self:ret(false, "success")
end

return redis
