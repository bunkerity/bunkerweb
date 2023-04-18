local class			= require "middleclass"
local plugin		= require "bunkerweb.plugin"
local utils     	= require "bunkerweb.utils"
local cachestore 	= require "bunkerweb.cachestore"

local country	= class("country", plugin)

function country:initialize()
	-- Call parent initialize
	plugin.initialize(self, "country")
	-- Instantiate cachestore
	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if not use_redis then
		self.logger:log(ngx.ERR, err)
	end
	self.use_redis = use_redis == "yes"
	self.cachestore = cachestore:new(self.use_redis)
end

function country:access()
	-- Don't go further if nothing is enabled
	if self.variables["WHITELIST_COUNTRY"] == "" and self.variables["BLACKLIST_COUNTRY"] == "" then
		return self:ret(true, "country not activated")
	end
	-- Check if IP is in cache
	local data, err = self:is_in_cache(ngx.var.remote_addr)
	if data then
		if data.result == "ok" then
			return self:ret(true, "client IP " .. ngx.var.remote_addr .. " is in country cache (not blacklisted, country = " .. data.country .. ")")
		end
		return self:ret(true, "client IP " .. ngx.var.remote_addr .. " is in country cache (blacklisted, country = " .. data.country .. ")", utils.get_deny_status())
	end

	-- Don't go further if IP is not global
	local is_global, err = utils.ip_is_global(ngx.var.remote_addr)
	if is_global == nil then
		return self:ret(false, "error while checking if ip is global : " .. err)
	elseif not is_global then
		local ok, err = self:add_to_cache(ngx.var.remote_addr, "unknown", "ok")
		if not ok then
			return self:ret(false, "error while adding ip to cache : " .. err)
		end
		return self:ret(true, "client IP " .. ngx.var.remote_addr .. " is not global, skipping check")
	end

	-- Get the country of client
	local country, err = utils.get_country(ngx.var.remote_addr)
	if not country then
		return self:ret(false, "can't get country of client IP " .. ngx.var.remote_addr .. " : " .. err)
	end
	
	-- Process whitelist first
	if self.variables["WHITELIST_COUNTRY"] ~= "" then
		for wh_country in self.variables["WHITELIST_COUNTRY"]:gmatch("%S+") do
			if wh_country == country then
				local ok, err = self:add_to_cache(ngx.var.remote_addr, country, "ok")
				if not ok then
					return self:ret(false, "error while adding item to cache : " .. err)
				end
				return self:ret(true, "client IP " .. ngx.var.remote_addr .. " is whitelisted (country = " .. country .. ")")
			end
		end
		local ok, err = self:add_to_cache(ngx.var.remote_addr, country, "ko")
		if not ok then
			return self:ret(false, "error while adding item to cache : " .. err)
		end
		return self:ret(true, "client IP " .. ngx.var.remote_addr .. " is not whitelisted (country = " .. country .. ")", utils.get_deny_status())
	end
	
	-- And then blacklist
	if self.variables["BLACKLIST_COUNTRY"] ~= "" then
		for bl_country in self.variables["BLACKLIST_COUNTRY"]:gmatch("%S+") do
			if bl_country == country then
				local ok, err = self:add_to_cache(ngx.var.remote_addr, country, "ko")
				if not ok then
					return self:ret(false, "error while adding item to cache : " .. err)
				end
				return self:ret(true, "client IP " .. ngx.var.remote_addr .. " is blacklisted (country = " .. country .. ")", true, utils.get_deny_status())
			end
		end
	end

	-- Country IP is not in blacklist
	local ok, err = self:add_to_cache(ngx.var.remote_addr, country, "ok")
	if not ok then
		return self:ret(false, "error while caching IP " .. ngx.var.remote_addr .. " : " .. err)
	end
	return self:ret(true, "client IP " .. ngx.var.remote_addr .. " is not blacklisted (country = " .. country .. ")")
end

function country:preread()
	return self:access()
end

function country:is_in_cache(ip)
	local ok, data = self.cachestore:get("plugin_country_cache_" .. ip)
	if not ok then
		return false, data
	end 
	return true, cjson.decode(data)
end

function country:add_to_cache(ip, country, result)
	local ok, err = self.cachestore:set("plugin_country_cache_" .. ip, cjson.encode({country = country, result = result}))
	if not ok then
		return false, err
	end 
	return true
end

return country