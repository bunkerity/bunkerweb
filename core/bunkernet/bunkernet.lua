local _M = {}
_M.__index = _M

local utils		= require "utils"
local datastore	= require "datastore"
local logger	= require "logger"
local cjson		= require "cjson"
local http		= require "resty.http"

function _M.new()
	local self = setmetatable({}, _M)
	local server, err = datastore:get("variable_BUNKERNET_SERVER")
	if not server then
		return nil, "can't get BUNKERNET_SERVER from datastore : " .. err
	end
	self.server = server
	local id, err = datastore:get("plugin_bunkernet_id")
	if not id then
		self.id = nil
	else
		self.id = id
	end
	return self, nil
end

function _M:init()
	local init_needed, err = utils.has_variable("USE_BUNKERNET", "yes")
	if init_needed == nil then
		return false, err
	end
	if not init_needed then
		return true, "no service uses BunkerNet, skipping init"
	end
	-- Check if instance ID is present
	local f, err = io.open("/opt/bunkerweb/cache/bunkernet/instance.id", "r")
	if not f then
		return false, "can't read instance id : " .. err
	end
	-- Retrieve instance ID
	id = f:read("*all"):gsub("[\r\n]", "")
	f:close()
	self.id = id
	-- TODO : regex check just in case
	-- Send a ping with the ID
	--local ok, err, status, response = self:ping()
	-- BunkerNet server is down or instance can't access it
	--if not ok then
		--return false, "can't send request to BunkerNet service : " .. err
	-- Local instance ID is unknown to the server, let's delete it
	--elseif status == 401 then
		--local ok, message = os.remove("/opt/bunkerweb/cache/bunkernet/instance.id")
		--if not ok then
			--return false, "can't remove instance ID " .. message
		--end
		--return false, "instance ID is not valid"
	--elseif status == 429 then
		--return false, "sent too many requests to the BunkerNet service"
	--elseif status ~= 200 then
		--return false, "unknown error from BunkerNet service (HTTP status = " .. tostring(status) .. ")"
	--end
	-- Store ID in datastore
	local ok, err = datastore:set("plugin_bunkernet_id", id)
	if not ok then
		return false, "can't save instance ID to the datastore : " .. err
	end
	-- Load databases
	local ret = true
	local i = 0
	local db = {
		ip = {}
	}
	f, err = io.open("/opt/bunkerweb/cache/bunkernet/ip.list", "r")
	if not f then
		ret = false
	else
		for line in f:lines() do
			if utils.is_ipv4(line) and utils.ip_is_global(line) then
				table.insert(db.ip, line)
				i = i + 1
			end
		end
	end
	if not ret then
		return false, "error while reading database : " .. err
	end
	f:close()
	local ok, err = datastore:set("plugin_bunkernet_db", cjson.encode(db))
	if not ok then
		return false, "can't store BunkerNet database into datastore : " .. err
	end
	return true, "successfully connected to the BunkerNet service " .. self.server .. " with machine ID " .. id .. " and " .. tostring(i) .. " bad IPs in database"
end

function _M:request(method, url, data)
	local httpc, err = http.new()
	if not httpc then
		return false, "can't instantiate http object : " .. err, nil, nil
	end
	local all_data = {
		id = self.id,
		integration = utils.get_integration(),
		version = utils.get_version()
	}
	for k, v in pairs(data) do
		all_data[k] = v
	end
	local res, err = httpc:request_uri(self.server .. url, {
		method = method,
		body = cjson.encode(all_data),
		headers = {
			["Content-Type"] = "application/json",
			["User-Agent"] = "BunkerWeb/" .. utils.get_version()
		}
	})
	httpc:close()
	if not res then
		return false, "error while sending request : " .. err, nil, nil
	end
	if res.status ~= 200 then
		return false, "status code != 200", res.status, nil
	end
	local ok, ret = pcall(cjson.decode, res.body)
	if not ok then
		return false, "error while decoding json : " .. ret, nil, nil
	end
	return true, "success", res.status, ret
