local _M        = {}
_M.__index      = _M

local utils     = require "utils"
local datastore = require "datastore"
local logger    = require "logger"
local cjson     = require "cjson"
local session   = require "resty.session"
local captcha   = require "antibot.captcha"
local base64    = require "base64"
local sha256    = require "resty.sha256"
local str       = require "resty.string"
local http      = require "resty.http"

function _M.new()
	local self = setmetatable({}, _M)
	return self, nil
end

function _M:init()
	-- Check if init is needed
	local init_needed, err = utils.has_not_variable("USE_ANTIBOT", "no")
	if init_needed == nil then
		return false, err
	end
	if not init_needed then
		return true, "no service uses Antibot, skipping init"
	end
	-- Load templates
	local templates = {}
	for i, template in ipairs({ "javascript", "captcha", "recaptcha", "hcaptcha" }) do
		local f, err = io.open("/usr/share/bunkerweb/core/antibot/files/" .. template .. ".html")
		if not f then
			return false, "error while loading " .. template .. ".html : " .. err
		end
		templates[template] = f:read("*all")
		f:close()
	end
	local ok, err = datastore:set("plugin_antibot_templates", cjson.encode(templates))
	if not ok then
		return false, "can't save templates to datastore : " .. err
	end
	return true, "success"
end

function _M:access()
	-- Check if access is needed
	local antibot, err = utils.get_variable("USE_ANTIBOT")
	if antibot == nil then
		return false, err, nil, nil
	end
	if antibot == "no" then
		return true, "Antibot not activated", nil, nil
	end

	-- Get challenge URI
	local challenge_uri, err = utils.get_variable("ANTIBOT_URI")
	if not challenge_uri then
		return false, "can't get Antibot URI from datastore : " .. err, nil, nil
	end

	-- Don't go further if client resolved the challenge
	local resolved, err, original_uri = self:challenge_resolved(antibot)
	if resolved == nil then
		return false, "can't check if challenge is resolved : " .. err, nil, nil
	end
	if resolved then
		if ngx.var.uri == challenge_uri then
			return true, "client already resolved the challenge", true, ngx.redirect(original_uri)
		end
		return true, "client already resolved the challenge", nil, nil
	end

	-- Redirect to challenge page
	if ngx.var.uri ~= challenge_uri then
		local ok, err = self:prepare_challenge(antibot, challenge_uri)
		if not ok then
			return false, "can't prepare challenge : " .. err, true, ngx.HTTP_INTERNAL_SERVER_ERROR
		end
		return true, "redirecting client to the challenge uri", true, ngx.redirect(challenge_uri)
	end

	-- Display challenge
	if ngx.var.request_method == "GET" then
		local ok, err = self:display_challenge(antibot, challenge_uri)
		if not ok then
			if err == "can't open session" then
				local ok, err = self:prepare_challenge(antibot, challenge_uri)
				if not ok then
					return false, "can't prepare challenge : " .. err, true, ngx.HTTP_INTERNAL_SERVER_ERROR
				end
				return true, "redirecting client to the challenge uri", true, ngx.redirect(challenge_uri)
			end
			return false, "display challenge error : " .. err, true, ngx.HTTP_INTERNAL_SERVER_ERROR
		end
		return true, "displaying challenge to client", true, ngx.HTTP_OK
	end

	-- Check challenge
	if ngx.var.request_method == "POST" then
		local ok, err, redirect = self:check_challenge(antibot)
		if ok == nil then
			if err == "can't open session" then
				local ok, err = self:prepare_challenge(antibot, challenge_uri)
				if not ok then
					return false, "can't prepare challenge : " .. err, true, ngx.HTTP_INTERNAL_SERVER_ERROR
				end
				return true, "redirecting client to the challenge uri", true, ngx.redirect(challenge_uri)
			end
			return false, "check challenge error : " .. err, true, ngx.HTTP_INTERNAL_SERVER_ERROR
		end
		if redirect then
			return true, "check challenge redirect : " .. redirect, true, ngx.redirect(redirect)
		end
		local ok, err = self:display_challenge(antibot)
		if not ok then
			if err == "can't open session" then
				local ok, err = self:prepare_challenge(antibot, challenge_uri)
				if not ok then
					return false, "can't prepare challenge : " .. err, true, ngx.HTTP_INTERNAL_SERVER_ERROR
				end
				return true, "redirecting client to the challenge uri", true, ngx.redirect(challenge_uri)
			end
			return false, "display challenge error : " .. err, true, ngx.HTTP_INTERNAL_SERVER_ERROR
		end
		return true, "displaying challenge to client", true, ngx.HTTP_OK
	end

	-- Method is suspicious, let's deny the request
	return true, "unsupported HTTP method for Antibot", true, utils.get_deny_status()
