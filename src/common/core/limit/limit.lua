local cjson = require "cjson"
local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local ratelimit = require "bunkerweb.ratelimit"
local utils = require "bunkerweb.utils"

local limit = class("limit", plugin)

-- What a client is allowed on the antibot endpoint, whatever the service's own rule says.
-- Four requests solve a challenge and a reload costs three more, so this leaves room for a
-- couple of attempts per second and no more.
local CHALLENGE_RATE = "10r/s"

local ngx = ngx
local ERR = ngx.ERR
local HTTP_TOO_MANY_REQUESTS = ngx.HTTP_TOO_MANY_REQUESTS
local get_phase = ngx.get_phase
local has_variable = utils.has_variable
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local is_whitelisted = utils.is_whitelisted
local regex_match = utils.regex_match
local get_security_mode = utils.get_security_mode
local ratelimit_incr = ratelimit.incr
local time = os.time
local date = os.date
local encode = cjson.encode
local decode = cjson.decode

local limit_req_timestamps = function(rate_max, rate_time, timestamps)
	-- Compute new timestamps
	local updated = false
	local new_timestamps = {}
	local current_timestamp = time(date("!*t"))
	local delay = 0
	if rate_time == "s" then
		delay = 1
	elseif rate_time == "m" then
		delay = 60
	elseif rate_time == "h" then
		delay = 3600
	elseif rate_time == "d" then
		delay = 86400
	end
	-- Keep only timestamp within the delay
	for _, timestamp in ipairs(timestamps) do
		if current_timestamp - timestamp <= delay then
			table.insert(new_timestamps, timestamp)
		else
			updated = true
		end
	end
	-- Only insert the new timestamp if client is not limited already to avoid infinite insert
	if #new_timestamps <= rate_max then
		table.insert(new_timestamps, current_timestamp)
		updated = true
	end
	return updated, new_timestamps, delay
end

function limit:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "limit", ctx)
	-- Load rules if needed
	if get_phase() ~= "init" and self:is_needed() then
		-- Get all rules from internalstore
		local all_rules, err = self.internalstore:get("plugin_limit_rules", true)
		if not all_rules then
			self.logger:log(ERR, err)
			return
		end
		self.rules = {}
		-- Extract global rules
		if all_rules.global then
			for k, v in pairs(all_rules.global) do
				self.rules[k] = v
			end
		end
		-- Extract and overwrite if needed server rules
		if all_rules[self.ctx.bw.server_name] then
			for k, v in pairs(all_rules[self.ctx.bw.server_name]) do
				self.rules[k] = v
			end
		end
		-- Get global (aggregate, per-service) rate, if any
		local all_global_rules, err = self.internalstore:get("plugin_limit_global_rules", true)
		if not all_global_rules then
			self.logger:log(ERR, err)
			return
		end
		self.global_rate = all_global_rules.global
		if all_global_rules[self.ctx.bw.server_name] then
			self.global_rate = all_global_rules[self.ctx.bw.server_name]
		end
	end
end

function limit:is_needed()
	-- Loading case
	if self.is_loading then
		return false
	end
	-- Request phases (no default)
	if self.is_request and (self.ctx.bw.server_name ~= "_") then
		return self.variables["USE_LIMIT_REQ"] == "yes" or self.variables["USE_LIMIT_REQ_GLOBAL"] == "yes"
	end
	-- Other cases : at least one service uses it
	local is_needed, err = has_variable("USE_LIMIT_REQ", "yes")
	if is_needed == nil then
		self.logger:log(ngx.ERR, "can't check USE_LIMIT_REQ variable : " .. err)
	end
	if not is_needed then
		local is_needed_global, err_global = has_variable("USE_LIMIT_REQ_GLOBAL", "yes")
		if is_needed_global == nil then
			self.logger:log(ngx.ERR, "can't check USE_LIMIT_REQ_GLOBAL variable : " .. err_global)
		end
		is_needed = is_needed_global
	end
	return is_needed
end

