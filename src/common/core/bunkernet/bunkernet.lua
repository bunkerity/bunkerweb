local class     = require "middleclass"
local plugin    = require "bunkerweb.plugin"
local utils     = require "bunkerweb.utils"
local datastore = require "bunkerweb.datastore"
local cjson     = require "cjson"
local http      = require "resty.http"

local bunkernet = class("bunkernet", plugin)

function bunkernet:initialize()
	-- Call parent initialize
	plugin.initialize(self, "bunkernet")
	-- Get BunkerNet ID and save info
	if ngx.get_phase() ~= "init" and self:is_needed() then
		local id, err = self.datastore:get("plugin_bunkernet_id")
		if id then
			self.bunkernet_id = id
			self.version = ngx.ctx.bw.version
			self.integration = ngx.ctx.bw.integration
		else
			self.logger:log(ngx.ERR, "can't get BunkerNet ID from datastore : " .. err)
		end
	end
end

function bunkernet:is_needed()
	-- Loading case
	if self.is_loading then
		return false
	end
	-- Request phases (no default)
	if self.is_request and (ngx.ctx.bw.server_name ~= "_") then
		return self.variables["USE_BUNKERNET"] == "yes"
	end
	-- Other cases : at least one service uses it
	local is_needed, err = utils.has_variable("USE_BUNKERNET", "yes")
	if is_needed == nil then
		self.logger:log(ngx.ERR, "can't check USE_BUNKERNET variable : " .. err)
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
	local ok, err, status, data = self:ping()
	if not ok then
		return self:ret(false, "error while sending request to API : " .. err)
	end
	if status ~= 200 then
		return self:ret(false, "received status " .. tostring(status) .. " from API using instance ID " .. self.bunkernet_id)
	end
	self.logger:log(ngx.NOTICE, "connectivity with API using instance ID " .. self.id .. " is successful")
	return self:ret(true, "connectivity with API using instance ID " .. self.id .. " is successful")
end

function bunkernet:init()
	-- Check if needed
	if not self:is_needed() then
		return self:ret(true, "no service uses BunkerNet, skipping init")
	end
	-- Check if instance ID is present
	local f, err = io.open("/var/cache/bunkerweb/bunkernet/instance.id", "r")
	if not f then
		return self:ret(false, "can't read instance id : " .. err)
	end
	-- Retrieve instance ID
	local id = f:read("*all"):gsub("[\r\n]", "")
	f:close()
	-- Store ID in datastore
	local ok, err = self.datastore:set("plugin_bunkernet_id", id)
	if not ok then
		return self:ret(false, "can't save instance ID to the datastore : " .. err)
	end
	-- Load databases
	local ret = true
	local i = 0
	local db = {
		ip = {}
	}
	local f, err = io.open("/var/cache/bunkerweb/bunkernet/ip.list", "r")
	if not f then
		ret = false
	else
		for line in f:lines() do
			if (utils.is_ipv4(line) or utils.is_ipv6(line)) and utils.ip_is_global(line) then
				table.insert(db.ip, line)
				i = i + 1
			end
		end
	end
	if not ret then
		return self:ret(false, "error while reading database : " .. err)
	end
	f:close()
	local ok, err = self.datastore:set("plugin_bunkernet_db", cjson.encode(db))
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
	if not ngx.ctx.bw.ip_is_global then
		return self:ret(true, "IP is not global")
	end
	-- Check if whitelisted
	if ngx.ctx.bw.is_whitelisted == "yes" then
		return self:ret(true, "client is whitelisted")
	end
	-- Extract DB
	local db, err = self.datastore:get("plugin_bunkernet_db")
	if db then
		db = cjson.decode(db)
		-- Check if is IP is present
		if #db.ip > 0 then
			local present, err = utils.is_ip_in_networks(ngx.ctx.bw.remote_addr, db.ip)
			if present == nil then
				return self:ret(false, "can't check if ip is in db : " .. err)
			end
			if present then
				return self:ret(true, "ip is in db", utils.get_deny_status())
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
	local reason = utils.get_reason()
	if not reason then
		return self:ret(true, "ip is not blocked")
	end
	if reason == "bunkernet" then
		return self:ret(true, "skipping report because the reason is bunkernet")
	end
	-- Check if IP is global
	if not ngx.ctx.bw.ip_is_global then
		return self:ret(true, "IP is not global")
	end
	-- TODO : check if IP has been reported recently
	local function report_callback(premature, obj, ip, reason, method, url, headers)
		local ok, err, status, data = obj:report(ip, reason, method, url, headers)
		if status == 429 then
			obj.logger:log(ngx.WARN, "bunkernet API is rate limiting us")
		elseif not ok then
			obj.logger:log(ngx.ERR, "can't report IP : " .. err)
		else
			obj.logger:log(ngx.NOTICE, "successfully reported IP " .. ip .. " (reason : " .. reason .. ")")
		end
	end

	local hdr, err = ngx.timer.at(0, report_callback, self, ngx.ctx.bw.remote_addr, reason, ngx.ctx.bw.request_method,
		ngx.ctx.bw.request_uri, ngx.req.get_headers())
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
	local check, err = utils.get_variable("DISABLE_DEFAULT_SERVER", false)
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
	local httpc, err = http.new()
	if not httpc then
		return false, "can't instantiate http object : " .. err
	end
	local all_data = {
		id = self.bunkernet_id,
		version = self.version,
		integration = self.integration
	}
	if data then
		for k, v in pairs(data) do
			all_data[k] = v
		end
	end
	local res, err = httpc:request_uri(self.variables["BUNKERNET_SERVER"] .. url, {
		method = method,
		body = cjson.encode(all_data),
		headers = {
			["Content-Type"] = "application/json",
			["User-Agent"] = "BunkerWeb/" .. self.version
		}
	})
	httpc:close()
	if not res then
		return false, "error while sending request : " .. err
	end
	if res.status ~= 200 then
		return false, "status code != 200", res.status, nil
	end
	local ok, ret = pcall(cjson.decode, res.body)
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
		headers = headers
	}
	return self:request("POST", "/report", data)
end

return bunkernet
