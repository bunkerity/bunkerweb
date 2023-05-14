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
    local multisite = false
    local current_phase = ngx.get_phase()
    for i, check_phase in ipairs({"set", "access", "log", "preread"}) do
        if current_phase == check_phase then
            multisite = true
            break
        end
    end
    self.is_request = multisite
    for k, v in pairs(metadata.settings) do
        local value, err = utils.get_variable(k, v.context == "multisite" and multisite)
        if value == nil then
            self.logger:log(ngx.ERR, "can't get " .. k .. " variable : " .. err)
        end
        self.variables[k] = value
    end
    -- Is loading
    local is_loading, err = utils.get_variable("IS_LOADING", false)
    if is_loading == nil then
        self.logger:log(ngx.ERR, "can't get IS_LOADING variable : " .. err)
    end
    self.is_loading = is_loading == "yes"
    -- Kind of server
    self.kind = "http"
    if ngx.shared.datastore_stream then
        self.kind = "stream"
    end
end

function plugin:get_id()
    return self.id
end

function plugin:ret(ret, msg, status, redirect)
    return {ret = ret, msg = msg, status = status, redirect = redirect}
end

return plugin