local _M = {}
_M.__index = _M

local utils     = require "utils"
local datastore = require "datastore"
local logger    = require "logger"
local cjson     = require "cjson"

function _M.new()
	local self = setmetatable({}, _M)
	return self, nil
end

function _M:init()
	-- Save default errors into datastore
	local default_errors = {
		["400"] = {
			title = "400 - Bad Request",
			body1 = "Bad Request",
			body2 = "400",
			body3 = "The server did not understand the request."
		},
		["401"] = {
			title = "401 - Not Authorized",
			body1 = "Not Authorized",
			body2 = "401",
			body3 = "Valid authentication credentials needed for the target resource."
		},
		["403"] = {
			title = "403 - Forbidden",
			body1 = "Forbidden",
			body2 = "403",
			body3 = "Access is forbidden to the requested page."
		},
		["404"] = {
			title = "404 - Not Found",
			body1 = "Not Found",
			body2 = "404",
			body3 = "The server cannot find the requested page."
		},
		["405"] = {
			title = "405 - Method Not Allowed",
			body1 = "Method Not Allowed",
			body2 = "405",
			body3 = "The method specified in the request is not allowed."
		},
		["413"] = {
			title = "413 - Request Entity Too Large",
			body1 = "Request Entity Too Large",
			body2 = "413",
			body3 = "The server will not accept the request, because the request entity is too large."
		},
		["429"] = {
			title = "429 - Too Many Requests",
			body1 = "Too Many Requests",
			body2 = "429",
			body3 = "Too many requests sent in a given amount of time, try again later."
		},
		["500"] = {
			title = "500 - Internal Server Error",
			body1 = "Internal Server Error",
			body2 = "500",
			body3 = "The request was not completed. The server met an unexpected condition."
		},
		["501"] = {
			title = "501 - Not Implemented",
			body1 = "Not Implemented",
			body2 = "501",
			body3 = "The request was not completed. The server did not support the functionality required."
		},
		["502"] = {
			title = "502 - Bad Gateway",
			body1 = "Bad Gateway",
			body2 = "502",
			body3 = "The request was not completed. The server received an invalid response from the upstream server."
		},
		["503"] = {
			title = "503 - Service Unavailable",
			body1 = "Service Unavailable",
			body2 = "503",
			body3 = "The request was not completed. The server is temporarily overloading or down."
		},
		["504"] = {
			title = "504 - Gateway Timeout",
			body1 = "Gateway Timeout",
			body2 = "504",
			body3 = "The gateway has timed out."
		}
	}
	local ok, err = datastore:set("plugin_errors_default_errors", cjson.encode(default_errors))
	if not ok then
		return false, "can't save default errors to datastore : " .. err
	end
	-- Save generic template into datastore
	local f, err = io.open("/usr/share/bunkerweb/core/errors/files/error.html", "r")
	if not f then
		return false, "can't open error.html : " .. err
	end
	local template = f:read("*all")
	f:close()
	local ok, err = datastore:set("plugin_errors_template", template)
	if not ok then
		return false, "can't save error.html to datastore : " .. err
	end
	return true, "success"
end

function _M.error_html(code)
	-- Load default errors texts
	local default_errors, err = datastore:get("plugin_errors_default_errors")
	if not default_errors then
		return false, "can't get default errors from datastore : " .. err
	end
	default_errors = cjson.decode(default_errors)
	-- Load template
	local template, err = datastore:get("plugin_errors_template")
	if not template then
		return false, "can't get template from datastore : " .. err
	end
	-- Compute template
	return template:format(default_errors[code].title, default_errors[code].body1, default_errors[code].body2,
		default_errors[code].body3), "success"
end

return _M
