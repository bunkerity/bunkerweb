local cjson = require "cjson"
local class = require "middleclass"
local datastore = require "bunkerweb.datastore"
local lrucache = require "resty.lrucache"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local metrics = class("metrics", plugin)
local ngx = ngx
local ERR = ngx.ERR
local INFO = ngx.INFO
local unescape_uri = ngx.unescape_uri

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
	local reason, data, security_mode = get_reason(self.ctx)
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
			id = self.ctx.bw.request_id,
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
			security_mode = security_mode,
			synced = not self.use_redis,
		}
		-- Get requests from LRU
		local requests = lru:get("requests") or {}

		-- Add to LRU
		table_insert(requests, request)

		-- Remove old requests if needed
		local max_requests = tonumber(self.variables["METRICS_MAX_BLOCKED_REQUESTS"])
		while #requests > max_requests do
			table_remove(requests, 1)
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
				-- Add table entries
				elseif kind == "tables" then
					for metric_key, metric_value in pairs(kind_metrics) do
						local lru_key = plugin_id .. "_table_" .. metric_key
						local metric_table = lru:get(lru_key) or {}
						-- Add value to table
						table_insert(metric_table, metric_value)
						-- Update LRU cache
						lru:set(lru_key, metric_table)
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

	local clusterstore_ok = nil
	if self.use_redis then
		clusterstore_ok, err = self.clusterstore:connect()
		if not clusterstore_ok then
			self.logger:log(ERR, "Can't connect to Redis server: " .. err .. " - requests will be stored in datastore")
		end
	end

	-- Loop on all keys
	for _, key in ipairs(lru:get_keys()) do
		-- Get LRU data
		local value = lru:get(key)
		if clusterstore_ok then
			if key == "requests" then
				for _, request in ipairs(value) do
					if not request.synced then
						-- Add only unsynced requests
						local ok
						ok, err = self.clusterstore:call("rpush", "requests", encode(request))
						if not ok then
							self.logger:log(ERR, "Can't sync request to Redis: " .. err)
							break
						end
						request.synced = true -- Mark as synced
					end
				end

				-- Remove old requests if needed
				local max_requests = tonumber(self.variables["METRICS_MAX_BLOCKED_REQUESTS_REDIS"])
				local nb_requests = self.clusterstore:call("llen", "requests")
				if nb_requests and nb_requests > max_requests then
					self.clusterstore:call("ltrim", "requests", -max_requests, -1)
				end

				-- Update LRU cache
				lru:set("requests", value)
			elseif key ~= "setup" and self.variables["METRICS_SAVE_TO_REDIS"] == "yes" then
				-- Sync other metrics (counters and tables) to Redis with optimized data structures
				local redis_key = "metrics:" .. key .. ":" .. wid
				local ok
				if type(value) == "table" then
					-- Use Redis list for table values
					ok, err = self.clusterstore:call("del", redis_key)
					if ok then
						for _, item in ipairs(value) do
							local item_value = type(item) == "table" and encode(item) or tostring(item)
							ok, err = self.clusterstore:call("rpush", redis_key, item_value)
							if not ok then
								self.logger:log(ERR, "Can't push metric table item " .. key .. " to Redis: " .. err)
								break
							end
						end
					else
						self.logger:log(ERR, "Can't clear metric table " .. key .. " in Redis: " .. err)
					end
				elseif type(value) == "number" then
					-- Use Redis string for numeric counters
					ok, err = self.clusterstore:call("set", redis_key, value)
					if not ok then
						self.logger:log(ERR, "Can't sync metric counter " .. key .. " to Redis: " .. err)
					end
				else
					-- Use Redis string for other types
					ok, err = self.clusterstore:call("set", redis_key, tostring(value))
					if not ok then
						self.logger:log(ERR, "Can't sync metric " .. key .. " to Redis: " .. err)
					end
				end
			end
		end
		if type(value) == "table" then
			value = encode(value)
		end
		-- Push to dict (with LRU eviction if needed)
		local ok
		ok, err = self.metrics_datastore:set_with_retries(key .. "_" .. wid, value)
		if not ok then
			-- If there isn't enough memory : we fallback to delete everything
			if err == "no memory" then
				self.logger:log(INFO, "not enough memory in the metrics datastore, purging LRU key " .. key)
				lru:delete(key)
			else
				ret = false
				ret_err = err
				self.logger:log(ERR, "can't set " .. key .. "_" .. wid .. " : " .. err)
			end
		end
	end

	if clusterstore_ok then
		self.clusterstore:close()
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

	-- Handle special /metrics/requests/query endpoint for optimized queries
	if filter == "requests/query" then
		return self:api_requests_query()
	end

	-- Loop on keys
	local metrics_data = {}
	for _, key in ipairs(self.metrics_datastore:keys()) do
		-- Check if key starts with our filter
		if key:match("^" .. filter .. "_") then
			-- Get the value
			local data, err = self.metrics_datastore:get(key)
			if not data then
				return self:ret(true, "error while fetching metric : " .. err, HTTP_INTERNAL_SERVER_ERROR)
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

