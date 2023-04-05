local _M = {}
_M.__index = _M

local utils     = require "utils"
local datastore = require "datastore"
local logger    = require "logger"
local cjson     = require "cjson"

function _M.new()
    local self = setmetatable({}, _M)
    return self, nil
end

function _M:access()
    -- Check if access is needed
    local access_needed, err = utils.get_variable("USE_REVERSE_SCAN")
    if access_needed == nil then
        return false, "can't get USE_REVERSE_SCAN setting from datastore : " .. err, nil, nil
    end
    if access_needed ~= "yes" then
        return true, "reverse scan not activated", nil, nil
    end
    -- Get ports
    local ports, err = utils.get_variable("REVERSE_SCAN_PORTS")
    if ports == nil then
        return false, "can't get REVERSE_SCAN_PORTS setting from datastore : " .. err, nil, nil
    end
    if ports == "" then
        return true, "no port defined", nil, nil
    end
    -- Get timeout
    local timeout, err = utils.get_variable("REVERSE_SCAN_TIMEOUT")
    if timeout == nil then
        return false, "can't get REVERSE_SCAN_TIMEOUT setting from datastore : " .. err, nil, nil
    end
    -- Loop on ports
    for port in ports:gmatch("%S+") do
        -- Check if the scan is already cached
        local cached, err = self:is_in_cache(ngx.var.remote_addr .. ":" .. port)
        if cached == nil then
            return false, "error getting cache from datastore : " .. err, nil, nil
        end
        if cached == "open" then
            return true, "port " .. port .. " is opened for IP " .. ngx.var.remote_addr, true, utils.get_deny_status()
        elseif not cached then
            -- Do the scan
            local res, err = self:scan(ngx.var.remote_addr, tonumber(port), tonumber(timeout))
            -- Cache the result
            local ok, err = self:add_to_cache(ngx.var.remote_addr .. ":" .. port, res)
            if not ok then
                return false, "error updating cache from datastore : " .. err, nil, nil
            end
            -- Deny request if port is open
            if res == "open" then
                return true, "port " .. port .. " is opened for IP " .. ngx.var.remote_addr, true, utils.get_deny_status()
            end
        end
    end
    return nil, "no port open for IP " .. ngx.var.remote_addr, nil, nil
end

function _M:scan(ip, port, timeout)
    local tcpsock = ngx.socket.tcp()
    tcpsock:settimeout(timeout)
    local ok, err = tcpsock:connect(ip, port)
    tcpsock:close()
    if not ok then
        return "close", err
    end
    return "open", nil
end

function _M:is_in_cache(ele)
    local res, err = datastore:get("plugin_reversescan_" .. ele)
    if not res then
        if err == "not found" then
            return false, nil
        end
        return nil, err
    end
    return true, res
end

function _M:add_to_cache(ele, value)
    local ok, err = datastore:set("plugin_reversescan_" .. ele, value, 86400)
    if not ok then
        return false, err
    end
    return true, nil
end


return _M