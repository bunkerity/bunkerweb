local class		= require "middleclass"
local plugin	= require "bunkerweb.plugin"
local utils     = require "bunkerweb.utils"
local datastore = require "bunkerweb.datastore"
local logger    = require "bunkerweb.logger"
local cjson     = require "cjson"
local captcha   = require "antibot.captcha"
local base64    = require "base64"
local sha256    = require "resty.sha256"
local str       = require "resty.string"
local http      = require "resty.http"

local antibot	= class("antibot", plugin)

function antibot:new()
	-- Call parent new
	local ok, err = plugin.new(self, "antibot")
	if not ok then
		return false, err
	end
	-- Check if init is needed
	if ngx.get_phase() == "init" then
		local init_needed, err = utils.has_not_variable("USE_ANTIBOT", "no")
		if init_needed == nil then
			return false, err
		end
		self.init_needed = init_needed
	end
	return true, "success"
end

function antibot:init()
	if self.init_needed then
		-- Load templates
		local templates = {}
		for i, template in ipairs({ "javascript", "captcha", "recaptcha", "hcaptcha" }) do
			local f, err = io.open("/usr/share/bunkerweb/core/antibot/files/" .. template .. ".html")
			if not f then
				return self:ret(false, "error while loading " .. template .. ".html : " .. err)
			end
			templates[template] = f:read("*all")
			f:close()
		end
		local ok, err = datastore:set("plugin_antibot_templates", cjson.encode(templates))
		if not ok then
			return self:ret(false, "can't save templates to datastore : " .. err)
		end
	end
	return self:ret(true, "success")
end

function antibot:access()
	-- Check if access is needed
	if self.variables["USE_ANTIBOT"] == "no" then
		return self:ret(true, "antibot not activated")
	end

	-- Prepare challenge
	local ok, err = self:prepare_challenge(antibot, challenge_uri)
	if not ok then
		return self:ret(false, "can't prepare challenge : " .. err, ngx.HTTP_INTERNAL_SERVER_ERROR)
	end

	-- Don't go further if client resolved the challenge
	local resolved, err, original_uri = self:challenge_resolved(antibot)
	if resolved == nil then
		return self:ret(false, "can't check if challenge is resolved : " .. err)
	end
	if resolved then
		if ngx.var.uri == challenge_uri then
			return self:ret(true, "client already resolved the challenge", nil, original_uri)
		end
		return self:ret(true, "client already resolved the challenge")
	end

	-- Redirect to challenge page
	if ngx.var.uri ~= challenge_uri then
		return self:ret(true, "redirecting client to the challenge uri", nil, challenge_uri)
	end

	-- Display challenge needed
	if ngx.var.request_method == "GET" then
		ngx.ctx.antibot_display_content = true
		return self:ret(true, "displaying challenge to client", ngx.HTTP_OK)
	end

	-- Check challenge
	if ngx.var.request_method == "POST" then
		local ok, err, redirect = self:check_challenge(antibot)
		if ok == nil then
			return self:ret(false, "check challenge error : " .. err, ngx.HTTP_INTERNAL_SERVER_ERROR)
		end
		if redirect then
			return self:ret(true, "check challenge redirect : " .. redirect, nil, redirect)
		end
		ngx.ctx.antibot_display_content = true
		return self:ret(true, "displaying challenge to client", ngx.HTTP_OK)
	end

	-- Method is suspicious, let's deny the request
	return self:ret(true, "unsupported HTTP method for antibot", utils.get_deny_status())
end

function antibot:content()
	-- Check if access is needed
	local antibot, err = utils.get_variable("USE_ANTIBOT")
	if antibot == nil then
		return self:ret(false, err)
	end
	if antibot == "no" then
		return self:ret(true, "antibot not activated")
	end
	-- Check if display content is needed
	if not ngx.ctx.antibot_display_content then
		return self:ret(true, "display content not needed")
	end
	-- Display content
	local ok, err = self:display_challenge(antibot)
	if not ok then
		return self:ret(false, "display challenge error : " .. err)
	end
	return self:ret(true, "content displayed")
end

function antibot:challenge_resolved()
	local session, err, exists = utils.get_session()
	if err then
		return false, "session error : " .. err
	end
	local raw_data = get_session("antibot")
	if not raw_data then
		return false, "session is set but no antibot data", nil
	end
	local data = cjson.decode(raw_data)
	if data.resolved and self.variables["USE_ANTIBOT"] == data.antibot then
		return true, "challenge resolved", data.original_uri
	end
	return false, "challenge not resolved", data.original_uri
end

function antibot:prepare_challenge()
	local session, err, exists = utils.get_session()
	if err then
		return false, "session error : " .. err
	end
	local set_needed = false
	local data = nil
	if exists then
		local raw_data = get_session("antibot")
		if raw_data then
			data = cjson.decode(raw_data)
		end
	end
	if not data or current_data.antibot ~= self.variables["USE_ANTIBOT"] then
		data = {
			type = self.variables["USE_ANTIBOT"],
			resolved = self.variables["USE_ANTIBOT"] == "cookie",
			original_uri = ngx.var.request_uri
		}
		if ngx.var.original_uri == challenge_uri then
			data.original_uri = "/"
		end
		set_needed = true
	end
	if not data.resolved then
		if self.variables["USE_ANTIBOT"] == "javascript" then
			data.random = utils.rand(20)
			set_needed = true
		elseif self.variables["USE_ANTIBOT"] == "captcha" then
			local chall_captcha = captcha.new()
			chall_captcha:font("/usr/share/bunkerweb/core/antibot/files/font.ttf")
			chall_captcha:generate()
			data.image = base64.encode(chall_captcha:jpegStr(70))
			data.text = chall_captcha:getStr()
			set_needed = true
		end
	end
	if set_needed then
		utils.set_session("antibot", cjson.encode(data))
	end
	return true, "prepared"
