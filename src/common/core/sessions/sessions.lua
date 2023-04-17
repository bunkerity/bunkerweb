local class			= require "middleclass"
local plugin		= require "bunkerweb.plugin"
local utils     	= require "bunkerweb.utils"
local session   	= require "resty.session"

local sessions = class("sessions", plugin)

function sessions:initialize()
    -- Call parent initialize
    plugin.initialize(self, "sessions")
end

function sessions:init()
    -- Get redis vars
    local redis_vars = {
        ["USE_REDIS"] = "",
        ["REDIS_HOST"] = "",
        ["REDIS_PORT"] = "",
        ["REDIS_SSL"] = "",
        ["REDIS_TIMEOUT"] = "",
        ["REDIS_KEEPALIVE_IDLE"] = "",
        ["REDIS_KEEPALIVE_POOL"] = ""
    }
    for k, v in pairs(redis_vars) do
        local var, err = utils.get_variable(k, false)
        if var == nil then
            return self:ret(false, "can't get " .. k .. " variable : " .. err)
        end
    end
    -- Init configuration
    local config = {
        secret = self.variables["SESSIONS_SECRET"],
        cookie_name = self.variables["SESSIONS_NAME"],
        idling_timeout = tonumber(self.variables["SESSIONS_IDLING_TIMEOUT"]),
        rolling_timeout = tonumber(self.variables["SESSIONS_ROLLING_TIMEOUT"]),
        absolute_timeout = tonumber(self.variables["SESSIONS_ABSOLUTE_TIMEOUT"])
    }
    if self.variables["SESSIONS_SECRET"] == "random" then
        config.secret = utils.rand(16)
    end
    if self.variables["SESSIONS_NAME"] == "random" then
        config.cookie_name = utils.rand(16)
    end
    if redis_vars["USE_REDIS"] ~= "yes" then
        config.storage = "cookie"
    else
        config.storage = "redis"
        config.redis = {
            prefix = "sessions_",
            connect_timeout = tonumber(redis_vars["REDIS_TIMEOUT"]),
            send_timeout = tonumber(redis_vars["REDIS_TIMEOUT"]),
            read_timeout = tonumber(redis_vars["REDIS_TIMEOUT"]),
            keepalive_timeout = tonumber(redis_vars["REDIS_KEEPALIVE_IDLE"]),
            pool = "bw",
            pool_size = tonumber(redis_vars["REDIS_KEEPALIVE_POOL"]),
            ssl = redis_vars["REDIS_SSL"] == "yes",
            host = redis_vars["REDIS_HOST"],
            port = tonumber(redis_vars["REDIS_HOST"]),
            database = tonumber(redis_vars["REDIS_DATABASE"])
        }
    end
    session.init(config)
    return self:ret(true, "sessions init successful")
end

return sessions