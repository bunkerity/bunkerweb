local datastore	= require "datastore"
local cjson		= require "cjson"

local plugins	= {}

plugins.load = function(self, path)
	-- Read plugin.json file
	local file = io.open(path .. "/plugin.json")
	if not file then
		return false, "can't read plugin.json file"
	end
	
	-- Decode plugin.json
	-- TODO : check return value of file:read and cjson.encode
	local data = cjson.decode(file:read("*a"))
	file:close()
	
	-- Check required fields
	local required_fields = {"id", "order", "name", "description", "version", "settings"}
	for i, field in ipairs(required_fields) do
		if data[field] == nil then
			return false, "missing field " .. field .. " in plugin.json"
		end
		-- TODO : check values and types with regex
	end
	
	-- Get existing plugins
	local list, err = plugins:list()
	if not list then
		return false, err
	end 
	
	-- Add our plugin to existing list and sort it
	table.insert(list, data)
	table.sort(list, function (a, b)
		return a.order < b.order
	end)
	
	-- Save new plugin list in datastore
	local ok, err = datastore:set("plugins", cjson.encode(list))
	if not ok then
		return false, "can't save new plugin list"
	end
	
	-- Save default settings value
	for variable, value in pairs(data.settings) do
		ok, err = datastore:set("plugin_" .. data.id .. "_" .. variable, value["default"])
		if not ok then
			return false, "can't save default variable value of " .. variable .. " into datastore"
		end
	end
	
	-- Return the plugin
	return data, "success"
end

plugins.list = function(self)
	-- Get encoded plugins from datastore
	local encoded_plugins, err = datastore:get("plugins")
	if not encoded_plugins then
		return false, "can't get encoded plugins from datastore"
	end
	
	-- Decode and return the list
	return cjson.decode(encoded_plugins), "success"
end

return plugins
