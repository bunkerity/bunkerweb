local cjson = require "cjson"
local class = require "middleclass"
local http = require "resty.http"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local bunkernet = class("bunkernet", plugin)

local ngx = ngx
local ERR = ngx.ERR
local WARN = ngx.WARN
local NOTICE = ngx.NOTICE
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local HTTP_OK = ngx.HTTP_OK
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
local match = string.match
local table_insert = table.insert

function bunkernet:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "bunkernet", ctx)
	-- Get BunkerNet ID and save info
	if get_phase() ~= "init" and self:is_needed() then
		local id, _ = self.internalstore:get("plugin_bunkernet_id", true)
		if id then
			self.bunkernet_id = id
			self.version = get_version(self.ctx)
			self.integration = get_integration(self.ctx)
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
		self.logger:log(WARN, "missing instance ID")
		return self:ret(true, "missing instance ID")
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
		self.logger:log(WARN, "instance ID not found, skipping instance id initialization: " .. tostring(err))
		return self:ret(true, "instance ID not found")
	end
	-- Retrieve instance ID
	local id = f:read("*all"):gsub("[\r\n]", "")
	f:close()
	-- Store ID in internalstore
	local ok, err = self.internalstore:set("plugin_bunkernet_id", id, nil, true)
	if not ok then
		return self:ret(false, "can't save instance ID to the internalstore : " .. err)
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
	local ok, err = self.internalstore:set("plugin_bunkernet_db", db, nil, true)
	if not ok then
		return self:ret(false, "can't store bunkernet database into internalstore : " .. err)
	end
	return self:ret(true, "successfully loaded " .. tostring(i) .. " bad IPs using instance ID " .. id)
end

function bunkernet:access()
	-- Check if needed
	if not self:is_needed() then
		return self:ret(true, "service doesn't use BunkerNet, skipping access")
	end
	-- Check if IP is global
	if not self.ctx.bw.ip_is_global then
		return self:ret(true, "IP is not global")
	end
	-- Check if whitelisted
	if is_whitelisted(self.ctx) then
		return self:ret(true, "client is whitelisted")
	end
	-- Check id
	if not self.bunkernet_id then
		self.logger:log(WARN, "missing instance ID")
		return self:ret(true, "missing instance ID")
	end
	-- Extract DB
	local db, err = self.internalstore:get("plugin_bunkernet_db", true)
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
	end

	-- Check if IP has been blocked
	local reason, reason_data = get_reason(self.ctx)
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

	-- Check id
	if not self.bunkernet_id then
		self.logger:log(WARN, "missing instance ID")
		return self:ret(true, "missing instance ID")
	end

	-- Check if IP has been reported recently
	local ret, err = self.datastore:get("plugin_bunkernet_" .. self.ctx.bw.remote_addr .. "_" .. reason)
	if not ret and err ~= "not found" then
		return self:ret(false, "can't get IP from datastore : " .. err)
	elseif err == "not found" then
		-- Push report
		local report = {
			["ip"] = self.ctx.bw.remote_addr,
			["reason"] = reason,
			["data"] = reason_data,
			["method"] = self.ctx.bw.request_method,
			["url"] = self.ctx.bw.request_uri,
			["headers"] = ngx.req.get_headers(),
			["server_name"] = self.ctx.bw.server_name,
			["date"] = os.date("!%Y-%m-%dT%H:%M:%SZ", ngx.time()),
		}
		ret, err = self.datastore.dict:rpush("plugin_bunkernet_reports", encode(report))
		if not ret then
			return self:ret(false, "can't set IP report into datastore : " .. err)
		end
		-- Store in recent reports
		ret, err = self.datastore:set_with_retries(
			"plugin_bunkernet_" .. self.ctx.bw.remote_addr .. "_" .. reason,
			"added",
			5400
		)
		if not ret then
			return self:ret(false, "can't add recent IP into datastore : " .. err)
		end
		return self:ret(true, "IP added to reports")
	end

	return self:ret(true, "IP already added to reports recently")
