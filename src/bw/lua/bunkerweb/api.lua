
local class     = require "middleclass"
local datastore	= require "bunkerweb.datastore"
local utils		= require "bunkerweb.utils"
local cjson		= require "cjson"
local upload	= require "resty.upload"

local api = class("api")

api.global = { GET = {}, POST = {}, PUT = {}, DELETE = {} }

function api:initialize()
	self.datastore = datastore:new()
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
	local status = os.execute("nginx -s reload")
	if status == 0 then
		return self:response(ngx.HTTP_OK, "success", "reload successful")
	end
	return self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "exit status = " .. tostring(status))
end

api.global.POST["^/stop$"] = function(self)
	local status = os.execute("nginx -s quit")
	if status == 0 then
		return self:response(ngx.HTTP_OK, "success", "stop successful")
	end
	return self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "exit status = " .. tostring(status))
end

api.global.POST["^/confs$"] = function(self)
	local tmp = "/var/tmp/bunkerweb/api_" .. ngx.var.uri:sub(2) .. ".tar.gz"
	local destination = "/usr/share/bunkerweb/" .. ngx.var.uri:sub(2)
	if ngx.var.uri == "/confs" then
		destination = "/etc/nginx"
	elseif ngx.var.uri == "/data" then
		destination = "/data"
	elseif ngx.var.uri == "/cache" then
		destination = "/data/cache"
	elseif ngx.var.uri == "/custom_configs" then
		destination = "/data/configs"
	elseif ngx.var.uri == "/plugins" then
		destination = "/data/plugins"
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
	local status = os.execute("rm -rf " .. destination .. "/*")
	if status ~= 0 then
		return self:response(ngx.HTTP_BAD_REQUEST, "error", "can't remove old files")
	end
	status = os.execute("tar xzf " .. tmp .. " -C " .. destination)
	if status ~= 0 then
		return self:response(ngx.HTTP_BAD_REQUEST, "error", "can't extract archive")
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
		return self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "can't decode JSON : " .. env)
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
		return self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "can't decode JSON : " .. env)
	end
	self.datastore:set("bans_ip_" .. ip["ip"], "manual", ip["exp"])
	return self:response(ngx.HTTP_OK, "success", "ip " .. ip["ip"] .. " banned")
end

api.global.GET["^/bans$"] = function(self)
	local data = {}
	for i, k in ipairs(self.datastore:keys()) do
		if k:find("^bans_ip_") then
			local ret, reason = datastore:get(k)
			if not ret then
				return self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error",
					"can't access " .. k .. " from datastore : " + reason)
			end
			local ret, exp = self.datastore:exp(k)
			if not ret then
				return self:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error",
					"can't access exp " .. k .. " from datastore : " + exp)
			end
			local ban = { ip = k:sub(9, #k), reason = reason, exp = exp }
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
	if utils.is_ip_in_networks(ngx.var.remote_addr, cjson.decode(data)) then
		return true, "ok"
	end
	return false, "IP is not in API_WHITELIST_IP"
end

function api:do_api_call()
	if self.global[ngx.var.request_method] ~= nil then
		for uri, api_fun in pairs(self.global[ngx.var.request_method]) do
			if string.match(ngx.var.uri, uri) then
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
