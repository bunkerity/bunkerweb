local ngx = ngx
local ngx_req = ngx.req
local bit = require "bit"
local cdatastore = require "bunkerweb.datastore"
local cjson = require "cjson"
local class = require "middleclass"
local clogger = require "bunkerweb.logger"
local helpers = require "bunkerweb.helpers"
local process = require "ngx.process"
local rsignal = require "resty.signal"
local upload = require "resty.upload"
local utils = require "bunkerweb.utils"

local api = class("api")

local datastore = cdatastore:new()
local logger = clogger:new("API")

local get_country = utils.get_country
local get_variable = utils.get_variable
local is_ip_in_networks = utils.is_ip_in_networks
-- local run = shell.run
local NOTICE = ngx.NOTICE
local ERR = ngx.ERR
local HTTP_OK = ngx.HTTP_OK
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local HTTP_BAD_REQUEST = ngx.HTTP_BAD_REQUEST
local HTTP_NOT_FOUND = ngx.HTTP_NOT_FOUND
local kill = rsignal.kill
local get_master_pid = process.get_master_pid
local execute = os.execute
local open = io.open
local read_body = ngx_req.read_body
local get_body_data = ngx_req.get_body_data
local get_body_file = ngx_req.get_body_file
local decode = cjson.decode
local encode = cjson.encode
local match = string.match
local require_plugin = helpers.require_plugin
local new_plugin = helpers.new_plugin
local call_plugin = helpers.call_plugin

api.global = { GET = {}, POST = {}, PUT = {}, DELETE = {} }

-- Constant-time string comparison to mitigate timing attacks
local function secure_compare(a, b)
	if not a or not b then
		return false
	end
	if #a ~= #b then
		return false
	end
	local diff = 0
	for i = 1, #a do
		diff = bit.bor(diff, bit.bxor(a:byte(i), b:byte(i)))
	end
	return diff == 0
end

function api:is_allowed_token()
	-- If no token configured, allow
	if not self.api_token or self.api_token == "" then
		return true, "ok"
	end
	local headers = ngx_req.get_headers()
	local auth = headers["authorization"] or headers["Authorization"]
	local provided = auth and auth:match("^[Bb]earer%s+(.+)$") or nil
	if not provided then
		return false, "missing API token"
	end
	if not secure_compare(provided, self.api_token) then
		return false, "invalid API token"
	end
	return true, "ok"
end

function api:initialize(ctx)
	self.ctx = ctx
	local data, err = get_variable("API_WHITELIST_IP", false)
	self.ips = {}
	self.api_token = nil
	if not data then
		logger:log(ERR, "can't get API_WHITELIST_IP variable : " .. err)
	else
		for ip in data:gmatch("%S+") do
			table.insert(self.ips, ip)
		end
	end

	-- Load optional API token (from datastore variables, same pattern as whitelist)
	local tok = get_variable("API_TOKEN", false)
	if tok and tok ~= "" then
		self.api_token = tok
	end
end

-- luacheck: ignore 212
function api:log_cmd(cmd, status, stdout, stderr)
	local level = NOTICE
	local prefix = "success"
	if status ~= 0 then
		level = ERR
		prefix = "error"
	end
	logger:log(level, prefix .. " while running command " .. cmd)
	logger:log(level, "stdout = " .. stdout)
	logger:log(level, "stdout = " .. stderr)
end

-- TODO : use this if we switch to OpenResty
function api:cmd(cmd)
	-- Non-blocking command
	-- luacheck: ignore 113
	local ok, stdout, stderr, reason, status = run(cmd, nil, 10000)
	self:log_cmd(cmd, status, stdout, stderr)
	-- Timeout
	if ok == nil then
		return nil, reason
	end
	-- Other cases : exit 0, exit !0 and killed by signal
	return status == 0, reason, status
end

-- luacheck: ignore 212
function api:response(http_status, api_status, msg)
	local resp = {}
	resp["status"] = api_status
	resp["msg"] = msg
	return http_status, resp
end

api.global.GET["^/ping$"] = function(self)
	return self:response(HTTP_OK, "success", "pong")
end