end

function _M:challenge_resolved(antibot)
	local chall_session, present, reason = session.open()
	if present and chall_session.data.resolved and chall_session.data.type == antibot then
		return true, "challenge " .. antibot .. " resolved", chall_session.data.original_uri
	end
	return false, "challenge " .. antibot .. " not resolved", nil
end

function _M:prepare_challenge(antibot, challenge_uri)
	local chall_session, present, reason = session.open()
	if not present then
		local chall_session, present, reason = chall_session:start()
		if not chall_session then
			return false, "can't start session", nil
		end
		chall_session.data.type = antibot
		chall_session.data.resolved = false
		if ngx.var.request_uri == challenge_uri then
			chall_session.data.original_uri = "/"
		else
			chall_session.data.original_uri = ngx.var.request_uri
		end
		if antibot == "cookie" then
			chall_session.data.resolved = true
		end
		local saved, err = chall_session:save()
		if not saved then
			return false, "error while saving session : " .. err
		end
	end
	return true, antibot .. " challenge prepared"
end

function _M:display_challenge(antibot, challenge_uri)
	-- Open session
	local chall_session, present, reason = session.open()
	if not present then
		return false, "can't open session"
	end

	-- Check if session type is equal to antibot type
	if antibot ~= chall_session.data.type then
		return false, "session type is different from antibot type"
	end

	-- Compute challenges
	if antibot == "javascript" then
		chall_session:start()
		chall_session.data.random = utils.rand(20)
		chall_session:save()
	elseif antibot == "captcha" then
		chall_session:start()
		local chall_captcha = captcha.new()
		chall_captcha:font("/usr/share/bunkerweb/core/antibot/files/font.ttf")
		chall_captcha:generate()
		chall_session.data.image = base64.encode(chall_captcha:jpegStr(70))
		chall_session.data.text = chall_captcha:getStr()
		chall_session:save()
	end

	-- Load HTML templates
	local str_templates, err = datastore:get("plugin_antibot_templates")
	if not str_templates then
		return false, "can't get templates from datastore : " .. err
	end
	local templates = cjson.decode(str_templates)

	local html = ""

	-- Javascript case
	if antibot == "javascript" then
		html = templates.javascript:format(challenge_uri, chall_session.data.random)
	end

	-- Captcha case
	if antibot == "captcha" then
		html = templates.captcha:format(challenge_uri, chall_session.data.image)
	end

	-- reCAPTCHA case
	if antibot == "recaptcha" then
		local recaptcha_sitekey, err = utils.get_variable("ANTIBOT_RECAPTCHA_SITEKEY")
		if not recaptcha_sitekey then
			return false, "can't get reCAPTCHA sitekey variable : " .. err
		end
		html = templates.recaptcha:format(recaptcha_sitekey, challenge_uri, recaptcha_sitekey)
	end

	-- hCaptcha case
	if antibot == "hcaptcha" then
		local hcaptcha_sitekey, err = utils.get_variable("ANTIBOT_HCAPTCHA_SITEKEY")
		if not hcaptcha_sitekey then
			return false, "can't get hCaptcha sitekey variable : " .. err
		end
		html = templates.hcaptcha:format(challenge_uri, hcaptcha_sitekey)
	end

	ngx.header["Content-Type"] = "text/html"
	ngx.say(html)

	return true, "displayed challenge"
end

