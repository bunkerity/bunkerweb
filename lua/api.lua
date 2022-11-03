local datastore	= require "datastore"
local utils	= require "utils"
local cjson	= require "cjson"
local plugins	= require "plugins"
local upload	= require "resty.upload"
local logger	= require "logger"

local api = {global = {GET = {}, POST = {}, PUT = {}, DELETE = {}}}

api.response = function(self, http_status, api_status, msg)
	local resp = {}
	resp["status"] = api_status
	resp["msg"] = msg
	return http_status, resp
end

api.global.GET["^/ping$"] = function(api)
	return api:response(ngx.HTTP_OK, "success", "pong")
end

api.global.POST["^/jobs$"] = function(api)
	-- ngx.req.read_body()
	-- local data = ngx.req.get_body_data()
	-- if not data then
		-- local data_file = ngx.req.get_body_file()
		-- if data_file then
			-- local file = io.open(data_file)
			-- data = file:read("*a")
			-- file:close()
		-- end
	-- end
	-- local ok, env = pcall(cjson.decode, data)
	-- if not ok then
		-- return api:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "can't decode JSON : " .. env)
	-- end
	-- local file = io.open("/opt/bunkerweb/tmp/jobs.env", "w+")
	-- for k, v in pairs(env) do
		-- file:write(k .. "=" .. v .. "\n")
	-- end
	-- file:close()
	local status = os.execute("/opt/bunkerweb/helpers/scheduler-restart.sh")
	if status == 0 then
		return api:response(ngx.HTTP_OK, "success", "jobs executed and scheduler started")
	end
	return api:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "exit status = " .. tostring(status))
end

api.global.POST["^/reload$"] = function(api)
	local status = os.execute("/usr/sbin/nginx -s reload")
	if status == 0 then
		return api:response(ngx.HTTP_OK, "success", "reload successful")
	end
	return api:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "exit status = " .. tostring(status))
end

api.global.POST["^/stop$"] = function(api)
	local status = os.execute("/usr/sbin/nginx -s quit")
	if status == 0 then
		return api:response(ngx.HTTP_OK, "success", "stop successful")
	end
	return api:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "exit status = " .. tostring(status))
end

api.global.POST["^/confs$"] = function(api)
	local tmp = "/opt/bunkerweb/tmp/api_" .. ngx.var.uri:sub(2) .. ".tar.gz"
	local destination = "/opt/bunkerweb/" .. ngx.var.uri:sub(2)
	if ngx.var.uri == "/confs" then
		destination = "/etc/nginx"
	elseif ngx.var.uri == "/data" then
		destination = "/data"
	end
	local form, err = upload:new(4096)
	if not form then
		return api:response(ngx.HTTP_BAD_REQUEST, "error", err)
	end
	form:set_timeout(1000)
	local file = io.open(tmp, "w+")
	while true do
		local typ, res, err = form:read()
		if not typ then
			file:close()
			return api:response(ngx.HTTP_BAD_REQUEST, "error", err)
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
		return api:response(ngx.HTTP_BAD_REQUEST, "error", "can't remove old files")
	end
	status = os.execute("tar xzf " .. tmp .. " -C " .. destination)
	if status ~= 0 then
		return api:response(ngx.HTTP_BAD_REQUEST, "error", "can't extract archive")
	end
	return api:response(ngx.HTTP_OK, "success", "saved data at " .. destination)
end

api.global.POST["^/data$"] = api.global.POST["^/confs$"]

api.global.POST["^/unban$"] = function(api)
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
		return api:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "can't decode JSON : " .. env)
	end
	datastore:delete("bans_ip_" .. ip["ip"])
	return api:response(ngx.HTTP_OK, "success", "ip " .. ip["ip"] .. " unbanned")
end

api.global.POST["^/ban$"] = function(api)
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
		return api:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "can't decode JSON : " .. env)
	end
	datastore:set("bans_ip_" .. ip["ip"], "manual", ip["exp"])
	return api:response(ngx.HTTP_OK, "success", "ip " .. ip["ip"] .. " banned")
end

api.global.GET["^/bans$"] = function(api)
	data = {}
	for i, k in ipairs(datastore:keys()) do
		if k:find("^bans_ip_") then
			local ret, reason = datastore:get(k)
			if not ret then
				return api:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "can't access " .. k .. " from datastore : " + reason)
			end
			local ret, exp = datastore:exp(k)
			if not ret then
				return api:response(ngx.HTTP_INTERNAL_SERVER_ERROR, "error", "can't access exp " .. k .. " from datastore : " + exp)
			end
			table.insert(data, {ip = k:sub(9, #k), reason = reason, exp = exp})
		end
	end
	return api:response(ngx.HTTP_OK, "success", data)
end

api.is_allowed_ip = function(self)
	local data, err = datastore:get("api_whitelist_ip")
	if not data then
		return false, "can't access api_allowed_ips in datastore"
	end
	if utils.is_ip_in_networks(ngx.var.remote_addr, cjson.decode(data).data) then
		return true, "ok"
	end
	return false, "IP is not in API_WHITELIST_IP"
end

api.do_api_call = function(self)
	if self.global[ngx.var.request_method] ~= nil then
		for uri, api_fun in pairs(self.global[ngx.var.request_method]) do
			if string.match(ngx.var.uri, uri) then
				local status, resp = api_fun(self)
				local ret = true
				if status ~= ngx.HTTP_OK then
					ret = false
				end
				return ret, resp["msg"], status, cjson.encode(resp) 
			end
		end
	end
	local list, err = plugins:list()
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
