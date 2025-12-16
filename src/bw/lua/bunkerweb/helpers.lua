local ngx = ngx
local base = require "resty.core.base"
local bwctx = require "bunkerweb.ctx"
local cjson = require "cjson"
local utils = require "bunkerweb.utils"

local open = io.open
local decode = cjson.decode
local encode = cjson.encode
local tostring = tostring
local get_phases = utils.get_phases
local get_request = base.get_request
local apply_ref = bwctx.apply_ref
local stash_ref = bwctx.stash_ref
local subsystem = ngx.config.subsystem
local var = ngx.var
local req = ngx.req
local shared = ngx.shared
local ip_is_global = utils.ip_is_global
local is_ipv4 = utils.is_ipv4
local is_ipv6 = utils.is_ipv6
local get_variable = utils.get_variable

local helpers = {}

helpers.load_plugin = function(json)
	-- Open file
	local file, err, nb = open(json, "r")
	if not file then
		return false, "can't load JSON at " .. json .. " : " .. err .. " (nb = " .. tostring(nb) .. ")"
	end
	-- Decode JSON
	local ok, plugin = pcall(decode, file:read("*a"))
	file:close()
	if not ok then
		return false, "invalid JSON at " .. json .. " : " .. err
	end
	-- Check fields
	local missing_fields = {}
	local required_fields = { "id", "name", "description", "version", "settings", "stream" }
	for _, field in ipairs(required_fields) do
		if plugin[field] == nil then
			table.insert(missing_fields, field)
		end
	end
	if #missing_fields > 0 then
		return false, "missing field(s) " .. encode(missing_fields) .. " for JSON at " .. json
	end
	-- Try require
	local plugin_lua, err = helpers.require_plugin(plugin.id)
	if plugin_lua == false then
		return false, err
	end
	-- Fill phases
	local phases = get_phases()
	plugin.phases = {}
	if plugin_lua then
		for _, phase in ipairs(phases) do
			if plugin_lua[phase] ~= nil then
				table.insert(plugin.phases, phase)
			end
		end
	end
	-- Return plugin
	return true, plugin
end

local function parse_override(value)
	if type(value) ~= "string" or value == "" then
		return {}
	end

	local ids = {}
	for token in value:gmatch("%S+") do
		table.insert(ids, token)
	end

	return ids
end

