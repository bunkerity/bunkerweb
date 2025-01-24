local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"
local cjson = require "cjson"

local badbehavior = class("badbehavior", plugin)

local ngx = ngx
local ERR = ngx.ERR
local WARN = ngx.WARN
local NOTICE = ngx.NOTICE
local timer_at = ngx.timer.at
local worker = ngx.worker
local add_ban = utils.add_ban
local is_whitelisted = utils.is_whitelisted
local is_banned = utils.is_banned
local get_country = utils.get_country
local get_security_mode = utils.get_security_mode
local tostring = tostring
local time = os.time
local date = os.date
local encode = cjson.encode
local decode = cjson.decode

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
	-- Get security mode
	local security_mode = get_security_mode(self.ctx)
	-- Get country
	local country = "local"
	local err
	if self.ctx.bw.ip_is_global then
		country, err = get_country(self.ctx.bw.remote_addr)
		if not country then
			country = "unknown"
			self.logger:log(ERR, "can't get country code " .. err)
		end
	end
	-- Add incr operation so timer can manage it
	local status = tostring(ngx.status)
	local ok, err = self.datastore.dict:rpush(
		"plugin_badbehavior_incr",
		encode({
			ip = self.ctx.bw.remote_addr,
			count_time = tonumber(self.variables["BAD_BEHAVIOR_COUNT_TIME"]),
			ban_time = tonumber(self.variables["BAD_BEHAVIOR_BAN_TIME"]),
			threshold = tonumber(self.variables["BAD_BEHAVIOR_THRESHOLD"]),
			use_redis = self.use_redis,
			server_name = self.ctx.bw.server_name,
			security_mode = security_mode,
			country = country,
			timestamp = time(date("!*t")),
			status = status
		})
	)
	if not ok then
		return self:ret(false, "can't add incr operation : " .. err)
	end
	self:set_metric("counters", status, 1)
	return self:ret(true, "success")
end

function badbehavior:log_default()
	return self:log()
end

function badbehavior:log_stream()
	return self:log()
end

function badbehavior:timer()

	-- Only execute on worker 0
	if worker.id() ~= 0 then
		return self:ret(true, "skipped")
	end

	-- Our ret values
	local ret = true
	local ret_err = "success"

	-- List of counters
	local counters = {}
	local timestamp = time(date("!*t"))

	-- Loop on decrease operations
	local decr_len, decr_len_err = self.datastore:llen("plugin_badbehavior_decr")
	if decr_len == nil then
		return self:ret(false, "can't get decr list length : " .. decr_len_err)
	end
	for i = 1, decr_len do
		-- Pop operation
		local decr, decr_err = self.datastore:lpop("plugin_badbehavior_decr")
		if decr == nil then
			return self:ret(false, "can't get decr list element : " .. decr_err)
		end
		decr = decode(decr)
		if timestamp > decr["timestamp"] then
			-- Call decrease
			local ok, err = self:decrease(decr["ip"], decr["count_time"], decr["threshold"], decr["use_redis"], decr["server_name"], decr["status"], decr["old_counter"])
			if not ok then
				ret = false
				ret_err = "can't decrease counter : " .. err
			end
		else
			-- Add back to list
			local ok, err = self.datastore.dict:rpush("plugin_badbehavior_decr", encode(decr))
			if not ok then
				ret = false
				ret_err = "can't add decr list element : " .. err
			end
		end
	end

	-- Loop on increase operations
	local incr_len, incr_len_err = self.datastore:llen("plugin_badbehavior_incr")
	if incr_len == nil then
		return self:ret(false, "can't get incr list length : " .. incr_len_err)
	end
	for i = 1, incr_len do
		-- Pop operation
		local incr, incr_err = self.datastore:lpop("plugin_badbehavior_incr")
		if incr == nil then
			return self:ret(false, "can't get incr list element : " .. incr_err)
		end
		incr = decode(incr)
		-- Call increase
		local counter, counter_err = self:increase(incr["ip"], incr["count_time"], incr["ban_time"], incr["threshold"], incr["use_redis"], incr["server_name"], incr["security_mode"], incr["country"], incr["status"])
		if not counter then
			ret = false
			ret_err = "can't increase counter : " .. counter_err
		else
			-- Add decrease later
			local ok, err = self.datastore.dict:rpush("plugin_badbehavior_decr", encode({
				ip = incr["ip"],
				old_counter = counter,
				count_time = incr["count_time"],
				threshold = incr["threshold"],
				use_redis = incr["use_redis"],
				timestamp = timestamp + incr["count_time"],
				server_name = incr["server_name"],
				status = incr["status"]
			}))
			if not ok then
				ret = false
				ret_err = "can't add decr list element : " .. err
			end
			-- Add counter to counters
			counters[incr["ip"] .. "_" .. incr["server_name"]] = {
				counter = counter,
				ip = incr["ip"],
				count_time = incr["count_time"],
				ban_time = incr["ban_time"],
				threshold = incr["threshold"],
				use_redis = incr["use_redis"],
				server_name = incr["server_name"],
				security_mode = incr["security_mode"],
				country = incr["country"],
				status = incr["status"]
			}
		end
	end

	-- Add bans if needed
	for ip_server_name, counter in pairs(counters) do
		local ip, server_name = ip_server_name:match("([^_]+)_([^_]+)")
		if counter["counter"] >= counter["threshold"] then
			if counter["security_mode"] == "block" then
				local ok, err = add_ban(
					counter["ip"],
					"bad behavior",
					counter["ban_time"],
					counter["server_name"],
					counter["country"]
				)
				if not ok then
					ret = false
					ret_err = "can't save ban : " .. err
				else
					self.logger:log(
						WARN,
						"IP "
							.. counter["ip"]
							.. " is banned for "
							.. counter["ban_time"]
							.. "s ("
							.. tostring(counter["counter"])
							.. "/"
							.. tostring(counter["threshold"])
							.. ") on server "
							.. counter["server_name"]
					)
				end
			else
				self.logger:log(
					WARN,
					"detected IP "
						.. counter["ip"]
						.. " ban for "
						.. counter["ban_time"]
						.. "s ("
						.. tostring(counter["counter"])
						.. "/"
						.. tostring(counter["threshold"])
						.. ") on server "
						.. counter["server_name"]
				)
			end
		end
	end
	return self:ret(ret, ret_err)
