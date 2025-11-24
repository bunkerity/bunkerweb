local cjson = require "cjson"
local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local badbehavior = class("badbehavior", plugin)

local ngx = ngx
local var = ngx.var
local ERR = ngx.ERR
local WARN = ngx.WARN
local NOTICE = ngx.NOTICE
local worker = ngx.worker
local add_ban = utils.add_ban
local remove_ban = utils.remove_ban
local is_whitelisted = utils.is_whitelisted
local is_ip_whitelisted = utils.is_ip_whitelisted
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
	-- Fallback to whitelist lists/cache in case the request skipped the whitelist phase
	local wl_ip, wl_info = is_ip_whitelisted(self.ctx.bw.remote_addr, self.ctx.bw.server_name)
	if wl_ip == nil then
		self.logger:log(ERR, "can't check whitelist for IP " .. self.ctx.bw.remote_addr .. " : " .. wl_info)
	elseif wl_ip then
		self.ctx.bw.is_whitelisted = "yes"
		if var then
			var.is_whitelisted = "yes"
		end
		return self:ret(true, "client is whitelisted (ip lookup : " .. wl_info .. ")")
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
	if is_banned(self.ctx.bw.remote_addr, self.ctx.bw.server_name) then
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
	local ban_scope = self.variables["BAD_BEHAVIOR_BAN_SCOPE"]
	local ban_time = tonumber(self.variables["BAD_BEHAVIOR_BAN_TIME"]) or 0

	local ok, err = self.datastore.dict:rpush(
		"plugin_badbehavior_incr",
		encode({
			ip = self.ctx.bw.remote_addr,
			count_time = tonumber(self.variables["BAD_BEHAVIOR_COUNT_TIME"]),
			ban_time = ban_time,
			threshold = tonumber(self.variables["BAD_BEHAVIOR_THRESHOLD"]),
			use_redis = self.use_redis,
			server_name = self.ctx.bw.server_name,
			security_mode = security_mode,
			country = country,
			timestamp = time(date("!*t")),
			status = status,
			ban_scope = ban_scope,
		})
	)
	if not ok then
		return self:ret(false, "can't add incr operation : " .. err)
	end
	self:set_metric("counters", "status_" .. status, 1)
	self:set_metric("counters", "ip_" .. self.ctx.bw.remote_addr, 1)
	local request_uri = self.ctx.bw.request_uri or "-"
	self:set_metric("counters", "url_" .. request_uri, 1)
	self:set_metric("tables", "increments_" .. self.ctx.bw.remote_addr, {
		date = self.ctx.bw.start_time,
		id = self.ctx.bw.request_id,
		ip = self.ctx.bw.remote_addr,
		country = country,
		server_name = self.ctx.bw.server_name,
		status = status,
		method = self.ctx.bw.request_method or "-",
		url = request_uri,
		security_mode = security_mode,
		ban_scope = ban_scope,
		ban_time = ban_time,
		threshold = tonumber(self.variables["BAD_BEHAVIOR_THRESHOLD"]) or 0,
		count_time = tonumber(self.variables["BAD_BEHAVIOR_COUNT_TIME"]) or 0,
	})
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
	for _ = 1, decr_len do
		-- Pop operation
		local decr, decr_err = self.datastore:lpop("plugin_badbehavior_decr")
		if decr == nil then
			return self:ret(false, "can't get decr list element : " .. decr_err)
		end
		decr = decode(decr)
		if timestamp > decr["timestamp"] then
			-- Call decrease
			local ok, err = self:decrease(
				decr["ip"],
				decr["count_time"],
				decr["threshold"],
				decr["use_redis"],
				decr["server_name"],
				decr["status"],
				decr["old_counter"],
				decr["ban_scope"]
			)
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
	local incr_len, incr_err = self.datastore:llen("plugin_badbehavior_incr")
	if not incr_len then
		return self:ret(false, "can't get incr list length : " .. incr_err)
	end
	for _ = 1, incr_len do
		local incr_json, lpop_err = self.datastore:lpop("plugin_badbehavior_incr")
		if not incr_json then
			return self:ret(false, "can't get incr list element : " .. lpop_err)
		end
		local incr = decode(incr_json)
		local ip = incr.ip
		local count_time = incr.count_time
		local ban_time = incr.ban_time
		local threshold = incr.threshold
		local use_redis = incr.use_redis
		local server_name = incr.server_name
		local security_mode = incr.security_mode
		local country = incr.country
		local status = incr.status
		local ban_scope = incr.ban_scope or "global"
		local counter, counter_err = self:increase(
			ip,
			count_time,
			ban_time,
			threshold,
			use_redis,
			server_name,
			security_mode,
			country,
			status,
			ban_scope
		)
		if not counter then
			ret = false
			ret_err = "can't increase counter : " .. counter_err
		else
			-- Add decrease later
			local decr_payload = {
				ip = ip,
				old_counter = counter,
				count_time = count_time,
				threshold = threshold,
				use_redis = use_redis,
				timestamp = timestamp + count_time,
				server_name = server_name,
				status = status,
				ban_scope = ban_scope,
			}
			local ok, err = self.datastore.dict:rpush("plugin_badbehavior_decr", encode(decr_payload))
			if not ok then
				ret = false
				ret_err = "can't add decr list element : " .. err
			end
			-- Save counter info indexed by "ip_serverName"
			local counter_key = ip
			if ban_scope == "service" then
				counter_key = server_name .. "_" .. ip
			end
			counters[counter_key] = {
				ip = ip,
				counter = counter,
				count_time = count_time,
				ban_time = ban_time,
				threshold = threshold,
				use_redis = use_redis,
				server_name = server_name,
				security_mode = security_mode,
				country = country,
				status = status,
				ban_scope = ban_scope,
			}
		end
	end

	-- Add bans if needed
	for _, data in pairs(counters) do
		if data.counter >= data.threshold then
			local wl_ip, wl_info = is_ip_whitelisted(data.ip, data.server_name)
			if wl_ip == nil then
				self.logger:log(ERR, "can't check whitelist for IP " .. data.ip .. " : " .. wl_info)
			elseif wl_ip then
				local rm_ok, rm_err = remove_ban(data.ip, data.server_name, data.ban_scope)
				if rm_ok == false and rm_err then
					self.logger:log(ERR, "can't remove ban for whitelisted IP " .. data.ip .. " : " .. rm_err)
				end
				self.logger:log(
					NOTICE,
					string.format(
						"skipped badbehavior ban for whitelisted IP %s on server %s (scope %s, info %s)",
						data.ip,
						data.server_name,
						data.ban_scope,
						wl_info or "ip"
					)
				)
			elseif data.security_mode == "block" then
				local ban_time = tonumber(data.ban_time) or 0
				local reason_data = self:get_metric("tables", "increments_" .. data.ip) or {}
				local ok, err = add_ban(
					data.ip,
					"bad behavior",
					ban_time,
					data.server_name,
					data.country,
					data.ban_scope,
					reason_data
				)
				if not ok then
					ret = false
					ret_err = "can't save ban : " .. err
				else
					local ban_duration = ban_time == 0 and "permanently" or "for " .. ban_time .. "s"
					self.logger:log(
						WARN,
						string.format(
							"IP %s is banned %s (%s/%s) on server %s with scope %s",
							data.ip,
							ban_duration,
							tostring(data.counter),
							tostring(data.threshold),
							data.server_name,
							data.ban_scope
						)
					)
				end
			else
				local detection_msg = (tonumber(data.ban_time) or 0) == 0 and "permanently"
					or "for " .. tostring(data.ban_time) .. "s"
				self.logger:log(
					WARN,
					string.format(
						"detected IP %s ban %s (%s/%s) on server %s with scope %s",
						data.ip,
						detection_msg,
						tostring(data.counter),
						tostring(data.threshold),
						data.server_name,
						data.ban_scope
					)
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
	status,
	ban_scope
)
	-- Declare counter
	local counter = false
	local key_suffix = ip
	if ban_scope == "service" then
		key_suffix = server_name .. "_" .. ip
	end

	-- Redis case
	if use_redis then
		local redis_counter, err = self:redis_increase(ip, count_time, threshold, ban_time, server_name, ban_scope)
		if not redis_counter then
			self.logger:log(ERR, "(increase) redis_increase failed, falling back to local : " .. err)
		else
			counter = redis_counter
		end
	end
	-- Local case
	if not counter then
		local local_counter, err = self.datastore:get("plugin_badbehavior_count_" .. key_suffix)
		if not local_counter and err ~= "not found" then
			self.logger:log(ERR, "(increase) can't get counts from the datastore : " .. err)
		end
		if local_counter == nil then
			local_counter = 0
		end
		counter = local_counter + 1
	end
	-- Store local counter
	local ok, err = self.datastore:set_with_retries("plugin_badbehavior_count_" .. key_suffix, counter, count_time)
	if not ok then
		self.logger:log(ERR, "(increase) can't save counts to the datastore : " .. err)
		return false, err
	end
	self.logger:log(
		NOTICE,
		"increased counter for IP "
			.. ip
			.. " ("
			.. tostring(counter)
			.. "/"
			.. tostring(threshold)
			.. ") on server "
			.. server_name
			.. " (status "
			.. status
			.. ", scope "
			.. ban_scope
			.. ")"
	)
	return counter, "success"
