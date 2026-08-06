local ngx = ngx
local cdatastore = require "bunkerweb.datastore"
local clogger = require "bunkerweb.logger"
local mmdb = require "bunkerweb.mmdb"

local cjson = require "cjson"
local ipmatcher = require "resty.ipmatcher"
local random = require "resty.random"
local resolver = require "resty.dns.resolver"
local resty_lock = require "resty.lock"
local session = require "resty.session"

local logger = clogger:new("UTILS")

local var = ngx.var
local ERR = ngx.ERR
local INFO = ngx.INFO
local WARN = ngx.WARN
local HTTP_FORBIDDEN = ngx.HTTP_FORBIDDEN
local HTTP_CLOSE = ngx.HTTP_CLOSE or 444
local null = ngx.null
local re_match = ngx.re.match
local subsystem = ngx.config.subsystem
local get_phase = ngx.get_phase
local kill = ngx.thread.kill
local ipmatcher_new = ipmatcher.new
local parse_ipv4 = ipmatcher.parse_ipv4
local parse_ipv6 = ipmatcher.parse_ipv6
local open = io.open
local encode = cjson.encode
local decode = cjson.decode
local bytes = random.bytes
local char = string.char
local session_start = session.start
local tonumber = tonumber

local shared = ngx.shared
local math_ceil = math.ceil
local math_min = math.min
local math_max = math.max
local wall_time = ngx.now or os.time

local datastore = cdatastore:new()
local internalstore
local ban_epoch_store
local stream_syncstore

if subsystem == "http" then
	internalstore = cdatastore:new(shared.internalstore)
	ban_epoch_store = cdatastore:new(shared.ban_sync)
else
	internalstore = cdatastore:new(shared.internalstore_stream)
	stream_syncstore = cdatastore:new(shared.ban_sync_stream)
end

local internal_api = subsystem == "stream" and require "bunkerweb.internal_api" or nil
local BAN_EPOCH_KEY = "ban_snapshot_epoch"
local BAN_SNAPSHOT_KEY = "ban_snapshot"
local BAN_SNAPSHOT_LOCK_KEY = "ban_snapshot_mutation"
local BAN_SNAPSHOT_LOCK_OPTIONS = { timeout = 10, exptime = 30 }
local INTERNAL_API_TIMEOUT = 1000

-- Short TTL for locally cached HTTP bans so unbans propagate from Redis.
local BAN_LOCAL_CACHE_TTL = 30

local utils = {}

local function ensure_ban_epoch()
	if not ban_epoch_store then
		return false, "ban epoch is only available in the HTTP subsystem"
	end
	local ok, err = ban_epoch_store.dict:safe_add(BAN_EPOCH_KEY, 0)
	if not ok and err ~= "exists" then
		return false, "can't initialize ban snapshot epoch without eviction : " .. tostring(err)
	end
	return true
end

local function get_ban_epoch()
	local ok, err = ensure_ban_epoch()
	if not ok then
		return nil, err
	end
	local epoch
	epoch, err = ban_epoch_store:get(BAN_EPOCH_KEY)
	if epoch == nil then
		return nil, "can't read ban snapshot epoch : " .. tostring(err)
	end
	epoch = tonumber(epoch)
	if not epoch or epoch < 0 or epoch % 1 ~= 0 then
		return nil, "invalid ban snapshot epoch"
	end
	return epoch
end

local function advance_ban_epoch()
	local ok, err = ensure_ban_epoch()
	if not ok then
		return nil, err
	end
	local epoch
	epoch, err = ban_epoch_store.dict:incr(BAN_EPOCH_KEY, 1)
	if not epoch then
		return nil, "can't advance ban snapshot epoch : " .. tostring(err)
	end
	return epoch
end

local function with_ban_snapshot_lock(callback)
	if subsystem ~= "http" then
		return false, "ban snapshot lock is only available in the HTTP subsystem"
	end
	local lock, err = resty_lock:new("cachestore_locks", BAN_SNAPSHOT_LOCK_OPTIONS)
	if not lock then
		return false, "can't create ban snapshot lock : " .. tostring(err)
	end
	local elapsed
	elapsed, err = lock:lock(BAN_SNAPSHOT_LOCK_KEY)
	if elapsed == nil then
		return false, "can't acquire ban snapshot lock : " .. tostring(err)
	end

	local call_ok, result, result_err = pcall(callback)
	local unlock_ok, unlock_err = lock:unlock()
	if not call_ok then
		error(result, 0)
	end
	if not unlock_ok then
		return false, "can't release ban snapshot lock : " .. tostring(unlock_err)
	end
	return result, result_err
end

utils.get_ban_epoch = get_ban_epoch
utils.next_ban_snapshot_epoch = advance_ban_epoch
utils.with_ban_snapshot_lock = with_ban_snapshot_lock

local stream_snapshot_raw
local stream_snapshot
local EMPTY_STREAM_SNAPSHOT = { generation_epoch = 0, bans = {} }

local function get_stream_snapshot()
	local raw, err = stream_syncstore:get(BAN_SNAPSHOT_KEY)
	if not raw then
		if err == "not found" then
			return EMPTY_STREAM_SNAPSHOT
		end
		return nil, "can't read Stream ban snapshot : " .. tostring(err)
	end
	if raw == stream_snapshot_raw then
		return stream_snapshot
	end
	local ok, decoded = pcall(decode, raw)
	if
		not ok
		or type(decoded) ~= "table"
		or type(decoded.bans) ~= "table"
		or type(decoded.generation_epoch) ~= "number"
	then
		return nil, "invalid Stream ban snapshot"
	end
	stream_snapshot_raw = raw
	stream_snapshot = decoded
	return decoded
end