end

function _M:ping()
	return self:request("GET", "/ping", {})
end

function _M:report(ip, reason, method, url, headers)
	local data = {
		ip = ip,
		reason = reason,
		method = method,
		url = url,
		headers = headers
	}
	return self:request("POST", "/report", data)
end

function _M:log(bypass_use_bunkernet)
	if bypass_use_bunkernet then
		-- Check if BunkerNet is activated
		local use_bunkernet = utils.get_variable("USE_BUNKERNET")
		if use_bunkernet ~= "yes" then
			return true, "bunkernet not activated"
		end
	end
	-- Check if BunkerNet ID is generated
	if not self.id then
		return true, "bunkernet ID is not generated"
	end
	-- Check if IP has been blocked
	local reason = utils.get_reason()
	if not reason then
		return true, "ip is not blocked"
	end
	if reason == "bunkernet" then
		return true, "skipping report because the reason is bunkernet"
	end
	-- Check if IP is global
	local is_global, err = utils.ip_is_global(ngx.var.remote_addr)
	if is_global == nil then
		return false, "error while checking if IP is global " .. err
	end
	if not is_global then
		return true, "IP is not global"
	end
	-- Only report if it hasn't been reported for the same reason recently
	--local reported = datastore:get("plugin_bunkernet_cache_" .. ngx.var.remote_addr .. reason)
	--if reported then
		--return true, "ip already reported recently"
	--end
	local function report_callback(premature, obj, ip, reason, method, url, headers)
		local ok, err, status, data = obj:report(ip, reason, method, url, headers)
		if status == 429 then
			logger.log(ngx.WARN, "BUNKERNET", "BunkerNet API is rate limiting us")
		elseif not ok then
			logger.log(ngx.ERR, "BUNKERNET", "Can't report IP : " .. err)
		else
			logger.log(ngx.NOTICE, "BUNKERNET", "Successfully reported IP " .. ip .. " (reason : " .. reason .. ")")
			--local ok, err = datastore:set("plugin_bunkernet_cache_" .. ip .. reason, true, 3600)
			--if not ok then
				--logger.log(ngx.ERR, "BUNKERNET", "Can't store cached report : " .. err)
			--end
		end
	end
	local hdr, err = ngx.timer.at(0, report_callback, self, ngx.var.remote_addr, reason, ngx.var.request_method, ngx.var.request_uri, ngx.req.get_headers())
	if not hdr then
		return false, "can't create report timer : " .. err
	end
	return true, "created report timer"
end

function _M:log_default()
	-- Check if bunkernet is activated
	local check, err = utils.has_variable("USE_BUNKERNET", "yes")
	if check == nil then
		return false, "error while checking variable USE_BUNKERNET (" .. err .. ")"
	end
	if not check then
		return true, "bunkernet not enabled"
	end
	-- Check if default server is disabled
	local check, err = utils.get_variable("DISABLE_DEFAULT_SERVER", false)
	if check == nil then
		return false, "error while getting variable DISABLE_DEFAULT_SERVER (" .. err .. ")"
	end
	if check ~= "yes" then
		return true, "default server not disabled"
	end
	-- Call log method
	return self:log(true)
end

function _M:access()
	local use_bunkernet = utils.get_variable("USE_BUNKERNET")
	if use_bunkernet ~= "yes" then
		return true, "bunkernet not activated", false, nil
	end
	-- Check if BunkerNet ID is generated
	if not self.id then
		return true, "bunkernet ID is not generated"
	end
	local data, err = datastore:get("plugin_bunkernet_db")
	if not data then
		return false, "can't get bunkernet db : " .. err, false, nil
	end
	local db = cjson.decode(data)
	for index, value in ipairs(db.ip) do
		if value == ngx.var.remote_addr then
			return true, "ip is in database", true, ngx.exit(ngx.HTTP_FORBIDDEN)
		end
	end
	return true, "ip is not in database", false, nil
end

function _M:api()
	return false, nil, nil
end

return _M
