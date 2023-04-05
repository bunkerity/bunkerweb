local _M = {}
_M.__index = _M

local utils			= require "utils"
local session   	= require "resty.session"

function _M.new()
	local self = setmetatable({}, _M)
	return self, nil
end

function _M:init()
    -- Get vars
    local vars = {
        ["SESSION_SECRET"] = "",
        ["SESSION_NAME"] = "",
        ["SESSION_IDLING_TIMEOUT"] = "",
        ["SESSION_ROLLING_TIMEOUT"] = "",
        ["SESSION_ABSOLUTE_TIMEOUT"] = "",
        ["USE_REDIS"] = "",
        ["REDIS_HOST"] = "",
        ["REDIS_PORT"] = "",
        ["REDIS_SSL"] = "",
        ["REDIS_TIMEOUT"] = "",
        ["REDIS_KEEPALIVE_IDLE"] = "",
        ["REDIS_KEEPALIVE_POOL"] = ""
    }
    for k, v in pairs(vars) do
        local var, err = utils.get_variable(k, false)
        if var == nil then
            return false, "can't get " .. k .. " variable : " .. err
        end
    end
    -- Init configuration
    local config = {
        secret = vars["SESSION_SECRET"],
        cookie_name = vars["SESSION_NAME"],
        idling_timeout = tonumber(vars["SESSION_IDLING_TIMEOUT"]),
        rolling_timeout = tonumber(vars["SESSION_ROLLING_TIMEOUT"]),
        absolute_timeout = tonumber(vars["SESSION_ABSOLUTE_TIMEOUT"])
    }
    if vars["SESSION_SECRET"] == "random" then
        config.secret = utils.rand(16)
    end
    if vars["SESSION_NAME"] == "random" then
        config.cookie_name = utils.rand(16)
    end
    if vars["USE_REDIS"] == "no" then
        config.storage = "cookie"
    else
        config.storage = "redis"
        config.redis = {
            prefix = "session_",
            connect_timeout = tonumber(vars["REDIS_TIMEOUT"]),
            send_timeout = tonumber(vars["REDIS_TIMEOUT"]),
            read_timeout = tonumber(vars["REDIS_TIMEOUT"]),
            keepalive_timeout = tonumber(vars["REDIS_KEEPALIVE_IDLE"]),
            pool = "bw",
            pool_size = tonumber(vars["REDIS_KEEPALIVE_POOL"]),
            ssl = vars["REDIS_SSL"] == "yes",
            host = vars["REDIS_HOST"],
            port = tonumber(vars["REDIS_HOST"]),
            database = tonumber(vars["REDIS_DATABASE"])
        }
    end
    session.init(config)
end

function _M:access()
    -- Start session and refresh it if needed
    local client_session, err, exists, refreshed = session.start()
    if err then
        return false, "can't open session : " .. err, nil, nil
    end
    -- Refresh it
    if exists then
        local ok, err = client_session:refresh()
        if err then
            return false, "can't refresh session : " .. err, nil, nil
        end
    end
end

return _M