end

function badbehavior:decrease(ip, count_time, threshold, use_redis, server_name, status, old_counter, ban_scope)
	-- Declare counter
	local counter = false
	local key_suffix = ip
	if ban_scope == "service" then
		key_suffix = server_name .. "_" .. ip
	end

	-- Redis case
	if use_redis then
		local redis_counter, err = self:redis_decrease(ip, count_time, server_name, ban_scope)
		if not redis_counter then
			self.logger:log(ERR, "(decrease) redis_decrease failed, falling back to local : " .. err)
		else
			counter = redis_counter
		end
	end
	-- Local case
	if not counter then
		local local_counter, err = self.datastore:get("plugin_badbehavior_count_" .. key_suffix)
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
		self.datastore:delete("plugin_badbehavior_count_" .. key_suffix)
	else
		local ok, err = self.datastore:set_with_retries("plugin_badbehavior_count_" .. key_suffix, counter, count_time)
		if not ok then
			self.logger:log(ERR, "(decrease) can't save counts to the datastore : " .. err)
			return false, err
		end
	end
	self.logger:log(
		NOTICE,
		"decreased counter for IP "
			.. ip
			.. " ("
			.. tostring(counter)
			.. "/"
			.. tostring(threshold)
			.. ") on server "
			.. server_name
			.. " (status "
			.. status
			.. ", scope "
			.. (ban_scope or "global")
			.. ")"
	)
	return true, "success"
