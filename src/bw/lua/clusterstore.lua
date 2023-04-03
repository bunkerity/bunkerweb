local M     = {}
local redis = require "resty.redis"
local utils = require "utils"

function M:connect()
    -- Instantiate object
    local redis_client, err = redis:new()
    if redis_client == nil then
        return false, err
    end
    -- Get variables
    local variables = {
        ["REDIS_HOST"] = "",
        ["REDIS_PORT"] = "",
        ["REDIS_SSL"] = "",
        ["REDIS_TIMEOUT"] = "",
        ["REDIS_KEEPALIVE_IDLE"] = "",
        ["REDIS_KEEPALIVE_POOL"] = ""
    }
    for k, v in pairs(variables) do
        local value, err = utils.get_variable(k, false)
        if value == nil then
            return false, err
        end
        variables[k] = value
    end
    -- Set timeouts
    redis_client:set_timeouts(tonumber(variables["REDIS_TIMEOUT"]), tonumber(variables["REDIS_TIMEOUT"]), tonumber(variables["REDIS_TIMEOUT"]))
    -- Connect
    local options = {
        ["ssl"] = false
    }
    if variables["REDIS_SSL"] == "yes" then
        options["ssl"] = true
    end
    local ok, err = redis_client:connect(variables["REDIS_HOST"], tonumber(variables["REDIS_PORT"]), options)
    if not ok then
        return false, err
    end
    return redis_client
end

function M:close(redis_client)
    -- Get variables
    local variables = {
        ["REDIS_KEEPALIVE_IDLE"] = "",
        ["REDIS_KEEPALIVE_POOL"] = ""
    }
    for k, v in pairs(variables) do
        local value, err = utils.get_variable(k, false)
        if value == nil then
            return false, err
        end
        variables[k] = value
    end
    -- Equivalent to close but keep a pool of connections
    return redis_client:set_keepalive(tonumber(variables["REDIS_KEEPALIVE_IDLE"]), tonumber(variables["REDIS_KEEPALIVE_POOL"]))
end

return M