function metrics:api_requests_query()
	-- Parse query parameters from request args
	local args = ngx.req.get_uri_args()
	local start_idx = tonumber(args.start) or 0
	local length = tonumber(args.length) or 10
	local search = unescape_uri(args.search or "")
	local order_column = args.order_column or "date"
	local order_dir = args.order_dir or "desc"
	local count_only = args.count_only == "true"

	-- Parse search panes filters (format: field1:value1,value2;field2:value3)
	local search_panes = {}
	local search_panes_raw = unescape_uri(args.search_panes or "")
	if search_panes_raw and search_panes_raw ~= "" then
		for field_filter in search_panes_raw:gmatch("[^;]+") do
			local field, values = field_filter:match("^([^:]+):(.+)$")
			if field and values then
				search_panes[field] = {}
				for value in values:gmatch("[^,]+") do
					table_insert(search_panes[field], value)
				end
			end
		end
	end

	-- Collect all requests from all workers
	local all_requests = {}
	for _, key in ipairs(self.metrics_datastore:keys()) do
		if key:match("^requests_[0-9]+$") then
			local data, _ = self.metrics_datastore:get(key)
			if data then
				local ok, decoded = pcall(decode, data)
				if ok and type(decoded) == "table" then
					for _, request in ipairs(decoded) do
						table_insert(all_requests, request)
					end
				end
			end
		end
	end

	-- Filter requests
	local filtered_requests = {}
	for _, request in ipairs(all_requests) do
		-- Filter: status 400-499 or detect mode
		if (request.status and request.status >= 400 and request.status < 500) or request.security_mode == "detect" then
			local matches = true

			-- Apply search filter
			if search ~= "" then
				local search_lower = search:lower()
				matches = false
				for _, value in pairs(request) do
					if type(value) == "string" and value:lower():find(search_lower, 1, true) then
						matches = true
						break
					elseif type(value) == "number" and tostring(value):find(search_lower, 1, true) then
						matches = true
						break
					end
				end
			end

			-- Apply search panes filters
			if matches then
				for field, allowed_values in pairs(search_panes) do
					local field_value = tostring(request[field] or "N/A")
					local field_matches = false
					for _, allowed in ipairs(allowed_values) do
						if field_value == allowed then
							field_matches = true
							break
						end
					end
					if not field_matches then
						matches = false
						break
					end
				end
			end

			if matches then
				table_insert(filtered_requests, request)
			end
		end
	end

	-- If only count is requested, return early
	if count_only then
		return self:ret(true, { total = #all_requests, filtered = #filtered_requests }, HTTP_OK)
	end

	-- Sort filtered requests
	if order_column == "date" then
		table.sort(filtered_requests, function(a, b)
			local a_val = tonumber(a.date) or 0
			local b_val = tonumber(b.date) or 0
			if order_dir == "desc" then
				return a_val > b_val
			else
				return a_val < b_val
			end
		end)
	else
		table.sort(filtered_requests, function(a, b)
			local a_val = a[order_column] or ""
			local b_val = b[order_column] or ""
			if order_dir == "desc" then
				return a_val > b_val
			else
				return a_val < b_val
			end
		end)
	end

	-- Paginate
	local paginated = {}
	local end_idx = start_idx + length
	if length == -1 then
		end_idx = #filtered_requests
	end

	for i = start_idx + 1, math.min(end_idx, #filtered_requests) do
		table_insert(paginated, filtered_requests[i])
	end

	-- Calculate search panes options
	local pane_counts = {}
	local filtered_ids = {}
	for _, req in ipairs(filtered_requests) do
		filtered_ids[req.id] = true
	end

	local pane_fields = { "ip", "country", "method", "url", "status", "reason", "server_name", "security_mode" }
	for _, field in ipairs(pane_fields) do
		pane_counts[field] = {}
	end

	for _, request in ipairs(all_requests) do
		if (request.status and request.status >= 400 and request.status < 500) or request.security_mode == "detect" then
			for _, field in ipairs(pane_fields) do
				local value = tostring(request[field] or "N/A")
				if not pane_counts[field][value] then
					pane_counts[field][value] = { total = 0, count = 0 }
				end
				pane_counts[field][value].total = pane_counts[field][value].total + 1
				if filtered_ids[request.id] then
					pane_counts[field][value].count = pane_counts[field][value].count + 1
				end
			end
		end
	end

	return self:ret(true, {
		total = #all_requests,
		filtered = #filtered_requests,
		data = paginated,
		pane_counts = pane_counts,
	}, HTTP_OK)
end

return metrics