-- The URI antibot challenges on, or nil when the service does not challenge at all. Read from
-- the datastore rather than from self.variables : the settings belong to the antibot plugin.
function limit:antibot_uri()
	local use_antibot, err = get_variable("USE_ANTIBOT", true, self.ctx)
	if not use_antibot then
		if err then
			self.logger:log(ERR, "can't check USE_ANTIBOT variable : " .. err)
		end
		return nil
	end
	if use_antibot == "no" then
		return nil
	end
	local antibot_uri, uri_err = get_variable("ANTIBOT_URI", true, self.ctx)
	if not antibot_uri and uri_err then
		self.logger:log(ERR, "can't check ANTIBOT_URI variable : " .. uri_err)
	end
	return antibot_uri
end

function limit:init()
	-- Check if init is needed
	if not self:is_needed() then
		return self:ret(true, "no service uses limit for requests, skipping init")
	end
	-- Get variables
	local variables, err = get_multiple_variables({
		"USE_LIMIT_REQ",
		"LIMIT_REQ_URL",
		"LIMIT_REQ_RATE",
		"USE_LIMIT_REQ_GLOBAL",
		"LIMIT_REQ_GLOBAL_RATE",
	})
	if variables == nil then
		return self:ret(false, err)
	end
	-- Store URLs and rates
	local data = {}
	local global_data = {}
	local i = 0
	local g = 0
	for srv, vars in pairs(variables) do
		if vars["USE_LIMIT_REQ"] == "yes" then
			for var, value in pairs(vars) do
				if regex_match(var, "LIMIT_REQ_URL") then
					local url = value
					local rate = vars[var:gsub("URL", "RATE")]
					if data[srv] == nil then
						data[srv] = {}
					end
					data[srv][url] = rate
					i = i + 1
				end
			end
		end
		if vars["USE_LIMIT_REQ_GLOBAL"] == "yes" then
			-- A missing rate here would store nothing at all for the service and the aggregate
			-- limit would silently never apply, so say so instead of failing open in silence.
			if not vars["LIMIT_REQ_GLOBAL_RATE"] then
				self.logger:log(
					ERR,
					"USE_LIMIT_REQ_GLOBAL is yes for "
						.. srv
						.. " but LIMIT_REQ_GLOBAL_RATE is missing, no aggregate limit will apply"
				)
			else
				global_data[srv] = vars["LIMIT_REQ_GLOBAL_RATE"]
				g = g + 1
			end
		end
	end
	local ok, err = self.internalstore:set("plugin_limit_rules", data, nil, true)
	if not ok then
		return self:ret(false, err)
	end
	local ok_global, err_global = self.internalstore:set("plugin_limit_global_rules", global_data, nil, true)
	if not ok_global then
		return self:ret(false, err_global)
	end
	return self:ret(
		true,
		"successfully loaded " .. tostring(i) .. " limit rules and " .. tostring(g) .. " aggregate rates for requests"
	)
end