end

function bunkernet:log_default()
	-- Check if needed
	if not self:is_needed() then
		return self:ret(true, "no service uses BunkerNet, skipping log_default")
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

	local os_data = {
		name = "Linux",
		version = "Unknown",
		version_id = "Unknown",
		version_codename = "Unknown",
		id = "Unknown",
		arch = "Unknown",
	}
	local uname_cmd = io.popen("uname -m")
	if uname_cmd then
		os_data.arch = uname_cmd:read("*a"):gsub("\n", "")
		uname_cmd:close()
	end

	local file = io.open("/etc/os-release", "r")
	if file then
		for line in file:lines() do
			local key, value = line:match("^(%w+)=(.+)$")
			if key and value then
				value = value:gsub('"', "")
				if key == "NAME" then
					os_data.name = value
				elseif key == "VERSION" then
					os_data.version = value
				elseif key == "VERSION_ID" then
					os_data.version_id = value
				elseif key == "VERSION_CODENAME" then
					os_data.version_codename = value
				elseif key == "ID" then
					os_data.id = value
				end
			end
		end
		file:close()
	end

	local all_data = {
		id = self.bunkernet_id,
		version = self.version,
		integration = self.integration,
		os = os_data,
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

function bunkernet:report(ip, reason, reason_data, method, url, headers, server_name)
	local data = {
		ip = ip,
		reason = reason,
		data = reason_data,
		method = method,
		url = url,
		headers = headers,
		server_name = server_name,
	}
	return self:request("POST", "/report", data)
end

function bunkernet:api()
	-- Match request
	local is_ping = match(self.ctx.bw.uri, "^/bunkernet/ping$") and self.ctx.bw.request_method == "POST"
	local is_reports = match(self.ctx.bw.uri, "^/bunkernet/reports$") and self.ctx.bw.request_method == "GET"
	if not (is_ping or is_reports) then
		return self:ret(false, "success")
	end

	if match(self.ctx.bw.uri, "^/bunkernet/ping$") then
		-- Check id
		local id, err_id = self.internalstore:get("plugin_bunkernet_id", true)
		if not id and err_id ~= "not found" then
			return self:ret(true, "error while getting bunkernet id : " .. err_id, HTTP_INTERNAL_SERVER_ERROR)
		elseif not id then
			return self:ret(true, "missing instance ID", HTTP_INTERNAL_SERVER_ERROR)
		end

		self.bunkernet_id = id
		self.version = get_version(self.ctx)
		self.integration = get_integration(self.ctx)
		-- Send ping request
		local ok, err, status, _ = self:ping()
		if not ok then
			return self:ret(true, "error while sending request to API : " .. err, HTTP_INTERNAL_SERVER_ERROR)
		end
		if status ~= 200 then
			return self:ret(
				true,
				"received status " .. tostring(status) .. " from API using instance ID " .. self.bunkernet_id,
				HTTP_INTERNAL_SERVER_ERROR
			)
		end
		return self:ret(
			true,
			"connectivity with API using instance ID " .. self.bunkernet_id .. " is successful",
			HTTP_OK
		)
	elseif match(self.ctx.bw.uri, "^/bunkernet/reports$") then
		-- Get reports list length
		local len, _ = self.datastore:llen("plugin_bunkernet_reports")
		if len == nil then
			return self:ret(true, {}, HTTP_OK)
		end
		-- Loop on reports
		local reports = {}
		for _ = 1, len do
			-- Pop the report and decode it
			local report, report_err = self.datastore:lpop("plugin_bunkernet_reports")
			if not report then
				self.logger:log(ERR, "can't lpop report : " .. report_err)
			else
				table_insert(reports, decode(report))
			end
		end
		-- Return reports
		return self:ret(true, reports, HTTP_OK)
	end
end

return bunkernet