end

-- luacheck: ignore 212
function badbehavior:increase(
	ip,
	count_time,
	ban_time,
	threshold,
	use_redis,
	server_name,
	security_mode,
	country,
	status
)
	-- Declare counter
	local counter = false

	-- Redis case
	if use_redis then
		local redis_counter, err = self:redis_increase(ip, count_time, ban_time)
		if not redis_counter then
			self.logger:log(ERR, "(increase) redis_increase failed, falling back to local : " .. err)
		else
			counter = redis_counter
		end
	end
	-- Local case
	if not counter then
		local local_counter, err = self.datastore:get("plugin_badbehavior_count_" .. ip)
		if not local_counter and err ~= "not found" then
			logger:log(ERR, "(increase) can't get counts from the datastore : " .. err)
		end
		if local_counter == nil then
			local_counter = 0
		end
		counter = local_counter + 1
	end
	-- Store local counter
	local ok, err = self.datastore:set("plugin_badbehavior_count_" .. ip, counter, count_time)
	if not ok then
		self.logger:log(ERR, "(increase) can't save counts to the datastore : " .. err)
		return false, err
	end
	self.logger:log(
		NOTICE,
		"increased counter for IP " .. ip .. " (" .. tostring(counter) .. "/" .. tostring(threshold) .. ") on server " .. server_name .. " (status " .. status .. ")"
	)
	return counter, "success"
end

function badbehavior:decrease(ip, count_time, threshold, use_redis, server_name, status, old_counter)
	-- Declare counter
	local counter = false
	-- Redis case
	if use_redis then
		local redis_counter, err = self:redis_decrease(ip, count_time)
		if not redis_counter then
			self.logger:log(ERR, "(decrease) redis_decrease failed, falling back to local : " .. err)
		else
			counter = redis_counter
		end
	end
	-- Local case
	if not counter then
		local local_counter, err = self.datastore:get("plugin_badbehavior_count_" .. ip)
		if not local_counter and err ~= "not found" then
			self.logger:log(ERR, "(decrease) can't get counts from the datastore : " .. err)
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
		self.datastore:delete("plugin_badbehavior_count_" .. ip)
	else
		local ok, err = self.datastore:set("plugin_badbehavior_count_" .. ip, counter, count_time)
		if not ok then
			self.logger:log(ERR, "(decrease) can't save counts to the datastore : " .. err)
			return false, err
		end
	end
	self.logger:log(
		NOTICE,
		"decreased counter for IP " .. ip .. " (" .. tostring(counter) .. "/" .. tostring(threshold) .. ") on server " .. server_name .. " (status " .. status .. ")"
	)
	return true, "success"
end

function badbehavior:redis_increase(ip, count_time, ban_time)

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
	local ok, err = self.clusterstore:connect()
	if not ok then
		return false, err
	end
	-- Execute LUA script
	local counter, err =
		self.clusterstore:call("eval", redis_script, 2, "plugin_bad_behavior_" .. ip, "bans_ip" .. ip, count_time, ban_time)
	if not counter then
		self.clusterstore:close()
		return false, err
	end
	-- End connection
	self.clusterstore:close()
	return counter
end

function badbehavior:redis_decrease(ip, count_time)
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
	local ok, err = self.clusterstore:connect()
	if not ok then
		return false, err
	end
	local counter, err = self.clusterstore:call("eval", redis_script, 1, "plugin_bad_behavior_" .. ip, count_time)
	if not counter then
		self.clusterstore:close()
		return false, err
	end
	self.clusterstore:close()
	return counter
end

return badbehavior
