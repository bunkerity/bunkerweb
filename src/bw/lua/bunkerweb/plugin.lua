local class     = require "middleclass"
local logger    = require "bunkerweb.logger"
local datastore = require "bunkerweb.datastore"
local utils     = require "bunkerweb.utils"
local cjson		= require "cjson"
local plugin    = class("plugin")

function plugin:initialize(id)
    -- Store default values
    self.id = id
    self.variables = {}
    -- Instantiate objects
    self.logger = logger:new(id)
    self.datastore = datastore:new()
    -- Get metadata
    local encoded_metadata, err = self.datastore:get("plugin_" .. id)
    if not encoded_metadata then
        self.logger:log(ngx.ERR, err)
        return
    end
    -- Store variables
    local metadata = cjson.decode(encoded_metadata)
    for k, v in pairs(metadata.settings) do
        local value, err = utils.get_variable(k, v.context == "multisite" and ngx.get_phase() ~= "init")
        if value == nil then
            self.logger:log(ngx.ERR, "can't get " .. k .. " variable : " .. err)
        end
        self.variables[k] = value
    end
end

function plugin:get_id()
    return self.id
end

function plugin:ret(ret, msg, status, redirect)
    return {ret = ret, msg = msg, status = status, redirect = redirect}
end

return plugin