local cjson = require "cjson"
local class = require "middleclass"
local datastore = require "bunkerweb.datastore"
local lrucache = require "resty.lrucache"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local metrics = class("metrics", plugin)
local ngx = ngx
local ERR = ngx.ERR

local lru, err_lru = lrucache.new(100000)
if not lru then
	require "bunkerweb.logger":new("METRICS"):log(ERR, "failed to instantiate LRU cache : " .. err_lru)
end

local shared = ngx.shared
local subsystem = ngx.config.subsystem
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local HTTP_OK = ngx.HTTP_OK
local worker = ngx.worker
local worker_id = worker.id

local get_reason = utils.get_reason
local get_country = utils.get_country
local has_variable = utils.has_variable
local encode = cjson.encode
local decode = cjson.decode

local match = string.match
local time = os.time
local tonumber = tonumber
local tostring = tostring
local table_insert = table.insert
local table_remove = table.remove

function metrics:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "metrics", ctx)
	local dict
	if subsystem == "http" then
		dict = shared.metrics_datastore
	else
		dict = shared.metrics_datastore_stream
	end
	self.metrics_datastore = datastore:new(dict)
end

function metrics:log(bypass_checks)
	-- Don't go further if metrics is not enabled
	if not bypass_checks and self.variables["USE_METRICS"] == "no" then
		return self:ret(true, "metrics are disabled")
	end
	-- Store blocked requests
	local reason, data = get_reason(self.ctx)
	if reason then
		local country = "local"
		local err
		if self.ctx.bw.ip_is_global then
			country, err = get_country(self.ctx.bw.remote_addr)
			if not country then
				country = "unknown"
				self.logger:log(ERR, "can't get country code " .. err)
			end
		end
		local request = {
			date = self.ctx.bw.start_time or time(),
			ip = self.ctx.bw.remote_addr,
			country = country,
			method = self.ctx.bw.request_method,
			url = self.ctx.bw.request_uri,
			status = ngx.status,
			user_agent = self.ctx.bw.http_user_agent or "",
			reason = reason,
			server_name = self.ctx.bw.server_name,
			data = data,
		}
		-- Get current requests
		local requests = lru:get("requests")
		if not requests then
			requests = {}
		end
		-- Add current request
		table_insert(requests, request)
		-- Remove old requests
		local nb_delete = #requests - tonumber(self.variables["METRICS_MAX_BLOCKED_REQUESTS"])
		while nb_delete > 0 do
			table_remove(requests, 1)
			nb_delete = nb_delete - 1
		end
		-- Update worker cache
		lru:set("requests", requests)
	end
	-- Get metrics from plugins
	local all_metrics = self.ctx.bw.metrics
	if all_metrics then
		-- Loop on plugins
		for plugin_id, plugin_metrics in pairs(all_metrics) do
			-- Loop on kinds
			for kind, kind_metrics in pairs(plugin_metrics) do
				-- Increment counters
				if kind == "counters" then
					for metric_key, metric_value in pairs(kind_metrics) do
						local lru_key = plugin_id .. "_counter_" .. metric_key
						local metric_counter = lru:get(lru_key)
						if not metric_counter then
							metric_counter = metric_value
						else
							metric_counter = metric_counter + metric_value
						end
						lru:set(lru_key, metric_counter)
					end
				end
			end
		end
	end
	return self:ret(true, "success")
end

function metrics:log_default()
	local is_needed, err = has_variable("USE_METRICS", "yes")
	if is_needed == nil then
		return self:ret(false, "can't check USE_METRICS variable : " .. err)
	end
	if is_needed then
		return self:log(true)
	end
	return self:ret(true, "metrics not used")
end

function metrics:timer()
	-- Check if metrics is used
	local is_needed, err = has_variable("USE_METRICS", "yes")
	if is_needed == nil then
		return self:ret(false, "can't check USE_METRICS variable : " .. err)
	end
	if not is_needed then
		return self:ret(true, "metrics not used")
	end

	local ret = true
	local ret_err = "metrics updated"
	local wid = tostring(worker_id())

	-- Purpose of following code is to populate the LRU cache.
	-- In case of a reload, everything in LRU cache is removed
	-- so we need to copy it from SHM cache if it exists.
	local setup = lru:get("setup")
	if not setup then
		for _, key in ipairs(self.metrics_datastore:keys()) do
			if key:match("_" .. wid .. "$") then
				local value
				value, err = self.metrics_datastore:get(key)
				if not value and err ~= "not found" then
					ret = false
					ret_err = err
					self.logger:log(ERR, "error while checking " .. key .. " : " .. err)
				end
				if value then
					local ok, decoded = pcall(decode, value)
					if ok then
						value = decoded
					end
					lru:set(key:gsub("_" .. wid .. "$", ""), value)
				end
			end
		end
		lru:set("setup", true)
	end
	-- Loop on all keys
	for _, key in ipairs(lru:get_keys()) do
		-- Get LRU data
		local value = lru:get(key)
		if type(value) == "table" then
			value = encode(value)
		end
		-- Push to dict
		local ok
		ok, err = self.metrics_datastore:set(key .. "_" .. wid, value)
		if not ok then
			ret = false
			ret_err = err
			self.logger:log(ERR, "can't update " .. key .. "_" .. wid .. " : " .. err)
		end
	end
	-- Done
	return self:ret(ret, ret_err)
end

function metrics:api()
	-- Match request
	if not match(self.ctx.bw.uri, "^/metrics/.+$") or self.ctx.bw.request_method ~= "GET" then
		return self:ret(false, "success")
	end
	-- Extract filter parameter
	local filter = self.ctx.bw.uri:gsub("^/metrics/", "")
	-- Loop on keys
	local metrics_data = {}
	for _, key in ipairs(self.metrics_datastore:keys()) do
		-- Check if key starts with our filter
		if key:match("^" .. filter .. "_") then
			-- Get the value
			local data, err = self.metrics_datastore:get(key)
			if not data then
				return self:ret(true, "error while fetching requests : " .. err, HTTP_INTERNAL_SERVER_ERROR)
			end
			local metric_key = key:gsub("_[0-9]+$", ""):gsub("^" .. filter .. "_", "")
			if metric_key == "" then
				metric_key = filter
			end
			-- Table case
			local ok, decoded = pcall(decode, data)
			if ok then
				data = decoded
			end
			if type(data) == "table" then
				if not metrics_data[metric_key] then
					metrics_data[metric_key] = {}
				end
				for _, metric_value in ipairs(data) do
					table_insert(metrics_data[metric_key], metric_value)
				end
			else
				-- Counter case
				if not metrics_data[metric_key] then
					metrics_data[metric_key] = 0
				end
				metrics_data[metric_key] = metrics_data[metric_key] + data
			end
		end
	end
	return self:ret(true, metrics_data, HTTP_OK)
end

return metrics
