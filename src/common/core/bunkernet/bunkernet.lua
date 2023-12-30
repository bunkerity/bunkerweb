local cjson = require "cjson"
local class = require "middleclass"
local http = require "resty.http"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local bunkernet = class("bunkernet", plugin)

local ngx = ngx
local ERR = ngx.ERR
local NOTICE = ngx.NOTICE
local WARN = ngx.WARN
local timer_at = ngx.timer.at
local get_phase = ngx.get_phase
local get_version = utils.get_version
local get_integration = utils.get_integration
local get_deny_status = utils.get_deny_status
local is_ipv4 = utils.is_ipv4
local is_ipv6 = utils.is_ipv6
local ip_is_global = utils.ip_is_global
local has_variable = utils.has_variable
local is_whitelisted = utils.is_whitelisted
local is_ip_in_networks = utils.is_ip_in_networks
local get_reason = utils.get_reason
local get_variable = utils.get_variable
local tostring = tostring
local open = io.open
local encode = cjson.encode
local decode = cjson.decode
local http_new = http.new

function bunkernet:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "bunkernet", ctx)
	-- Get BunkerNet ID and save info
	if get_phase() ~= "init" and self:is_needed() then
		local id, err = self.datastore:get("plugin_bunkernet_id", true)
		if id then
			self.bunkernet_id = id
			self.version = (self.ctx and self.ctx.bw.version) or get_version()
			self.integration = (self.ctx and self.ctx.bw.integration) or get_integration()
		else
			self.logger:log(ERR, "can't get BunkerNet ID from datastore : " .. err)
		end
	end
end

function bunkernet:is_needed()
	-- Loading case
	if self.is_loading then
		return false
	end
	-- Request phases (no default)
	if self.is_request and (self.ctx.bw.server_name ~= "_") then
		return self.variables["USE_BUNKERNET"] == "yes"
	end
	-- Other cases : at least one service uses it
	local is_needed, err = has_variable("USE_BUNKERNET", "yes")
	if is_needed == nil then
		self.logger:log(ERR, "can't check USE_BUNKERNET variable : " .. err)
	end
	return is_needed
end

function bunkernet:init_worker()
	-- Check if needed
	if not self:is_needed() then
		return self:ret(true, "no service uses BunkerNet, skipping init_worker")
	end
	-- Check id
	if not self.bunkernet_id then
		return self:ret(false, "missing instance ID")
	end
	-- Send ping request
	local ok, err, status, _ = self:ping()
	if not ok then
		return self:ret(false, "error while sending request to API : " .. err)
	end
	if status ~= 200 then
		return self:ret(
			false,
			"received status " .. tostring(status) .. " from API using instance ID " .. self.bunkernet_id
		)
	end
	self.logger:log(NOTICE, "connectivity with API using instance ID " .. self.bunkernet_id .. " is successful")
	return self:ret(true, "connectivity with API using instance ID " .. self.bunkernet_id .. " is successful")
end

function bunkernet:init()
	-- Check if needed
	if not self:is_needed() then
		return self:ret(true, "no service uses BunkerNet, skipping init")
	end
	-- Check if instance ID is present
	local f, err = open("/var/cache/bunkerweb/bunkernet/instance.id", "r")
	if not f then
		return self:ret(false, "can't read instance id : " .. err)
	end
	-- Retrieve instance ID
	local id = f:read("*all"):gsub("[\r\n]", "")
	f:close()
	-- Store ID in datastore
	local ok, err = self.datastore:set("plugin_bunkernet_id", id, nil, true)
	if not ok then
		return self:ret(false, "can't save instance ID to the datastore : " .. err)
	end
	-- Load databases
	local ret = true
	local i = 0
	local db = {
		ip = {},
	}
	local f, err = open("/var/cache/bunkerweb/bunkernet/ip.list", "r")
	if not f then
		ret = false
	else
		for line in f:lines() do
			if (is_ipv4(line) or is_ipv6(line)) and ip_is_global(line) then
				table.insert(db.ip, line)
				i = i + 1
			end
		end
	end
	if not ret then
		return self:ret(false, "error while reading database : " .. err)
	end
	f:close()
	local ok, err = self.datastore:set("plugin_bunkernet_db", db, nil, true)
	if not ok then
		return self:ret(false, "can't store bunkernet database into datastore : " .. err)
	end
	return self:ret(true, "successfully loaded " .. tostring(i) .. " bad IPs using instance ID " .. id)
end

