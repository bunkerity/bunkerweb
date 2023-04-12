local class     = require "middleclass"
local plugin    = class("plugin")

function plugin:new(id)
    self.id = id
    self.logger = require "bunkerweb.logger"
    self.logger:new(id)
end

function plugin:get_id()
    return self.id
end

function plugin:ret(ret, msg, status, redirect)
    return {ret = ret, msg = msg, status = status, redirect = redirect}
end

return plugin