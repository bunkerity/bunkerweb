local utils = require "bunkerweb.utils"
local cjson = require "cjson"

local helpers = {}

helpers.load_plugin = function(json)
    -- Open file
    local file, err, nb = io.open(json, "r")
    if not file then
        return false, "can't load JSON at " .. json .. " : " .. err .. "(nb = " .. tostring(nb) .. ")"
    end
    -- Decode JSON
    local ok, plugin = pcall(cjson.decode, file:read("*a"))
    file:close()
    if not ok then
        return false, "invalid JSON at " .. json .. " : " .. err
    end
    -- Check fields
    local missing_fields = {}
    local required_fields = {"id", "order", "name", "description", "version", "settings"}
    for i, field in ipairs(required_fields) do
        if plugin[field] == nil then
            valid_json = false
            table.insert(missing_fields, field)
        end
    end
    if #missing_fields > 0 then
        return false, "missing field(s) " .. cjson.encode(missing_fields) .. " for JSON at " .. json
    end
    -- Return plugin
    return true, plugin
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
    return plugin_lua, "new() call successful for plugin " .. id
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
    local required_values = {"ret", "msg"}
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
    -- Check if ctx is already filled
    if ngx.ctx.bw then
        return true, "already filled"
    end
    -- Return errors as table
    local errors = {}
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
    -- Plugins
    data.plugins = {}
    -- Fill ctx
    ngx.ctx.bw = data
    return true, "ctx filled", errors
end

return helpers