local base64 = require "base64"
local captcha = require "antibot.captcha"
local cjson = require "cjson"
local class = require "middleclass"
local http = require "resty.http"
local plugin = require "bunkerweb.plugin"
local sha256 = require "resty.sha256"
local str = require "resty.string"
local utils = require "bunkerweb.utils"

local ngx = ngx
local subsystem = ngx.config.subsystem
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local OK = ngx.OK
local INFO = ngx.INFO
local tonumber = tonumber
local tostring = tostring
local get_session = utils.get_session
local get_deny_status = utils.get_deny_status
local rand = utils.rand
local now = ngx.now
local captcha_new = captcha.new
local base64_encode = base64.encode
local to_hex = str.to_hex
local http_new = http.new
local decode = cjson.decode

local template
local render = nil
if subsystem == "http" then
	template = require "resty.template"
	render = template.render
end

local antibot = class("antibot", plugin)

function antibot:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "antibot", ctx)
end

function antibot:header()
	-- Check if access is needed
	if self.variables["USE_ANTIBOT"] == "no" then
		return self:ret(true, "antibot not activated")
	end
	-- Check if antibot uri
	if self.ctx.bw.uri ~= self.variables["ANTIBOT_URI"] then
		return self:ret(true, "not antibot uri")
	end

	-- Get session data
	self.session_data = self.ctx.bw.antibot_session_data
	if not self.session_data then
		return self:ret(false, "can't get session data", HTTP_INTERNAL_SERVER_ERROR)
	end

	-- Don't go further if client resolved the challenge
	if self.session_data.resolved then
		return self:ret(true, "client already resolved the challenge", nil, self.session_data.original_uri)
	end

	-- Override CSP header
	local csp_directives = {
		["default-src"] = "'none'",
		["base-uri"] = "'none'",
		["img-src"] = "'self' data:",
		["font-src"] = "'self' data:",
		["script-src"] = "http: https: 'unsafe-inline' 'strict-dynamic' 'nonce-"
			.. self.ctx.bw.antibot_nonce_script
			.. "'",
		["style-src"] = "'self' 'nonce-" .. self.ctx.bw.antibot_nonce_style .. "'",
		["frame-ancestors"] = "'none'",
		["require-trusted-types-for"] = "'script'",
	}
	if self.session_data.type == "recaptcha" then
		csp_directives["script-src"] = csp_directives["script-src"]
			.. "  https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/"
		csp_directives["frame-src"] = "https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/"
	elseif self.session_data.type == "hcaptcha" then
		csp_directives["script-src"] = csp_directives["script-src"] .. "  https://hcaptcha.com https://*.hcaptcha.com"
		csp_directives["frame-src"] = "https://hcaptcha.com https://*.hcaptcha.com"
		csp_directives["style-src"] = csp_directives["style-src"] .. " https://hcaptcha.com https://*.hcaptcha.com"
		csp_directives["connect-src"] = "https://hcaptcha.com https://*.hcaptcha.com"
	elseif self.session_data.type == "turnstile" then
		csp_directives["script-src"] = csp_directives["script-src"] .. "  https://challenges.cloudflare.com"
		csp_directives["frame-src"] = "https://challenges.cloudflare.com"
	end
	local csp_content = ""
	for directive, value in pairs(csp_directives) do
		csp_content = csp_content .. directive .. " " .. value .. "; "
	end

	local hdr = ngx.header

	hdr["Content-Security-Policy"] = csp_content

	local ssl = (self.ctx.bw and self.ctx.bw.scheme == "https") or ngx.var.scheme == "https"
	if ssl then
		hdr["Content-Security-Policy"] = hdr["Content-Security-Policy"] .. " upgrade-insecure-requests;"
	end

	return self:ret(true, "successfully overridden CSP header")
end

