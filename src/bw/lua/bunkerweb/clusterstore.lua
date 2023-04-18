local class     = require "middleclass"
local utils     = require "bunkerweb.utils"
local logger    = require "bunkerweb.logger"
local redis     = require "resty.redis"

local clusterstore = class("clusterstore")

function clusterstore:initialize()
    -- Instantiate logger
    self.logger = logger:new("CLUSTERSTORE")
    -- Get variables
    local variables = {
        ["REDIS_HOST"] = "",
        ["REDIS_PORT"] = "",
        ["REDIS_DATABASE"] = "",
        ["REDIS_SSL"] = "",
        ["REDIS_TIMEOUT"] = "",
        ["REDIS_KEEPALIVE_IDLE"] = "",
        ["REDIS_KEEPALIVE_POOL"] = ""
    }
    -- Set them for later user
    self.variables = {}
    for k, v in pairs(variables) do
        local value, err = utils.get_variable(k, false)
        if value == nil then
            self.logger:log(ngx.ERR, err)
        end
        self.variables[k] = value
    end
    -- Don't instantiate a redis object for now
    self.redis_client = nil
end

function clusterstore:connect()
    -- Check if we are already connected
    if self.redis_client ~= nil then
        return true, "already connected"
    end
    -- Instantiate object
    local redis_client, err = redis:new()
    if redis_client == nil then
        return false, err
    end
    -- Set timeouts
    redis_client:set_timeouts(tonumber(self.variables["REDIS_TIMEOUT"]), tonumber(self.variables["REDIS_TIMEOUT"]), tonumber(self.variables["REDIS_TIMEOUT"]))
    -- Connect
    local options = {
        ssl = self.variables["REDIS_SSL"] == "yes",
        pool = "bw",
        pool_size = tonumber(self.variables["REDIS_KEEPALIVE_POOL"])
    }
    local ok, err = redis_client:connect(self.variables["REDIS_HOST"], tonumber(self.variables["REDIS_PORT"]), options)
    if not ok then
        return false, err
    end
    -- Save client
    self.redis_client = redis_client
    -- Select database if needed
    local times, err = redis_client:get_reused_times()
    if err then
        self:close()
        return false, err
    end
    if times == 0 then
        local select, err = redis_client:select(tonumber(variables["REDIS_DATABASE"]))
        if err then
            self:close()
            return false, err
        end
    end
    return true, "success"
end

function clusterstore:close()
    if self.redis_client then
        -- Equivalent to close but keep a pool of connections
        self.redis_client = nil
        return self.redis_client:set_keepalive(tonumber(self.variables["REDIS_KEEPALIVE_IDLE"]), tonumber(self.variables["REDIS_KEEPALIVE_POOL"]))
    end
    return false, "not connected"
end

function clusterstore:call(method, ...)
    -- Check if we are connected
    if not self.redis_client then
        return false, "not connected"
    end
    -- Call method
    return self.redis_client[method](self.redis_client, ...)
end

function clusterstore:multi(calls)
    -- Check if we are connected
    if not self.redis_client then
        return false, "not connected"
    end
    -- Start transaction
    local ok, err = self.redis_client:multi()
    if not ok then
        return false, "multi() failed : " .. err
    end
    -- Loop on calls
    for i, call in ipairs(calls) do
        local method = call[1]
        local args = table.unpack(call[2])
        local ok, err = self.redis_client[method](self.redis_client, args)
        if not ok then
            return false, method + "() failed : " .. err
        end
    end
    -- Exec transaction
    local exec, err = self.redis_client:exec()
    if not exec then
        return false, "exec() failed : " .. err
    end
    if type(exec) ~= "table" then
        return false, "exec() result is not a table"
    end
    return true, "success", exec
end

return clusterstore