function limit:access()
	-- Check if we are whitelisted
	if is_whitelisted(self.ctx) then
		return self:ret(true, "client is whitelisted")
	end
	-- Check if access is needed
	if not self:is_needed() then
		return self:ret(true, "limit request not enabled")
	end

	local addr = self.ctx.bw.remote_addr

	-- Check global (aggregate, all clients and URLs) rate first : cheap O(1) circuit-breaker
	if self.global_rate then
		local global_rate_max, global_rate_time = self.global_rate:match("(%d+)r/(.)")
		global_rate_max = tonumber(global_rate_max)
		local limited, err, current_rate = self:limit_req_global(global_rate_max, global_rate_time)
		if limited == nil then
			return self:ret(false, err)
		end
		if limited then
			self:set_metric("counters", "limited_global", 1)
			local security_mode = get_security_mode(self.ctx)
			local msg
			if security_mode == "block" then
				msg = string.format(
					"client IP %s is limited by global rate limit (current rate = %sr/%s and max rate = %s)",
					addr,
					current_rate,
					global_rate_time,
					self.global_rate
				)
			else
				msg = string.format(
					"detected client IP %s would be limited by global rate limit (current rate = %sr/%s and max rate = %s)",
					addr,
					current_rate,
					global_rate_time,
					self.global_rate
				)
			end
			local data = {
				scope = "global",
				current_rate = current_rate,
				rate_time = global_rate_time,
				rate = self.global_rate,
			}
			return self:ret(true, msg, HTTP_TOO_MANY_REQUESTS, nil, data)
		end
	end

	-- Check if URI is limited
	local uri = self.ctx.bw.uri
	local rate = self.rules["/"]
	-- Keep the rule that matched : the counter below is keyed by it rather than by the raw
	-- URI, whose values come from the client and are unbounded.
	local matched_rule = "/"
	for pattern, r in pairs(self.rules) do
		if pattern ~= "/" and regex_match(uri, pattern) then
			rate = r
			matched_rule = pattern
			break
		end
	end

	-- The antibot endpoint runs on a fixed allowance instead of the service's rule. Solving a
	-- challenge costs several requests inside the second the client needs to solve it -- the
	-- redirect, the challenge page, cap.js's isolated widget iframe, then the POST carrying the
	-- token -- against a default LIMIT_REQ_RATE of 2r/s. The client we just redirected here was
	-- therefore limited on the very page that would let it through, with no way out: a reload
	-- costs two more requests. Deliberately an allowance and not an exemption -- a bot POSTing
	-- junk tokens still makes us call the captcha provider once per request.
	-- Only where a rule already applies: an endpoint the operator left unlimited stays that way.
	if rate and uri == self:antibot_uri() then
		rate = CHALLENGE_RATE
	end
	if not rate then
		return self:ret(true, "no rule for " .. uri)
	end
	-- Parse rate and extract the maximum limit and time unit
	local rate_max, rate_time = rate:match("(%d+)r/(.)")
	rate_max = tonumber(rate_max)
	local limited, err, current_rate = self:limit_req(rate_max, rate_time)
	if limited == nil then
		return self:ret(false, err)
	end

	if limited then
		self:set_metric("counters", "limited_uri_" .. matched_rule, 1)
		local security_mode = get_security_mode(self.ctx)
		local msg
		if security_mode == "block" then
			msg = string.format(
				"client IP %s is limited for URL %s (current rate = %sr/%s and max rate = %s)",
				addr,
				uri,
				current_rate,
				rate_time,
				rate
			)
		else
			msg = string.format(
				"detected client IP %s limit for URL %s (current rate = %sr/%s and max rate = %s)",
				addr,
				uri,
				current_rate,
				rate_time,
				rate
			)
		end
		local data = {
			uri = uri,
			current_rate = current_rate,
			rate_time = rate_time,
			rate = rate,
		}
		return self:ret(true, msg, HTTP_TOO_MANY_REQUESTS, nil, data)
	end

	local msg = string.format(
		"client IP %s is not limited for URL %s (current rate = %sr/%s and max rate = %s)",
		addr,
		uri,
		current_rate,
		rate_time,
		rate
	)
	return self:ret(true, msg)
end

-- Window length in seconds. Shared by limit_req (shm mirror TTL) and limit_req_global.
local function limit_global_delay(rate_time)
	if rate_time == "s" then
		return 1
	elseif rate_time == "m" then
		return 60
	elseif rate_time == "h" then
		return 3600
	elseif rate_time == "d" then
		return 86400
	end
	return 1
end

function limit:limit_req(rate_max, rate_time)
	local timestamps = nil
	-- Redis case
	if self.use_redis then
		local redis_timestamps, err = self:limit_req_redis(rate_max, rate_time)
		if redis_timestamps == nil then
			self.logger:log(ERR, "limit_req_redis failed, falling back to local : " .. err)
		else
			timestamps = redis_timestamps
			-- Save the new timestamps. The TTL used to be a bare `delay`, a global that
			-- nothing in the tree ever assigned : it was always nil, datastore mapped
			-- nil to "no expiry", and every plugin_limit_<service><ip><uri> mirror key
			-- lived forever until the shared dict ran out of memory.
			-- luacheck: ignore 421
			local ok, err = self.datastore:set_with_retries(
				"plugin_limit_" .. self.ctx.bw.server_name .. self.ctx.bw.remote_addr .. self.ctx.bw.uri,
				encode(timestamps),
				limit_global_delay(rate_time)
			)
			if not ok then
				return nil, "can't update timestamps : " .. err
			end
		end
	end
	-- Local case (or fallback)
	if timestamps == nil then
		local local_timestamps, err = self:limit_req_local(rate_max, rate_time)
		if local_timestamps == nil then
			return nil, "limit_req_local failed : " .. err
		end
		timestamps = local_timestamps
	end
	if #timestamps > rate_max then
		return true, "success - limited", #timestamps
	end
	return false, "success - not limited", #timestamps
