local ngx = ngx
local cdatastore = require "bunkerweb.datastore"
local clogger = require "bunkerweb.logger"
local mmdb = require "bunkerweb.mmdb"

local cjson = require "cjson"
local ipmatcher = require "resty.ipmatcher"
local resolver = require "resty.dns.resolver"
local session = require "resty.session"

local logger = clogger:new("UTILS")
local datastore = cdatastore:new()

local var = ngx.var
local ERR = ngx.ERR
local INFO = ngx.INFO
local WARN = ngx.WARN
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
local char = string.char
local random = math.random
local session_start = session.start
local session_open = session.open
local tonumber = tonumber

local utils = {}

math.randomseed(os.time())

utils.get_variable = function(variable, site_search, ctx)
	-- Default site search to true
	if site_search == nil then
		site_search = true
	end
	-- Get global value
	local variables, err = datastore:get("variables", true)
	if not variables then
		return nil, "can't access variables from datastore : " .. err
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
	return value, "success"
end

utils.has_variable = function(variable, value)
	-- Get global variable
	local variables, err = datastore:get("variables", true)
	if not variables then
		return nil, "can't access variables " .. variable .. " from datastore : " .. err
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
	local variables, err = datastore:get("variables", true)
	if not variables then
		return nil, "can't access variables " .. variable .. " from datastore : " .. err
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
	local variables, err = datastore:get("variables", true)
	if not variables then
		return nil, "can't access variables " .. vars .. " from datastore : " .. err
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
	-- Check if already in datastore
	local integration, _ = datastore:get("misc_integration", true)
	if integration then
		return integration
	end
	local variables, err = datastore:get("variables", true)
	if not variables then
		logger:log(ERR, "can't get variables from datastore : " .. err)
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
	local ok, err = datastore:set("misc_integration", integration, nil, true)
	if not ok then
		logger:log(ERR, "can't cache integration to datastore : " .. err)
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
	-- Check if already in datastore
	local version, _ = datastore:get("misc_version", true)
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
	local ok, err = datastore:set("misc_version", version, nil, true)
	if not ok then
		logger:log(ERR, "can't cache version to datastore : " .. err)
	end
	if ctx then
		ctx.bw.version = version
	end
	return version
end

utils.get_reason = function(ctx)
	-- ngx.ctx
	if ctx and ctx.bw and ctx.bw.reason then
		return ctx.bw.reason
	end
	-- ngx.var
	if var.reason and var.reason ~= "" then
		return var.reason
	end
	-- os.getenv
	if os.getenv("REASON") == "modsecurity" then
		return "modsecurity"
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
		return banned
	end
	-- unknown
	if ngx.status == utils.get_deny_status() then
		return "unknown"
	end
	return nil
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

utils.get_resolvers = function()
	-- Get resolvers from datastore if existing
	local resolvers, _ = datastore:get("misc_resolvers", true)
	if resolvers then
		return resolvers
	end
	-- Otherwise extract DNS_RESOLVERS variable
	local variables, err = datastore:get("variables", true)
	if not variables then
		logger:log(ERR, "can't get variables from datastore : " .. err)
		return "unknown"
	end
	-- Make table for resolver1 resolver2 ... string
	resolvers = {}
	for str_resolver in variables["global"]["DNS_RESOLVERS"]:gmatch("%S+") do
		table.insert(resolvers, str_resolver)
	end
	-- Add it to the datastore
	local ok, err = datastore:set("misc_resolvers", resolvers, nil, true)
	if not ok then
		logger:log(ERR, "can't save misc_resolvers to datastore : " .. err)
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
		logger:log(ERR, "error while doing reverse DNS query for " .. ip .. " : " .. err)
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

utils.get_asn = function(ip)
	-- Check if mmdp is loaded
	if not mmdb.asn_db then
		return false, "mmdb asn not loaded"
	end
	-- Perform lookup
	local ok, result, err = pcall(mmdb.asn_db.lookup, mmdb.asn_db, ip)
	if not ok then
		return nil, result
	end
	if not result then
		return nil, err
	end
	return result.autonomous_system_number, "success"
end

