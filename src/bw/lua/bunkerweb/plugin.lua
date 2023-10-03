local class        = require "middleclass"
local logger       = require "bunkerweb.logger"
local datastore    = require "bunkerweb.datastore"
local cachestore   = require "bunkerweb.cachestore"
local clusterstore = require "bunkerweb.clusterstore"
local utils        = require "bunkerweb.utils"
local cjson        = require "cjson"
local plugin       = class("plugin")

function plugin:initialize(id, ctx)
    -- Store common, values
    self.id = id
    local multisite = false
    local current_phase = ngx.get_phase()
    for i, check_phase in ipairs({ "set", "access", "content", "header_filter", "log", "preread", "log_stream",
        "log_default" }) do
        if current_phase == check_phase then
            multisite = true
            break
        end
    end
    self.is_request = multisite
    -- Store common objects
    self.logger = logger:new(self.id)
    local use_redis, err = utils.get_variable("USE_REDIS", false)
    if not use_redis then
        self.logger:log(ngx.ERR, err)
    end
    self.use_redis = use_redis == "yes"
    if self.is_request then
        -- Store ctx
        self.ctx = ctx or ngx.ctx
        self.datastore = utils.get_ctx_obj("datastore", self.ctx) or datastore:new()
        self.cachestore = utils.get_ctx_obj("cachestore", self.ctx) or cachestore:new(use_redis == "yes", true, self.ctx)
        self.clusterstore = utils.get_ctx_obj("clusterstore", self.ctx) or clusterstore:new(false)
    else
        self.datastore = datastore:new()
        self.cachestore = cachestore:new(use_redis == "yes", true)
        self.clusterstore = clusterstore:new(false)
    end
    -- Get metadata
    local metadata, err = self.datastore:get("plugin_" .. id, true)
    if not metadata then
        self.logger:log(ngx.ERR, err)
        return
    end
    -- Store variables
    self.variables = {}
    self.multiples = {}
    for k, v in pairs(metadata.settings) do
        local value, err = utils.get_variable(k, v.context == "multisite" and multisite)
        if value == nil then
            self.logger:log(ngx.ERR, "can't get " .. k .. " variable : " .. err)
        end
        self.variables[k] = value
        -- if v.multiple then
        --     local multiples, err = utils.get_multiple_variables(k)
        --     if not multiples then
        --         self.logger:log(ngx.ERR, "can't get " .. k .. " multiple variable : " .. err)
        --         self.multiples[k] = {}
        --     else
        --         self.multiples[k] = multiples
        --     end
        -- end
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
    return { ret = ret, msg = msg, status = status, redirect = redirect }
end

return plugin
