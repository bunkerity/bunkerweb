local class			= require "middleclass"
local plugin		= require "bunkerweb.plugin"
local utils     	= require "bunkerweb.utils"
local cachestore	= require "bunkerweb.cachestore"
local cjson			= require "cjson"
local resolver		= require "resty.dns.resolver"

local dnsbl			= class("dnsbl", plugin)

function dnsbl:initialize()
	-- Call parent initialize
	plugin.initialize(self, "dnsbl")
	-- Instantiate cachestore
	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if not use_redis then
		self.logger:log(ngx.ERR, err)
	end
	self.use_redis = use_redis == "yes"
	self.cachestore = cachestore:new(self.use_redis)
end

function dnsbl:access()
	-- Check if access is needed
	if self.variables["USE_DNSBL"] ~= "yes" then
		return self:ret(true, "dnsbl not activated")
	end
	if self.variables["DNSBL_LIST"] == "" then
		return self:ret(true, "dnsbl list is empty")
	end
	-- Check if IP is in cache
	local ok, cached = self:is_in_cache(ngx.var.remote_addr)
	if not ok then
		return self:ret(false, "error while checking cache : " .. err)
	elseif cached then
		if cached == "ok" then
			return self:ret(true, "client IP " .. ngx.var.remote_addr .. " is in DNSBL cache (not blacklisted)")
		end
		return self:ret(true, "client IP " .. ngx.var.remote_addr .. " is in DNSBL cache (server = " .. cached .. ")", utils.get_deny_status())
	end
	-- Don't go further if IP is not global
	local is_global, err = utils.ip_is_global(ngx.var.remote_addr)
	if is_global == nil then
		return self:ret(false, "can't check if client IP is global : " .. err)
	end
	if not is_global then
		local ok, err self:add_to_cache(ngx.var.remote_addr, "ok")
		if not ok then
			return self:ret(false, "error while adding element to cache")
		end
		return self:ret(true, "client IP is not global, skipping DNSBL check")
	end
	-- Loop on DNSBL list
	for server in self.variables["DNSBL_LIST"]:gmatch("%S+") do
		local result, err = self:is_in_dnsbl(server)
		if result == nil then
			self.logger:log(ngx.ERR, "error while sending DNS request to " .. server .. " : " .. err)
		end
		if result then
			local ok, err self:add_to_cache(ngx.var.remote_addr, server)
			if not ok then
				return self:ret(false, "error while adding element to cache : " .. err)
			end
			return self:ret(true, "IP is blacklisted by " .. server, utils.get_deny_status())
		end
	end
	-- IP is not in DNSBL
	local ok, err = self:add_to_cache(ngx.var.remote_addr, "ok")
	if not ok then
		return self:ret(false, "IP is not in DNSBL (error = " .. err .. ")")
	end
	return self:ret(true, "IP is not in DNSBL", false, nil)
end

function dnsbl:preread()
	return self:access()
end

function dnsbl:is_in_cache(ip)
	local ok, data = self.cachestore:get("plugin_dnsbl_" .. ip)
	if not ok then
		return false, data
	end 
	return true, data
end

function dnsbl:add_to_cache(ip, value)
	local ok, err = self.cachestore:set("plugin_dnsbl_" .. ip, value)
	if not ok then
		return false, err
	end 
	return true
end

function dnsbl:is_in_dnsbl(server)
	local request = resolver.arpa_str(ip) .. "." .. server
	local ips, err = utils.get_ips(request)
	if not ips then
		return nil, err
	end
	for i, ip in ipairs(ips) do
		local a, b, c, d = ip:match("([%d]+).([%d]+).([%d]+).([%d]+)")
		if a == "127" then
			return true, "success"
		end
	end
	return false, "success"
end

return dnsbl