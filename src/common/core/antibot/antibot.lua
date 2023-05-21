local class     = require "middleclass"
local plugin    = require "bunkerweb.plugin"
local utils     = require "bunkerweb.utils"
local datastore = require "bunkerweb.datastore"
local cjson     = require "cjson"
local captcha   = require "antibot.captcha"
local base64    = require "base64"
local sha256    = require "resty.sha256"
local str       = require "resty.string"
local http      = require "resty.http"
local template  = nil
if ngx.shared.datastore then
	template = require "resty.template"
end

local antibot = class("antibot", plugin)

function antibot:initialize()
	-- Call parent initialize
	plugin.initialize(self, "antibot")
end

function antibot:access()
	-- Check if access is needed
	if self.variables["USE_ANTIBOT"] == "no" then
		return self:ret(true, "antibot not activated")
	end

	-- Get session data
	local session, err = utils.get_session("antibot")
	if not session then
		return self:ret(false, "can't get session : " .. err, ngx.HTTP_INTERNAL_SERVER_ERROR)
	end
	self.session = session
	self.session_data = utils.get_session_data(self.session)
	-- Check if session is valid
	self:check_session()

	-- Don't go further if client resolved the challenge
	if self.session_data.resolved then
		if ngx.ctx.bw.uri == self.variables["ANTIBOT_URI"] then
			return self:ret(true, "client already resolved the challenge", nil, self.session_data.original_uri)
		end
		return self:ret(true, "client already resolved the challenge")
	end

	-- Prepare challenge if needed
	self:prepare_challenge()
	local ok, err = self:set_session_data()
	if not ok then
		return self:ret(false, "can't save session : " .. err, ngx.HTTP_INTERNAL_SERVER_ERROR)
	end

	-- Redirect to challenge page
	if ngx.ctx.bw.uri ~= self.variables["ANTIBOT_URI"] then
		return self:ret(true, "redirecting client to the challenge uri", nil, self.variables["ANTIBOT_URI"])
	end

	-- Cookie case : don't display challenge page
	if self.session_data.resolved then
		return self:ret(true, "client already resolved the challenge", nil, self.session_data.original_uri)
	end

	-- Display challenge needed
	if ngx.ctx.bw.request_method == "GET" then
		ngx.ctx.bw.antibot_display_content = true
		return self:ret(true, "displaying challenge to client", ngx.OK)
	end

	-- Check challenge
	if ngx.ctx.bw.request_method == "POST" then
		local ok, err, redirect = self:check_challenge()
		local set_ok, set_err = self:set_session_data()
		if not set_ok then
			return self:ret(false, "can't save session : " .. set_err, ngx.HTTP_INTERNAL_SERVER_ERROR)
		end
		if ok == nil then
			return self:ret(false, "check challenge error : " .. err, ngx.HTTP_INTERNAL_SERVER_ERROR)
		elseif not ok then
			self.logger:log(ngx.WARN, "client failed challenge : " .. err)
		end
		if redirect then
			return self:ret(true, "check challenge redirect : " .. redirect, nil, redirect)
		end
		self:prepare_challenge()
		local ok, err = self:set_session_data()
		if not ok then
			return self:ret(false, "can't save session : " .. err, ngx.HTTP_INTERNAL_SERVER_ERROR)
		end
		ngx.ctx.bw.antibot_display_content = true
		return self:ret(true, "displaying challenge to client", ngx.OK)
	end

	-- Method is suspicious, let's deny the request
	return self:ret(true, "unsupported HTTP method for antibot", utils.get_deny_status())
end