function antibot:access()
	-- Check if access is needed
	if self.variables["USE_ANTIBOT"] == "no" then
		return self:ret(true, "antibot not activated")
	end

	-- Get session data
	local session, err = get_session(self.ctx)
	if not session then
		return self:ret(false, "can't get session : " .. err)
	end
	self.session = session
	self.session_data = session:get("antibot") or {}
	self.ctx.bw.antibot_session_data = self.session_data

	-- Check if session is valid
	local msg = self:check_session()
	self.logger:log(INFO, "check_session returned : " .. msg)

	-- Don't go further if client resolved the challenge
	if self.session_data.resolved then
		if self.ctx.bw.uri == self.variables["ANTIBOT_URI"] then
			return self:ret(true, "client already resolved the challenge", nil, self.session_data.original_uri)
		end
		return self:ret(true, "client already resolved the challenge")
	end

	-- Prepare challenge if needed
	self:prepare_challenge()

	-- Redirect to challenge page
	if self.ctx.bw.uri ~= self.variables["ANTIBOT_URI"] then
		return self:ret(true, "redirecting client to the challenge uri", nil, self.variables["ANTIBOT_URI"])
	end

	-- Cookie case : don't display challenge page
	if self.session_data.resolved then
		return self:ret(true, "client already resolved the challenge", nil, self.session_data.original_uri)
	end

	-- Display challenge needed
	if self.ctx.bw.request_method == "GET" then
		self.ctx.bw.antibot_display_content = true
		return self:ret(true, "displaying challenge to client", ngx.OK)
	end

	-- Check challenge
	if self.ctx.bw.request_method == "POST" then
		-- luacheck: ignore 421
		local ok, err, redirect = self:check_challenge()
		if ok == nil then
			return self:ret(false, "check challenge error : " .. err, HTTP_INTERNAL_SERVER_ERROR)
		elseif not ok then
			self:set_metric("counters", "failed_challenges", 1)
			self.logger:log(ngx.WARN, "client failed challenge : " .. err)
		end
		if redirect then
			return self:ret(true, "check challenge redirect : " .. redirect, nil, redirect)
		end
		self:prepare_challenge()
		self.ctx.bw.antibot_display_content = true
		return self:ret(true, "displaying challenge to client", OK)
	end

	-- Method is suspicious, let's deny the request
	local data = {}
	data["id"] = "suspicious-method"
	data["method"] = self.ctx.bw.request_method
	return self:ret(true, "unsupported HTTP method for antibot", get_deny_status(), nil, data)
end

function antibot:content()
	-- Check if content is needed
	if self.variables["USE_ANTIBOT"] == "no" then
		return self:ret(true, "antibot not activated")
	end

	-- Check if display content is needed
	if not self.ctx.bw.antibot_display_content then
		return self:ret(true, "display content not needed", nil, "/")
	end

	-- Get session data
	self.session_data = self.ctx.bw.antibot_session_data
	if not self.session_data then
		return self:ret(false, "missing session data", HTTP_INTERNAL_SERVER_ERROR)
	end

	-- Direct access without session
	if not self.session_data.prepared then
		return self:ret(true, "no session", nil, "/")
	end

	self.ctx.bw.antibot_nonce_script = rand(32)
	self.ctx.bw.antibot_nonce_style = rand(32)

	-- Display content
	local ok, err = self:display_challenge()
	if not ok then
		return self:ret(false, "display challenge error : " .. err)
	end
	return self:ret(true, "content displayed")
end

function antibot:check_session()
	-- Get values
	local time_resolve = self.session_data.time_resolve
	local time_valid = self.session_data.time_valid
	-- Not resolved and not prepared
	if not time_resolve and not time_valid then
		self.session_data = {}
		self:set_session_data()
		return "not prepared"
	end
	-- Check if still valid
	local time = now()
	local resolved = self.session_data.resolved
	if resolved and (time_valid > time or time - time_valid > tonumber(self.variables["ANTIBOT_TIME_VALID"])) then
		self.session_data = {}
		self:set_session_data()
		return "need new resolve"
	end
	-- Check if new prepare is needed
	if
		not resolved and (time_resolve > time or time - time_resolve > tonumber(self.variables["ANTIBOT_TIME_RESOLVE"]))
	then
		self.session_data = {}
		self:set_session_data()
		return "need new prepare"
	end
	return "valid"