api.global.GET["^/health$"] = function(self)
	-- Check if reload indicator file exists
	local f = open("/var/tmp/bunkerweb_reloading", "r")
	if f then
		f:close()
		return self:response(HTTP_OK, "success", "reloading")
	end

	local data, err = get_variable("IS_LOADING", false)
	if not data then
		logger:log(ERR, "can't get IS_LOADING variable : " .. err)
		return self:response(HTTP_OK, "success", "loading")
	end
	if data == "yes" then
		return self:response(HTTP_OK, "success", "loading")
	end
	return self:response(HTTP_OK, "success", "ok")
end

api.global.POST["^/reload"] = function(self)
	-- Get test argument
	local args = ngx.req.get_uri_args()
	local test_arg = args.test or "yes"

	if test_arg ~= "no" then
		-- Check Nginx configuration
		logger:log(NOTICE, "Checking Nginx configuration")
		local handle = io.popen("/usr/sbin/nginx -t 2>&1")
		local result = handle:read("*a")
		handle:close()

		-- Check for success message in output regardless of exit code
		if string.match(result, "configuration file .+ test is successful") then
			logger:log(NOTICE, "Nginx configuration is valid")
		else
			return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "config check failed: " .. result)
		end
	end

	-- Reload Nginx
	logger:log(NOTICE, "Reloading Nginx")
	-- Send HUP signal to master process
	local ok, err = kill(get_master_pid(), "HUP")
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "err = " .. err)
	end

	-- Create temporary file to indicate reconfiguration
	local file, err = open("/var/tmp/bunkerweb_reloading", "w")
	if file then
		file:write(tostring(os.time()))
		file:close()
	else
		logger:log(ERR, "Failed to create reload indicator file: " .. err)
	end

	return self:response(HTTP_OK, "success", "reload successful")
end

api.global.POST["^/stop$"] = function(self)
	-- Send QUIT signal to master process
	local ok, err = kill(get_master_pid(), "QUIT")
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "err = " .. err)
	end
	return self:response(HTTP_OK, "success", "stop successful")
end

api.global.POST["^/confs$"] = function(self)
	local tmp = "/var/tmp/bunkerweb/api_" .. self.ctx.bw.uri:sub(2) .. ".tar.gz"
	local destination = "/usr/share/bunkerweb/" .. self.ctx.bw.uri:sub(2)
	if self.ctx.bw.uri == "/confs" then
		destination = "/etc/nginx"
	elseif self.ctx.bw.uri == "/data" then
		destination = "/data"
	elseif self.ctx.bw.uri == "/cache" then
		destination = "/var/cache/bunkerweb"
	elseif self.ctx.bw.uri == "/custom_configs" then
		destination = "/etc/bunkerweb/configs"
	elseif self.ctx.bw.uri == "/plugins" then
		destination = "/etc/bunkerweb/plugins"
	elseif self.ctx.bw.uri == "/pro_plugins" then
		destination = "/etc/bunkerweb/pro/plugins"
	end
	local form, err = upload:new(4096)
	if not form then
		return self:response(HTTP_BAD_REQUEST, "error", err)
	end
	form:set_timeout(1000)
	local file, err = open(tmp, "w+")
	if not file then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", err)
	end
	while true do
		-- luacheck: ignore 421
		local typ, res, err = form:read()
		if not typ then
			file:close()
			return self:response(HTTP_BAD_REQUEST, "error", err)
		end
		if typ == "eof" then
			break
		end
		if typ == "body" then
			file:write(res)
		end
	end
	file:flush()
	file:close()
	local cmds = {
		"rm -rf " .. destination .. "/*",
		"tar xzf " .. tmp .. " -C " .. destination,
		-- Remove the temporary archive once extracted
		"rm -f " .. tmp,
	}
	for _, cmd in ipairs(cmds) do
		local status = execute(cmd)
		if status ~= 0 then
			return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "exit status = " .. tostring(status))
		end
	end
	return self:response(HTTP_OK, "success", "saved data at " .. destination)
end

api.global.POST["^/data$"] = api.global.POST["^/confs$"]

api.global.POST["^/cache$"] = api.global.POST["^/confs$"]

api.global.POST["^/custom_configs$"] = api.global.POST["^/confs$"]

api.global.POST["^/plugins$"] = api.global.POST["^/confs$"]

api.global.POST["^/pro_plugins$"] = api.global.POST["^/confs$"]

