local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local badbehavior = class("badbehavior", plugin)

local ngx = ngx
local ERR = ngx.ERR
local WARN = ngx.WARN
local NOTICE = ngx.NOTICE
local timer_at = ngx.timer.at
local add_ban = utils.add_ban
local is_whitelisted = utils.is_whitelisted
local is_banned = utils.is_banned
local tostring = tostring

function badbehavior:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "badbehavior", ctx)
end

function badbehavior:log()
	-- Check if we are whitelisted
	if is_whitelisted(self.ctx) then
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
	if is_banned(self.ctx.bw.remote_addr) then
		return self:ret(true, "already banned")
	end
	-- Call increase function later and with cosocket enabled
	local ok, err = timer_at(
		0,
		badbehavior.increase,
		self.ctx.bw.remote_addr,
		tonumber(self.variables["BAD_BEHAVIOR_COUNT_TIME"]),
		tonumber(self.variables["BAD_BEHAVIOR_BAN_TIME"]),
		tonumber(self.variables["BAD_BEHAVIOR_THRESHOLD"]),
		self.use_redis
	)
	if not ok then
		return self:ret(false, "can't create increase timer : " .. err)
	end
	self:set_metric("counters", tostring(ngx.status), 1)
	return self:ret(true, "success")
end

function badbehavior:log_default()
	return self:log()
end

function badbehavior:log_stream()
	return self:log()
end

-- luacheck: ignore 212
function badbehavior.increase(premature, ip, count_time, ban_time, threshold, use_redis)
	-- Instantiate objects
	local logger = require "bunkerweb.logger":new("badbehavior")
	local datastore = require "bunkerweb.datastore":new()

	-- Declare counter
	local counter = false
	-- Redis case
	if use_redis then
		local redis_counter, err = badbehavior.redis_increase(ip, count_time, ban_time)
		if not redis_counter then
			logger:log(ERR, "(increase) redis_increase failed, falling back to local : " .. err)
		else
			counter = redis_counter
		end
	end
	-- Local case
	if not counter then
		local local_counter, err = datastore:get("plugin_badbehavior_count_" .. ip)
		if not local_counter and err ~= "not found" then
			logger:log(ERR, "(increase) can't get counts from the datastore : " .. err)
		end
		if local_counter == nil then
			local_counter = 0
		end
		counter = local_counter + 1
	end
	-- Call decrease later
	local ok, err = timer_at(count_time, badbehavior.decrease, ip, count_time, threshold, use_redis)
	if not ok then
		logger:log(ERR, "(increase) can't create decrease timer : " .. err)
	end
	-- Store local counter
	local ok, err = datastore:set("plugin_badbehavior_count_" .. ip, counter, count_time)
	if not ok then
		logger:log(ERR, "(increase) can't save counts to the datastore : " .. err)
		return
	end
	-- Store local ban
	if counter > threshold then
		ok, err = add_ban(ip, "bad behavior", ban_time)
		if not ok then
			logger:log(ERR, "(increase) can't save ban : " .. err)
			return
		end
		logger:log(
			WARN,
			"IP "
				.. ip
				.. " is banned for "
				.. ban_time
				.. "s ("
				.. tostring(counter)
				.. "/"
				.. tostring(threshold)
				.. ")"
		)
	end
	logger:log(
		NOTICE,
		"increased counter for IP " .. ip .. " (" .. tostring(counter) .. "/" .. tostring(threshold) .. ")"
	)
end