function antibot:content()
	-- Check if content is needed
	if self.variables["USE_ANTIBOT"] == "no" then
		return self:ret(true, "antibot not activated")
	end

	-- Check if display content is needed
	if not ngx.ctx.bw.antibot_display_content then
		return self:ret(true, "display content not needed", nil, "/")
	end

	-- Get session data
	local session, err = utils.get_session("antibot")
	if not session then
		return self:ret(false, "can't get session : " .. err, ngx.HTTP_INTERNAL_SERVER_ERROR)
	end
	self.session = session
	self.session_data = utils.get_session_data(self.session)

	-- Direct access without session
	if not self.session_data.prepared then
		return self:ret(true, "no session", nil, "/")
	end

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
		self.session_updated = true
		return
	end
	-- Check if still valid
	local time = ngx.now()
	local resolved = self.session_data.resolved
	if resolved and (time_valid > time or time - time_valid > tonumber(self.variables["ANTIBOT_TIME_VALID"])) then
		self.session_data = {}
		self.session_updated = true
		return
	end
	-- Check if new prepare is needed
	if not resolved and (time_resolve > time or time - time_resolve > tonumber(self.variables["ANTIBOT_TIME_RESOLVE"])) then
		self.session_data = {}
		self.session_updated = true
		return
	end
end

function antibot:set_session_data()
	if self.session_updated then
		local ok, err = utils.set_session_data(self.session, self.session_data)
		if not ok then
			return false, err
		end
		self.session_updated = false
		return true, "updated"
	end
	return true, "no update"
end

function antibot:prepare_challenge()
	if not self.session_data.prepared then
		self.session_updated = true
		self.session_data.prepared = true
		self.session_data.time_resolve = ngx.now()
		self.session_data.type = self.variables["USE_ANTIBOT"]
		self.session_data.resolved = false
		self.session_data.original_uri = ngx.ctx.bw.request_uri
		if ngx.ctx.bw.uri == self.variables["ANTIBOT_URI"] then
			self.session_data.original_uri = "/"
		end
		if self.variables["USE_ANTIBOT"] == "cookie" then
			self.session_data.resolved = true
			self.session_data.time_valid = ngx.now()
		elseif self.variables["USE_ANTIBOT"] == "javascript" then
			self.session_data.random = utils.rand(20)
		elseif self.variables["USE_ANTIBOT"] == "captcha" then
			self.session_data.captcha = utils.rand(6, true)
		end
	end
end

function antibot:display_challenge()
	-- Check if prepared
	if not self.session_data.prepared then
		return false, "challenge not prepared"
	end

	-- Common variables for templates
	local template_vars = {
		antibot_uri = self.variables["ANTIBOT_URI"]
	}

	-- Javascript case
	if self.variables["USE_ANTIBOT"] == "javascript" then
		template_vars.random = self.session_data.random
	end

	-- Captcha case
	if self.variables["USE_ANTIBOT"] == "captcha" then
		local chall_captcha = captcha.new()
		chall_captcha:font("/usr/share/bunkerweb/core/antibot/files/font.ttf")
		chall_captcha:string(self.session_data.captcha)
		chall_captcha:generate()
		template_vars.captcha = base64.encode(chall_captcha:jpegStr(70))
	end

	-- reCAPTCHA case
	if self.variables["USE_ANTIBOT"] == "recaptcha" then
		template_vars.recaptcha_sitekey = self.variables["ANTIBOT_RECAPTCHA_SITEKEY"]
	end

	-- hCaptcha case
	if self.variables["USE_ANTIBOT"] == "hcaptcha" then
		template_vars.hcaptcha_sitekey = self.variables["ANTIBOT_HCAPTCHA_SITEKEY"]
	end

	-- Render content
	template.render(self.variables["USE_ANTIBOT"] .. ".html", template_vars)

	return true, "displayed challenge"
end