function bunkernet:access()
	-- Check if needed
	if not self:is_needed() then
		return self:ret(true, "service doesn't use BunkerNet, skipping access")
	end
	-- Check id
	if not self.bunkernet_id then
		return self:ret(false, "missing instance ID")
	end
	-- Check if IP is global
	if not self.ctx.bw.ip_is_global then
		return self:ret(true, "IP is not global")
	end
	-- Check if whitelisted
	if is_whitelisted(self.ctx) then
		return self:ret(true, "client is whitelisted")
	end
	-- Extract DB
	local db, err = self.datastore:get("plugin_bunkernet_db", true)
	if db then
		-- Check if is IP is present
		if #db.ip > 0 then
			-- luacheck: ignore 421
			local present, err = is_ip_in_networks(self.ctx.bw.remote_addr, db.ip)
			if present == nil then
				return self:ret(false, "can't check if ip is in db : " .. err)
			end
			if present then
				return self:ret(true, "ip is in db", get_deny_status())
			end
		end
	else
		return self:ret(false, "can't get bunkernet db " .. err)
	end
	return self:ret(true, "not in db")
end

function bunkernet:log(bypass_checks)
	if not bypass_checks then
		-- Check if needed
		if not self:is_needed() then
			return self:ret(true, "service doesn't use BunkerNet, skipping log")
		end
		-- Check id
		if not self.bunkernet_id then
			return self:ret(false, "missing instance ID")
		end
	end
	-- Check if IP has been blocked
	local reason = get_reason(self.ctx)
	if not reason then
		return self:ret(true, "ip is not blocked")
	end
	if reason == "bunkernet" then
		return self:ret(true, "skipping report because the reason is bunkernet")
	end
	-- Check if IP is global
	if not self.ctx.bw.ip_is_global then
		return self:ret(true, "IP is not global")
	end
	-- Check if IP has been reported recently
	local ok, data = self.cachestore:get("plugin_bunkernet_" .. self.ctx.bw.remote_addr .. "_" .. reason)
	if not ok then
		self.logger:log(ERR, "can't check cachestore : " .. data)
	elseif data then
		return self:ret(true, "already reported recently")
	end
	-- luacheck: ignore 212 431
	local function report_callback(premature, obj, ip, reason, method, url, headers, use_redis)
		local ok, err, status, _ = obj:report(ip, reason, method, url, headers)
		if status == 429 then
			obj.logger:log(WARN, "bunkernet API is rate limiting us")
		elseif not ok then
			obj.logger:log(ERR, "can't report IP : " .. err)
		else
			obj.logger:log(NOTICE, "successfully reported IP " .. ip .. " (reason : " .. reason .. ")")
			local cachestore = require "bunkerweb.cachestore":new(use_redis, nil, true)
			local ok, err = cachestore:set("plugin_bunkernet_" .. ip .. "_" .. reason)
			if not ok then
				obj.logger:log(ERR, "error from cachestore : " .. err)
			end
		end
	end
	local hdr, err = timer_at(
		0,
		report_callback,
		self,
		self.ctx.bw.remote_addr,
		reason,
		self.ctx.bw.request_method,
		self.ctx.bw.request_uri,
		ngx.req.get_headers()
	)
	if not hdr then
		return self:ret(false, "can't create report timer : " .. err)
	end
	return self:ret(true, "created report timer")
end

function bunkernet:log_default()
	-- Check if needed
	if not self:is_needed() then
		return self:ret(true, "no service uses BunkerNet, skipping log_default")
	end
	-- Check id
	if not self.bunkernet_id then
		return self:ret(false, "missing instance ID")
	end
	-- Check if default server is disabled
	local check, err = get_variable("DISABLE_DEFAULT_SERVER", false)
	if check == nil then
		return self:ret(false, "error while getting variable DISABLE_DEFAULT_SERVER : " .. err)
	end
	if check ~= "yes" then
		return self:ret(true, "default server is not disabled")
	end
	-- Call log method
	return self:log(true)
end

function bunkernet:log_stream()
	return self:log()
end

function bunkernet:request(method, url, data)
	local httpc, err = http_new()
	if not httpc then
		return false, "can't instantiate http object : " .. err
	end
	local all_data = {
		id = self.bunkernet_id,
		version = self.version,
		integration = self.integration,
	}
	if data then
		for k, v in pairs(data) do
			all_data[k] = v
		end
	end
	local res, err = httpc:request_uri(self.variables["BUNKERNET_SERVER"] .. url, {
		method = method,
		body = encode(all_data),
		headers = {
			["Content-Type"] = "application/json",
			["User-Agent"] = "BunkerWeb/" .. self.version,
		},
	})
	httpc:close()
	if not res then
		return false, "error while sending request : " .. err
	end
	if res.status ~= 200 then
		return false, "status code != 200", res.status, nil
	end
	local ok, ret = pcall(decode, res.body)
	if not ok then
		return false, "error while decoding json : " .. ret
	end
	return true, "success", res.status, ret
end

function bunkernet:ping()
	return self:request("GET", "/ping", {})
end

function bunkernet:report(ip, reason, method, url, headers)
	local data = {
		ip = ip,
		reason = reason,
		method = method,
		url = url,
		headers = headers,
	}
	return self:request("POST", "/report", data)
end

return bunkernet
