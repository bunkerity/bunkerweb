local cdatastore	= require "bunkerweb.datastore"
local ipmatcher		= require "resty.ipmatcher"
local cjson			= require "cjson"
local resolver		= require "resty.dns.resolver"
local mmdb			= require "bunkerweb.mmdb"
local clogger		= require "bunkerweb.logger"
local session		= require "resty.session"

local logger = clogger:new("UTILS")
local datastore = cdatastore:new()

local utils = {}

utils.set_values = function()
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
		"255.255.255.255/32"
	}
	local ok, err = datastore:set("misc_reserved_ips", cjson.encode({ data = reserved_ips }))
	if not ok then
		return false, err
	end
	local var_resolvers, err = datastore:get("variable_DNS_RESOLVERS")
	if not var_resolvers then
		return false, err
	end
	local list_resolvers = {}
	for str_resolver in var_resolvers:gmatch("%S+") do
		table.insert(list_resolvers, str_resolver)
	end
	ok, err = datastore:set("misc_resolvers", cjson.encode(list_resolvers))
	if not ok then
		return false, err
	end
	return true, "success"
end

utils.get_variable = function(var, site_search)
	if site_search == nil then
		site_search = true
	end
	local value, err = datastore:get("variable_" .. var)
	if not value then
		return nil, "Can't access variable " .. var .. " from datastore : " .. err
	end
	if site_search then
		local multisite, err = datastore:get("variable_MULTISITE")
		if not multisite then
			return nil, "Can't access variable MULTISITE from datastore : " .. err
		end
		if multisite == "yes" and ngx.var.server_name then
			local value_site, err = datastore:get("variable_" .. ngx.var.server_name .. "_" .. var)
			if value_site then
				value = value_site
			end
		end
	end
	return value, "success"
end

utils.has_variable = function(var, value)
	local check_value, err = datastore:get("variable_" .. var)
	if not value then
		return nil, "Can't access variable " .. var .. " from datastore : " .. err
	end
	local multisite, err = datastore:get("variable_MULTISITE")
	if not multisite then
		return nil, "Can't access variable MULTISITE from datastore : " .. err
	end
	if multisite == "yes" then
		local servers, err = datastore:get("variable_SERVER_NAME")
		if not servers then
			return nil, "Can't access variable SERVER_NAME from datastore : " .. err
		end
		for server in servers:gmatch("%S+") do
			local check_value_site, err = datastore:get("variable_" .. server .. "_" .. var)
			if check_value_site and check_value_site == value then
				return true, "success"
			end
		end
		return false, "success"
	end
	return check_value == value, "success"
end

utils.has_not_variable = function(var, value)
	local check_value, err = datastore:get("variable_" .. var)
	if not value then
		return nil, "Can't access variable " .. var .. " from datastore : " .. err
	end
	local multisite, err = datastore:get("variable_MULTISITE")
	if not multisite then
		return nil, "Can't access variable MULTISITE from datastore : " .. err
	end
	if multisite == "yes" then
		local servers, err = datastore:get("variable_SERVER_NAME")
		if not servers then
			return nil, "Can't access variable SERVER_NAME from datastore : " .. err
		end
		for server in servers:gmatch("%S+") do
			local check_value_site, err = datastore:get("variable_" .. server .. "_" .. var)
			if check_value_site and check_value_site ~= value then
				return true, "success"
			end
		end
		return false, "success"
	end
	return check_value ~= value, "success"
end

function utils.get_multiple_variables(vars)
	local keys = datastore:keys()
	local result = {}
	for i, key in ipairs(keys) do
		for j, var in ipairs(vars) do
			local _, _, server, subvar = key:find("variable_(.*)_?(" .. var .. "_?%d*)")
			if subvar then
				if not server or server == "" then
					server = "global"
				else
					server = server:sub(1, -2)
				end
				if result[server] == nil then
					result[server] = {}
				end
				local value, err = datastore:get(key)
				if not value then
					return nil, err
				end
				result[server][subvar] = value
			end
		end
	end
	return result
end

utils.is_ip_in_networks = function(ip, networks)
	local ipm, err = ipmatcher.new(networks)
	if not ipm then
		return nil, "can't instantiate ipmatcher : " .. err
	end
	local matched, err = ipm:match(ip)
	if err then
		return nil, "can't check ip : " .. err
	end
	return matched
end

utils.is_ipv4 = function(ip)
	return ipmatcher.parse_ipv4(ip)
end

utils.is_ipv6 = function(ip)
	return ipmatcher.parse_ipv6(ip)
end

utils.ip_is_global = function(ip)
	local data, err = datastore:get("misc_reserved_ips")
	if not data then
		return nil, "can't get reserved ips : " .. err
	end
	local ok, reserved_ips = pcall(cjson.decode, data)
	if not ok then
		return nil, "can't decode json : " .. reserved_ips
	end
	local ipm, err = ipmatcher.new(reserved_ips)
	if not ipm then
		return nil, "can't instantiate ipmatcher : " .. err
	end
	local matched, err = ipm:match(ip)
	if err then
		return nil, "can't check ip : " .. err
	end
	return not matched, "success"
end

