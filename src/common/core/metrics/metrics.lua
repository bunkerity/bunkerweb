local cjson = require "cjson"
local class = require "middleclass"
local datastore = require "bunkerweb.datastore"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local metrics = class("metrics", plugin)

local ngx = ngx
local shared = ngx.shared
local subsystem = ngx.config.subsystem
local ERR = ngx.ERR
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local HTTP_OK = ngx.HTTP_OK

local get_reason = utils.get_reason
local get_country = utils.get_country
local encode = cjson.encode
local decode = cjson.decode

local match = string.match
local time = os.time

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

function metrics:log()
	-- Don't go further if metrics is not enabled
	if self.variables["USE_METRICS"] == "no" then
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
			["user-agent"] = self.ctx.bw.http_user_agent or "",
			reason = reason,
			data = data,
		}
		local ok
		ok, err = self.metrics_datastore:safe_rpush("metrics_requests", encode(request))
		if not ok then
			self.logger:log(ERR, "can't save request to datastore : " .. err)
		end
	end
	return self:ret(true, "success")
end

function metrics:log_default()
	return self:log()
end

function metrics:api()
	-- Match request
	if not match(self.ctx.bw.uri, "^/metrics/requests$") or self.ctx.bw.request_method ~= "GET" then
		return self:ret(false, "success")
	end

	-- Get requests metrics
	local len, err = self.metrics_datastore:llen("metrics_requests")
	if not len then
		return self:ret(true, "error while getting length of metrics_requests : " .. err, HTTP_INTERNAL_SERVER_ERROR)
	end
	local i = 0
	local data = {}
	while i < len do
		local request
		request, err = self.metrics_datastore:lpop("metrics_requests")
		if request then
			table.insert(data, decode(request))
		else
			return self:ret(true, "error while getting metrics_requests : " .. err, HTTP_INTERNAL_SERVER_ERROR)
		end
		local ok
		ok, err = self.metrics_datastore:safe_rpush("metrics_requests", request)
		if not ok then
			self.logger:log(ERR, "can't save request to datastore : " .. err)
		end
		i = i + 1
	end
	return self:ret(true, data, HTTP_OK)
end

return metrics