utils.rand = function(nb, no_numbers)
	local charset = {}
	-- lowers, uppers and numbers
	if not no_numbers then
		for i = 48, 57 do
			table.insert(charset, char(i))
		end
	end
	for i = 65, 90 do
		table.insert(charset, char(i))
	end
	for i = 97, 122 do
		table.insert(charset, char(i))
	end
	local result = ""
	for _ = 1, nb do
		result = result .. charset[random(1, #charset)]
	end
	return result
end

utils.get_deny_status = function()
	if subsystem == "http" then
		local variables, err = datastore:get("variables", true)
		if not variables then
			logger:log(ERR, "can't get variables from datastore : " .. err)
			return 403
		end
		return tonumber(variables["global"]["DENY_HTTP_STATUS"])
	end
	return 444
end

utils.check_session = function(ctx)
	local _session, _, exists, _ = session_start({ audience = "metadata" })
	if exists then
		for _, check in ipairs(ctx.bw.sessions_checks) do
			local key = check[1]
			local value = check[2]
			if _session:get(key) ~= value then
				_session:clear_request_cookie()
				local ok, err = _session:destroy()
				if not ok then
					return false, "session:destroy() error : " .. err
				end
				logger:log(WARN, "session check " .. key .. " failed, destroying session")
				return utils.check_session(ctx)
			end
		end
	else
		for _, check in ipairs(ctx.bw.sessions_checks) do
			_session:set(check[1], check[2])
		end
		local ok, err = _session:save()
		if not ok then
			_session:close()
			return false, "session:save() error : " .. err
		end
	end
	ctx.bw.sessions_is_checked = true
	return true, exists
end

utils.get_session = function(audience, ctx)
	-- Check session
	if not ctx.bw.sessions_is_checked then
		local ok, err = utils.check_session(ctx)
		if not ok then
			return false, "error while checking session, " .. err
		end
	end
	-- Open session with specific audience
	local _session, err, _ = session_open({ audience = audience })
	if err then
		logger:log(INFO, "session:open() error : " .. err)
	end
	return _session
end

-- luacheck: ignore 214
utils.get_session_data = function(_session, site, ctx)
	local site_only = site == nil or site
	local data = _session:get_data()
	if site_only then
		return data[ctx.bw.server_name] or {}
	end
	return data
end

-- luacheck: ignore 214
utils.set_session_data = function(_session, data, site, ctx)
	local site_only = site == nil or site
	if site_only then
		local all_data = _session:get_data()
		all_data[ctx.bw.server_name] = data
		_session:set_data(all_data)
		return _session:save()
	end
	_session:set_data(data)
	return _session:save()
end

utils.is_banned = function(ip)
	-- Check on local datastore
	local reason, err = datastore:get("bans_ip_" .. ip)
	if not reason and err ~= "not found" then
		return nil, "datastore:get() error : " .. reason
	elseif reason and err ~= "not found" then
		local ok, ttl = datastore:ttl("bans_ip_" .. ip)
		if not ok then
			return true, reason, -1
		end
		return true, reason, ttl
	end
	-- Redis case
	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if not use_redis then
		return nil, "can't get USE_REDIS variable : " .. err
	elseif use_redis ~= "yes" then
		return false, "not banned"
	end
	-- Connect
	local clusterstore = require "bunkerweb.clusterstore":new()
	local ok, err = clusterstore:connect(true)
	if not ok then
		return nil, "can't connect to redis server : " .. err
	end
	-- Redis atomic script : GET+TTL
	local redis_script = [[
		local ret_get = redis.pcall("GET", KEYS[1])
		if type(ret_get) == "table" and ret_get["err"] ~= nil then
			redis.log(redis.LOG_WARNING, "access GET error : " .. ret_get["err"])
			return ret_get
		end
		local ret_ttl = nil
		if ret_get ~= nil then
			ret_ttl = redis.pcall("TTL", KEYS[1])
			if type(ret_ttl) == "table" and ret_ttl["err"] ~= nil then
				redis.log(redis.LOG_WARNING, "access TTL error : " .. ret_ttl["err"])
				return ret_ttl
			end
		end
		return {ret_get, ret_ttl}
	]]
	-- Execute redis script
	local data, err = clusterstore:call("eval", redis_script, 1, "bans_ip_" .. ip)
	if not data then
		clusterstore:close()
		return nil, "redis call error : " .. err
	elseif data.err then
		clusterstore:close()
		return nil, "redis script error : " .. data.err
	elseif data[1] ~= null then
		clusterstore:close()
		-- Update local cache
		ok, err = datastore:set("bans_ip_" .. ip, data[1], data[2])
		if not ok then
			return nil, "datastore:set() error : " .. err
		end
		return true, data[1], data[2]
	end
	clusterstore:close()
	return false, "not banned"
end

utils.add_ban = function(ip, reason, ttl)
	-- Set on local datastore
	local ok, err = datastore:set("bans_ip_" .. ip, reason, ttl)
	if not ok then
		return false, "datastore:set() error : " .. err
	end
	-- Set on redis
	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if not use_redis then
		return nil, "can't get USE_REDIS variable : " .. err
	elseif use_redis ~= "yes" then
		return true, "success"
	end
	-- Connect
	local clusterstore = require "bunkerweb.clusterstore":new()
	ok, err = clusterstore:connect()
	if not ok then
		return false, "can't connect to redis server : " .. err
	end
	-- SET call
	ok, err = clusterstore:call("set", "bans_ip_" .. ip, reason, "EX", ttl)
	if not ok then
		clusterstore:close()
		return false, "redis SET failed : " .. err
	end
	clusterstore:close()
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
		"ssl_certificate",
		"header",
		"log",
		"preread",
		"log_stream",
		"log_default"
	}
end

utils.is_cosocket_available = function()
	local phases = {
		"timer",
		"rewrite",
		"access",
		"content",
		"ssl_certificate",
		"preread"
	}
	local current_phase = get_phase()
	for _, phase in ipairs(phases) do
		if current_phase == phase then
			return true
		end
	end
	return false
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

return utils