helpers.order_plugins = function(plugins, variables)
	-- Extract default orders
	local file, err, nb = open("/usr/share/bunkerweb/core/order.json", "r")
	if not file then
		return false, err .. " (nb = " .. tostring(nb) .. ")"
	end
	local ok, orders = pcall(decode, file:read("*a"))
	file:close()
	if not ok then
		return false, "invalid order.json : " .. err
	end

	-- Map legacy keys to phases
	local phase_aliases = { headers = "header" }
	local phases = get_phases()
	local default_orders = {}
	for _, phase in ipairs(phases) do
		default_orders[phase] = {}
	end
	for phase, order in pairs(orders) do
		local canonical_phase = phase_aliases[phase] or phase
		if default_orders[canonical_phase] then
			for _, id in ipairs(order) do
				table.insert(default_orders[canonical_phase], id)
			end
		end
	end

	-- Utility
	local function deep_copy_phases(phases_map)
		local copy = {}
		for id, phases_present in pairs(phases_map) do
			copy[id] = {}
			for phase, present in pairs(phases_present) do
				copy[id][phase] = present
			end
		end
		return copy
	end

	-- Compute plugins/id/phases table
	local plugins_phases = {}
	local plugin_lookup = {}
	for _, plugin in ipairs(plugins) do
		plugins_phases[plugin.id] = {}
		plugin_lookup[plugin.id] = true
		for _, phase in ipairs(plugin.phases) do
			plugins_phases[plugin.id][phase] = true
		end
	end
	local base_plugins_phases = deep_copy_phases(plugins_phases)

	-- Collect overrides (global + per-site for multisite-aware phases)
	local overrides = { global = {} }
	local global_variables = variables and variables["global"] or variables or {}
	for _, phase in ipairs(phases) do
		local key = "PLUGINS_ORDER_" .. phase:upper()
		overrides.global[phase] = parse_override(global_variables[key])
	end

	local per_site_overrides = {}
	if variables then
		for server_name, vars in pairs(variables) do
			if server_name ~= "global" then
				per_site_overrides[server_name] = {}
				for _, phase in ipairs(phases) do
					local key = "PLUGINS_ORDER_" .. phase:upper()
					per_site_overrides[server_name][phase] = parse_override(vars[key])
				end
			end
		end
	end

	-- Order result
	local function build_order(override_set)
		local build_orders = {}
		local missing = {}
		for _, phase in ipairs(phases) do
			build_orders[phase] = {}
			missing[phase] = {}

			local seen = {}

			for _, id in ipairs(override_set[phase] or {}) do
				if not seen[id] and plugin_lookup[id] and plugins_phases[id] and plugins_phases[id][phase] then
					table.insert(build_orders[phase], id)
					seen[id] = true
					plugins_phases[id][phase] = nil
				elseif not seen[id] then
					missing[phase][id] = true
				end
			end

			for _, id in ipairs(default_orders[phase]) do
				if plugins_phases[id] and plugins_phases[id][phase] and not seen[id] then
					table.insert(build_orders[phase], id)
					seen[id] = true
					plugins_phases[id][phase] = nil
				end
			end

			for id, plugin in pairs(plugins_phases) do
				if plugin[phase] and not seen[id] then
					table.insert(build_orders[phase], id)
					plugin[phase] = nil
				end
			end
		end
		return build_orders, missing
	end

	-- Global order (backward compatible keys at root)
	plugins_phases = deep_copy_phases(base_plugins_phases)
	local global_orders, global_missing = build_order(overrides.global)
	local result_orders = {}
	for phase, ids in pairs(global_orders) do
		result_orders[phase] = ids
	end
	result_orders.global = global_orders

	-- Per-site orders (only if overrides exist)
	local per_site_orders = {}
	local per_site_missing = {}
	for server_name, override_set in pairs(per_site_overrides) do
		plugins_phases = deep_copy_phases(base_plugins_phases)
		local server_name_orders, missing = build_order(override_set)
		per_site_orders[server_name] = server_name_orders
		per_site_missing[server_name] = missing
	end
	result_orders.per_site = per_site_orders

	-- Merge missing maps for reporting (global + per-site)
	local missing_plugins = { global = global_missing, per_site = per_site_missing }

	return true, result_orders, missing_plugins
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

helpers.new_plugin = function(plugin_lua, ctx)
	-- Require call
	local ok, plugin_obj = pcall(plugin_lua.new, plugin_lua, ctx)
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
	for _, value in ipairs(required_values) do
		if ret[value] == nil then
			table.insert(missing_values, value)
		end
	end
	if #missing_values > 0 then
		return false, "missing required return value(s) : " .. encode(missing_values)
	end
	-- Return
	return true, ret
end

