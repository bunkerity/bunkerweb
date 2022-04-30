local M		= {}
local api_list	= {}
local iputils	= require "resty.iputils"
local upload	= require "resty.upload"
local logger	= require "logger"

api_list["^/ping$"] = function ()
	return true
end

api_list["^/reload$"] = function ()
	local jobs = true
	local file = io.open("/etc/nginx/global.env", "r")
	for line in file:lines() do
		if line == "KUBERNETES_MODE=yes" or line == "SWARM_MODE=yes" then
			jobs = false
			break
		end
	end
	file:close()
	if jobs then
		os.execute("/opt/bunkerized-nginx/entrypoint/jobs.sh")
	end
	return os.execute("/usr/sbin/nginx -s reload") == 0
end

api_list["^/stop$"] = function ()
	return os.execute("/usr/sbin/nginx -s quit") == 0
end

api_list["^/stop%-temp$"] = function ()
	return os.execute("/usr/sbin/nginx -c /tmp/nginx-temp.conf -s stop") == 0
end

api_list["^/conf$"] = function ()
	if not M.save_file("/tmp/conf.tar.gz") then
		return false
	end
	return M.extract_file("/tmp/conf.tar.gz", "/etc/nginx/")
end

api_list["^/letsencrypt$"] = function ()
	if not M.save_file("/tmp/letsencrypt.tar.gz") then
		return false
	end
	return M.extract_file("/tmp/letsencrypt.tar.gz", "/etc/letsencrypt/")
end

api_list["^/acme$"] = function ()
	if not M.save_file("/tmp/acme.tar.gz") then
		return false
	end
	return M.extract_file("/tmp/acme.tar.gz", "/acme-challenge")
end

api_list["^/http$"] = function ()
	if not M.save_file("/tmp/http.tar.gz") then
		return false
	end
	return M.extract_file("/tmp/http.tar.gz", "/http-confs/")
end

api_list["^/server$"] = function ()
	if not M.save_file("/tmp/server.tar.gz") then
		return false
	end
	return M.extract_file("/tmp/server.tar.gz", "/server-confs/")
end

api_list["^/modsec$"] = function ()
	if not M.save_file("/tmp/modsec.tar.gz") then
		return false
	end
	return M.extract_file("/tmp/modsec.tar.gz", "/modsec-confs/")
end

api_list["^/modsec%-crs$"] = function ()
	if not M.save_file("/tmp/modsec-crs.tar.gz") then
		return false
	end
	return M.extract_file("/tmp/modsec-crs.tar.gz", "/modsec-crs-confs/")
end

function M.save_file (name)
	local form, err = upload:new(4096)
	if not form then
		logger.log(ngx.ERR, "API", err)
		return false
	end
	form:set_timeout(1000)
	local file = io.open(name, "w")
	while true do
		local typ, res, err = form:read()
		if not typ then
			file:close()
			logger.log(ngx.ERR, "API", "not typ")
			return false
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
	return true
end

function M.extract_file(archive, destination)
	return os.execute("tar xzf " .. archive .. " -C " .. destination) == 0
end

function M.is_api_call (api_uri, api_whitelist_ip)
	local whitelist = iputils.parse_cidrs(api_whitelist_ip)
	if iputils.ip_in_cidrs(ngx.var.remote_addr, whitelist) and ngx.var.request_uri:sub(1, #api_uri) .. "/" == api_uri .. "/" then
		for uri, code in pairs(api_list) do
			if string.match(ngx.var.request_uri:sub(#api_uri + 1), uri) then
				return true
			end
		end
	end
	return false
end

function M.do_api_call (api_uri)
	for uri, code in pairs(api_list) do
		if string.match(ngx.var.request_uri:sub(#api_uri + 1), uri) then
			return code()
		end
	end
end

return M