api.global.POST["^/unban$"] = function(self)
	read_body()
	local data = get_body_data()
	if not data then
		local data_file = get_body_file()
		if data_file then
			local file, err = open(data_file)
			if not file then
				return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", err)
			end
			data = file:read("*a")
			file:close()
		end
	end
	local ok, ip = pcall(decode, data)
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "can't decode JSON : " .. ip)
	end

	local ban_scope = ip["ban_scope"] or "global"
	local service = ip["service"]
	local response_msg = "ip " .. ip["ip"] .. " unbanned"

	-- Validate ban scope
	if ban_scope ~= "global" and ban_scope ~= "service" then
		logger:log(ERR, "Invalid ban scope: " .. ban_scope .. ", defaulting to global")
		ban_scope = "global"
	end

	-- For service-specific unbans, validate the service
	if ban_scope == "service" then
		if not service or service == "unknown" or service == "Web UI" or service == "bwcli" or service == "" then
			logger:log(ERR, "Invalid service name for service-specific unban, defaulting to global unban")
			ban_scope = "global"
			service = nil
		else
			response_msg = response_msg .. " for service " .. service
		end
	end

	-- Use utils.remove_ban to remove the ban(s)
	local ok, err = utils.remove_ban(ip["ip"], service, ban_scope)
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "failed to remove ban: " .. err)
	end

	return self:response(HTTP_OK, "success", response_msg)
end

api.global.POST["^/ban$"] = function(self)
	read_body()
	local data = get_body_data()
	if not data then
		local data_file = get_body_file()
		if data_file then
			local file, err = open(data_file)
			if not file then
				return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", err)
			end
			data = file:read("*a")
			file:close()
		end
	end
	local ok, ip = pcall(decode, data)
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "can't decode JSON : " .. ip)
	end
	local ban = {
		ip = "",
		exp = 86400,
		reason = "manual",
		service = "unknown",
		country = "local",
		ban_scope = "global", -- Default to global for consistency
	}

	-- Copy values from request
	ban.ip = ip["ip"]
	if ip["exp"] then
		ban.exp = ip["exp"]
	end
	if ip["reason"] then
		ban.reason = ip["reason"]
	end
	if ip["service"] then
		ban.service = ip["service"]
	end
	if ip["ban_scope"] then
		ban.ban_scope = ip["ban_scope"]
	end

	-- Validate ban scope
	if ban.ban_scope ~= "global" and ban.ban_scope ~= "service" then
		logger:log(ERR, "Invalid ban scope: " .. ban.ban_scope .. ", defaulting to global")
		ban.ban_scope = "global"
	end

	-- Validate service name for service-specific bans
	if ban.ban_scope == "service" then
		if ban.service == "unknown" or ban.service == "Web UI" or ban.service == "bwcli" or ban.service == "" then
			logger:log(ERR, "Invalid service name: " .. ban.service .. ", defaulting to global ban")
			ban.ban_scope = "global"
			ban.service = "unknown"
		end
	end

	local country, err = get_country(ban["ip"])
	if not country then
		country = "unknown"
		logger:log(ERR, "can't get country code " .. err)
	end
	ban.country = country

	-- Use utils.add_ban to ensure ban is applied to datastore and Redis
	local ok, err = utils.add_ban(ban.ip, ban.reason, ban.exp, ban.service, ban.country, ban.ban_scope)
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "failed to add ban: " .. err)
	end

	-- Create a more informative response message
	local scope_text = ban.ban_scope == "global" and "globally" or ("for service " .. ban.service)
	local duration_text = not ban["exp"] and "permanently" or ("for " .. ban["exp"] .. " seconds")
	return self:response(HTTP_OK, "success", "ip " .. ip["ip"] .. " banned " .. scope_text .. " " .. duration_text)
end