end

function antibot:set_session_data()
	self.session:set("antibot", self.session_data)
	self.ctx.bw.antibot_session_data = self.session_data
	self.ctx.bw.sessions_updated = true
end

function antibot:prepare_challenge()
	if not self.session_data.prepared then
		self.session_data.prepared = true
		self.session_data.time_resolve = ngx.now()
		self.session_data.type = self.variables["USE_ANTIBOT"]
		self.session_data.resolved = false
		self.session_data.original_uri = self.ctx.bw.request_uri
		if self.ctx.bw.uri == self.variables["ANTIBOT_URI"] then
			self.session_data.original_uri = "/"
		end
		if self.session_data.type == "cookie" then
			self.session_data.resolved = true
			self.session_data.time_valid = now()
		elseif self.session_data.type == "javascript" then
			self.session_data.random = rand(20)
		elseif self.session_data.type == "captcha" then
			self.session_data.captcha = rand(6, true)
		end
		self:set_session_data()
	end
end

function antibot:display_challenge()
	-- Check if prepared
	if not self.session_data.prepared then
		return false, "challenge not prepared"
	end

	-- Common variables for templates
	local template_vars = {
		antibot_uri = self.variables["ANTIBOT_URI"],
		nonce_script = self.ctx.bw.antibot_nonce_script,
		nonce_style = self.ctx.bw.antibot_nonce_style,
	}

	-- Javascript case
	if self.session_data.type == "javascript" then
		template_vars.random = self.session_data.random
	end

	-- Captcha case
	if self.session_data.type == "captcha" then
		local chall_captcha = captcha_new()
		chall_captcha:font("/usr/share/bunkerweb/core/antibot/files/font.ttf")
		chall_captcha:string(self.session_data.captcha)
		chall_captcha:generate()
		template_vars.captcha = base64_encode(chall_captcha:jpegStr(70))
	end

	-- reCAPTCHA case
	if self.session_data.type == "recaptcha" then
		template_vars.recaptcha_sitekey = self.variables["ANTIBOT_RECAPTCHA_SITEKEY"]
	end

	-- hCaptcha case
	if self.session_data.type == "hcaptcha" then
		template_vars.hcaptcha_sitekey = self.variables["ANTIBOT_HCAPTCHA_SITEKEY"]
	end

	-- Turnstile case
	if self.session_data.type == "turnstile" then
		template_vars.turnstile_sitekey = self.variables["ANTIBOT_TURNSTILE_SITEKEY"]
	end

	-- Render content
	render(self.session_data.type .. ".html", template_vars)

	return true, "displayed challenge"
end

