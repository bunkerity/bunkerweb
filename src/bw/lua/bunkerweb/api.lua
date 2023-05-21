local class     = require "middleclass"
local datastore = require "bunkerweb.datastore"
local utils     = require "bunkerweb.utils"
local logger	= require "bunkerweb.logger"
local cjson     = require "cjson"
local upload    = require "resty.upload"
local rsignal	= require "resty.signal"
local process	= require "ngx.process"

local api       = class("api")

api.global      = { GET = {}, POST = {}, PUT = {}, DELETE = {} }

function api:initialize()
	self.datastore = datastore:new()
	self.logger = logger:new("API")
end

function api:log_cmd(cmd, status, stdout, stderr)
	local level = ngx.NOTICE
	local prefix = "success"
	if status ~= 0 then
		level = ngx.ERR
		prefix = "error"
	end
	self.logger:log(level, prefix .. " while running command " .. command)
	self.logger:log(level, "stdout = " .. stdout)
	self.logger:log(level, "stdout = " .. stderr)
end

-- TODO : use this if we switch to OpenResty
function api:cmd(cmd)
	-- Non-blocking command
	local ok, stdout, stderr, reason, status = shell.run(cmd, nil, 10000)
	self.logger:log_cmd(cmd, status, stdout, stderr)
	-- Timeout
	if ok == nil then
		return nil, reason
	end
	-- Other cases : exit 0, exit !0 and killed by signal
	return status == 0, reason, status
end

function api:response(http_status, api_status, msg)
	local resp = {}
	resp["status"] = api_status
	resp["msg"] = msg
	return http_status, resp
end

api.global.GET["^/ping$"] = function(self)
	return self:response(ngx.HTTP_OK, "success", "pong")
end

api.global.POST["^/reload$"] = function(self)
	-- Send HUP signal to master process
	local ok, err = rsignal.kill(process.get_master_pid(), "HUP")
	if not ok then
		return self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "err = " .. err)
	end
	return self:response(ngx.HTTP_OK, "success", "reload successful")
end

api.global.POST["^/stop$"] = function(self)
	-- Send QUIT signal to master process
	local ok, err = rsignal.kill(process.get_master_pid(), "QUIT")
	if not ok then
		return self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "err = " .. err)
	end
	return self:response(ngx.HTTP_OK, "success", "stop successful")
end

api.global.POST["^/confs$"] = function(self)
	local tmp = "/var/tmp/bunkerweb/api_" .. ngx.ctx.bw.uri:sub(2) .. ".tar.gz"
	local destination = "/usr/share/bunkerweb/" .. ngx.ctx.bw.uri:sub(2)
	if ngx.ctx.bw.uri == "/confs" then
		destination = "/etc/nginx"
	elseif ngx.ctx.bw.uri == "/data" then
		destination = "/data"
	elseif ngx.ctx.bw.uri == "/cache" then
		destination = "/var/cache/bunkerweb"
	elseif ngx.ctx.bw.uri == "/custom_configs" then
		destination = "/etc/bunkerweb/configs"
	elseif ngx.ctx.bw.uri == "/plugins" then
		destination = "/etc/bunkerweb/plugins"
	end
	local form, err = upload:new(4096)
	if not form then
		return self:response(ngx.HTTP_BAD_REQUEST, "error", err)
	end
	form:set_timeout(1000)
	local file = io.open(tmp, "w+")
	while true do
		local typ, res, err = form:read()
		if not typ then
			file:close()
			return self:response(ngx.HTTP_BAD_REQUEST, "error", err)
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
		"tar xzf " .. tmp .. " -C " .. destination
	}
	for i, cmd in ipairs(cmds) do
		local status = os.execute(cmd)
		if status ~= 0 then
			return self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "exit status = " .. tostring(status))
		end
	end
	return self:response(ngx.HTTP_OK, "success", "saved data at " .. destination)
end

api.global.POST["^/data$"] = api.global.POST["^/confs$"]

api.global.POST["^/cache$"] = api.global.POST["^/confs$"]

