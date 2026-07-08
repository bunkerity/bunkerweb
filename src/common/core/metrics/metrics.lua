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
local null = ngx.null
local unescape_uri = ngx.unescape_uri

-- Default cap for the per-worker LRU: governs both the slot count (distinct
-- counter/table keys held) and the per-key event-history array length. Overridden
-- per-worker from the MAX_LRU_HISTORY global setting once init_worker() runs and
-- self.variables is populated.
local DEFAULT_MAX_LRU_HISTORY = 1000

local lru, err_lru = lrucache.new(DEFAULT_MAX_LRU_HISTORY)
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
local is_connection_error = utils.is_connection_error
local encode = cjson.encode
local decode = cjson.decode

local match = string.match
local time = os.time
local tonumber = tonumber
local tostring = tostring
local table_insert = table.insert
local table_remove = table.remove

local REQUEST_FACET_FIELDS = { "ip", "country", "method", "url", "status", "reason", "server_name", "security_mode" }

-- Bounded set of nginx $upstream_cache_status values counted per served request
-- (reverseproxy proxy_cache). Distinct axis from the blocked-request facets above;
-- keeps the cache-status counter cardinality fixed and skips nil/unknown statuses.
local CACHE_STATUS_VALUES = {
	HIT = true,
	MISS = true,
	BYPASS = true,
	EXPIRED = true,
	STALE = true,
	UPDATING = true,
	REVALIDATED = true,
}

-- Parse a count value with optional SI shorthand suffix: "100", "1k", "10K", "1m", "5M".
-- k/K = x1000, m/M = x1_000_000. Returns the integer count, or nil if value is missing
-- or unparsable.
local function parse_count(value)
	if value == nil or value == "" then
		return nil
	end
	local num_str, suffix = match(tostring(value), "^(%d+)([kKmM]?)$")
	if not num_str then
		return nil
	end
	local num = tonumber(num_str)
	if not num then
		return nil
	end
	if suffix == "k" or suffix == "K" then
		return num * 1000
	elseif suffix == "m" or suffix == "M" then
		return num * 1000000
	end
	return num
end

local function get_request_facet_value(request, field)
	local value = request[field]
	if value == nil or value == "" or value == null then
		return "N/A"
	end
	return tostring(value)
end

local function clear_request_facets(self, set_initialized)
	if set_initialized == nil then
		set_initialized = true
	end

	for _, field in ipairs(REQUEST_FACET_FIELDS) do
		local _, err = self:redis_call("del", "requests:facet:" .. field)
		if err then
			self:log_throttled(ERR, "facet_clear", "Can't clear request facet " .. field .. ": " .. err)
		end
	end

	if set_initialized then
		local ok, err = self:redis_call("set", "requests:facets:initialized", "1")
		if not ok then
			self:log_throttled(
				ERR,
				"facet_init_set",
				"Can't mark request facets as initialized: " .. (err or "unknown error")
			)
		end
	end
end

local function incr_request_facets(self, request)
	for _, field in ipairs(REQUEST_FACET_FIELDS) do
		local facet_key = "requests:facet:" .. field
		local facet_value = get_request_facet_value(request, field)
		local count_raw, err = self:redis_call("hincrby", facet_key, facet_value, 1)
		if count_raw == nil or count_raw == false then
			self:log_throttled(
				ERR,
				"facet_incr",
				"Can't increment request facet " .. field .. "=" .. facet_value .. ": " .. (err or "unknown error")
			)
		end
	end
end

local function decr_request_facets(self, request)
	for _, field in ipairs(REQUEST_FACET_FIELDS) do
		local facet_key = "requests:facet:" .. field
		local facet_value = get_request_facet_value(request, field)
		local count_raw, err = self:redis_call("hincrby", facet_key, facet_value, -1)
		if count_raw == nil or count_raw == false then
			self:log_throttled(
				ERR,
				"facet_decr",
				"Can't decrement request facet " .. field .. "=" .. facet_value .. ": " .. (err or "unknown error")
			)
		else
			local count = tonumber(count_raw)
			if count and count <= 0 then
				local ok, hdel_err = self:redis_call("hdel", facet_key, facet_value)
				if ok == nil or ok == false then
					self:log_throttled(
						ERR,
						"facet_hdel",
						"Can't remove empty request facet "
							.. field
							.. "="
							.. facet_value
							.. ": "
							.. (hdel_err or "unknown error")
					)
				end
			end
		end
	end
end

