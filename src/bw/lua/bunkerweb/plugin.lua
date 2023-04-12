local class     = require "middleclass"
local datastore = require "bunkerweb.datastore"
local datastore = require "bunkerweb.utils"
local cjson		= require "cjson"
local plugin    = class("plugin")


function plugin:new(id)
    -- Store default values
    self.id = id
    self.variables = {}
    -- Instantiate logger
    self.logger = require "bunkerweb.logger"
    self.logger:new(id)
    -- Get metadata
    local encoded_metadata, err = datastore:get("plugin_" .. id)
    if not encoded_metadata then
        return false, err
    end
    -- Store variables
    local metadata = cjson.decode(encoded_metadata)
    for k, v in pairs(metadata.settings) do
        local value, err = utils.get_variable(k, v.context == "multisite")
        if value == nil then
            return false, "can't get " .. k .. " variable : " .. err
        end
        self.variables[k] = value
    end
    return true, "success"
end

function plugin:get_id()
    return self.id
end

function plugin:ret(ret, msg, status, redirect)
    return {ret = ret, msg = msg, status = status, redirect = redirect}
end

return plugin