api.global.POST["^/custom_configs$"] = api.global.POST["^/confs$"]

api.global.POST["^/plugins$"] = api.global.POST["^/confs$"]

api.global.POST["^/unban$"] = function(self)
	ngx.req.read_body()
	local data = ngx.req.get_body_data()
	if not data then
		local data_file = ngx.req.get_body_file()
		if data_file then
			local file = io.open(data_file)
			data = file:read("*a")
			file:close()
		end
	end
	local ok, ip = pcall(cjson.decode, data)
	if not ok then
		return self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "can't decode JSON : " .. ip)
	end
	self.datastore:delete("bans_ip_" .. ip["ip"])
	return self:response(ngx.HTTP_OK, "success", "ip " .. ip["ip"] .. " unbanned")
end

api.global.POST["^/ban$"] = function(self)
	ngx.req.read_body()
	local data = ngx.req.get_body_data()
	if not data then
		local data_file = ngx.req.get_body_file()
		if data_file then
			local file = io.open(data_file)
			data = file:read("*a")
			file:close()
		end
	end
	local ok, ip = pcall(cjson.decode, data)
	if not ok then
		return self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "can't decode JSON : " .. ip)
	end
	self.datastore:set("bans_ip_" .. ip["ip"], "manual", ip["exp"])
	return self:response(ngx.HTTP_OK, "success", "ip " .. ip["ip"] .. " banned")
end

api.global.GET["^/bans$"] = function(self)
	local data = {}
	for i, k in ipairs(self.datastore:keys()) do
		if k:find("^bans_ip_") then
			local ret, reason = self.datastore:get(k)
			if not ret then
				return self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error",
					"can't access " .. k .. " from datastore : " + reason)
			end
			local ok, ttl = self.datastore:ttl(k)
			if not ok then
				return self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error",
					"can't access ttl " .. k .. " from datastore : " .. ttl)
			end
			local ban = { ip = k:sub(9, #k), reason = reason, exp = math.floor(ttl) }
			table.insert(data, ban)
		end
	end
	return self:response(ngx.HTTP_OK, "success", data)
end

function api:is_allowed_ip()
	local data, err = self.datastore:get("api_whitelist_ip")
	if not data then
		return false, "can't access api_allowed_ips in datastore"
	end
	if utils.is_ip_in_networks(ngx.ctx.bw.remote_addr, cjson.decode(data)) then
		return true, "ok"
	end
	return false, "IP is not in API_WHITELIST_IP"
end

function api:do_api_call()
	if self.global[ngx.ctx.bw.request_method] ~= nil then
		for uri, api_fun in pairs(self.global[ngx.ctx.bw.request_method]) do
			if string.match(ngx.ctx.bw.uri, uri) then
				local status, resp = api_fun(self)
				local ret = true
				if status ~= ngx.HTTP_OK then
					ret = false
				end
				if (#resp["msg"] == 0) then
					resp["msg"] = ""
				elseif (type(resp["msg"]) == "table") then
					resp["data"] = resp["msg"]
					resp["msg"] = resp["status"]
				end
				return ret, resp["msg"], status, cjson.encode(resp)
			end
		end
	end
	local list, err = self.datastore:get("plugins")
	if not list then
		local status, resp = self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "can't list loaded plugins : " .. err)
		return false, resp["msg"], ngx.HTTP_INTERNAL_SERVER_ERROR, resp
	end
	list = cjson.decode(list)
	for i, plugin in ipairs(list) do
		if pcall(require, plugin.id .. "/" .. plugin.id) then
			local plugin_lua = require(plugin.id .. "/" .. plugin.id)
			if plugin_lua.api ~= nil then
				local matched, status, resp = plugin_lua.api()
				if matched then
					local ret = true
					if status ~= ngx.HTTP_OK then
						ret = false
					end
					return ret, resp["msg"], status, cjson.encode(resp)
				end
			end
		end
	end
	local resp = {}
	resp["status"] = "error"
	resp["msg"] = "not found"
	return false, "error", ngx.HTTP_NOT_FOUND, cjson.encode(resp)
end

return api
