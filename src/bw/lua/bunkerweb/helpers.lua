local utils = require "bunkerweb.utils"
local cjson = require "cjson"

local helpers = {}

helpers.load_plugin = function(json)
    -- Open file
    local file, err, nb = io.open(json, "r")
    if not file then
        return false, "can't load JSON at " .. json .. " : " .. err .. " (nb = " .. tostring(nb) .. ")"
    end
    -- Decode JSON
    local ok, plugin = pcall(cjson.decode, file:read("*a"))
    file:close()
    if not ok then
        return false, "invalid JSON at " .. json .. " : " .. err
    end
    -- Check fields
    local missing_fields = {}
    local required_fields = { "id", "name", "description", "version", "settings", "stream" }
    for i, field in ipairs(required_fields) do
        if plugin[field] == nil then
            table.insert(missing_fields, field)
        end
    end
    if #missing_fields > 0 then
        return false, "missing field(s) " .. cjson.encode(missing_fields) .. " for JSON at " .. json
    end
    -- Try require
    local plugin_lua, err = helpers.require_plugin(plugin.id)
    if plugin_lua == false then
        return false, err
    end
    -- Fill phases
    local phases = utils.get_phases()
    plugin.phases = {}
    if plugin_lua then
        for i, phase in ipairs(phases) do
            if plugin_lua[phase] ~= nil then
                table.insert(plugin.phases, phase)
            end
        end
    end
    -- Return plugin
    return true, plugin
end

helpers.order_plugins = function(plugins)
    -- Extract orders
    local file, err, nb = io.open("/usr/share/bunkerweb/core/order.json", "r")
    if not file then
        return false, err .. " (nb = " .. tostring(nb) .. ")"
    end
    local ok, orders = pcall(cjson.decode, file:read("*a"))
    file:close()
    if not ok then
        return false, "invalid order.json : " .. err
    end
    -- Compute plugins/id/phases table
    local plugins_phases = {}
    for i, plugin in ipairs(plugins) do
        plugins_phases[plugin.id] = {}
        for j, phase in ipairs(plugin.phases) do
            plugins_phases[plugin.id][phase] = true
        end
    end
    -- Order result
    local result_orders = {}
    for i, phase in ipairs(utils.get_phases()) do
        result_orders[phase] = {}
    end
    -- Fill order first
    for phase, order in pairs(orders) do
        for i, id in ipairs(order) do
            local plugin = plugins_phases[id]
            if plugin and plugin[phase] then
                table.insert(result_orders[phase], id)
                plugin[phase] = nil
            end
        end
    end
    -- Then append missing plugins to the end
    for i, phase in ipairs(utils.get_phases()) do
        for id, plugin in pairs(plugins_phases) do
            if plugin[phase] then
                table.insert(result_orders[phase], id)
                plugin[phase] = nil
            end
        end
    end
    return true, result_orders
end

helpers.require_plugin = function(id)
    -- Require call
    local ok, plugin_lua = pcall(require, id .. "/" .. id)
    if not ok then
        if plugin_lua:match("not found") then
            return nil, "plugin " .. id .. " doesn't have LUA code"
        end
        return false, "require error for plugin " .. id .. " : " .. plugin_lua
    end
    -- New call
    if plugin_lua.new == nil then
        return false, "missing new() method for plugin " .. id
    end
    -- Return plugin
    return plugin_lua, "require() call successful for plugin " .. id
end

helpers.new_plugin = function(plugin_lua)
    -- Require call
    local ok, plugin_obj = pcall(plugin_lua.new, plugin_lua)
    if not ok then
        return false, "new error for plugin " .. plugin_lua.name .. " : " .. plugin_obj
    end
    return true, plugin_obj
end

helpers.call_plugin = function(plugin, method)
    -- Check if method is present
    if plugin[method] == nil then
        return nil, "missing " .. method .. "() method for plugin " .. plugin:get_id()
    end
    -- Call method
    local ok, ret = pcall(plugin[method], plugin)
    if not ok then
        return false, plugin:get_id() .. ":" .. method .. "() failed : " .. ret
    end
    if ret == nil then
        return false, plugin:get_id() .. ":" .. method .. "() returned nil value"
    end
    -- Check values
    local missing_values = {}
    local required_values = { "ret", "msg" }
    for i, value in ipairs(required_values) do
        if ret[value] == nil then
            table.insert(missing_values, value)
        end
    end
    if #missing_values > 0 then
        return false, "missing required return value(s) : " .. cjson.encode(missing_values)
    end
    -- Return
    return true, ret
end

helpers.fill_ctx = function()
    -- Return errors as table
    local errors = {}
    local use_redis = nil
    -- Check if ctx is already filled
    if not ngx.ctx.bw then
        -- Instantiate bw table
        local data = {}
        -- Common vars
        data.kind = "http"
        if ngx.shared.datastore_stream then
            data.kind = "stream"
        end
        data.remote_addr = ngx.var.remote_addr
        data.uri = ngx.var.uri
        data.request_uri = ngx.var.request_uri
        data.request_method = ngx.var.request_method
        data.http_user_agent = ngx.var.http_user_agent
        data.http_host = ngx.var.http_host
        data.server_name = ngx.var.server_name
        data.http_content_type = ngx.var.http_content_type
        data.http_origin = ngx.var.http_origin
        -- IP data : global
        local ip_is_global, err = utils.ip_is_global(data.remote_addr)
        if ip_is_global == nil then
            table.insert(errors, "can't check if IP is global : " .. err)
        else
            data.ip_is_global = ip_is_global
        end
        -- IP data : v4 / v6
        data.ip_is_ipv4 = utils.is_ipv4(data.ip)
        data.ip_is_ipv6 = utils.is_ipv6(data.ip)
        -- Misc info
        data.integration = utils.get_integration()
        data.version = utils.get_version()
        -- Common objects
        use_redis, err = utils.get_variable("USE_REDIS", false)
        if not use_redis then
            table.insert(errors, "can't get variable from datastore : " .. err)
        end
        -- Fill ctx
        ngx.ctx.bw = data
    end
    -- Always create new objects for current phases in case of cosockets
    ngx.ctx.bw.datastore = require "bunkerweb.datastore":new()
    ngx.ctx.bw.clusterstore = require "bunkerweb.clusterstore":new()
    ngx.ctx.bw.cachestore = require "bunkerweb.cachestore":new(use_redis == "yes")
    return true, "ctx filled", errors
end

return helpers
