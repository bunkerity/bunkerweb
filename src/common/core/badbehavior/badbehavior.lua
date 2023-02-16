local _M = {}
_M.__index = _M

local utils			= require "utils"
local datastore		= require "datastore"
local logger		= require "logger"
local cjson			= require "cjson"
local clusterstore	= require "clusterstore"

function _M.new()
	local self = setmetatable({}, _M)
	return self, nil
end

function _M.increase(premature, use_redis, ip, count_time, ban_time, threshold)
	-- Local case
	local counter, err = datastore:get("plugin_badbehavior_count_" .. ip)
	if not counter and err ~= "not found" then
		return false, "can't get counts from the datastore : " .. err
	end
	if counter == nil then
		counter = 0
	end
	counter = counter + 1
	-- Redis case
	if use_redis then
		-- Connect to server
		local redis_client, err = clusterstore:connect()
		if not redis_client then
			logger.log(ngx.ERR, "BAD-BEHAVIOR", "(increase) Can't connect to redis server : " .. err)
			return
		end
		-- Start transaction
		local ok, err = redis_client:multi()
		if not ok then
			logger.log(ngx.ERR, "BAD-BEHAVIOR", "(increase) Can't start transaction : " .. err)
			redis_client:close()
			return
		end
		-- Increment counter
		counter, err = redis_client:incr("bad_behavior_" .. ip)
		if not counter then
			logger.log(ngx.ERR, "BAD-BEHAVIOR", "(increase) INCR failed : " .. err)
			redis_client:close()
			return
		end
		-- Expires counter
		local expire, err = redis_client:expire("bad_behavior_" .. ip, count_time)
		if not counter then
			logger.log(ngx.ERR, "BAD-BEHAVIOR", "(increase) EXPIRE failed : " .. err)
			redis_client:close()
			return
		end
		-- Add IP to redis bans if needed
		if counter > threshold then
			local ban, err = redis_client:set("ban_" .. ip, "bad behavior", "EX", ban_time)
			if not ban then
				logger.log(ngx.ERR, "BAD-BEHAVIOR", "(increase) SET failed : " .. err)
				redis_client:close()
				return
			end
		end
		-- Exec transaction
		local exec, err = redis_client:exec()
		if not exec then
			logger.log(ngx.ERR, "BAD-BEHAVIOR", "(increase) EXEC failed : " .. err)
			redis_client:close()
			return
		end
		for i, v in ipairs(exec) do
			if v[1] == false then
				logger.log(ngx.ERR, "BAD-BEHAVIOR", "(increase) Transaction failed : " .. v[2])
				redis_client:close()
				return
			end
		end
		-- End connection
		redis_client:close()
	end
	-- Store local counter
	local ok, err = datastore:set("plugin_badbehavior_count_" .. ip, counter)
	if not ok then
		logger.log(ngx.ERR, "BAD-BEHAVIOR", "(increase) can't save counts to the datastore : " .. err)
		return
	end
	-- Store local ban
	if counter > threshold then
		local ok, err = datastore:set("bans_ip_" .. ip, "bad behavior", ban_time)
		if not ok then
			logger.log(ngx.ERR, "BAD-BEHAVIOR", "(increase) can't save ban to the datastore : " .. err)
			return
		end
		logger.log(ngx.WARN, "BAD-BEHAVIOR", "IP " .. ip .. " is banned for " .. ban_time .. "s (" .. tostring(counter) .. "/" .. tostring(threshold) .. ")")
	end
	-- Call decrease later
	local ok, err = ngx.timer.at(count_time, _M.decrease, use_redis, ip)
	if not ok then
		logger.log(ngx.ERR, "BAD-BEHAVIOR", "(increase) can't create decrease timer : " .. err)
	end
end

function _M.decrease(premature, use_redis, ip)
	-- Decrease from local store
	local count, err = datastore:get("plugin_badbehavior_count_" .. ip)
	if err then
		logger.log(ngx.ERR, "BAD-BEHAVIOR", "(decrease) Can't get counts from the datastore : " .. err)
		return
	end
	if not count then
		logger.log(ngx.ERR, "BAD-BEHAVIOR", "(decrease) Count is null")
		return
	end
	local new_count = count - 1
	if new_count <= 0 then
		datastore:delete("plugin_badbehavior_count_" .. ip)
		return
	end
	local ok, err = datastore:set("plugin_badbehavior_count_" .. ip, new_count)
	if not ok then
		logger.log(ngx.ERR, "BAD-BEHAVIOR", "(decrease) Can't save counts to the datastore : " .. err)
		return
	end
	-- Decrease from redis
	if use_redis then
		-- Connect to server
		local redis_client, err = clusterstore:connect()
		if not redis_client then
			logger.log(ngx.ERR, "BAD-BEHAVIOR", "(decrease) Can't connect to redis server : " .. err)
			return
		end
		-- Decrement counter
		local counter, err = redis_client:decr("bad_behavior_" .. ip)
		if not counter then
			logger.log(ngx.ERR, "BAD-BEHAVIOR", "(decrease) DECR failed : " .. err)
			redis_client:close()
			return
		end
		redis_client:close()
	end
end

function _M:log()
	-- Get vars
	self.use			= utils.get_variable("USE_BAD_BEHAVIOR")
	self.ban_time		= utils.get_variable("BAD_BEHAVIOR_BAN_TIME")
	self.status_codes	= utils.get_variable("BAD_BEHAVIOR_STATUS_CODES")
	self.threshold		= utils.get_variable("BAD_BEHAVIOR_THRESHOLD")
	self.count_time		= utils.get_variable("BAD_BEHAVIOR_COUNT_TIME")
	self.use_redis		= utils.get_variable("USE_REDIS")
	-- Check if bad behavior is activated
	if self.use ~= "yes" then
		return true, "bad behavior not activated"
	end
	-- Check if we have a bad status code
	if not self.status_codes:match(tostring(ngx.status)) then
		return true, "not increasing counter"
	end
	-- Check if we are whitelisted
	if ngx.var.is_whitelisted == "yes" then
		return true, "client is whitelisted"
	end
	-- Call increase function later and with cosocket enabled
	local use_redis = false
	if self.use_redis == "yes" then
		use_redis = true
	end
	local ok, err = ngx.timer.at(0, _M.increase, use_redis, ngx.var.remote_addr, tonumber(self.count_time), tonumber(self.ban_time), tonumber(self.threshold))
	if not ok then
		return false, "can't create decrease timer : " .. err
	end
	return true, "success"
end

function _M:log_default()
	return _M:log()
end

return _M
