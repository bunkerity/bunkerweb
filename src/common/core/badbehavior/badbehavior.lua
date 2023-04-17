local class			= require "middleclass"
local plugin		= require "bunkerweb.plugin"
local utils			= require "bunkerweb.utils"
local datastore		= require "bunkerweb.datastore"
local clusterstore	= require "bunkerweb.clusterstore"

local badbehavior = class("badbehavior", plugin)

function badbehavior:initialize()
	-- Call parent initialize
	plugin.initialize(self, "badbehavior")
	-- Check if redis is enabled
	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if not use_redis then
		self.logger:log(ngx.ERR, err)
	end
	self.use_redis = use_redis == "yes"
end

function badbehavior:log()
	-- Check if we are whitelisted
	if ngx.var.is_whitelisted == "yes" then
		return self:ret(true, "client is whitelisted")
	end
	-- Check if bad behavior is activated
	if self.variables["USE_BAD_BEHAVIOR"] ~= "yes" then
		return self:ret(true, "bad behavior not activated")
	end
	-- Check if we have a bad status code
	if not self.variables["BAD_BEHAVIOR_STATUS_CODES"]:match(tostring(ngx.status)) then
		return self:ret(true, "not increasing counter")
	end
	-- Check if we are already banned
	local banned, err = self.datastore:get("bans_ip_" .. ngx.var.remote_addr)
	if banned then
		return self:ret(true, "already banned")
	end
	-- Call increase function later and with cosocket enabled
	local ok, err = ngx.timer.at(0, badbehavior.increase, self, ngx.var.remote_addr)
	if not ok then
		return self:ret(false, "can't create increase timer : " .. err)
	end
	return self:ret(true, "success")
end

function badbehavior:log_default()
	return self:log()
end

function badbehavior.increase(premature, obj, ip)
	-- Our vars
	local count_time = tonumber(obj.variables["BAD_BEHAVIOR_COUNT_TIME"])
	local ban_time = tonumber(obj.variables["BAD_BEHAVIOR_BAN_TIME"])
	local threshold = tonumber(obj.variables["BAD_BEHAVIOR_THRESHOLD"])
	-- Declare counter
	local counter = false
	-- Redis case
	if obj.use_redis then
		local redis_counter, err = obj:redis_increase(ip)
		if not redis_counter then
			obj.logger:log(ngx.ERR, "(increase) redis_increase failed, falling back to local : " .. err)
		else
			counter = redis_counter
		end
	end
	-- Local case
	if not counter then
		local local_counter, err = obj.datastore:get("plugin_badbehavior_count_" .. ip)
		if not local_counter and err ~= "not found" then
			obj.logger:log(ngx.ERR, "(increase) can't get counts from the datastore : " .. err)
		end
		if local_counter == nil then
			local_counter = 0
		end
		counter = local_counter + 1
	end
	-- Call decrease later
	local ok, err = ngx.timer.at(count_time, badbehavior.decrease, obj, ip)
	if not ok then
		obj.logger:log(ngx.ERR, "(increase) can't create decrease timer : " .. err)
	end
	-- Store local counter
	local ok, err = obj.datastore:set("plugin_badbehavior_count_" .. ip, counter)
	if not ok then
		obj.logger:log(ngx.ERR, "(increase) can't save counts to the datastore : " .. err)
		return
	end
	-- Store local ban
	if counter > threshold then
		local ok, err = obj.datastore:set("bans_ip_" .. ip, "bad behavior", ban_time)
		if not ok then
			obj.logger:log(ngx.ERR, "(increase) can't save ban to the datastore : " .. err)
			return
		end
		obj.logger:log(ngx.WARN, "IP " .. ip .. " is banned for " .. ban_time .. "s (" .. tostring(counter) .. "/" .. tostring(threshold) .. ")")
	end
end

function badbehavior.decrease(premature, obj, ip)
	-- Our vars
	local count_time = tonumber(obj.variables["BAD_BEHAVIOR_COUNT_TIME"])
	local ban_time = tonumber(obj.variables["BAD_BEHAVIOR_BAN_TIME"])
	local threshold = tonumber(obj.variables["BAD_BEHAVIOR_THRESHOLD"])
	-- Declare counter
	local counter = false
	-- Redis case
	if obj.use_redis then
		local redis_counter, err = obj:redis_decrease(ip)
		if not redis_counter then
			obj.logger:log(ngx.ERR, "(increase) redis_increase failed, falling back to local : " .. err)
		else
			counter = redis_counter
		end
	end
	-- Local case
	if not counter then
		local local_counter, err = obj.datastore:get("plugin_badbehavior_count_" .. ip)
		if not local_counter and err ~= "not found" then
			obj.logger:log(ngx.ERR, "(increase) can't get counts from the datastore : " .. err)
		end
		if local_counter == nil or local_counter <= 1 then
			counter = 0
		else
			counter = local_counter - 1
		end
	end
	-- Store local counter
	if counter <= 0 then
		local ok, err = obj.datastore:delete("plugin_badbehavior_count_" .. ip)
	else
		local ok, err = obj.datastore:delete("plugin_badbehavior_count_" .. ip, counter)
		if not ok then
			obj.logger:log(ngx.ERR, "(increase) can't save counts to the datastore : " .. err)
			return
		end
	end
end

function badbehavior:redis_increase(ip)
	-- Our vars
	local count_time = tonumber(self.variables["BAD_BEHAVIOR_COUNT_TIME"])
	local ban_time = tonumber(self.variables["BAD_BEHAVIOR_BAN_TIME"])
	-- Connect to server
	local cstore, err = clusterstore:new()
	if not cstore then
		return false, err
	end
	local ok, err = clusterstore:connect()
	if not ok then
		return false, err
	end
	-- Exec transaction
	local calls = {
		{"incr", {"bad_behavior_" .. ip}},
		{"expire", {"bad_behavior_" .. ip, count_time}}
	}
	local ok, err, exec = clusterstore:multi(calls)
	if not ok then
		clusterstore:close()
		return false, err
	end
	-- Extract counter
	local counter = exec[1]
	if type(counter) == "table" then
		clusterstore:close()
		return false, counter[2]
	end
	-- Check expire result
	local expire = exec[2]
	if type(expire) == "table" then
		clusterstore:close()
		return false, expire[2]
	end
	-- Add IP to redis bans if needed
	if counter > threshold then
		local ok, err = clusterstore:call("set", "ban_" .. ip, "bad behavior", "EX", ban_time)
		if err then
			clusterstore:close()
			return false, err
		end
	end
	-- End connection
	clusterstore:close()
	return counter
end

function badbehavior:redis_decrease(ip)
	-- Connect to server
	local cstore, err = clusterstore:new()
	if not cstore then
		return false, err
	end
	local ok, err = clusterstore:connect()
	if not ok then
		return false, err
	end
	-- Decrement counter
	local counter, err = clusterstore:call("decr", "bad_behavior_" .. ip)
	if err then
		clusterstore:close()
		return false, err
	end
	-- Delete counter
	if counter < 0 then
		counter = 0
	end
	if counter == 0 then
		local ok, err = clusterstore:call("del", "bad_behavior_" .. ip)
		if err then
			clusterstore:close()
			return false, err
		end
	end
	-- End connection
	clusterstore:close()
	return counter
end

return badbehavior