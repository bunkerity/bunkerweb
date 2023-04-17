local class			= require "middleclass"
local plugin		= require "bunkerweb.plugin"
local utils     	= require "bunkerweb.utils"
local cachestore 	= require "bunkerweb.cachestore"

local reversescan = class("reversescan", plugin)

function reversescan:new()
	-- Call parent new
	local ok, err = plugin.new(self, "reversescan")
	if not ok then
		return false, err
	end
	-- Instantiate cachestore
	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if not use_redis then
		return false, err
	end
	cachestore:new(use_redis)
	return true, "success"
end

function reversescan:access()
    -- Check if access is needed
    if self.variables["USE_REVERSE_SCAN"] ~= "yes" then
        return self:ret(true, "reverse scan not activated")
    end
    -- Loop on ports
    for port in self.variables["REVERSE_SCAN_PORTS"]:gmatch("%S+") do
        -- Check if the scan is already cached
        local cached, err = self:is_in_cache(ngx.var.remote_addr .. ":" .. port)
        if cached == nil then
            return self:ret(false, "error getting cache from datastore : " .. err)
        end
        if cached == "open" then
            return self:ret(true, "port " .. port .. " is opened for IP " .. ngx.var.remote_addr, utils.get_deny_status())
        elseif not cached then
            -- Do the scan
            local res, err = self:scan(ngx.var.remote_addr, tonumber(port), tonumber(self.variables["REVERSE_SCAN_TIMEOUT"]))
            -- Cache the result
            local ok, err = self:add_to_cache(ngx.var.remote_addr .. ":" .. port, res)
            if not ok then
                return self:ret(false, "error updating cache from datastore : " .. err)
            end
            -- Deny request if port is open
            if res == "open" then
                return self:ret(true, "port " .. port .. " is opened for IP " .. ngx.var.remote_addr, utils.get_deny_status())
            end
        end
    end
    -- No port opened
    return self:ret(true, "no port open for IP " .. ngx.var.remote_addr)
end

function reversescan:scan(ip, port, timeout)
    local tcpsock = ngx.socket.tcp()
    tcpsock:settimeout(timeout)
    local ok, err = tcpsock:connect(ip, port)
    tcpsock:close()
    if not ok then
        return "close", err
    end
    return "open", nil
end

function reversescan:is_in_cache(ip_port)
	local ok, data = cachestore:get("plugin_reversescan_cache_" .. ip_port)
	if not ok then then
		return false, data
	end 
	return true, data
end

function reversescan:add_to_cache(ip_port, value)
	local ok, err = cachestore:set("plugin_reversescan_cache_" .. ip_port, value)
	if not ok then then
		return false, err
	end 
	return true
end

return reversescan