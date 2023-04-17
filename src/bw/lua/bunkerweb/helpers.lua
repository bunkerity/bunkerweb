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

return helpers