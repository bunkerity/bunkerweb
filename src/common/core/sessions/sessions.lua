local class    = require "middleclass"
local plugin   = require "bunkerweb.plugin"
local utils    = require "bunkerweb.utils"
local session  = require "resty.session"

local sessions = class("sessions", plugin)

function sessions:initialize()
    -- Call parent initialize
    plugin.initialize(self, "sessions")
    -- Check if random cookie name and secrets are already generated
    local is_random = {
        "SESSIONS_SECRET",
        "SESSIONS_NAME"
    }
    self.randoms = {}
    for i, var in ipairs(is_random) do
        if self.variables[var] == "random" then
            local data, err = self.datastore:get("storage_sessions_" .. var)
            if data then
                self.randoms[var] = data
            end
        end
    end
end

function sessions:set()
    if self.is_loading or self.kind ~= "http" then
        return self:ret(true, "set not needed")
    end
    local checks = {
        ["IP"] = ngx.ctx.bw.remote_addr,
        ["USER_AGENT"] = ngx.ctx.bw.http_user_agent or ""
    }
    ngx.ctx.bw.sessions_checks = {}
    for check, value in pairs(checks) do
        if self.variables["SESSIONS_CHECK_" .. check] == "yes" then
            table.insert(ngx.ctx.bw.sessions_checks, {check, value})
        end
    end
    return self:ret(true, "success")
end

function sessions:init()
    if self.is_loading or self.kind ~= "http" then
        return self:ret(true, "init not needed")
    end
    -- Get redis vars
    local redis_vars = {
        ["USE_REDIS"] = "",
        ["REDIS_HOST"] = "",
        ["REDIS_PORT"] = "",
        ["REDIS_DATABASE"] = "",
        ["REDIS_SSL"] = "",
        ["REDIS_TIMEOUT"] = "",
        ["REDIS_KEEPALIVE_IDLE"] = "",
        ["REDIS_KEEPALIVE_POOL"] = ""
    }
    for k, v in pairs(redis_vars) do
        local value, err = utils.get_variable(k, false)
        if value == nil then
            return self:ret(false, "can't get " .. k .. " variable : " .. err)
        end
        redis_vars[k] = value
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
        if self.randoms["SESSIONS_SECRET"] then
            config.secret = self.randoms["SESSIONS_SECRET"]
        else
            config.secret = utils.rand(16)
            local ok, err = self.datastore:set("storage_sessions_SESSIONS_SECRET", config.secret)
            if not ok then
                self.logger:log(ngx.ERR, "error from datastore:set : " .. err)
            end
        end
    end
    if self.variables["SESSIONS_NAME"] == "random" then
        if self.randoms["SESSIONS_NAME"] then
            config.cookie_name = self.randoms["SESSIONS_NAME"]
        else
            config.cookie_name = utils.rand(16)
            local ok, err = self.datastore:set("storage_sessions_SESSIONS_NAME", config.cookie_name)
            if not ok then
                self.logger:log(ngx.ERR, "error from datastore:set : " .. err)
            end
        end
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
            pool = "bw-redis",
            pool_size = tonumber(redis_vars["REDIS_KEEPALIVE_POOL"]),
            ssl = redis_vars["REDIS_SSL"] == "yes",
            host = redis_vars["REDIS_HOST"],
            port = tonumber(redis_vars["REDIS_PORT"]),
            database = tonumber(redis_vars["REDIS_DATABASE"])
        }
    end
    session.init(config)
    return self:ret(true, "sessions init successful")
end

return sessions
