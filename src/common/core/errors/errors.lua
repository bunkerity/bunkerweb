local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local ngx = ngx
local rand = utils.rand
local subsystem = ngx.config.subsystem
local tostring = tostring
local tonumber = tonumber

local template
local render = nil
if subsystem == "http" then
	template = require "resty.template"
	render = template.render
end

local errors = class("errors", plugin)

function errors:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "errors", ctx)
	-- Default error texts
	self.default_solution = "Please try again in a few minutes"
	self.default_errors = {
		["301"] = {
			title = "Moved Permanently",
			text = "The requested page has moved to a new url.",
		},
		["302"] = {
			title = "Found",
			text = "The requested page has moved temporarily to a new url.",
		},
		["400"] = {
			title = "Bad Request",
			text = "The server did not understand the request.",
			solution = "Please check the request and try again",
		},
		["401"] = {
			title = "Not Authorized",
			text = "Valid authentication credentials needed for the target resource.",
			solution = "Please check that you're authenticated and try again",
		},
		["403"] = {
			title = "Forbidden",
			text = "Access is forbidden to the requested page.",
		},
		["404"] = {
			title = "Not Found",
			text = "The server cannot find the requested page.",
			solution = "Please check the URL and try again",
		},
		["405"] = {
			title = "Method Not Allowed",
			text = "The method specified in the request is not allowed.",
			solution = "Please check the request method and try again",
		},
		["413"] = {
			title = "Request Entity Too Large",
			text = "The server will not accept the request, because the request entity is too large.",
			solution = "Please reduce the size of the request and try again",
		},
		["429"] = {
			title = "Too Many Requests",
			text = "Too many requests sent in a given amount of time, try again later.",
		},
		["500"] = {
			title = "Internal Server Error",
			text = "The request was not completed. The server met an unexpected condition.",
		},
		["501"] = {
			title = "Not Implemented",
			text = "The request was not completed. The server did not support the functionality required.",
		},
		["502"] = {
			title = "Bad Gateway",
			text = "The request was not completed. The server received an invalid response from the upstream server.",
		},
		["503"] = {
			title = "Service Unavailable",
			text = "The request was not completed. The server is temporarily overloading or down.",
		},
		["504"] = {
			title = "Gateway Timeout",
			text = "The gateway has timed out.",
		},
	}
end

function errors:log()
	self:set_metric("counters", tostring(ngx.status), 1)
	return self:ret(true, "success")
end

function errors:render_template(code)
	local nonce_script = rand(32)
	local nonce_style = rand(32)

	-- Override CSP header
	--luacheck: ignore 631
	ngx.header["Content-Security-Policy"] = "default-src 'none'; script-src 'strict-dynamic' 'nonce-"
		.. nonce_script
		.. "'; style-src 'nonce-"
		.. nonce_style
		--luacheck: ignore 631
		.. "'; frame-ancestors 'none'; base-uri 'none'; img-src data:; font-src data:; require-trusted-types-for 'script';"

	-- Remove server header
	ngx.header["Server"] = nil

	-- Override HSTS header
	local ssl

	if self.ctx.bw and self.ctx.bw.scheme == "https" then
		ssl = true
	else
		ssl = ngx.var.scheme == "https"
	end

	if ssl then
		ngx.header["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
		ngx.header["Content-Security-Policy"] = ngx.header["Content-Security-Policy"] .. " upgrade-insecure-requests;"
	end

	-- Override X-Content-Type-Options header
	ngx.header["X-Content-Type-Options"] = "nosniff"

	-- Override Referrer-Policy header
	ngx.header["Referrer-Policy"] = "no-referrer"

	-- Override Permissions-Policy header
	ngx.header["Permissions-Policy"] =
		"accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), bluetooth=(), browsing-topics=(), camera=(), compute-pressure=(), display-capture=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), gyroscope=(), hid=(), identity-credentials-get=(), idle-detection=(), local-fonts=(), magnetometer=(), microphone=(), midi=(), otp-credentials=(), payment=(), picture-in-picture=(), publickey-credentials-create=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), speaker-selection=(), storage-access=(), usb=(), web-share=(), window-management=(), xr-spatial-tracking=(), interest-cohort=()"

	-- Override Content-Type header
	ngx.header["Content-Type"] = "text/html; charset=utf-8"

	-- Override Cache-Control header
	ngx.header["Cache-Control"] = "no-cache, no-store, must-revalidate"

	local error_type = "unknown"
	local error_code = tonumber(code)
	if error_code >= 500 and error_code <= 599 then
		error_type = "server"
	elseif error_code >= 400 and error_code <= 499 then
		error_type = "client"
	end

	-- Render template
	render("error.html", {
		title = code .. " | " .. self.default_errors[code].title,
		error_title = self.default_errors[code].title,
		error_code = code,
		error_text = self.default_errors[code].text,
		error_type = error_type,
		error_solution = self.default_errors[code].solution or self.default_solution,
		nonce_script = nonce_script,
		nonce_style = nonce_style,
	})
end

return errors