local function forward_stream_ban(path, payload)
	payload.not_after = wall_time() + (INTERNAL_API_TIMEOUT / 1000)
	local encoded_ok, body = pcall(encode, payload)
	if not encoded_ok then
		local err = "can't encode Stream ban mutation : " .. tostring(body)
		logger:log(ERR, err .. " (not queued for retry)")
		return false, err
	end

	local call_ok, response, request_err = pcall(internal_api.request, path, {
		method = "POST",
		timeout = INTERNAL_API_TIMEOUT,
		headers = { ["Content-Type"] = "application/json" },
		body = body,
	})
	if not call_ok then
		request_err = "internal API request raised : " .. tostring(response)
		response = nil
	end
	if not response then
		local err = request_err or "internal API request failed"
		logger:log(ERR, err .. " (Stream ban mutation not queued for retry)")
		return false, err
	end
	if response.status ~= 200 then
		local err = "internal API returned HTTP " .. tostring(response.status)
		logger:log(ERR, err .. " (Stream ban mutation not queued for retry)")
		return false, err
	end
	return true, "success"
end

math.randomseed(os.time())

utils.get_variable = function(variable, site_search, ctx)
	-- Default site search to true
	if site_search == nil then
		site_search = true
	end
	-- Get global value
	local variables, err = internalstore:get("variables", true)
	if not variables then
		return nil, "can't access variables from internalstore : " .. err
	end
	local value = variables["global"][variable]
	-- Site search case
	if site_search and variables["global"]["MULTISITE"] == "yes" then
		local server_name
		if ctx and ctx.bw then
			server_name = ctx.bw.server_name
		else
			server_name = var.server_name
		end
		if variables[server_name] then
			value = variables[server_name][variable]
		end
	end
	if value == nil then
		return nil, "not found"
	end
	return value, "success"
end

utils.has_variable = function(variable, value)
	-- Get global variable
	local variables, err = internalstore:get("variables", true)
	if not variables then
		return nil, "can't access variables " .. variable .. " from internalstore : " .. err
	end
	-- Multisite case
	local multisite = variables["global"]["MULTISITE"] == "yes"
	if multisite then
		local servers = variables["global"]["SERVER_NAME"]
		-- Check each server
		for server in servers:gmatch("%S+") do
			if variables[server][variable] == value then
				return true, "success"
			end
		end
		if servers ~= "" then
			return false, "success"
		end
	end
	return variables["global"][variable] == value, "success"
end

utils.has_not_variable = function(variable, value)
	-- Get global variable
	local variables, err = internalstore:get("variables", true)
	if not variables then
		return nil, "can't access variables " .. variable .. " from internalstore : " .. err
	end
	-- Multisite case
	local multisite = variables["global"]["MULTISITE"] == "yes"
	if multisite then
		local servers = variables["global"]["SERVER_NAME"]
		-- Check each server
		for server in servers:gmatch("%S+") do
			if variables[server][variable] ~= "value" then
				return true, "success"
			end
		end
		if servers ~= "" then
			return false, "success"
		end
	end
	return variables["global"][variable] ~= value, "success"
end

utils.get_multiple_variables = function(vars)
	local variables, err = internalstore:get("variables", true)
	if not variables then
		return nil, "can't access variables " .. vars .. " from internalstore : " .. err
	end
	local result = {}
	-- Loop on scoped vars
	for scope, scoped_vars in pairs(variables) do
		result[scope] = {}
		-- Loop on vars
		for variable, value in pairs(scoped_vars) do
			for _, tvar in ipairs(vars) do
				if variable:find("^" .. tvar .. "_?[0-9]*$") then
					result[scope][variable] = value
				end
			end
		end
	end
	return result
end

utils.is_ip_in_networks = function(ip, networks)
	-- Instantiate ipmatcher
	local ipm, err = ipmatcher_new(networks)
	if not ipm then
		return nil, "can't instantiate ipmatcher : " .. err
	end
	-- Match
	local matched, err = ipm:match(ip)
	if err then
		return nil, "can't check ip : " .. err
	end
	return matched
end

utils.is_ipv4 = function(ip)
	return parse_ipv4(ip)
end

utils.is_ipv6 = function(ip)
	return parse_ipv6(ip)
end

utils.ip_is_global = function(ip)
	-- Reserved, non public IPs
	local reserved_ips = {
		"0.0.0.0/8",
		"10.0.0.0/8",
		"100.64.0.0/10",
		"127.0.0.0/8",
		"169.254.0.0/16",
		"172.16.0.0/12",
		"192.0.0.0/24",
		"192.88.99.0/24",
		"192.168.0.0/16",
		"198.18.0.0/15",
		"198.51.100.0/24",
		"203.0.113.0/24",
		"224.0.0.0/4",
		"233.252.0.0/24",
		"240.0.0.0/4",
		"255.255.255.255/32",
		"::/128",
		"::1/128",
		"::ffff:0:0/96",
		"::ffff:0:0:0/96",
		"64:ff9b::/96",
		"64:ff9b:1::/48",
		"100::/64",
		"2001:0000::/32",
		"2001:20::/28",
		"2001:db8::/32",
		"2002::/16",
		"fc00::/7",
		"fe80::/10",
		"ff00::/8",
	}
	-- Instantiate ipmatcher
	local ipm, err = ipmatcher_new(reserved_ips)
	if not ipm then
		return nil, "can't instantiate ipmatcher : " .. err
	end
	-- Match
	local matched, err = ipm:match(ip)
	if err then
		return nil, "can't check ip : " .. err
	end
	return not matched, "success"
end