end

function badbehavior:redis_increase(ip, count_time, threshold, ban_time, server_name, ban_scope)
	-- Determine key based on ban scope
	local counter_key = "plugin_bad_behavior_" .. ip
	local ban_key = "bans_ip_" .. ip
	if ban_scope == "service" then
		counter_key = "plugin_bad_behavior_" .. server_name .. "_" .. ip
		ban_key = "bans_service_" .. server_name .. "_ip_" .. ip
	end

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
		local threshold = tonumber(ARGV[2])
		local ban_time = tonumber(ARGV[3])
		if ret_incr >= threshold then
			-- For permanent bans (ban_time = 0), don't set an expiration
			if ban_time == 0 then
				local ret_set = redis.pcall("SET", KEYS[2], "bad behavior")
				if type(ret_set) == "table" and ret_set["err"] ~= nil then
					redis.log(redis.LOG_WARNING, "Bad behavior increase SET (permanent) error : " .. ret_set["err"])
					return ret_set
				end
			else
				local ret_set = redis.pcall("SET", KEYS[2], "bad behavior", "EX", ban_time)
				if type(ret_set) == "table" and ret_set["err"] ~= nil then
					redis.log(redis.LOG_WARNING, "Bad behavior increase SET error : " .. ret_set["err"])
					return ret_set
				end
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
		self.clusterstore:call("eval", redis_script, 2, counter_key, ban_key, count_time, threshold, ban_time)
	if not counter then
		self.clusterstore:close()
		return false, err
	end
	-- End connection
	self.clusterstore:close()
	return counter
end

function badbehavior:redis_decrease(ip, count_time, server_name, ban_scope)
	-- Determine key based on ban scope
	local counter_key = "plugin_bad_behavior_" .. ip
	if ban_scope == "service" then
		counter_key = "plugin_bad_behavior_" .. server_name .. "_" .. ip
	end

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
	local counter, err = self.clusterstore:call("eval", redis_script, 1, counter_key, count_time)
	if not counter then
		self.clusterstore:close()
		return false, err
	end
	self.clusterstore:close()
	return counter
end

return badbehavior
