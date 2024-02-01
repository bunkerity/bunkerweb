local cjson = require "cjson"
local class = require "middleclass"
local datastore = require "bunkerweb.datastore"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"
local lrucache = require "resty.lrucache"

local metrics = class("metrics", plugin)

local lru, err_lru = lrucache.new(100000)
if not lru then
	require "bunkerweb.logger":new("METRICS"):log(ERR, "failed to instantiate LRU cache : " .. err_lru)
end

local ngx = ngx
local shared = ngx.shared
local subsystem = ngx.config.subsystem
local ERR = ngx.ERR
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
	-- Purpose of following code is to populate the LRU cache.
	-- In case of a reload, everything in LRU cache is removed
	-- so we need to copy it from SHM cache if it exists.
	local setup = lru:get("setup")
	if not setup then
		local requests, err = self.metrics_datastore:get("requests_" .. tostring(worker_id()))
		if not requests and err ~= "not found" then
			self.logger:log(ERR, "error while checking datastore : " .. err)
		end
		if requests then
			lru:set("requests", decode(requests))
		end
		lru:set("setup", true)
	end
	-- Get worker requests
	local requests = lru:get("requests")
	if not requests then
		requests = {}
	end
	-- Push to dict
	local ok, err = self.metrics_datastore:set("requests_" .. tostring(worker_id()), encode(requests))
	if not ok then
		return self:ret(false, "can't update requests : " .. err)
	end
	return self:ret(true, "metrics updated")
end

function metrics:api()
	-- Match request
	if not match(self.ctx.bw.uri, "^/metrics/requests$") or self.ctx.bw.request_method ~= "GET" then
		return self:ret(false, "success")
	end
	-- Get requests metrics
	local keys = self.metrics_datastore:keys()
	local requests = {}
	for _, key in ipairs(keys) do
		if key:match("^requests_") then
			local data, err = self.metrics_datastore:get(key)
			if not data then
				return self:ret(true, "error while fetching requests : " .. err, HTTP_INTERNAL_SERVER_ERROR)
			end
			for _, request in ipairs(decode(data)) do
				table_insert(requests, request)
			end
		end
	end
	return self:ret(true, requests, HTTP_OK)
end

return metrics
