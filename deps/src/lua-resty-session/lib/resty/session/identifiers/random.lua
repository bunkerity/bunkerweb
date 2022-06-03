local tonumber = tonumber
local random   = require "resty.random".bytes
local var      = ngx.var

local defaults = {
    length = tonumber(var.session_random_length, 10) or 16
}

return function(session)
    local config = session.random or defaults
    local length = tonumber(config.length, 10) or defaults.length
    return random(length, true) or random(length)
end
