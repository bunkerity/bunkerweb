local M		= {}
local http	= require "resty.http"
local cjson	= require "cjson"
local logger	= require "logger"

function M.send(method, url, data)
	local httpc, err = http.new()
	if not httpc then
		logger.log(ngx.ERR, "REMOTE API", "Can't instantiate HTTP object : " .. err)
		return false, nil, nil
	end
	local res, err = httpc:request_uri(ngx.shared.remote_api:get("server") .. url, {
		method = method,
		body = cjson.encode(data),
		headers = {
			["Content-Type"] = "application/json",
			["User-Agent"] = "bunkerized-nginx/" .. data["version"]
		}
	})
	if not res then
		logger.log(ngx.ERR, "REMOTE API", "Can't send HTTP request : " .. err)
		return false, nil, nil
	end
	if res.status ~= 200 then
		logger.log(ngx.WARN, "REMOTE API", "Received status " .. res.status .. " from API : " .. res.body)
	end
	return true, res.status, cjson.decode(res.body)["data"]
end

function M.gen_data(use_id, data)
	local all_data = {}
	if use_id then
		all_data["id"] = ngx.shared.remote_api:get("id")
	end
	all_data["version"] = ngx.shared.remote_api:get("version")
	for k, v in pairs(data) do
		all_data[k] = v
	end
	return all_data
end

function M.register()
	local request = {}
	local res, status, data = M.send("POST", "/register", M.gen_data(false, request))
	if res and status == 200 then
		return true, data
	end
	return false, data
end

function M.ping()
	local request = {}
	local res, status, data = M.send("GET", "/ping", M.gen_data(true, request))
	if res and status == 200 then
		return true, data
	end
	return false, data
end

function M.ip(ip, reason)
	-- TODO : check if IP is global
	local request = {
		["ip"] = ip,
		["reason"] = reason
	}
	local res, status, data = M.send("POST", "/ip", M.gen_data(true, request))
	if res and status == 200 then
		return true, data
	end
	return false, data
end

function M.db()
	local request = {}
	local res, status, data = M.send("GET", "/db", M.gen_data(true, request))
	if res and status == 200 then
		return true, data
	end
	return false, data
end

return M
