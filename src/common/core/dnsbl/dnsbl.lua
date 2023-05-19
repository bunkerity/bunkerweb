local class      = require "middleclass"
local plugin     = require "bunkerweb.plugin"
local utils      = require "bunkerweb.utils"
local cachestore = require "bunkerweb.cachestore"
local cjson      = require "cjson"
local resolver   = require "resty.dns.resolver"

local dnsbl      = class("dnsbl", plugin)

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

function dnsbl:init_worker()
	-- Check if loading
	if self.is_loading then
		return self:ret(false, "BW is loading")
	end
	-- Check if at least one service uses it
	local is_needed, err = utils.has_variable("USE_DNSBL", "yes")
	if is_needed == nil then
		return self:ret(false, "can't check USE_DNSBL variable : " .. err)
	elseif not is_needed then
		return self:ret(true, "no service uses DNSBL, skipping init_worker")
	end
	-- Loop on DNSBL list
	for server in self.variables["DNSBL_LIST"]:gmatch("%S+") do
		local result, err = self:is_in_dnsbl("127.0.0.2", server)
		if result == nil then
			self.logger:log(ngx.ERR, "error while sending DNS request to " .. server .. " : " .. err)
		elseif not result then
			self.logger:log(ngx.ERR, "dnsbl check for " .. server .. " failed")
		else
			self.logger:log(ngx.NOTICE, "dnsbl check for " .. server .. " is successful")
		end
	end
	return self:ret(true, "success")
end

function dnsbl:access()
	-- Check if access is needed
	if self.variables["USE_DNSBL"] ~= "yes" then
		return self:ret(true, "dnsbl not activated")
	end
	if self.variables["DNSBL_LIST"] == "" then
		return self:ret(true, "dnsbl list is empty")
	end
	-- Don't go further if IP is not global
	if not ngx.ctx.bw.ip_is_global then
		return self:ret(true, "client IP is not global, skipping DNSBL check")
	end
	-- Check if IP is in cache
	local ok, cached = self:is_in_cache(ngx.ctx.bw.remote_addr)
	if not ok then
		return self:ret(false, "error while checking cache : " .. cached)
	elseif cached then
		if cached == "ok" then
			return self:ret(true, "client IP " .. ngx.ctx.bw.remote_addr .. " is in DNSBL cache (not blacklisted)")
		end
		return self:ret(true, "client IP " .. ngx.ctx.bw.remote_addr .. " is in DNSBL cache (server = " .. cached .. ")",
			utils.get_deny_status())
	end
	-- Loop on DNSBL list
	for server in self.variables["DNSBL_LIST"]:gmatch("%S+") do
		local result, err = self:is_in_dnsbl(ngx.ctx.bw.remote_addr, server)
		if result == nil then
			self.logger:log(ngx.ERR, "error while sending DNS request to " .. server .. " : " .. err)
		end
		if result then
			local ok, err = self:add_to_cache(ngx.ctx.bw.remote_addr, server)
			if not ok then
				return self:ret(false, "error while adding element to cache : " .. err)
			end
			return self:ret(true, "IP is blacklisted by " .. server, utils.get_deny_status())
		end
	end
	-- IP is not in DNSBL
	local ok, err = self:add_to_cache(ngx.ctx.bw.remote_addr, "ok")
	if not ok then
		return self:ret(false, "IP is not in DNSBL (error = " .. err .. ")")
	end
	return self:ret(true, "IP is not in DNSBL", false, nil)
end

function dnsbl:preread()
	return self:access()
end

function dnsbl:is_in_cache(ip)
	local ok, data = self.cachestore:get("plugin_dnsbl_" .. ngx.ctx.bw.server_name .. ip)
	if not ok then
		return false, data
	end
	return true, data
end

function dnsbl:add_to_cache(ip, value)
	local ok, err = self.cachestore:set("plugin_dnsbl_" .. ngx.ctx.bw.server_name .. ip, value, 86400)
	if not ok then
		return false, err
	end
	return true
end

function dnsbl:is_in_dnsbl(ip, server)
	local request = resolver.arpa_str(ip):gsub("%.in%-addr%.arpa", ""):gsub("%.ip6%.arpa", "") .. "." .. server
	local ips, err = utils.get_ips(request, false)
	if not ips then
		return nil, err
	end
	for i, ip in ipairs(ips) do
		if ip:find("^127%.0%.0%.") then
			return true, "success"
		end
	end
	return false, "success"
end

return dnsbl
