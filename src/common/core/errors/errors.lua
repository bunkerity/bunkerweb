local class			= require "middleclass"
local plugin		= require "bunkerweb.plugin"
local utils     	= require "bunkerweb.utils"
local cachestore	= require "bunkerweb.cachestore"
local cjson			= require "cjson"

local errors		= class("errors", plugin)

function errors:new()
	-- Call parent new
	local ok, err = plugin.new(self, "errors")
	if not ok then
		return false, err
	end
	return true, "success"
end

function errors:init()
	-- Save default errors into datastore
	local default_errors = {
		["400"] = {
			body1 = "Bad Request",
			body2 = "The server did not understand the request."
		},
		["401"] = {
			body1 = "Not Authorized",
			body2 = "Valid authentication credentials needed for the target resource."
		},
		["403"] = {
			body1 = "Forbidden",
			body2 = "Access is forbidden to the requested page."
		},
		["404"] = {
			body1 = "Not Found",
			body2 = "The server cannot find the requested page."
		},
		["405"] = {
			body1 = "Method Not Allowed",
			body2 = "The method specified in the request is not allowed."
		},
		["413"] = {
			body1 = "Request Entity Too Large",
			body2 = "The server will not accept the request, because the request entity is too large."
		},
		["429"] = {
			body1 = "Too Many Requests",
			body2 = "Too many requests sent in a given amount of time, try again later."
		},
		["500"] = {
			body1 = "Internal Server Error",
			body2 = "The request was not completed. The server met an unexpected condition."
		},
		["501"] = {
			body1 = "Not Implemented",
			body2 = "The request was not completed. The server did not support the functionality required."
		},
		["502"] = {
			body1 = "Bad Gateway",
			body2 = "The request was not completed. The server received an invalid response from the upstream server."
		},
		["503"] = {
			body1 = "Service Unavailable",
			body2 = "The request was not completed. The server is temporarily overloading or down."
		},
		["504"] = {
			body1 = "Gateway Timeout",
			body2 = "The gateway has timed out."
		}
	}
	local ok, err = datastore:set("plugin_errors_default_errors", cjson.encode(default_errors))
	if not ok then
		return self:ret(false, "can't save default errors to datastore : " .. err)
	end
	-- Save generic template into datastore
	local f, err = io.open("/usr/share/bunkerweb/core/errors/files/error.html", "r")
	if not f then
		return self:ret(false, "can't open error.html : " .. err)
	end
	local template = f:read("*all")
	f:close()
	local ok, err = datastore:set("plugin_errors_template", template)
	if not ok then
		return false, "can't save error.html to datastore : " .. err
	end
	return true, "success"
end

function errors:error_html(code)
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
	return template:format(code .. " - " .. default_errors[code].body1, code, default_errors[code].body1,
		default_errors[code].body2), "success"
end

return errors