function antibot:check_challenge()
	-- Check if prepared
	if not self.session_data.prepared then
		return nil, "challenge not prepared"
	end

	local resolved = false
	local err = ""
	local redirect = nil

	self.session_data.prepared = false
	self.session_updated = true

	-- Javascript case
	if self.variables["USE_ANTIBOT"] == "javascript" then
		ngx.req.read_body()
		local args, err = ngx.req.get_post_args(1)
		if err == "truncated" or not args or not args["challenge"] then
			return nil, "missing challenge arg"
		end
		local hash = sha256:new()
		hash:update(self.session_data.random .. args["challenge"])
		local digest = hash:final()
		resolved = str.to_hex(digest):find("^0000") ~= nil
		if not resolved then
			return false, "wrong value"
		end
		self.session_data.resolved = true
		self.session_data.time_valid = ngx.now()
		return true, "resolved", self.session_data.original_uri
	end

	-- Captcha case
	if self.variables["USE_ANTIBOT"] == "captcha" then
		ngx.req.read_body()
		local args, err = ngx.req.get_post_args(1)
		if err == "truncated" or not args or not args["captcha"] then
			return nil, "missing challenge arg", nil
		end
		if self.session_data.captcha ~= args["captcha"] then
			return false, "wrong value", nil
		end
		self.session_data.resolved = true
		self.session_data.time_valid = ngx.now()
		return true, "resolved", self.session_data.original_uri
	end

	-- reCAPTCHA case
	if self.variables["USE_ANTIBOT"] == "recaptcha" then
		ngx.req.read_body()
		local args, err = ngx.req.get_post_args(1)
		if err == "truncated" or not args or not args["token"] then
			return nil, "missing challenge arg", nil
		end
		local httpc, err = http.new()
		if not httpc then
			return nil, "can't instantiate http object : " .. err, nil, nil
		end
		local res, err = httpc:request_uri("https://www.google.com/recaptcha/api/siteverify", {
			method = "POST",
			body = "secret=" ..
			self.variables["ANTIBOT_RECAPTCHA_SECRET"] ..
			"&response=" .. args["token"] .. "&remoteip=" .. ngx.ctx.bw.remote_addr,
			headers = {
				["Content-Type"] = "application/x-www-form-urlencoded"
			}
		})
		httpc:close()
		if not res then
			return nil, "can't send request to reCAPTCHA API : " .. err, nil
		end
		local ok, rdata = pcall(cjson.decode, res.body)
		if not ok then
			return nil, "error while decoding JSON from reCAPTCHA API : " .. rdata, nil
		end
		if not rdata.success or rdata.score < tonumber(self.variables["ANTIBOT_RECAPTCHA_SCORE"]) then
			return false, "client failed challenge with score " .. tostring(rdata.score), nil
		end
		self.session_data.resolved = true
		self.session_data.time_valid = ngx.now()
		return true, "resolved", self.session_data.original_uri
	end

	-- hCaptcha case
	if self.variables["USE_ANTIBOT"] == "hcaptcha" then
		ngx.req.read_body()
		local args, err = ngx.req.get_post_args(1)
		if err == "truncated" or not args or not args["token"] then
			return nil, "missing challenge arg", nil
		end
		local httpc, err = http.new()
		if not httpc then
			return nil, "can't instantiate http object : " .. err, nil, nil
		end
		local res, err = httpc:request_uri("https://hcaptcha.com/siteverify", {
			method = "POST",
			body = "secret=" ..
			self.variables["ANTIBOT_HCAPTCHA_SECRET"] ..
			"&response=" .. args["token"] .. "&remoteip=" .. ngx.ctx.bw.remote_addr,
			headers = {
				["Content-Type"] = "application/x-www-form-urlencoded"
			}
		})
		httpc:close()
		if not res then
			return nil, "can't send request to hCaptcha API : " .. err, nil
		end
		local ok, hdata = pcall(cjson.decode, res.body)
		if not ok then
			return nil, "error while decoding JSON from hCaptcha API : " .. data, nil
		end
		if not hdata.success then
			return false, "client failed challenge", nil
		end
		self.session_data.resolved = true
		self.session_data.time_valid = ngx.now()
		return true, "resolved", self.session_data.original_uri
	end

	return nil, "unknown", nil
end

return antibot