utils.get_integration = function(ctx)
	-- Check if already in ctx
	if ctx and ctx.bw.integration then
		return ctx.bw.integration
	end
	-- Check if already in internalstore
	local integration, _ = internalstore:get("misc_integration", true)
	if integration then
		return integration
	end
	local variables, err = internalstore:get("variables", true)
	if not variables then
		logger:log(ERR, "can't get variables from internalstore : " .. err)
		return "unknown"
	end
	-- Swarm
	if variables["global"]["SWARM_MODE"] == "yes" then
		integration = "swarm"
	else
		-- Kubernetes
		if variables["global"]["KUBERNETES_MODE"] == "yes" then
			integration = "kubernetes"
		else
			-- Autoconf
			if variables["global"]["AUTOCONF_MODE"] == "yes" then
				integration = "autoconf"
			else
				-- Already present (e.g. : linux)
				local f, _ = open("/usr/share/bunkerweb/INTEGRATION", "r")
				if f then
					integration = f:read("*a"):gsub("[\n\r]", "")
					f:close()
				else
					f, _ = open("/etc/os-release", "r")
					if f then
						local data = f:read("*a")
						f:close()
						-- Docker
						if data:find("Alpine") then
							integration = "docker"
						end
						-- Strange case ...
					else
						integration = "unknown"
					end
				end
			end
		end
	end
	-- Save integration
	local ok, err = internalstore:set("misc_integration", integration, nil, true)
	if not ok then
		logger:log(ERR, "can't cache integration to internalstore : " .. err)
	end
	if ctx then
		ctx.bw.integration = integration
	end
	return integration
end

utils.get_version = function(ctx)
	-- Check if already in ctx
	if ctx and ctx.bw.version then
		return ctx.bw.version
	end
	-- Check if already in internalstore
	local version, _ = internalstore:get("misc_version", true)
	if version then
		return version
	end
	-- Read VERSION file
	local f, err = open("/usr/share/bunkerweb/VERSION", "r")
	if not f then
		logger:log(ERR, "can't read VERSION file : " .. err)
		return nil
	end
	version = f:read("*a"):gsub("[\n\r]", "")
	f:close()
	-- Save version
	local ok, err = internalstore:set("misc_version", version, nil, true)
	if not ok then
		logger:log(ERR, "can't cache version to internalstore : " .. err)
	end
	if ctx then
		ctx.bw.version = version
	end
	return version
end

