local _M = {}
_M.__index = _M

local logger = require "logger"
local cjson  = require "cjson"

function _M.new()
	local self = setmetatable({}, _M)
	return self, nil
end

function _M:access()
	if string.sub(ngx.var.uri, 1, string.len("/.well-known/acme-challenge/")) == "/.well-known/acme-challenge/" then
		logger.log(ngx.NOTICE, "LETS-ENCRYPT", "Got a visit from Let's Encrypt, let's whitelist it.")
		return true, "success", true, ngx.exit(ngx.OK)
	end
	return true, "success", false, nil
end

function _M:api()
	if not string.match(ngx.var.uri, "^/lets%-encrypt/challenge$") or
			(ngx.var.request_method ~= "POST" and ngx.var.request_method ~= "DELETE") then
		return false, nil, nil
	end
	local acme_folder = "/var/tmp/bunkerweb/lets-encrypt/.well-known/acme-challenge/"
	ngx.req.read_body()
	local ret, data = pcall(cjson.decode, ngx.req.get_body_data())
	if not ret then
		return true, ngx.HTTP_BAD_REQUEST, { status = "error", msg = "json body decoding failed" }
	end
	os.execute("mkdir -p " .. acme_folder)
	if ngx.var.request_method == "POST" then
		local file, err = io.open(acme_folder .. data.token, "w+")
		if not file then
			return true, ngx.HTTP_INTERNAL_SERVER_ERROR, { status = "error", msg = "can't write validation token : " .. err }
		end
		file:write(data.validation)
		file:close()
		return true, ngx.HTTP_OK, { status = "success", msg = "validation token written" }
	elseif ngx.var.request_method == "DELETE" then
		local ok, err = os.remove(acme_folder .. data.token)
		if not ok then
			return true, ngx.HTTP_INTERNAL_SERVER_ERROR, { status = "error", msg = "can't remove validation token : " .. err }
		end
		return true, ngx.HTTP_OK, { status = "success", msg = "validation token removed" }
	end
	return true, ngx.HTTP_NOT_FOUND, { status = "error", msg = "unknown request" }
end

return _M