end

function antibot:display_challenge(challenge_uri)
	-- Open session
	local session, err, exists = utils.get_session()
	if err then
		return false, "can't open session : " .. err
	end

	-- Get data
	local raw_data = get_session("antibot")
	if not raw_data then
		return false, "session is set but no data"
	end
	local data = cjson.decode(raw_data)

	-- Check if session type is equal to antibot type
	if self.variables["USE_ANTIBOT"] ~= data.type then
		return false, "session type is different from antibot type"
	end

	-- Load HTML templates
	local str_templates, err = datastore:get("plugin_antibot_templates")
	if not str_templates then
		return false, "can't get templates from datastore : " .. err
	end
	local templates = cjson.decode(str_templates)

	local html = ""

	-- Javascript case
	if self.variables["USE_ANTIBOT"] == "javascript" then
		html = templates.javascript:format(self.variables["ANTIBOT_URI"], data.random)
	end

	-- Captcha case
	if self.variables["USE_ANTIBOT"] == "captcha" then
		html = templates.captcha:format(self.variables["ANTIBOT_URI"], data.image)
	end

	-- reCAPTCHA case
	if self.variables["USE_ANTIBOT"] == "recaptcha" then
		html = templates.recaptcha:format(self.variables["ANTIBOT_RECAPTCHA_SITEKEY"], self.variables["ANTIBOT_URI"], self.variables["ANTIBOT_RECAPTCHA_SITEKEY"])
	end

	-- hCaptcha case
	if self.variables["USE_ANTIBOT"] == "hcaptcha" then
		html = templates.hcaptcha:format(self.variables["ANTIBOT_URI"], self.variables["ANTIBOT_HCAPTCHA_SITEKEY"])
	end

	-- Send content
	ngx.header["Content-Type"] = "text/html"
	ngx.say(html)

	return true, "displayed challenge"
end

function antibot:check_challenge()
	-- Open session
	local session, err, exists = utils.get_session()
	if err then
		return nil, "can't open session : " .. err, nil
	end

	-- Get data
	local raw_data = get_session("antibot")
	if not raw_data then
		return false, "session is set but no data", nil
	end
	local data = cjson.decode(raw_data)

	-- Check if session type is equal to antibot type
	if elf.variables["USE_ANTIBOT"] ~= data.type then
		return nil, "session type is different from antibot type", nil
	end

	local resolved = false
	local err = ""
	local redirect = nil

	-- Javascript case
	if self.variables["USE_ANTIBOT"] == "javascript" then
		ngx.req.read_body()
		local args, err = ngx.req.get_post_args(1)
		if err == "truncated" or not args or not args["challenge"] then
			return false, "missing challenge arg", nil
		end
		local hash = sha256:new()
		hash:update(data.random .. args["challenge"])
		local digest = hash:final()
		resolved = str.to_hex(digest):find("^0000") ~= nil
		if not resolved then
			return false, "wrong value", nil
		end
		data.resolved = true
		utils.set_session("antibot", cjson.encode(data))
		return true, "resolved", data.original_uri
	end

	-- Captcha case
	if self.variables["USE_ANTIBOT"] == "captcha" then
		ngx.req.read_body()
		local args, err = ngx.req.get_post_args(1)
		if err == "truncated" or not args or not args["captcha"] then
			return false, "missing challenge arg", nil
		end
		if data.text ~= args["captcha"] then
			return false, "wrong value", nil
		end
		data.resolved = true
		utils.set_session("antibot", cjson.encode(data))
		return true, "resolved", data.original_uri
	end

	-- reCAPTCHA case
	if self.variables["USE_ANTIBOT"] == "recaptcha" then
		ngx.req.read_body()
		local args, err = ngx.req.get_post_args(1)
		if err == "truncated" or not args or not args["token"] then
			return false, "missing challenge arg", nil
		end
		local httpc, err = http.new()
		if not httpc then
			return false, "can't instantiate http object : " .. err, nil, nil
		end
		local res, err = httpc:request_uri("https://www.google.com/recaptcha/api/siteverify", {
			method = "POST",
			body = "secret=" .. self.variables["ANTIBOT_RECAPTCHA_SECRET"] .. "&response=" .. args["token"] .. "&remoteip=" .. ngx.var.remote_addr,
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
		data.resolved = true
		utils.set_session("antibot", cjson.encode(data))
		return true, "resolved", data.original_uri
	end

	-- hCaptcha case
	if self.variables["USE_ANTIBOT"] == "hcaptcha" then
		ngx.req.read_body()
		local args, err = ngx.req.get_post_args(1)
		if err == "truncated" or not args or not args["token"] then
			return false, "missing challenge arg", nil
		end
		local httpc, err = http.new()
		if not httpc then
			return false, "can't instantiate http object : " .. err, nil, nil
		end
		local res, err = httpc:request_uri("https://hcaptcha.com/siteverify", {
			method = "POST",
			body = "secret=" .. self.variables["ANTIBOT_HCAPTCHA_SECRET"] .. "&response=" .. args["token"] .. "&remoteip=" .. ngx.var.remote_addr,
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
		data.resolved = true
		utils.set_session("antibot", cjson.encode(data))
		return true, "resolved", data.original_uri
	end

	return nil, "unknown", nil
end

return _M