function antibot:check_challenge()
	-- Check if prepared
	if not self.session_data.prepared then
		return nil, "challenge not prepared"
	end

	local resolved
	local ngx_req = ngx.req
	local read_body = ngx_req.read_body
	local get_post_args = ngx_req.get_post_args
	self.session_data.prepared = false
	self.session_updated = true

	-- Javascript case
	if self.session_data.type == "javascript" then
		read_body()
		local args, err = get_post_args(1)
		if err == "truncated" or not args or not args["challenge"] then
			return nil, "missing challenge arg"
		end
		local hash = sha256:new()
		hash:update(self.session_data.random .. args["challenge"])
		local digest = hash:final()
		resolved = to_hex(digest):find("^0000") ~= nil
		if not resolved then
			return false, "wrong value"
		end
		self.session_data.resolved = true
		self.session_data.time_valid = now()
		self:set_session_data()
		return true, "resolved", self.session_data.original_uri
	end

	-- Captcha case
	if self.session_data.type == "captcha" then
		read_body()
		local args, err = get_post_args(1)
		if err == "truncated" or not args or not args["captcha"] then
			return nil, "missing challenge arg", nil
		end
		if self.session_data.captcha ~= args["captcha"] then
			return false, "wrong value, expected " .. self.session_data.captcha, nil
		end
		self.session_data.resolved = true
		self.session_data.time_valid = now()
		self:set_session_data()
		return true, "resolved", self.session_data.original_uri
	end

	-- reCAPTCHA case
	if self.session_data.type == "recaptcha" then
		read_body()
		local args, err = get_post_args(1)
		if err == "truncated" or not args or not args["token"] then
			return nil, "missing challenge arg", nil
		end
		local httpc, err = http_new()
		if not httpc then
			return nil, "can't instantiate http object : " .. err, nil, nil
		end
		local res, err = httpc:request_uri("https://www.google.com/recaptcha/api/siteverify", {
			method = "POST",
			body = "secret="
				.. self.variables["ANTIBOT_RECAPTCHA_SECRET"]
				.. "&response="
				.. args["token"]
				.. "&remoteip="
				.. self.ctx.bw.remote_addr,
			headers = {
				["Content-Type"] = "application/x-www-form-urlencoded",
			},
		})
		httpc:close()
		if not res then
			return nil, "can't send request to reCAPTCHA API : " .. err, nil
		end
		local ok, rdata = pcall(decode, res.body)
		if not ok then
			return nil, "error while decoding JSON from reCAPTCHA API : " .. rdata, nil
		end
		if not rdata.success then
			return false, "client failed challenge", nil
		end
		if rdata.score and rdata.score < tonumber(self.variables["ANTIBOT_RECAPTCHA_SCORE"]) then
			return false, "client failed challenge with score " .. tostring(rdata.score), nil
		end
		self.session_data.resolved = true
		self.session_data.time_valid = now()
		self:set_session_data()
		return true, "resolved", self.session_data.original_uri
	end

	-- hCaptcha case
	if self.session_data.type == "hcaptcha" then
		read_body()
		local args, err = get_post_args(1)
		if err == "truncated" or not args or not args["token"] then
			return nil, "missing challenge arg", nil
		end
		local httpc, err = http_new()
		if not httpc then
			return nil, "can't instantiate http object : " .. err, nil, nil
		end
		local res, err = httpc:request_uri("https://hcaptcha.com/siteverify", {
			method = "POST",
			body = "secret="
				.. self.variables["ANTIBOT_HCAPTCHA_SECRET"]
				.. "&response="
				.. args["token"]
				.. "&remoteip="
				.. self.ctx.bw.remote_addr,
			headers = {
				["Content-Type"] = "application/x-www-form-urlencoded",
			},
		})
		httpc:close()
		if not res then
			return nil, "can't send request to hCaptcha API : " .. err, nil
		end
		local ok, hdata = pcall(decode, res.body)
		if not ok then
			return nil, "error while decoding JSON from hCaptcha API : " .. hdata, nil
		end
		if not hdata.success then
			return false, "client failed challenge", nil
		end
		self.session_data.resolved = true
		self.session_data.time_valid = now()
		self:set_session_data()
		return true, "resolved", self.session_data.original_uri
	end

	-- Turnstile case
	if self.session_data.type == "turnstile" then
		read_body()
		local args, err = get_post_args(1)
		if err == "truncated" or not args or not args["token"] then
			return nil, "missing challenge arg", nil
		end
		local httpc, err = http_new()
		if not httpc then
			return nil, "can't instantiate http object : " .. err, nil, nil
		end
		local res, err = httpc:request_uri("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
			method = "POST",
			body = "secret="
				.. self.variables["ANTIBOT_TURNSTILE_SECRET"]
				.. "&response="
				.. args["token"]
				.. "&remoteip="
				.. self.ctx.bw.remote_addr,
			headers = {
				["Content-Type"] = "application/x-www-form-urlencoded",
			},
		})
		httpc:close()
		if not res then
			return nil, "can't send request to Turnstile API : " .. err, nil
		end
		local ok, tdata = pcall(decode, res.body)
		if not ok then
			return nil, "error while decoding JSON from Turnstile API : " .. tdata, nil
		end
		if not tdata.success then
			return false, "client failed challenge", nil
		end
		self.session_data.resolved = true
		self.session_data.time_valid = now()
		self:set_session_data()
		return true, "resolved", self.session_data.original_uri
	end

	return nil, "unknown", nil
end

return antibot