function badbehavior.decrease(premature, ip, count_time, threshold, use_redis)
	-- Instantiate objects
	local logger = require "bunkerweb.logger":new("badbehavior")
	local datastore = require "bunkerweb.datastore":new()
	-- Declare counter
	local counter = false
	-- Redis case
	if use_redis then
		local redis_counter, err = badbehavior.redis_decrease(ip, count_time)
		if not redis_counter then
			logger:log(ERR, "(decrease) redis_decrease failed, falling back to local : " .. err)
		else
			counter = redis_counter
		end
	end
	-- Local case
	if not counter then
		local local_counter, err = datastore:get("plugin_badbehavior_count_" .. ip)
		if not local_counter and err ~= "not found" then
			logger:log(ERR, "(decrease) can't get counts from the datastore : " .. err)
		end
		if local_counter == nil or local_counter <= 1 then
			counter = 0
		else
			counter = local_counter - 1
		end
	end
	-- Store local counter
	if counter <= 0 then
		counter = 0
		datastore:delete("plugin_badbehavior_count_" .. ip)
	else
		local ok, err = datastore:set("plugin_badbehavior_count_" .. ip, counter, count_time)
		if not ok then
			logger:log(ERR, "(decrease) can't save counts to the datastore : " .. err)
			return
		end
	end
	logger:log(
		NOTICE,
		"decreased counter for IP " .. ip .. " (" .. tostring(counter) .. "/" .. tostring(threshold) .. ")"
	)
end

function badbehavior.redis_increase(ip, count_time, ban_time)
	-- Instantiate objects
	local clusterstore = require "bunkerweb.clusterstore":new()
	-- Our LUA script to execute on redis
	local redis_script = [[
		local ret_incr = redis.pcall("INCR", KEYS[1])
		if type(ret_incr) == "table" and ret_incr["err"] ~= nil then
			redis.log(redis.LOG_WARNING, "Bad behavior increase INCR error : " .. ret_incr["err"])
			return ret_incr
		end
		local ret_expire = redis.pcall("EXPIRE", KEYS[1], ARGV[1])
		if type(ret_expire) == "table" and ret_expire["err"] ~= nil then
			redis.log(redis.LOG_WARNING, "Bad behavior increase EXPIRE error : " .. ret_expire["err"])
			return ret_expire
		end
		if ret_incr > tonumber(ARGV[2]) then
			local ret_set = redis.pcall("SET", KEYS[2], "bad behavior", "EX", ARGV[2])
			if type(ret_set) == "table" and ret_set["err"] ~= nil then
				redis.log(redis.LOG_WARNING, "Bad behavior increase SET error : " .. ret_set["err"])
				return ret_set
			end
		end
		return ret_incr
	]]
	-- Connect to server
	local ok, err = clusterstore:connect()
	if not ok then
		return false, err
	end
	-- Execute LUA script
	local counter, err =
		clusterstore:call("eval", redis_script, 2, "plugin_bad_behavior_" .. ip, "bans_ip" .. ip, count_time, ban_time)
	if not counter then
		clusterstore:close()
		return false, err
	end
	-- End connection
	clusterstore:close()
	return counter
end

function badbehavior.redis_decrease(ip, count_time)
	-- Instantiate objects
	local clusterstore = require "bunkerweb.clusterstore":new()
	-- Our LUA script to execute on redis
	local redis_script = [[
		local ret_decr = redis.pcall("DECR", KEYS[1])
		if type(ret_decr) == "table" and ret_decr["err"] ~= nil then
			redis.log(redis.LOG_WARNING, "Bad behavior decrease DECR error : " .. ret_decr["err"])
			return ret_decr
		end
		local ret_expire = redis.pcall("EXPIRE", KEYS[1], ARGV[1])
		if type(ret_expire) == "table" and ret_expire["err"] ~= nil then
			redis.log(redis.LOG_WARNING, "Bad behavior decrease EXPIRE error : " .. ret_expire["err"])
			return ret_expire
		end
		if ret_decr <= 0 then
			local ret_del = redis.pcall("DEL", KEYS[1])
			if type(ret_del) == "table" and ret_del["err"] ~= nil then
				redis.log(redis.LOG_WARNING, "Bad behavior decrease DEL error : " .. ret_del["err"])
				return ret_del
			end
		end
		return ret_decr
	]]
	-- Connect to server
	local ok, err = clusterstore:connect()
	if not ok then
		return false, err
	end
	local counter, err = clusterstore:call("eval", redis_script, 1, "plugin_bad_behavior_" .. ip, count_time)
	if not counter then
		clusterstore:close()
		return false, err
	end
	clusterstore:close()
	return counter
end

return badbehavior