utils.get_integration = function()
	local integration, err = datastore:get("misc_integration")
	if integration then
		return integration
	end
	local var, err = datastore:get("variable_SWARM_MODE")
	if var == "yes" then
		integration = "swarm"
	else
		local var, err = datastore:get("variable_KUBERNETES_MODE")
		if var == "yes" then
			integration = "kubernetes"
		else
			local f, err = io.open("/etc/os-release", "r")
			if f then
				local data = f:read("*a")
				if data:find("Alpine") then
					integration = "docker"
				else
					integration = "unknown"
				end
				f:close()
			else
				integration = "unknown"
			end
		end
	end
	local ok, err = datastore:set("misc_integration", integration)
	if not ok then
		logger:log(ngx.ERR, "can't cache integration to datastore : " .. err)
	end
	return integration
end

utils.get_version = function()
	local version, err = datastore:get("misc_version")
	if version then
		return version
	end
	local f, err = io.open("/usr/share/bunkerweb/VERSION", "r")
	if not f then
		logger:log(ngx.ERR, "can't read VERSION file : " .. err)
		return "unknown"
	end
	version = f:read("*a")
	f:close()
	local ok, err = datastore:set("misc_version", version)
	if not ok then
		logger:log(ngx.ERR, "can't cache version to datastore : " .. err)
	end
	return version
end

utils.get_reason = function()
	if ngx.var.reason and ngx.var.reason ~= "" then
		return ngx.var.reason
	end
	if os.getenv("REASON") == "modsecurity" then
		return "modsecurity"
	end
	local banned, err = datastore:get("bans_ip_" .. ngx.var.remote_addr)
	if banned then
		return banned
	end
	if ngx.status == utils.get_deny_status() then
		return "unknown"
	end
	return nil
end

utils.get_rdns = function(ip)
	local str_resolvers, err = datastore:get("misc_resolvers")
	if not str_resolvers then
		return false, err
	end
	local resolvers = cjson.decode(str_resolvers)
	local rdns, err = resolver:new {
		nameservers = resolvers,
		retrans = 1,
		timeout = 1000
	}
	if not rdns then
		return false, err
	end
	local answers, err = rdns:reverse_query(ip)
	if not answers then
		return false, err
	end
	if answers.errcode then
		return false, answers.errstr
	end
	for i, answer in ipairs(answers) do
		if answer.ptrdname then
			return answer.ptrdname, "success"
		end
	end
	return false, nil
end

utils.get_ips = function(fqdn, resolvers)
	local str_resolvers, err = datastore:get("misc_resolvers")
	if not str_resolvers then
		return false, err
	end
	local resolvers = cjson.decode(str_resolvers)
	local rdns, err = resolver:new {
		nameservers = resolvers,
		retrans = 1,
		timeout = 1000
	}
	if not rdns then
		return false, err
	end
	local answers, err = rdns:query(fqdn, nil, {})
	if not answers then
		return false, err
	end
	if answers.errcode then
		return {}, answers.errstr
	end
	local ips = {}
	for i, answer in ipairs(answers) do
		if answer.address then
			table.insert(ips, answer.addres)
		end
	end
	return ips, "success"
end

utils.get_country = function(ip)
	if not mmdb.country_db then
		return false, "mmdb country not loaded"
	end
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
	if not mmdb.asn_db then
		return false, "mmdb asn not loaded"
	end
	local ok, result, err = pcall(mmdb.asn_db.lookup, mmdb.asn_db, ip)
	if not ok then
		return nil, result
	end
	if not result then
		return nil, err
	end
	return result.autonomous_system_number, "success"
end

utils.rand = function(nb)
	local charset = {}
	for i = 48, 57 do table.insert(charset, string.char(i)) end
	for i = 65, 90 do table.insert(charset, string.char(i)) end
	for i = 97, 122 do table.insert(charset, string.char(i)) end
	local result = ""
	for i = 1, nb do
		result = result .. charset[math.random(1, #charset)]
	end
	return result
end

utils.get_deny_status = function()
	if ngx.var.is_stream == "yes" then
		return 403
	end
	local status, err = datastore:get("variable_DENY_HTTP_STATUS")
	if not status then
		logger:log(ngx.ERR, "can't get DENY_HTTP_STATUS variable " .. err)
		return 403
	end
	return tonumber(status)
end

utils.get_session = function()
	if ngx.ctx.session then
		return ngx.ctx.session, ngx.ctx.session_err, ngx.ctx.session_exists
	end
	local _session, err, exists = session.start()
	if err then
		logger:log(ngx.ERR, "UTILS", "can't start session : " .. err)
	end
	ngx.ctx.session = _session
	ngx.ctx.session_err = err
	ngx.ctx.session_exists = exists
	ngx.ctx.session_saved = false
	ngx.ctx.session_data = _session.get_data()
	if not ngx.ctx.session_data then
		ngx.ctx.session_data = {}
	end
	return _session, err, exists
end

utils.save_session = function()
	if ngx.ctx.session and not ngx.ctx.session_err and not ngx.ctx.session_saved then
		ngx.ctx.session:set_data(ngx.ctx.session_data)
		local ok, err = ngx.ctx.session:save()
		if err then
			logger:log(ngx.ERR, "can't save session : " .. err)
			return false,  "can't save session : " .. err
		end
		ngx.ctx.session_saved = true
		return true, "session saved"
	elseif ngx.ctx.session_saved then
		return true, "session already saved"
	end
	return true, "no session"
end

utils.set_session = function(key, value)
	if ngx.ctx.session and not ngx.ctx.session_err then
		ngx.ctx.session_data[key] = value
		return true, "value set"
	end
	return true, "no session"
end

utils.get_session = function(key)
	if ngx.ctx.session and not ngx.ctx.session_err then
		return true, "value get", ngx.ctx.session_data[key]
	end
	return false, "no session"
end

return utils