api.global.GET["^/bans$"] = function(self)
	local data = {}
	-- Get system-wide bans
	for _, k in ipairs(datastore:keys()) do
		if k:find("^bans_ip_") then
			local result, err = datastore:get(k)
			if err then
				return self:response(
					HTTP_INTERNAL_SERVER_ERROR,
					"error",
					"can't access " .. k .. " from datastore : " .. result
				)
			end
			local ok, ttl = datastore:ttl(k)
			if not ok then
				return self:response(
					HTTP_INTERNAL_SERVER_ERROR,
					"error",
					"can't access ttl " .. k .. " from datastore : " .. ttl
				)
			end
			local ban_data
			ok, ban_data = pcall(decode, result)
			if not ok then
				ban_data = { reason = result, service = "unknown", date = 0, ban_scope = "global" }
			end

			-- Check for permanent ban flag and override TTL if set
			if ban_data["permanent"] then
				ttl = 0
			end

			table.insert(data, {
				ip = k:sub(9, #k),
				reason = ban_data["reason"],
				service = ban_data["service"],
				date = ban_data["date"],
				country = ban_data["country"],
				ban_scope = ban_data["ban_scope"] or "global",
				exp = math.floor(ttl),
				permanent = ban_data["permanent"] or false,
			})
		elseif k:find("^bans_service_") then
			-- Service-specific ban (format: bans_service_<servicename>_ip_<ipaddress>)
			local result, err = datastore:get(k)
			if err then
				return self:response(
					HTTP_INTERNAL_SERVER_ERROR,
					"error",
					"can't access " .. k .. " from datastore : " .. result
				)
			end
			local ok, ttl = datastore:ttl(k)
			if not ok then
				return self:response(
					HTTP_INTERNAL_SERVER_ERROR,
					"error",
					"can't access ttl " .. k .. " from datastore : " .. ttl
				)
			end

			-- Extract service and IP from the key
			local service, ip = k:match("^bans_service_(.-)_ip_(.+)$")
			if service and ip then
				local ban_data
				ok, ban_data = pcall(decode, result)
				if not ok then
					ban_data = { reason = result, service = service, date = 0, ban_scope = "service" }
				end

				-- Check for permanent ban flag and override TTL if set
				if ban_data["permanent"] then
					ttl = 0
				end

				table.insert(data, {
					ip = ip,
					reason = ban_data["reason"],
					service = service,
					date = ban_data["date"],
					country = ban_data["country"],
					ban_scope = "service",
					exp = math.floor(ttl),
					permanent = ban_data["permanent"] or false,
				})
			end
		end
	end
	return self:response(HTTP_OK, "success", data)
end

api.global.GET["^/variables$"] = function(self)
	local variables, err = datastore:get("variables", true)
	if not variables then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "can't access variables from datastore : " .. err)
	end
	return self:response(HTTP_OK, "success", variables)
end

function api:is_allowed_ip()
	if is_ip_in_networks(self.ctx.bw.remote_addr, self.ips) then
		return true, "ok"
	end
	return false, "IP is not in API_WHITELIST_IP"
end

function api:do_api_call()
	if self.global[self.ctx.bw.request_method] ~= nil then
		for uri, api_fun in pairs(self.global[self.ctx.bw.request_method]) do
			if match(self.ctx.bw.uri, uri) then
				local status, resp = api_fun(self)
				local ret = true
				if status ~= HTTP_OK then
					ret = false
				end
				if #resp["msg"] == 0 then
					resp["msg"] = ""
				elseif type(resp["msg"]) == "table" then
					resp["data"] = resp["msg"]
					resp["msg"] = resp["status"]
				end
				return ret, resp["msg"], status, encode(resp)
			end
		end
	end
	local list, err = datastore:get("plugins", true)
	if not list then
		local _, resp = self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "can't list loaded plugins : " .. err)
		return false, resp["msg"], HTTP_INTERNAL_SERVER_ERROR, encode(resp)
	end
	for _, plugin in ipairs(list) do
		local plugin_lua, _ = require_plugin(plugin.id)
		if plugin_lua and plugin_lua.api ~= nil then
			local ok, plugin_obj = new_plugin(plugin_lua, self.ctx)
			if not ok then
				logger:log(ERR, "can't instantiate " .. plugin.id .. " : " .. plugin_obj)
			else
				local ret
				ok, ret = call_plugin(plugin_obj, "api")
				if not ok then
					logger:log(ERR, "error while executing " .. plugin.id .. ":api() : " .. ret)
				else
					if ret.ret then
						local resp = {}
						if ret.status == HTTP_OK then
							resp["status"] = "success"
						else
							resp["status"] = "error"
						end
						resp["msg"] = ret.msg
						return ret.status == HTTP_OK, resp["status"], ret.status, encode(resp)
					end
				end
			end
		end
	end
	local resp = {}
	resp["status"] = "error"
	resp["msg"] = "not found"
	return false, "error", HTTP_NOT_FOUND, encode(resp)
end

return api