local function initialize_request_facets(self)
	local initialized_raw, _ = self:redis_call("get", "requests:facets:initialized")
	if
		initialized_raw ~= nil
		and initialized_raw ~= false
		and initialized_raw ~= null
		and tostring(initialized_raw) == "1"
	then
		return
	end

	clear_request_facets(self, false)

	local nb_requests_raw, len_err = self:redis_call("llen", "requests")
	if nb_requests_raw == nil or nb_requests_raw == false then
		self:log_throttled(
			ERR,
			"facet_init_llen",
			"Can't initialize request facets, failed to get requests length: " .. (len_err or "unknown error")
		)
		return
	end

	local nb_requests = tonumber(nb_requests_raw) or 0
	if nb_requests > 0 then
		local chunk_size = 1000
		for start_idx = 0, nb_requests - 1, chunk_size do
			local stop_idx = start_idx + chunk_size - 1
			local chunk, range_err = self:redis_call("lrange", "requests", start_idx, stop_idx)
			if chunk == nil or chunk == false then
				self:log_throttled(
					ERR,
					"facet_init_lrange",
					"Can't initialize request facets, failed to read requests chunk: " .. (range_err or "unknown error")
				)
				break
			end
			for _, request_raw in ipairs(chunk) do
				if request_raw ~= nil and request_raw ~= false and request_raw ~= null then
					local ok, request = pcall(decode, request_raw)
					if ok and type(request) == "table" then
						incr_request_facets(self, request)
					end
				end
			end
		end
	end

	local ok, set_err = self:redis_call("set", "requests:facets:initialized", "1")
	if not ok then
		self:log_throttled(
			ERR,
			"facet_init_final",
			"Can't finalize request facets initialization: " .. (set_err or "unknown error")
		)
	end
end

local function enforce_redis_requests_cap(self)
	local max_requests = parse_count(self.variables["METRICS_MAX_BLOCKED_REQUESTS_REDIS"]) or 0
	if max_requests < 0 then
		max_requests = 0
	end

	local nb_requests_raw, err = self:redis_call("llen", "requests")
	if nb_requests_raw == nil or nb_requests_raw == false then
		self:log_throttled(ERR, "cap_llen", "Can't get Redis requests length: " .. (err or "unknown error"))
		return
	end

	local nb_requests = tonumber(nb_requests_raw)
	if not nb_requests then
		self:log_throttled(ERR, "cap_parse", "Can't parse Redis requests length: " .. tostring(nb_requests_raw))
		return
	end

	if nb_requests <= max_requests then
		return
	end

	local ok
	if max_requests == 0 then
		ok, err = self:redis_call("del", "requests")
		if ok then
			clear_request_facets(self)
		end
	else
		local to_remove = nb_requests - max_requests
		ok = true
		for _ = 1, to_remove do
			local removed_raw, pop_err = self:redis_call("lpop", "requests")
			if removed_raw == nil or removed_raw == false then
				self:log_throttled(ERR, "cap_lpop", "Can't trim Redis requests list: " .. (pop_err or "unknown error"))
				ok = false
				break
			end
			if removed_raw == null then
				break
			end
			local decoded_ok, removed_request = pcall(decode, removed_raw)
			if decoded_ok and type(removed_request) == "table" then
				decr_request_facets(self, removed_request)
			end
		end
	end

	if not ok then
		self:log_throttled(ERR, "cap_enforce", "Can't enforce Redis requests cap: " .. (err or "unknown error"))
	end
end

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

function metrics:init_worker()
	-- Resize the per-worker LRU using the configured MAX_LRU_HISTORY (global setting).
	-- Until this runs, the module-level default LRU sized at DEFAULT_MAX_LRU_HISTORY is
	-- used. The resize is skipped when the configured value matches the default to avoid
	-- dropping any entries collected between module load and init_worker.
	local max_lru_history = parse_count(self.variables["MAX_LRU_HISTORY"]) or DEFAULT_MAX_LRU_HISTORY
	if max_lru_history < 1 then
		max_lru_history = DEFAULT_MAX_LRU_HISTORY
	end
	if max_lru_history == DEFAULT_MAX_LRU_HISTORY then
		return self:ret(true, "metrics LRU using default size (MAX_LRU_HISTORY=" .. max_lru_history .. ")")
	end
	local new_lru, err = lrucache.new(max_lru_history)
	if not new_lru then
		self.logger:log(ERR, "failed to resize metrics LRU to " .. max_lru_history .. " slots : " .. err)
		return self:ret(true, "kept default LRU size")
	end
	lru = new_lru
	return self:ret(true, "metrics LRU sized to " .. max_lru_history .. " slots")
end

