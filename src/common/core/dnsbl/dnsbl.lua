local _M = {}
_M.__index = _M

local utils		= require "utils"
local datastore	= require "datastore"
local logger	= require "logger"
local cjson		= require "cjson"
local resolver	= require "resty.dns.resolver"

function _M.new()
	local self = setmetatable({}, _M)
	return self, nil
end

function _M:init()
	-- Check if init is needed
	local init_needed, err = utils.has_variable("USE_DNSBL", "yes")
	if init_needed == nil then
		return false, "can't check USE_DNS variable : " .. err
	end
	if not init_needed then
		return true, "no service uses Blacklist, skipping init"
	end
	-- Read DNSBL list
	local str_dnsbls, err = utils.get_variable("DNSBL_LIST", false)
	if not str_dnsbls then
		return false, "can't get DNSBL_LIST variable : " .. err
	end
	local dnsbls = {}
	local i = 0
	for dnsbl in str_dnsbls:gmatch("%S+") do
		table.insert(dnsbls, dnsbl)
		i = i + 1
	end
	-- Load it into datastore
	local ok, err = datastore:set("plugin_dnsbl_list", cjson.encode(dnsbls))
	if not ok then
		return false, "can't store DNSBL list into datastore : " .. err
	end
	return true, "successfully loaded " .. tostring(i) .. " DNSBL server(s)"
end

function _M:access()
	-- Check if access is needed
	local access_needed, err = utils.get_variable("USE_DNSBL")
	if access_needed == nil then
		return false, err
	end
	if access_needed ~= "yes" then
		return true, "DNSBL not activated"
	end

	-- Check if IP is in cache
	local dnsbl, err = self:is_in_cache(ngx.var.remote_addr)
	if dnsbl then
		if dnsbl == "ok" then
			return true, "client IP " .. ngx.var.remote_addr .. " is in DNSBL cache (not blacklisted)", nil, nil
		end
		return true, "client IP " .. ngx.var.remote_addr .. " is in DNSBL cache (server = " .. dnsbl .. ")", true, utils.get_deny_status()
	end

	-- Don't go further if IP is not global
	local is_global, err = utils.ip_is_global(ngx.var.remote_addr)
	if is_global == nil then
		return false, "can't check if client IP is global : " .. err, nil, nil
	end
	if not utils.ip_is_global(ngx.var.remote_addr) then
		self:add_to_cache(ngx.var.remote_addr, "ok")
		return true, "client IP is not global, skipping DNSBL check", nil, nil
	end

	-- Get list
	local data, err = datastore:get("plugin_dnsbl_list")
	if not data then
		return false, "can't get DNSBL list : " .. err, false, nil
	end
	local ok, dnsbls = pcall(cjson.decode, data)
	if not ok then
		return false, "error while decoding DNSBL list : " .. dnsbls, false, nil
	end
	
	-- Loop on dnsbl list
	for i, dnsbl in ipairs(dnsbls) do
		local result, err = self:is_in_dnsbl(dnsbl, ngx.var.remote_addr)
		if result then
			self:add_to_cache(ngx.var.remote_addr, dnsbl)
			return ret, "client IP " .. ngx.var.remote_addr .. " is in DNSBL (server = " .. dnsbl .. ")", true, utils.get_deny_status()
		end
	end
	
	-- IP is not in DNSBL
	local ok, err = self:add_to_cache(ngx.var.remote_addr, "ok")
	if not ok then
		return false, "IP is not in DNSBL (error = " .. err .. ")", false, nil
	end
	return true, "IP is not in DNSBL", false, nil

end

function _M:preread()
	return self:access()
end

function _M:is_in_dnsbl(dnsbl, ip)
	local request = resolver.arpa_str(ip) .. "." .. dnsbl
	local ips, err = utils.get_ips(request)
	if not ips then
		logger.log(ngx.ERR, "DNSBL", "Error while asking DNSBL server " .. dnsbl .. " : " .. err)
		return false, err
	end
	for i, ip in ipairs(ips) do
		local a, b, c, d = ip:match("([%d]+).([%d]+).([%d]+).([%d]+)")
		if a == "127" then
			return true, "success"
		end
	end
	return false, "success"
end

function _M:is_in_cache(ip) 
	local kind, err = datastore:get("plugin_dnsbl_cache_" .. ip)
	if not kind then
		if err ~= "not found" then
			logger.log(ngx.ERR, "DNSBL", "Error while accessing cache : " .. err)
		end
		return false, err
	end
	return kind, "success"
end

function _M:add_to_cache(ip, kind)
	local ok, err = datastore:set("plugin_dnsbl_cache_" .. ip, kind, 3600)
	if not ok then
		logger.log(ngx.ERR, "DNSBL", "Error while adding ip to cache : " .. err)
		return false, err
	end
	return true, "success"
end

return _M