function _M:check_challenge(antibot)
	-- Open session
	local chall_session, present, reason = session.open()
	if not present then
		return nil, "can't open session", nil
	end

	-- Check if session type is equal to antibot type
	if antibot ~= chall_session.data.type then
		return nil, "session type is different from antibot type", nil
	end

	local resolved = false
	local err = ""
	local redirect = nil

	-- Javascript case
	if antibot == "javascript" then
		ngx.req.read_body()
		local args, err = ngx.req.get_post_args(1)
		if err == "truncated" or not args or not args["challenge"] then
			return false, "missing challenge arg", nil
		end
		local hash = sha256:new()
		hash:update(chall_session.data.random .. args["challenge"])
		local digest = hash:final()
		resolved = str.to_hex(digest):find("^0000") ~= nil
		if not resolved then
			return false, "wrong value", nil
		end
		chall_session:start()
		chall_session.data.resolved = true
		chall_session:save()
		return true, "resolved", chall_session.data.original_uri
	end

	-- Captcha case
	if antibot == "captcha" then
		ngx.req.read_body()
		local args, err = ngx.req.get_post_args(1)
		if err == "truncated" or not args or not args["captcha"] then
			return false, "missing challenge arg", nil
		end
		if chall_session.data.text ~= args["captcha"] then
			return false, "wrong value", nil
		end
		chall_session:start()
		chall_session.data.resolved = true
		chall_session:save()
		return true, "resolved", chall_session.data.original_uri
	end

	-- reCAPTCHA case
	if antibot == "recaptcha" then
		ngx.req.read_body()
		local args, err = ngx.req.get_post_args(1)
		if err == "truncated" or not args or not args["token"] then
			return false, "missing challenge arg", nil
		end
		local recaptcha_secret, err = utils.get_variable("ANTIBOT_RECAPTCHA_SECRET")
		if not recaptcha_secret then
			return nil, "can't get reCAPTCHA secret variable : " .. err, nil
		end
		local httpc, err = http.new()
		if not httpc then
			return false, "can't instantiate http object : " .. err, nil, nil
		end
		local res, err = httpc:request_uri("https://www.google.com/recaptcha/api/siteverify", {
			method = "POST",
			body = "secret=" .. recaptcha_secret .. "&response=" .. args["token"] .. "&remoteip=" .. ngx.var.remote_addr,
			headers = {
				["Content-Type"] = "application/x-www-form-urlencoded"
			}
		})
		httpc:close()
		if not res then
			return nil, "can't send request to reCAPTCHA API : " .. err, nil
		end
		local ok, data = pcall(cjson.decode, res.body)
		if not ok then
			return nil, "error while decoding JSON from reCAPTCHA API : " .. data, nil
		end
		local recaptcha_score, err = utils.get_variable("ANTIBOT_RECAPTCHA_SCORE")
		if not recaptcha_score then
			return nil, "can't get reCAPTCHA score variable : " .. err, nil
		end
		if not data.success or data.score < tonumber(recaptcha_score) then
			return false, "client failed challenge with score " .. tostring(data.score), nil
		end
		chall_session:start()
		chall_session.data.resolved = true
		chall_session:save()
		return true, "resolved", chall_session.data.original_uri
	end

	-- hCaptcha case
	if antibot == "hcaptcha" then
		ngx.req.read_body()
		local args, err = ngx.req.get_post_args(1)
		if err == "truncated" or not args or not args["token"] then
			return false, "missing challenge arg", nil
		end
		local hcaptcha_secret, err = utils.get_variable("ANTIBOT_HCAPTCHA_SECRET")
		if not hcaptcha_secret then
			return nil, "can't get hCaptcha secret variable : " .. err, nil
		end
		local httpc, err = http.new()
		if not httpc then
			return false, "can't instantiate http object : " .. err, nil, nil
		end
		local res, err = httpc:request_uri("https://hcaptcha.com/siteverify", {
			method = "POST",
			body = "secret=" .. hcaptcha_secret .. "&response=" .. args["token"] .. "&remoteip=" .. ngx.var.remote_addr,
			headers = {
				["Content-Type"] = "application/x-www-form-urlencoded"
			}
		})
		httpc:close()
		if not res then
			return nil, "can't send request to hCaptcha API : " .. err, nil
		end
		local ok, data = pcall(cjson.decode, res.body)
		if not ok then
			return nil, "error while decoding JSON from hCaptcha API : " .. data, nil
		end
		if not data.success then
			return false, "client failed challenge", nil
		end
		chall_session:start()
		chall_session.data.resolved = true
		chall_session:save()
		return true, "resolved", chall_session.data.original_uri
	end

	return nil, "unknown", nil
end

return _M