utils.get_reason = function(ctx)
	-- ngx.ctx
	local security_mode
	if ctx and ctx.bw then
		security_mode = ctx.bw.security_mode or utils.get_security_mode(ctx)
		if ctx.bw.reason then
			return ctx.bw.reason, ctx.bw.reason_data or {}, security_mode
		end
	end
	security_mode = security_mode or utils.get_security_mode(ctx)
	-- ngx.var
	local var_reason = var.reason
	if var_reason and var_reason ~= "" then
		local reason_data = {}
		local var_reason_data = var.reason_data
		if var_reason_data and reason_data ~= "" then
			local ok, data = pcall(decode, var_reason_data)
			if ok then
				reason_data = data
			end
		end
		return var_reason, reason_data, security_mode
	end
	-- ngx.var / modsecurity
	if ngx.var.modsecurity_reason == "modsecurity" then
		local reason_data = {}

		-- Handle IDs
		local env_reason_data_ids = ngx.var.modsecurity_rules
		if env_reason_data_ids and env_reason_data_ids ~= "" and env_reason_data_ids ~= "none" then
			if env_reason_data_ids:sub(1, 1) == " " then
				env_reason_data_ids = env_reason_data_ids:sub(2)
			end
			reason_data["ids"] = {}
			for rule_id in env_reason_data_ids:gmatch("%S+") do
				table.insert(reason_data["ids"], rule_id)
			end
		end

		-- Handle messages, matched_vars, and matched_var_names
		local env_unique_id_separator = ngx.var.modsecurity_unique_id
		local data_types = {
			{ key = "msgs", env_var = "modsecurity_msgs" },
			{ key = "matched_vars", env_var = "modsecurity_matched_vars" },
			{ key = "matched_var_names", env_var = "modsecurity_matched_var_names" },
			{ key = "anomaly_score", env_var = "modsecurity_anomaly_score" },
		}

		for _, data_type in ipairs(data_types) do
			local env_data = ngx.var[data_type.env_var]
			if env_data and env_data ~= "" and env_data ~= "none" and env_unique_id_separator then
				-- Remove leading |separator| if present
				local separator_pattern = "|" .. env_unique_id_separator .. "|"
				if env_data:sub(1, #separator_pattern) == separator_pattern then
					env_data = env_data:sub(#separator_pattern + 1)
				end
				reason_data[data_type.key] = {}
				-- Split by |separator| pattern
				local remaining = env_data
				while remaining and remaining ~= "" do
					local separator_pos = remaining:find("|" .. env_unique_id_separator .. "|", 1, true)
					if separator_pos then
						local item = remaining:sub(1, separator_pos - 1)
						if item and item ~= "" then
							table.insert(reason_data[data_type.key], item)
						end
						remaining = remaining:sub(separator_pos + #separator_pattern)
					else
						-- Last item (no separator after)
						if remaining and remaining ~= "" then
							table.insert(reason_data[data_type.key], remaining)
						end
						break
					end
				end
			end
		end

		return "modsecurity", reason_data, security_mode
	end
	-- datastore ban
	local ip
	if ctx and ctx.bw then
		ip = ctx.bw.remote_addr
	else
		ip = var.remote_addr
	end
	local banned, _ = datastore:get("bans_ip_" .. ip)
	if banned then
		local ok, ban_data = pcall(decode, banned)
		if ok then
			banned = ban_data["reason"]
		end
		return banned, {}, security_mode
	end
	-- unknown
	if ngx.status == utils.get_deny_status() then
		return "unknown", {}
	end
	return nil
end

utils.set_reason = function(reason, reason_data, ctx, security_mode)
	if ctx and ctx.bw then
		ctx.bw.reason = reason or "unknown"
		ctx.bw.reason_data = reason_data or {}
		ctx.bw.security_mode = security_mode or utils.get_security_mode(ctx)
	end
	if var.reason then
		var.reason = reason
		if var.reason_data then
			var.reason_data = encode(reason_data or {})
		end
	end
end

utils.is_whitelisted = function(ctx)
	-- ngx.ctx
	if ctx and ctx.bw and ctx.bw.is_whitelisted then
		return ctx.bw.is_whitelisted == "yes"
	end
	-- ngx.var
	if var.is_whitelisted and var.is_whitelisted == "yes" then
		return true
	end
	return false
end

utils.is_ip_whitelisted = function(ip, server_name)
	if not ip then
		return nil, "ip is nil"
	end
	-- Allow caller to provide service name; otherwise use current server_name
	if not server_name or server_name == "" then
		server_name = var.server_name
	end

	-- Helper to check a specific service whitelist list
	local function check_service(name)
		if not name or name == "" then
			return nil, "no service name"
		end
		-- Fast path: check whitelist cache for the service
		local cache = require("bunkerweb.cachestore"):new(false)
		local ok_cache, cached = cache:get("plugin_whitelist_" .. name .. "ip" .. ip)
		if not ok_cache then
			return nil, "can't check whitelist cache : " .. cached
		end
		if cached then
			if cached ~= "ok" then
				return true, cached
			end
			return false, "ok"
		end

		local lists, err = internalstore:get("plugin_whitelist_lists_" .. name, true)
		if not lists then
			return nil, "can't get whitelist lists : " .. err
		end
		if not lists["IP"] or #lists["IP"] == 0 then
			return false, "ok"
		end
		local ipm, ipm_err = ipmatcher_new(lists["IP"])
		if not ipm then
			return nil, "can't instantiate ipmatcher : " .. ipm_err
		end
		local match, match_err = ipm:match(ip)
		if match_err then
			return nil, "can't check ip : " .. match_err
		end
		if match then
			return true, "ip"
		end
		return false, "ok"
	end

	-- First try the current service (except default placeholder "_")
	if server_name and server_name ~= "" and server_name ~= "_" then
		local ok, info = check_service(server_name)
		if ok ~= nil then
			return ok, info
		end
	end

	-- Fallback: iterate all configured services (covers default-server paths)
	local variables, err = internalstore:get("variables", true)
	if not variables then
		return nil, "can't get variables : " .. err
	end
	local servers = variables["global"] and variables["global"]["SERVER_NAME"] or ""
	for srv in servers:gmatch("%S+") do
		local ok, info = check_service(srv)
		if ok then
			return true, info
		end
	end

	-- Last resort: check global whitelist IPs directly (useful when no services matched)
	local global_wl = variables["global"] and variables["global"]["WHITELIST_IP"] or ""
	if global_wl ~= "" then
		local networks = {}
		for n in global_wl:gmatch("%S+") do
			table.insert(networks, n)
		end
		if #networks > 0 then
			local ipm, ipm_err = ipmatcher_new(networks)
			if not ipm then
				return nil, "can't instantiate ipmatcher : " .. (ipm_err or "unknown")
			end
			local match, match_err = ipm:match(ip)
			if match_err then
				return nil, "can't check ip : " .. match_err
			end
			if match then
				return true, "ip"
			end
		end
	end

	return false, "ok"
end

utils.get_resolvers = function()
	-- Get resolvers from internalstore if existing
	local resolvers, _ = internalstore:get("misc_resolvers", true)
	if resolvers then
		return resolvers
	end
	-- Otherwise extract DNS_RESOLVERS variable
	local variables, err = internalstore:get("variables", true)
	if not variables then
		logger:log(ERR, "can't get variables from internalstore : " .. err)
		return "unknown"
	end
	-- Make table for resolver1 resolver2 ... string
	resolvers = {}
	for str_resolver in variables["global"]["DNS_RESOLVERS"]:gmatch("%S+") do
		table.insert(resolvers, str_resolver)
	end
	-- Add it to the internalstore
	local ok, err = internalstore:set("misc_resolvers", resolvers, nil, true)
	if not ok then
		logger:log(ERR, "can't save misc_resolvers to internalstore : " .. err)
	end
	return resolvers
end

utils.get_rdns = function(ip, ctx, pool)
	-- Check cache
	local cachestore = utils.new_cachestore(ctx, pool)
	local ok, value = cachestore:get("rdns_" .. ip)
	if not ok then
		logger:log(ERR, "can't get rdns from cachestore : " .. value)
	elseif value then
		return decode(value), "success"
	end
	-- Get resolvers
	local resolvers, err = utils.get_resolvers()
	if not resolvers then
		return false, err
	end
	-- Instantiate resolver
	local rdns, err = resolver:new {
		nameservers = resolvers,
		retrans = 1,
		timeout = 1000,
	}
	if not rdns then
		return false, err
	end
	-- Our results
	local ptrs = {}
	local ret_err = "success"
	-- Do rDNS query
	local answers, err = rdns:reverse_query(ip)
	if not answers then
		logger:log(WARN, "error while doing reverse DNS query for " .. ip .. " : " .. err)
		ret_err = err
	else
		if answers.errcode then
			ret_err = answers.errstr
		end
		-- Extract all PTR
		for _, answer in ipairs(answers) do
			if answer.ptrdname then
				table.insert(ptrs, answer.ptrdname)
			end
		end
	end
	-- Save to cache
	ok, err = cachestore:set("rdns_" .. ip, encode(ptrs), 3600)
	if not ok then
		logger:log(ERR, "can't set rdns into cachestore : " .. err)
	end
	return ptrs, ret_err
end

utils.get_ips = function(fqdn, ipv6, ctx, pool)
	-- Check cache
	local cachestore = utils.new_cachestore(ctx, pool)
	local ok, value = cachestore:get("dns_" .. fqdn)
	if not ok then
		logger:log(ERR, "can't get dns from cachestore : " .. value)
	elseif value then
		return decode(value), "success"
	end
	-- By default perform ipv6 lookups (only if USE_IPV6=yes)
	if ipv6 == nil then
		ipv6 = true
	end
	-- Get resolvers
	local resolvers, err = utils.get_resolvers()
	if not resolvers then
		return false, err
	end
	-- Instantiante resolver
	local res, err = resolver:new {
		nameservers = resolvers,
		retrans = 1,
		timeout = 1000,
	}
	if not res then
		return false, err
	end
	-- Get query types : AAAA and A if using IPv6 / only A if not using IPv6
	local qtypes = {}
	if ipv6 then
		-- luacheck: ignore 421
		local use_ipv6, err = utils.get_variable("USE_IPV6", false)
		if not use_ipv6 then
			logger:log(ERR, "can't get USE_IPV6 variable " .. err)
		elseif use_ipv6 == "yes" then
			table.insert(qtypes, res.TYPE_AAAA)
		end
	end
	table.insert(qtypes, res.TYPE_A)
	-- Loop on qtypes
	local res_answers = {}
	local res_errors = {}
	local ans_errors = {}
	local answers
	for _, qtype in ipairs(qtypes) do
		-- Query FQDN
		answers, err = res:query(fqdn, { qtype = qtype }, {})
		local qtype_str = qtype == res.TYPE_AAAA and "AAAA" or "A"
		if not answers then
			res_errors[qtype_str] = err
		elseif answers.errcode then
			ans_errors[qtype_str] = answers.errstr
		else
			table.insert(res_answers, answers)
		end
	end
	for qtype, error in pairs(res_errors) do
		logger:log(ERR, "error while doing " .. qtype .. " DNS query for " .. fqdn .. " : " .. error)
	end
	-- Extract all IPs
	local ips = {}
	-- luacheck: ignore 421
	for _, answers in ipairs(res_answers) do
		for _, answer in ipairs(answers) do
			if answer.address then
				table.insert(ips, answer.address)
			end
		end
	end
	-- Save to cache
	ok, err = cachestore:set("dns_" .. fqdn, encode(ips), 3600)
	if not ok then
		logger:log(ERR, "can't set dns into cachestore : " .. err)
	end
	return ips, encode(res_errors) .. " " .. encode(ans_errors)
end

-- Forward-confirmed reverse DNS (FCrDNS) suffix check.
-- For each PTR in rdns_list, if it ends with any suffix in suffix_list, the name is forward-resolved
-- (A/AAAA via get_ips) and each result compared to remote_addr. Returns (matched_suffix, matched_rdns)
-- only when a suffix match is forward-confirmed; returns nil otherwise.
-- Fail-closed: a suffix match that cannot be confirmed (resolver error, or empty/non-matching forward
-- result) returns nil and is logged as a possible spoof. An empty get_ips table needs no special case:
-- the inner loop runs zero times, so no match occurs and execution falls to the spoof branch.
utils.rdns_forward_confirmed = function(rdns_list, suffix_list, ctx, remote_addr, plugin_logger)
	if not rdns_list or not suffix_list then
		return nil
	end
	for _, rdns in ipairs(rdns_list) do
		for _, suffix in ipairs(suffix_list) do
			if rdns:sub(-#suffix) == suffix then
				local ip_list, err = utils.get_ips(rdns, nil, ctx, true)
				if ip_list then
					for _, ip in ipairs(ip_list) do
						if ip == remote_addr then
							return suffix, rdns
						end
					end
					if plugin_logger then
						plugin_logger:log(WARN, "IP " .. remote_addr .. " may spoof reverse DNS " .. rdns)
					end
				elseif plugin_logger then
					plugin_logger:log(ERR, "error while getting rdns (forward check) : " .. err)
				end
			end
		end
	end
	return nil
end

utils.get_country = function(ip)
	-- Check if mmdb is loaded
	if not mmdb.country_db then
		return false, "mmdb country not loaded"
	end
	-- Perform lookup
	local ok, result, err = pcall(mmdb.country_db.lookup, mmdb.country_db, ip)
	if not ok then
		return nil, result
	end
	if not result then
		return nil, err
	end
	return result.country.iso_code, "success"
end

utils.get_city = function(ip)
	-- Optional database : GEOIP_CITY is off by default and nothing is bundled
	if not mmdb.city_db then
		return false, "mmdb city not loaded"
	end
	-- Read the single field we expose instead of decoding the whole record : a city
	-- entry carries every language and subdivision, which is wasteful per request
	local ok, result, err = pcall(mmdb.city_db.lookup_value, mmdb.city_db, ip, "city", "names", "en")
	if not ok then
		return nil, result
	end
	if not result then
		return nil, err
	end
	return result, "success"
end

utils.get_asn = function(ip)
	-- Check if mmdp is loaded
	if not mmdb.asn_db then
		return false, nil, "mmdb asn not loaded"
	end
	-- Perform lookup
	local ok, result, err = pcall(mmdb.asn_db.lookup, mmdb.asn_db, ip)
	if not ok then
		return nil, nil, result
	end
	if not result then
		return nil, nil, err
	end
	return result.autonomous_system_number, result.autonomous_system_organization, "success"
end

utils.rand = function(nb, no_numbers, alphabet)
	local charset = {}
	if alphabet then
		-- Use custom alphabet
		for i = 1, #alphabet do
			table.insert(charset, alphabet:sub(i, i))
		end
	else
		if not no_numbers then
			for i = 48, 57 do
				table.insert(charset, char(i))
			end -- Numbers
		end
		for i = 65, 90 do
			table.insert(charset, char(i))
		end -- Uppercase
		for i = 97, 122 do
			table.insert(charset, char(i))
		end -- Lowercase
	end

	local result = {}
	for _ = 1, nb do
		local byte = bytes(1, true):byte() -- Get a secure random byte
		local index = (byte % #charset) + 1 -- Map byte to charset index
		table.insert(result, charset[index])
	end

	return table.concat(result)
end

utils.get_deny_status = function()
	if subsystem == "http" then
		local variables, err = internalstore:get("variables", true)
		if not variables then
			logger:log(ERR, "can't get variables from internalstore : " .. err)
			return HTTP_FORBIDDEN
		end
		return tonumber(variables["global"]["DENY_HTTP_STATUS"]) or HTTP_FORBIDDEN
	end
	return HTTP_CLOSE
end

utils.get_security_mode = function(ctx)
	-- Resolved once per request : set_reason() already shares this key, and several plugins
	-- (limit, badbehavior, misc, workflows) ask for the mode on the same request
	if ctx and ctx.bw and ctx.bw.security_mode then
		return ctx.bw.security_mode
	end
	local security_mode, _ = utils.get_variable("SECURITY_MODE", true, ctx)
	if not security_mode then
		security_mode = "block"
	end
	if ctx and ctx.bw then
		ctx.bw.security_mode = security_mode
	end
	return security_mode
end

utils.get_session = function(ctx)
	-- Return session from ctx if already there
	if ctx.bw.sessions_session then
		return ctx.bw.sessions_session
	end
	-- Resolve per-server cookie domain from the multisite SESSIONS_DOMAIN setting. An empty value
	-- must leave cookie_domain nil so lua-resty-session keeps the host-only default, and the
	-- multisite lookup guarantees unrelated tenants never receive a cross-tenant Domain attribute.
	local start_config
	local sessions_domain, sessions_domain_err = utils.get_variable("SESSIONS_DOMAIN", true, ctx)
	if sessions_domain == nil then
		logger:log(ERR, "error while getting variable SESSIONS_DOMAIN : " .. (sessions_domain_err or ""))
	elseif sessions_domain ~= "" then
		start_config = { cookie_domain = sessions_domain }
	end
	-- Open/create and do an optional refresh
	local err, exists, refreshed
	session, err, exists, refreshed = session_start(start_config)
	if not session then
		return nil, err
	end
	if err then
		logger:log(WARN, "can't open session : " .. err)
	end
	local checks = {
		["IP"] = ctx.bw.remote_addr,
		["USER_AGENT"] = ctx.bw.http_user_agent or "",
	}
	if exists then
		logger:log(INFO, "opening an existing session")
		if refreshed then
			logger:log(INFO, "existing session refreshed")
		end
		-- Get metadata
		local metadata = session:get("metadata")
		if metadata then
			-- Check if session passes the checks
			for check, value in pairs(checks) do
				local check_value
				check_value, err = utils.get_variable("SESSIONS_CHECK_" .. check, false, nil)
				if not check_value then
					logger:log(ERR, "error while getting variable SESSIONS_CHECK_" .. check .. " : " .. err)
				elseif check_value == "yes" and value ~= metadata[check] then
					logger:log(WARN, "session check failed : " .. check .. "!=" .. metadata[check])
					session:clear_request_cookie()
					local ok
					ok, err = session:destroy()
					if not ok then
						return nil, err
					end
					return utils.get_session(ctx)
				end
			end
		end
	else
		logger:log(INFO, "creating a new session")
		session:set("metadata", checks)
		ctx.bw.sessions_updated = true
	end
	ctx.bw.sessions_session = session
	return session
end

utils.save_session = function(ctx)
	if ctx.bw.sessions_session then
		if ctx.bw.sessions_updated then
			local ok, err = ctx.bw.sessions_session:save()
			if not err then
				err = "session saved"
			end
			return ok, err
		else
			return true, "session not updated"
		end
	else
		return true, "no session"
	end
end

utils.is_banned = function(ip, server_name)
	if subsystem == "stream" then
		local snapshot, snapshot_err = get_stream_snapshot()
		if not snapshot then
			return nil, snapshot_err, nil, nil
		end

		local function check_snapshot(key)
			local ban = snapshot.bans[key]
			if ban == nil then
				return false, "not banned", nil, nil
			end
			if type(ban) ~= "table" then
				return nil, "invalid ban in Stream snapshot", nil, nil
			end
			local expires_at = tonumber(ban.expires_at)
			local permanent = ban.permanent == true
			if permanent then
				expires_at = 0
			elseif not expires_at or expires_at <= wall_time() then
				return false, "not banned", nil, nil
			end
			local ttl = permanent and 0 or math_max(math_ceil(expires_at - wall_time()), 0)
			if not permanent and ttl <= 0 then
				return false, "not banned", nil, nil
			end
			return true, ban.reason or "unknown", ttl, ban.reason_data
		end

		if server_name then
			local banned, reason, ttl, reason_data = check_snapshot("bans_service_" .. server_name .. "_ip_" .. ip)
			if banned or banned == nil then
				return banned, reason, ttl, reason_data
			end
		end
		local banned, reason, ttl, reason_data = check_snapshot("bans_ip_" .. ip)
		if banned or banned == nil then
			return banned, reason, ttl, reason_data
		end
	end

	-- HTTP retains its local/Redis lookup path. Stream reaches this path only
	-- after a snapshot miss. With Redis enabled, absence from the node-local
	-- snapshot is not authoritative: this read-only fallback preserves cold-start
	-- and cross-instance cluster bans without mutating central authority.
	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if not use_redis then
		return nil, "can't get USE_REDIS variable: " .. err, nil, nil
	end
	use_redis = use_redis == "yes"

	local clusterstore
	local function check_ban(key, local_only)
		-- Ignore legacy Stream bans_* entries left in shared memory across a live
		-- upgrade. Redis fallback hits use a fresh, bounded cache namespace.
		local local_key = subsystem == "stream" and "ban_redis_cache_" .. key or key
		local value
		value, err = datastore:get(local_key)
		if value and err ~= "not found" then
			local reason = value
			local reason_data
			local ok, ban_data = pcall(decode, value)
			if ok and type(ban_data) == "table" then
				reason = ban_data.reason or reason
				reason_data = ban_data.reason_data
			end

			local ttl
			ok, ttl = datastore:ttl(local_key)
			if ok and ban_data and ban_data.permanent then
				ttl = 0
			end
			return true, reason, ttl or 0, reason_data
		elseif err ~= "not found" then
			return nil, "datastore:get() error: " .. tostring(err), nil, nil
		end

		if local_only or not use_redis then
			return false, "not banned", nil, nil
		end

		local redis_script = [[
			local ret_get = redis.pcall("GET", KEYS[1])
			if type(ret_get) == "table" and ret_get["err"] ~= nil then
				return {err = ret_get["err"]}
			end
			local ret_ttl = nil
			if ret_get ~= nil then
				ret_ttl = redis.pcall("TTL", KEYS[1])
				if type(ret_ttl) == "table" and ret_ttl["err"] ~= nil then
					return {err = ret_ttl["err"]}
				end
			end
			return {ret_get, ret_ttl}
		]]

		local data, script_err = clusterstore:call("eval", redis_script, 1, key)
		if not data then
			return nil, "redis call error: " .. script_err, nil, nil
		elseif data.err then
			return nil, "redis script error: " .. data.err, nil, nil
		elseif data[1] ~= null then
			local redis_ttl = data[2]
			local cache_ttl = redis_ttl > 0 and math_min(redis_ttl, BAN_LOCAL_CACHE_TTL) or BAN_LOCAL_CACHE_TTL
			local ok_cache, cache_err = datastore:set_with_retries(local_key, data[1], cache_ttl)
			if not ok_cache then
				logger:log(WARN, "datastore:set_with_retries() error: " .. cache_err)
			end

			local reason = data[1]
			local reason_data
			local ok, ban_data = pcall(decode, data[1])
			if ok and type(ban_data) == "table" then
				reason = ban_data.reason or reason
				reason_data = ban_data.reason_data
			end
			return true, reason, math_max(redis_ttl, 0), reason_data
		end

		return false, "not banned", nil, nil
	end

	local service_key = server_name and "bans_service_" .. server_name .. "_ip_" .. ip
	local global_key = "bans_ip_" .. ip
	if service_key then
		local banned, reason, ttl, reason_data = check_ban(service_key, true)
		if banned or banned == nil then
			return banned, reason, ttl, reason_data
		end
	end

	local banned, reason, ttl, reason_data = check_ban(global_key, true)
	if banned or banned == nil or not use_redis then
		return banned, reason, ttl, reason_data
	end

	clusterstore = require "bunkerweb.clusterstore":new()
	local ok, connect_err = clusterstore:connect(true)
	if not ok then
		return nil, "can't connect to redis: " .. connect_err, nil, nil
	end

	if service_key then
		banned, reason, ttl, reason_data = check_ban(service_key)
		if banned or banned == nil then
			clusterstore:close()
			return banned, reason, ttl, reason_data
		end
	end

	banned, reason, ttl, reason_data = check_ban(global_key)
	clusterstore:close()
	return banned, reason, ttl, reason_data
end

utils.add_ban = function(ip, reason, ttl, service, country, ban_scope, reason_data, not_after)
	if not ip or (not utils.is_ipv4(ip) and not utils.is_ipv6(ip)) then
		return false, "invalid IP address"
	end
	if ttl ~= nil then
		ttl = tonumber(ttl)
		if not ttl or ttl < 0 then
			return false, "invalid ban expiration"
		end
	end
	ban_scope = ban_scope == "service" and service and "service" or "global"

	if subsystem == "stream" then
		return forward_stream_ban("/ban", {
			ip = ip,
			exp = ttl or 0,
			reason = reason,
			service = service or "unknown",
			country = country or "local",
			ban_scope = ban_scope,
			reason_data = reason_data or {},
		})
	end

	local ban_key = "bans_ip_" .. ip
	if ban_scope == "service" then
		ban_key = "bans_service_" .. service .. "_ip_" .. ip
	end
	local ban_data
	local local_ok, local_err = with_ban_snapshot_lock(function()
		if not_after and wall_time() > not_after then
			return false, "ban mutation deadline expired"
		end
		local now = os.time()
		local expires_at = (not ttl or ttl == 0) and 0 or wall_time() + ttl
		local encoded_ok
		encoded_ok, ban_data = pcall(encode, {
			reason = reason,
			service = service or "unknown",
			date = now,
			country = country or "local",
			ban_scope = ban_scope,
			reason_data = reason_data or {},
			permanent = not ttl or ttl == 0,
			expires_at = expires_at,
		})
		if not encoded_ok then
			return false, "can't encode ban data : " .. tostring(ban_data)
		end
		local epoch, epoch_err = advance_ban_epoch()
		if not epoch then
			return false, epoch_err
		end
		local effective_ttl = (not ttl or ttl == 0) and nil or ttl
		local ok, err = datastore:set_with_retries(ban_key, ban_data, effective_ttl)
		if not ok then
			return false, "datastore:set_with_retries() error : " .. tostring(err)
		end
		return true, "success"
	end)
	if not local_ok then
		return false, local_err
	end

	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if not use_redis then
		return nil, "can't get USE_REDIS variable : " .. err
	elseif use_redis ~= "yes" then
		return true, "success"
	end

	local clusterstore = require "bunkerweb.clusterstore":new()
	local ok
	ok, err = clusterstore:connect()
	if not ok then
		return false, "can't connect to redis server : " .. err
	end
	if not ttl or ttl == 0 then
		ok, err = clusterstore:call("set", ban_key, ban_data)
	else
		ok, err = clusterstore:call("set", ban_key, ban_data, "EX", ttl)
	end
	if not ok then
		clusterstore:close()
		return false, "redis SET failed : " .. tostring(err)
	end
	clusterstore:close()
	return true, "success"
end

utils.remove_ban = function(ip, service, ban_scope, not_after)
	if not ip or (not utils.is_ipv4(ip) and not utils.is_ipv6(ip)) then
		return false, "invalid IP address"
	end
	ban_scope = ban_scope == "service" and service and "service" or "global"

	if subsystem == "stream" then
		return forward_stream_ban("/unban", {
			ip = ip,
			service = service,
			ban_scope = ban_scope,
		})
	end

	local keys_to_delete
	local local_ok, local_err = with_ban_snapshot_lock(function()
		if not_after and wall_time() > not_after then
			return false, "unban mutation deadline expired"
		end
		local epoch, epoch_err = advance_ban_epoch()
		if not epoch then
			return false, epoch_err
		end

		keys_to_delete = {}
		if ban_scope == "service" then
			local key = "bans_service_" .. service .. "_ip_" .. ip
			keys_to_delete[#keys_to_delete + 1] = key
			datastore:delete(key)
		else
			local global_key = "bans_ip_" .. ip
			keys_to_delete[#keys_to_delete + 1] = global_key
			datastore:delete(global_key)

			local suffix = "_ip_" .. ip
			for _, key in ipairs(datastore:keys()) do
				if key:sub(1, 13) == "bans_service_" and key:sub(-#suffix) == suffix then
					keys_to_delete[#keys_to_delete + 1] = key
					datastore:delete(key)
				end
			end
		end
		return true, "success"
	end)
	if not local_ok then
		return false, local_err
	end

	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if not use_redis then
		return nil, "can't get USE_REDIS variable : " .. err
	end
	if use_redis == "yes" then
		local clusterstore = require "bunkerweb.clusterstore":new()
		local ok, connect_err = clusterstore:connect()
		if not ok then
			logger:log(ERR, "can't connect to redis for unban: " .. connect_err)
			return false, "can't connect to redis for unban : " .. connect_err
		else
			local delete_err
			if ban_scope == "global" then
				local cursor = "0"
				local seen_cursors = {}
				while true do
					local scanned, scan_err = clusterstore:call(
						"scan",
						cursor,
						"MATCH",
						"bans_service_*_ip_" .. ip,
						"COUNT",
						100
					)
					local next_cursor = type(scanned) == "table" and tostring(scanned[1]) or nil
					if not scanned or type(scanned) ~= "table" or type(scanned[2]) ~= "table" or not next_cursor or not next_cursor:match("^%d+$") then
						delete_err = "redis SCAN failed : " .. tostring(scan_err)
						break
					end
					for _, key in ipairs(scanned[2]) do
						keys_to_delete[#keys_to_delete + 1] = key
					end
					cursor = next_cursor
					if cursor == "0" then
						break
					end
					if seen_cursors[cursor] then
						delete_err = "redis SCAN cursor did not advance"
						break
					end
					seen_cursors[cursor] = true
				end
			end
			for _, key in ipairs(keys_to_delete) do
				local deleted, call_err = clusterstore:call("del", key)
				if not deleted and not delete_err then
					delete_err = "redis DEL failed for " .. key .. " : " .. tostring(call_err)
				end
			end
			clusterstore:close()
			if delete_err then
				return false, delete_err
			end
		end
	end
	return true, "success"
end

utils.new_cachestore = function(ctx, pool)
	-- Check if redis is used
	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if not use_redis then
		logger:log(ERR, "can't get USE_REDIS variable : " .. err)
		use_redis = false
	else
		use_redis = use_redis == "yes"
	end
	-- Instantiate
	return require "bunkerweb.cachestore":new(use_redis, ctx, pool == nil or pool)
end

utils.regex_match = function(str, regex, options)
	local all_options = "o"
	if options then
		all_options = all_options .. options
	end
	local match, err = re_match(str, regex, all_options)
	if err then
		logger:log(ERR, "error while matching regex " .. regex .. "with string " .. str)
		return nil
	end
	return match
end

utils.get_phases = function()
	return {
		"init",
		"init_worker",
		"set",
		"rewrite",
		"access",
		"content",
		"ssl_client_hello_default",
		"ssl_certificate",
		"header",
		"log",
		"preread",
		"log_stream",
		"log_default",
		"timer",
		"init_workers",
	}
end

utils.is_cosocket_available = function()
	local phases = {
		"timer",
		"rewrite",
		"server_rewrite",
		"access",
		"content",
		"ssl_cert",
		"ssl_client_hello",
		"ssl_session_fetch",
		"preread",
	}
	local current_phase = get_phase()
	for _, phase in ipairs(phases) do
		if current_phase == phase then
			return true
		end
	end
	return false
end

utils.is_connection_error = function(err)
	return err
		and (err:find("closed", 1, true) or err:find("broken pipe", 1, true) or err:find("connection reset", 1, true))
end

utils.is_oom_error = function(err)
	return err and err:find("OOM", 1, true) ~= nil
end

utils.kill_all_threads = function(threads)
	for _, thread in ipairs(threads) do
		local ok, err = kill(thread)
		if not ok then
			logger:log(ERR, "error while killing thread : " .. err)
		end
	end
end

utils.get_ctx_obj = function(obj, ctx)
	local vctx = ctx or ngx.ctx
	if vctx and vctx.bw then
		return vctx.bw[obj]
	end
	return nil
end

utils.read_files = function(files)
	local data = {}
	for _, file in ipairs(files) do
		local f, err = open(file, "r")
		if not f then
			return false, file .. " = " .. err
		end
		table.insert(data, f:read("*a"))
		f:close()
	end
	return true, data
end

utils.deduplicate_list = function(list)
	local seen = {}
	local deduped = {}
	for _, v in ipairs(list) do
		if not seen[v] then
			seen[v] = true
			table.insert(deduped, v)
		end
	end
	return deduped
end

return utils