-- Call Redis with one automatic reconnect attempt on connection error.
-- Must be called after self.clusterstore:connect() has succeeded.
-- Acts as a circuit-breaker: once self.redis_ok is false, all calls
-- are short-circuited for the rest of the timer cycle.
function metrics:redis_call(method, ...)
	if self.redis_ok == false then
		return false, "Redis unavailable for this cycle"
	end
	local res, call_err = self.clusterstore:call(method, ...)
	if not res and call_err and is_connection_error(call_err) then
		self.clusterstore:close()
		local ok, reconnect_err = self.clusterstore:connect()
		if not ok then
			self:log_throttled(
				ERR,
				"redis_reconnect",
				"Can't reconnect to Redis: " .. (reconnect_err or "unknown error")
			)
			self.redis_ok = false
			return false, call_err
		end
		local res2, err2 = self.clusterstore:call(method, ...)
		if not res2 and err2 then
			self.redis_ok = false
		end
		return res2, err2
	end
	return res, call_err
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
		local max_requests = parse_count(self.variables["METRICS_MAX_BLOCKED_REQUESTS"]) or 1000
		while #requests > max_requests do
			table_remove(requests, 1)
		end

		-- Update worker cache
		lru:set("requests", requests)
	end
	-- Count proxy_cache hit/miss for served requests. Distinct axis from the
	-- blocked-request facets above (never touches the `requests` list): reads the
	-- reverseproxy plugin's $upstream_cache_status (also emitted as the
	-- X-Proxy-Cache header) and increments a bounded per-status counter. nil status
	-- (non-cached requests) is skipped. Exposed via GET /metrics/reverseproxy.
	local cache_status = ngx.var.upstream_cache_status
	if cache_status and CACHE_STATUS_VALUES[cache_status] then
		local lru_key = "reverseproxy_counter_cache_status_" .. cache_status
		local counter = lru:get(lru_key)
		lru:set(lru_key, (counter or 0) + 1)
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
					local max_lru_history = parse_count(self.variables["MAX_LRU_HISTORY"]) or DEFAULT_MAX_LRU_HISTORY
					for metric_key, metric_value in pairs(kind_metrics) do
						local lru_key = plugin_id .. "_table_" .. metric_key
						local metric_table = lru:get(lru_key) or {}
						-- Cap event history per (plugin, key) — drop oldest first
						while #metric_table >= max_lru_history do
							table_remove(metric_table, 1)
						end
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

	self.redis_ok = nil
	if self.use_redis then
		self.redis_ok, err = self.clusterstore:connect()
		if not self.redis_ok then
			self:log_throttled(
				ERR,
				"redis_connect",
				"Can't connect to Redis server: "
					.. (err or "unknown error")
					.. " - requests will be stored in datastore"
			)
		else
			initialize_request_facets(self)
		end
	end

	-- Loop on all keys
	for _, key in ipairs(lru:get_keys()) do
		-- Get LRU data
		local value = lru:get(key)
		if self.redis_ok then
			if key == "requests" then
				for _, request in ipairs(value) do
					if not request.synced then
						-- Add only unsynced requests
						local ok
						ok, err = self:redis_call("rpush", "requests", encode(request))
						if not ok then
							self:log_throttled(ERR, "sync_request", "Can't sync request to Redis: " .. err)
							break
						end
						request.synced = true -- Mark as synced
						incr_request_facets(self, request)
					end
				end

				-- Update LRU cache
				lru:set("requests", value)
			elseif key ~= "setup" and self.variables["METRICS_SAVE_TO_REDIS"] == "yes" then
				-- Sync other metrics (counters and tables) to Redis with optimized data structures
				local redis_key = "metrics:" .. key .. ":" .. wid
				local ok
				if type(value) == "table" then
					-- Use Redis list for table values
					ok, err = self:redis_call("del", redis_key)
					if ok then
						for _, item in ipairs(value) do
							local item_value = type(item) == "table" and encode(item) or tostring(item)
							ok, err = self:redis_call("rpush", redis_key, item_value)
							if not ok then
								self:log_throttled(
									ERR,
									"sync_table_item",
									"Can't push metric table item " .. key .. " to Redis: " .. err
								)
								break
							end
						end
					else
						self:log_throttled(
							ERR,
							"sync_table_clear",
							"Can't clear metric table " .. key .. " in Redis: " .. err
						)
					end
				elseif type(value) == "number" then
					-- Use Redis string for numeric counters
					ok, err = self:redis_call("set", redis_key, value)
					if not ok then
						self:log_throttled(
							ERR,
							"sync_counter",
							"Can't sync metric counter " .. key .. " to Redis: " .. err
						)
					end
				else
					-- Use Redis string for other types
					ok, err = self:redis_call("set", redis_key, tostring(value))
					if not ok then
						self:log_throttled(ERR, "sync_other", "Can't sync metric " .. key .. " to Redis: " .. err)
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
				self:log_throttled(ERR, "datastore_set", "can't set " .. key .. "_" .. wid .. " : " .. err)
			end
		end
	end

	if self.redis_ok then
		enforce_redis_requests_cap(self)
	end
	-- Always attempt cleanup when Redis was used, even if connection dropped mid-cycle.
	-- clusterstore:close() handles the "client is not instantiated" case gracefully.
	if self.use_redis then
		self.clusterstore:close()
	end

	-- Flush any end-of-window recaps for errors that stopped repeating.
	self:flush_log_recaps()

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