helpers.fill_ctx = function(no_ref)
	-- Return errors as table
	local errors = {}
	-- Try to load saved ctx
	local request = get_request()
	if no_ref ~= true and request then
		apply_ref()
	end
	local ctx = ngx.ctx
	-- Check if ctx is already filled
	if not ctx.bw then
		-- Instantiate bw table
		local data = {}
		if request then
			-- Common vars
			data.kind = "http"
			if subsystem == "stream" then
				data.kind = "stream"
			end
			data.remote_addr = var.remote_addr
			data.server_name = var.server_name
			data.time_local = var.time_local
			if data.kind == "http" then
				data.uri = var.uri
				data.request_id = var.request_id
				data.request_uri = var.request_uri
				data.request_method = var.request_method
				data.http_user_agent = var.http_user_agent
				data.http_host = var.http_host
				data.http_content_type = var.http_content_type
				data.http_content_length = var.http_content_length
				data.http_origin = var.http_origin
				data.http_version = req.http_version()
				data.start_time = req.start_time()
				data.scheme = var.scheme
			end
			-- IP data : global
			local ip_global, err = ip_is_global(data.remote_addr)
			if ip_global == nil then
				table.insert(errors, "can't check if IP is global : " .. err)
			else
				data.ip_is_global = ip_global
			end
			-- IP data : v4 / v6
			data.ip_is_ipv4 = is_ipv4(data.ip)
			data.ip_is_ipv6 = is_ipv6(data.ip)
		end
		-- Fill ctx
		ctx.bw = data
	end
	-- Always create new objects for current phases in case of cosockets
	local use_redis, err = get_variable("USE_REDIS", false)
	if not use_redis then
		table.insert(errors, "can't get variable from datastore : " .. err)
	end
	ctx.bw.internalstore =
		require "bunkerweb.datastore":new(subsystem == "http" and shared.internalstore or shared.internalstore_stream)
	ctx.bw.datastore = require "bunkerweb.datastore":new()
	ctx.bw.clusterstore = require "bunkerweb.clusterstore":new()
	ctx.bw.cachestore = require "bunkerweb.cachestore":new(use_redis == "yes", ctx)
	return true, "ctx filled", errors, ctx
end

helpers.save_ctx = function(ctx)
	if get_request() then
		stash_ref(ctx)
	end
end

function helpers.load_variables(all_variables, plugins)
	-- Extract settings from plugins and global ones
	local all_settings = {}
	for _, plugin in ipairs(plugins) do
		if plugin.settings then
			for setting, data in pairs(plugin.settings) do
				all_settings[setting] = data
			end
		end
	end
	local file = open("/usr/share/bunkerweb/settings.json")
	if not file then
		return false, "can't open settings.json"
	end
	local ok, settings = pcall(decode, file:read("*a"))
	file:close()
	if not ok then
		return false, "invalid settings.json : " .. settings
	end
	for setting, data in pairs(settings) do
		all_settings[setting] = data
	end

	-- Initialize variables structure
	local variables = { ["global"] = {} }
	local multisite = all_variables["MULTISITE"] == "yes"
	local server_names = {}
	if multisite then
		for server_name in all_variables["SERVER_NAME"]:gmatch("%S+") do
			variables[server_name] = {}
			table.insert(server_names, server_name)
		end
	end

	-- Pre-compile patterns for better performance
	local escaped_server_names = {}
	if multisite then
		for _, server_name in ipairs(server_names) do
			escaped_server_names[server_name] = server_name:gsub("([^%w])", "%%%1")
		end
	end

	-- Single pass through all_variables
	for variable, value in pairs(all_variables) do
		-- Check for direct global settings first
		if all_settings[variable] then
			variables["global"][variable] = value
		end

		-- Handle multisite and multiple settings in one pass
		if multisite then
			-- Try to match server-specific variables
			for _, server_name in ipairs(server_names) do
				local escaped_server_name = escaped_server_names[server_name]
				local setting = variable:match("^" .. escaped_server_name .. "_(.+)$")
				if setting then
					-- Check if it's a direct setting
					if all_settings[setting] then
						variables[server_name][setting] = value
					-- Check if it's a multiple setting
					elseif setting:match("^(.+)_%d+$") then
						local base_setting = setting:match("^(.+)_%d+$")
						if all_settings[base_setting] and all_settings[base_setting].multiple then
							variables[server_name][setting] = value
						end
					end
				end
			end
		end

		-- Handle multiple settings for global
		local base_setting = variable:match("^(.+)_%d+$")
		if base_setting and all_settings[base_setting] and all_settings[base_setting].multiple then
			variables["global"][variable] = value
		end
	end

	return true, variables
end

return helpers
