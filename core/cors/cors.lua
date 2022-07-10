local _M = {}
_M.__index = _M

local utils			= require "utils"
local datastore		= require "datastore"
local logger		= require "logger"

function _M.new()
	local self = setmetatable({}, _M)
	return self, nil
end

function _M:access()
	-- Check if access is needed
	local cors, err = utils.get_variable("USE_CORS")
	if cors == nil then
		return false, err, nil, nil
	end
	if cors == "no" then
		return true, "CORS not activated", nil, nil
	end
	
	-- Check if method is OPTIONS
	if ngx.var.request_method ~= "OPTIONS" then
		return true, "method is not OPTIONS", nil, nil
	end
	
	-- Add headers
	local cors_headers = {
		["CORS_MAX_AGE"] = "Access-Control-Max-Age",
		["CORS_ALLOW_METHODS"] = "Access-Control-Allow-Methods",
		["CORS_ALLOW_HEADERS"] = "Access-Control-Allow-Headers"
	}
	for variable, header in pairs(cors_headers) do
		local value, err = utils.get_variable(variable)
		if value == nil then
			logger.log(ngx.ERR, "CORS", "can't get " .. variable .. " from datastore : " .. err)
		elseif value ~= "" then
			ngx.header[header] = value
		end
	end
	ngx.header["Content-Type"] = "text/html"
	ngx.header["Content-Length"] = "0"
	
	-- Send CORS policy with a 204 (no content) status
	return true, "sent CORS policy", true, ngx.HTTP_NO_CONTENT

end

return _M