end

function limit:limit_req_local(rate_max, rate_time)
	-- Get timestamps
	local timestamps, err =
		self.datastore:get("plugin_limit_" .. self.ctx.bw.server_name .. self.ctx.bw.remote_addr .. self.ctx.bw.uri)
	if not timestamps and err ~= "not found" then
		return nil, err
	elseif err == "not found" then
		timestamps = "{}"
	end
	timestamps = decode(timestamps)
	-- Compute new timestamps
	local updated, new_timestamps, delay = limit_req_timestamps(rate_max, rate_time, timestamps)
	-- Save new timestamps if needed
	if updated then
		-- luacheck: ignore 421
		local ok, err = self.datastore:set_with_retries(
			"plugin_limit_" .. self.ctx.bw.server_name .. self.ctx.bw.remote_addr .. self.ctx.bw.uri,
			encode(new_timestamps),
			delay
		)
		if not ok then
			return nil, err
		end
	end
	return new_timestamps, "success"
end

function limit:limit_req_redis(rate_max, rate_time)
	-- Redis atomic script
	local redis_script = [[
		local ret_get = redis.pcall("GET", KEYS[1])
		if type(ret_get) == "table" and ret_get["err"] ~= nil then
			redis.log(redis.LOG_WARNING, "limit GET error : " .. ret_get["err"])
			return ret_get
		end
		local timestamps = {}
		if ret_get then
			timestamps = cjson.decode(ret_get)
		end
		-- Keep only timestamps within the delay
		local updated = false
		local new_timestamps = {}
		local rate_max = tonumber(ARGV[1])
		local rate_time = ARGV[2]
		local current_timestamp = tonumber(ARGV[3])
		local delay = 0
		if rate_time == "s" then
			delay = 1
		elseif rate_time == "m" then
			delay = 60
		elseif rate_time == "h" then
			delay = 3600
		elseif rate_time == "d" then
			delay = 86400
		end
		for i, timestamp in ipairs(timestamps) do
			if current_timestamp - timestamp <= delay then
				table.insert(new_timestamps, timestamp)
			else
				updated = true
			end
		end
		-- Only insert the new timestamp if client is not limited already to avoid infinite insert
		if #new_timestamps <= rate_max then
			table.insert(new_timestamps, current_timestamp)
			updated = true
		end
		-- Save new timestamps if needed
		if updated then
			local ret_set = redis.pcall("SET", KEYS[1], cjson.encode(new_timestamps), "EX", delay)
			if type(ret_set) == "table" and ret_set["err"] ~= nil then
				redis.log(redis.LOG_WARNING, "limit SET error : " .. ret_set["err"])
				return ret_set
			end
		end
		return new_timestamps
	]]
	-- Connect
	local ok, err = self.clusterstore:connect()
	if not ok then
		return nil, err
	end
	-- Execute script
	local timestamps, err = self.clusterstore:call(
		"eval",
		redis_script,
		1,
		"plugin_limit_" .. self.ctx.bw.server_name .. self.ctx.bw.remote_addr .. self.ctx.bw.uri,
		rate_max,
		rate_time,
		time(date("!*t"))
	)
	if not timestamps then
		self.clusterstore:close()
		return nil, err
	end
	-- Return timestamps
	self.clusterstore:close()
	return timestamps, "success"
end

-- Global (aggregate, per-service) rate limit : fixed-window counter, not the timestamp
-- log used above. The log is O(n) per request (n = rate_max) which is fine at the
-- existing low per-IP defaults but too costly at the hundreds/thousands of req/s a
-- global cap runs at. A fixed-window counter is O(1) per request.
-- The counter itself lives in bunkerweb.ratelimit so the workflow rate gates share it;
-- the key, the window arithmetic and the Redis-then-local fallback are unchanged, and the
-- limited/not-limited decision deliberately stays here where the settings are.
function limit:limit_req_global(rate_max, rate_time)
	local count, err =
		ratelimit_incr(self, "plugin_limit_global_" .. self.ctx.bw.server_name, limit_global_delay(rate_time))
	if count == nil then
		return nil, "limit_req_global_local failed : " .. err
	end
	if count > rate_max then
		return true, "success - limited", count
	end
	return false, "success - not limited", count
end

return limit
