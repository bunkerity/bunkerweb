local _M = {}
_M.__index = _M

local utils		= require "utils"
local datastore	= require "datastore"
local logger	= require "logger"
local cjson		= require "cjson"

function _M.new()
	local self = setmetatable({}, _M)
	return self, nil
end

function _M:access()
	-- Get variables
	local whitelist, err = utils.get_variable("WHITELIST_COUNTRY")
	if whitelist == nil then
		return false, err
	end
    local blacklist, err = utils.get_variable("BLACKLIST_COUNTRY")
    if blacklist == nil then
        return false, err
    end
    
    -- Don't go further if nothing is enabled
    if whitelist == "" and blacklist == "" then
        return true, "country not activated"
    end

	-- Check if IP is in cache
	local data, err = self:is_in_cache(ngx.var.remote_addr)
	if data then
		if data.result == "ok" then
			return true, "client IP " .. ngx.var.remote_addr .. " is in country cache (not blacklisted, country = " .. data.country .. ")", nil, nil
		end
		return true, "client IP " .. ngx.var.remote_addr .. " is in country cache (blacklisted, country = " .. data.country .. ")", true, utils.get_deny_status()
	end
	
	-- Don't go further if IP is not global
	local is_global, err = utils.ip_is_global(ngx.var.remote_addr)
	if is_global == nil then
		logger.log(ngx.ERR, "COUNTRY", "error while checking if ip is global : " .. err)
	elseif not is_global then
		self:add_to_cache(ngx.var.remote_addr, "unknown", "ok")
		return true, "client IP " .. ngx.var.remote_addr .. " is not global, skipping check", nil, nil
	end
	
	-- Get the country of client
	local country, err = utils.get_country(ngx.var.remote_addr)
	if not country then
		return false, "can't get country of client IP " .. ngx.var.remote_addr .. " : " .. err, nil, nil
	end
	
	-- Process whitelist first
	if whitelist ~= "" then
		for wh_country in whitelist:gmatch("%S+") do
			if wh_country == country then
				self:add_to_cache(ngx.var.remote_addr, country, "ok")
				return true, "client IP " .. ngx.var.remote_addr .. " is whitelisted (country = " .. country .. ")", nil, nil
			end
		end
		self:add_to_cache(ngx.var.remote_addr, country, "ko")
		return true, "client IP " .. ngx.var.remote_addr .. " is not whitelisted (country = " .. country .. ")", true, utils.get_deny_status()
	end
	
	-- And then blacklist
	if blacklist ~= "" then
		for bl_country in blacklist:gmatch("%S+") do
			if bl_country == country then
				self:add_to_cache(ngx.var.remote_addr, country, "ko")
				return true, "client IP " .. ngx.var.remote_addr .. " is blacklisted (country = " .. country .. ")", true, utils.get_deny_status()
			end
		end
	end

	-- Country IP is not in blacklist
	local ok, err = self:add_to_cache(ngx.var.remote_addr, country, "ok")
	if not ok then
		return false, "error while caching IP " .. ngx.var.remote_addr .. " : " .. err, false, nil
	end
	return true, "client IP " .. ngx.var.remote_addr .. " is not blacklisted (country = " .. country .. ")", nil, nil
end

function _M:preread()
	return self:access()
end

function _M:is_in_cache(ip)
	local data, err = datastore:get("plugin_country_cache_" .. ip)
	if not data then
		if err ~= "not found" then
			logger.log(ngx.ERR, "COUNTRY", "Error while accessing cache : " .. err)
		end
		return false, err
	end
	return cjson.decode(data), "success"
end

function _M:add_to_cache(ip, country, result)
	local data = {
		country = country,
		result = result
	}
	local ok, err = datastore:set("plugin_country_cache_" .. ip, cjson.encode(data), 3600)
	if not ok then
		logger.log(ngx.ERR, "COUNTRY", "Error while adding ip to cache : " .. err)
		return false, err
	end
	return true, "success"
end

return _M
