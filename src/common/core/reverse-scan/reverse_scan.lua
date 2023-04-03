local _M = {}
_M.__index = _M


local utils     = require "utils"
local datastore = require "datastore"
local logger    = require "logger"
local cjson     = require "cjson"
local socket = require "socket"

function _M.new()
    local self = setmetatable({}, _M)
        return self, nil
end

function _M:init()
    logger.log(ngx.NOTICE, "REVERSE_SCAN", "init called")
    -- Check if init is needed 
    local init_needed, err = utils.has_variable("REVERSE_SCAN", "yes")
    if init_needed == nil then
        return false, err
        end
    if not init_needed then
        return true, "no service uses port_scanning, skipping init"
        end
    local data = {}
    -- Get variable -- 
    local value, err = utils.get_variable("PORT_SCAN")
    logger.log(ngx.NOTICE, "REVERSE_SCAN", "port = " .. value)
    for srv in value:gmatch("%S+") do
        table.insert(data , srv)
    end
    -- Load them into datastore
    local ok, err = datastore:set("plug_scan_port" ,cjson.encode(data))
    if not ok then
                return false, "can't store port list into datastore : " .. err
    end
    return true, "successfully loaded scan port"
end

function _M:access()
    logger.log(ngx.NOTICE, "REVERSE_SCAN", "access called")
    -- Check if access is needed
    local scan_port, err = utils.get_variable("REVERSE_SCAN")

    if scan_port ~= "yes" then
        return true, "Scan port not activated"
    end
    -- Check the cache
    local cached_ip, err = self:is_in_cache("ip" .. ngx.var.remote_addr)
    -- check for errors
    if cached_ip=="denied"  then
        return true, "client IP " .. ngx.var.remote_addr  .. " is suspicious : port open", true, utils.get_deny_status()
    elseif cached_ip=="clean" then
        return true , "Ip already scanned and is clean" , nil , nil
    elseif cached_ip ~= false then
        return false, err , nil , nil
    end
    --get port
    local data, err = datastore:get("plug_scan_port")
    if not data then
        return false, "can't get port list : " .. err, false, nil
    end
    local port_List = cjson.decode(data)
    
    --call scan function
    local sus = nil
    for i = 1, #port_List do
        if _M:scan(port_List[i]) then

            sus = true
            self:add_to_cache("ip" .. ngx.var.remote_addr, "denied")

            return nil, "client IP " .. ngx.var.remote_addr  .. " is suspicious : port open", true, utils.get_deny_status()
        end
    end
    self:add_to_cache("ip" .. ngx.var.remote_addr, "clean")
    return nil, "client IP " .. ngx.var.remote_addr  .. " is safe ", true, nil
end

function  _M:scan(prt)
    local time, err = utils.get_variable("TIMEOUT")
    logger.log(ngx.NOTICE, "REVERSE_SCAN", " scan called on port " .. prt)
    if prt == nil then
        return false , "port is null"
    end
    local client = socket.tcp()
    client:settimeout(time) 
    local status, err = client:connect(ngx.var.remote_addr, prt)
    if not status then
        if err == "timeout" then
          return false, "timeout"
        else
          return false, err
        end
      end
      client:close()
      return true
end



function _M:is_in_cache(ele)
        local kind, err = datastore:get("plug_scan_port" .. ngx.var.server_name .. ele)
        if not kind then
            if err ~= "not found" then
                logger.log(ngx.ERR, "REVERSE_SCAN", " Error while accessing cache : " .. err)
        end
        return false, err
end
return kind, "success"
end

function _M:add_to_cache(ele, kind)
local ok, err = datastore:set("plug_scan_port" .. ngx.var.server_name .. ele, kind, 3600)
if not ok then
        logger.log(ngx.ERR, "REVERSE_SCAN", "Error while adding element to cache : " .. err)
        return false, err
end
return true, "success"
end


return _M