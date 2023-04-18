local class			= require "middleclass"
local plugin		= require "bunkerweb.plugin"
local utils     	= require "bunkerweb.utils"
local cjson			= require "cjson"
local template		= require "resty.template"

local errors		= class("errors", plugin)

function errors:initialize()
	-- Call parent initialize
	plugin.initialize(self, "errors")
	-- Default error texts
	self.default_errors = {
		["400"] = {
			title = "Bad Request",
			text = "The server did not understand the request."
		},
		["401"] = {
			title = "Not Authorized",
			text = "Valid authentication credentials needed for the target resource."
		},
		["403"] = {
			title = "Forbidden",
			text = "Access is forbidden to the requested page."
		},
		["404"] = {
			title = "Not Found",
			text = "The server cannot find the requested page."
		},
		["405"] = {
			title = "Method Not Allowed",
			text = "The method specified in the request is not allowed."
		},
		["413"] = {
			title = "Request Entity Too Large",
			text = "The server will not accept the request, because the request entity is too large."
		},
		["429"] = {
			title = "Too Many Requests",
			text = "Too many requests sent in a given amount of time, try again later."
		},
		["500"] = {
			title = "Internal Server Error",
			text = "The request was not completed. The server met an unexpected condition."
		},
		["501"] = {
			title = "Not Implemented",
			text = "The request was not completed. The server did not support the functionality required."
		},
		["502"] = {
			title = "Bad Gateway",
			text = "The request was not completed. The server received an invalid response from the upstream server."
		},
		["503"] = {
			title = "Service Unavailable",
			text = "The request was not completed. The server is temporarily overloading or down."
		},
		["504"] = {
			title = "Gateway Timeout",
			text = "The gateway has timed out."
		}
	}
end

function errors:render_template(code)
	-- Render template
	template.render("error.html", {
		title = code .. " - " .. self.default_errors[code].title,
		error_title = self.default_errors[code].title,
		error_code = code,
		error_text = self.default_errors[code].text
	})
end

return errors