local base64 = require "base64"
local captcha = require "antibot.captcha"
local cjson = require "cjson"
local class = require "middleclass"
local http = require "resty.http"
local ipmatcher = require "resty.ipmatcher"
local plugin = require "bunkerweb.plugin"
local sha256 = require "resty.sha256"
local str = require "resty.string"
local utils = require "bunkerweb.utils"

local ngx = ngx
local subsystem = ngx.config.subsystem
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local OK = ngx.OK
local ERR = ngx.ERR
local INFO = ngx.INFO
local get_phase = ngx.get_phase
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
local encode = cjson.encode
local get_rdns = utils.get_rdns
local get_asn = utils.get_asn
local get_country = utils.get_country
local regex_match = utils.regex_match
local ipmatcher_new = ipmatcher.new
local upper = string.upper

local template
local render = nil
if subsystem == "http" then
	template = require "resty.template"
	render = template.render
end

local antibot = class("antibot", plugin)
local CACHE_PREFIX = "plugin_antibot_"

local function get_http_client()
	local httpc, err = http_new()
	if not httpc then
		return nil, "can't instantiate http object: " .. err
	end
	return httpc
end

function antibot:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "antibot", ctx)
	self.use_antibot = self.variables["USE_ANTIBOT"] or "no"
	self.country_ignore = {}
	self.country_only = {}
	self.country_ignore_active = false
	self.country_only_active = false
	self.country_filter_enabled = false
	-- Decode lists only once
	if get_phase() ~= "init" and self.use_antibot ~= "no" then
		self.lists = {}
		for _, list in ipairs({ "IGNORE_URI", "IGNORE_IP", "IGNORE_RDNS", "IGNORE_ASN", "IGNORE_USER_AGENT" }) do
			self.lists[list] = {}
			local list_var = self.variables["ANTIBOT_" .. list]
			if list_var then
				for data in list_var:gmatch("%S+") do
					if data ~= "" then
						table.insert(self.lists[list], data)
					end
				end
			end
		end
		local ignore_country = self.variables["ANTIBOT_IGNORE_COUNTRY"]
		if ignore_country and ignore_country ~= "" then
			for code in ignore_country:gmatch("%S+") do
				self.country_ignore[upper(code)] = true
			end
			self.country_ignore_active = next(self.country_ignore) ~= nil
		end
		local only_country = self.variables["ANTIBOT_ONLY_COUNTRY"]
		if only_country and only_country ~= "" then
			for code in only_country:gmatch("%S+") do
				self.country_only[upper(code)] = true
			end
			self.country_only_active = next(self.country_only) ~= nil
		end
		self.country_filter_enabled = self.country_ignore_active or self.country_only_active
	end
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

	local hdr = ngx.header

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
		csp_directives["frame-ancestors"] = "https://www.google.com/"
		csp_directives["connect-src"] = "https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/"
	elseif self.session_data.type == "hcaptcha" then
		csp_directives["script-src"] = csp_directives["script-src"] .. "  https://hcaptcha.com https://*.hcaptcha.com"
		csp_directives["frame-src"] = "https://hcaptcha.com https://*.hcaptcha.com"
		csp_directives["style-src"] = csp_directives["style-src"] .. " https://hcaptcha.com https://*.hcaptcha.com"
		csp_directives["connect-src"] = "https://hcaptcha.com https://*.hcaptcha.com"
	elseif self.session_data.type == "turnstile" then
		csp_directives["script-src"] = csp_directives["script-src"] .. "  https://challenges.cloudflare.com"
		csp_directives["frame-src"] = "https://challenges.cloudflare.com"
		-- Remove the picture-in-picture directive from the Permissions Policy header if it is present
		if hdr["Permissions-Policy"] then
			local policy = hdr["Permissions-Policy"]
			if type(policy) == "table" then
				policy = table.concat(policy, ", ")
			end
			if policy then
				local directives = {}
				for directive in policy:gmatch("[^,]+") do
					if not directive:match("^%s*picture%-in%-picture=%(%)") then
						table.insert(directives, directive:match("^%s*(.-)%s*$"))
					end
				end
				local updated = table.concat(directives, ", ")
				hdr["Permissions-Policy"] = #updated > 0 and updated or nil
			end
		end
	elseif self.session_data.type == "mcaptcha" then
		csp_directives["frame-src"] = self.variables["ANTIBOT_MCAPTCHA_URL"]
	elseif self.session_data.type == "altcha" then
		csp_directives["frame-src"] = self.variables["ANTIBOT_ALTCHA_URL"]
		csp_directives["connect-src"] = self.variables["ANTIBOT_ALTCHA_URL"]
		csp_directives["worker-src"] = self.variables["ANTIBOT_ALTCHA_URL"]
		csp_directives["style-src"] = csp_directives["style-src"] .. " https://cdn.jsdelivr.net " .. self.variables["ANTIBOT_ALTCHA_URL"]
		csp_directives["script-src"] = csp_directives["script-src"] .. " https://cdn.jsdelivr.net " .. self.variables["ANTIBOT_ALTCHA_URL"]
	end
	local csp_content = ""
	for directive, value in pairs(csp_directives) do
		csp_content = csp_content .. directive .. " " .. value .. "; "
	end

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

	-- Check the caches and ignore lists
	local checks = {
		["IP"] = "ip" .. self.ctx.bw.remote_addr,
	}
	if self.country_filter_enabled then
		checks["COUNTRY"] = "country" .. self.ctx.bw.remote_addr
	end
	if self.ctx.bw.http_user_agent then
		checks["UA"] = "ua" .. self.ctx.bw.http_user_agent
	end
	if self.ctx.bw.uri then
		checks["URI"] = "uri" .. self.ctx.bw.uri
	end
	local already_cached = {
		["IP"] = false,
		["URI"] = false,
		["UA"] = false,
	}
	if self.country_filter_enabled then
		already_cached["COUNTRY"] = false
	end
	for k, v in pairs(checks) do
		local ok, cached = self:is_in_cache(v)
		if not ok then
			self.logger:log(ERR, "error while checking cache : " .. cached)
		elseif cached and cached ~= "ko" then
			return self:ret(true, k .. " is in cached antibot ignored (info : " .. cached .. ")")
		end
		if ok and cached then
			already_cached[k] = true
		end
	end

	if self.lists then
		-- Perform checks
		for k, _ in pairs(checks) do
			-- Skip URI ignore checks if current path is the challenge URI
			if not already_cached[k] and not (k == "URI" and self.ctx.bw.uri == self.variables["ANTIBOT_URI"]) then
				local ok, ignored = self:is_ignored(k)
				if ok == nil then
					self.logger:log(ERR, "error while checking if " .. k .. " is ignored : " .. ignored)
				else
					-- luacheck: ignore 421
					local ok, err = self:add_to_cache(self:kind_to_ele(k), ignored)
					if not ok then
						self.logger:log(ERR, "error while adding element to cache : " .. err)
					end
					if ignored ~= "ko" then
						return self:ret(true, k .. " is ignored (info : " .. ignored .. ")")
					end
				end
			end
		end
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
		-- Set all session data at once instead of multiple individual assignments
		local now_time = now()
		local session_update = {
			prepared = true,
			time_resolve = now_time,
			type = self.variables["USE_ANTIBOT"],
			resolved = false,
			original_uri = self.ctx.bw.uri == self.variables["ANTIBOT_URI"] and "/" or self.ctx.bw.request_uri,
		}

		-- Set type-specific fields
		if session_update.type == "cookie" then
			session_update.resolved = true
			session_update.time_valid = now_time
		elseif session_update.type == "javascript" then
			session_update.random = rand(20)
		elseif session_update.type == "captcha" then
			session_update.captcha = rand(6, true, self.variables["ANTIBOT_CAPTCHA_ALPHABET"])
		end

		-- Update session data with all changes at once
		for k, v in pairs(session_update) do
			self.session_data[k] = v
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
		template_vars.recaptcha_classic = self.variables["ANTIBOT_RECAPTCHA_CLASSIC"] == "yes"
	end

	-- hCaptcha case
	if self.session_data.type == "hcaptcha" then
		template_vars.hcaptcha_sitekey = self.variables["ANTIBOT_HCAPTCHA_SITEKEY"]
	end

	-- Turnstile case
	if self.session_data.type == "turnstile" then
		template_vars.turnstile_sitekey = self.variables["ANTIBOT_TURNSTILE_SITEKEY"]
	end

	-- mCaptcha case
	if self.session_data.type == "mcaptcha" then
		template_vars.mcaptcha_sitekey = self.variables["ANTIBOT_MCAPTCHA_SITEKEY"]
		template_vars.mcaptcha_url = self.variables["ANTIBOT_MCAPTCHA_URL"]
	end

	-- ALTCHA case
	if self.session_data.type == "altcha" then
		template_vars.altcha_apikey = self.variables["ANTIBOT_ALTCHA_APIKEY"]
		template_vars.altcha_url = self.variables["ANTIBOT_ALTCHA_URL"]
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
		local httpc, err = get_http_client()
		if not httpc then
			return nil, err, nil, nil
		end
		local res

		if self.variables["ANTIBOT_RECAPTCHA_CLASSIC"] == "yes" then
			local body_params = {
				secret = self.variables["ANTIBOT_RECAPTCHA_SECRET"],
				response = args["token"],
				remoteip = self.ctx.bw.remote_addr,
			}
			local body_parts = {}
			for k, v in pairs(body_params) do
				table.insert(body_parts, k .. "=" .. ngx.escape_uri(v))
			end
			local body = table.concat(body_parts, "&")
			res, err = httpc:request_uri("https://www.google.com/recaptcha/api/siteverify", {
				method = "POST",
				body = body,
				headers = {
					["Content-Type"] = "application/x-www-form-urlencoded",
				},
			})
		else
			local body_params = {
				event = {
					token = args["token"],
					expectedAction = "CAPTCHA",
					siteKey = self.variables["ANTIBOT_RECAPTCHA_SITEKEY"],
					userIpAddress = self.ctx.bw.remote_addr,
				},
			}
			if (self.ctx.bw.http_user_agent or "") ~= "" then
				body_params.event.userAgent = self.ctx.bw.http_user_agent
			end
			if self.variables["ANTIBOT_RECAPTCHA_JA3"] ~= "" then
				body_params.event.ja3 = self.variables["ANTIBOT_RECAPTCHA_JA3"]
			end
			if self.variables["ANTIBOT_RECAPTCHA_JA4"] ~= "" then
				body_params.event.ja4 = self.variables["ANTIBOT_RECAPTCHA_JA4"]
			end
			local body = encode(body_params)
			res, err = httpc:request_uri(
				"https://recaptchaenterprise.googleapis.com/v1/projects/"
					.. self.variables["ANTIBOT_RECAPTCHA_PROJECT_ID"]
					.. "/assessments?key="
					.. self.variables["ANTIBOT_RECAPTCHA_API_KEY"],
				{
					method = "POST",
					body = body,
					headers = {
						["Content-Type"] = "application/json; charset=utf-8",
					},
				}
			)
		end
		httpc:close()
		if not res then
			return nil, "can't send request to reCAPTCHA API : " .. (err or "unknown error"), nil
		end
		local ok, rdata = pcall(decode, res.body)
		if not ok then
			return nil, "error while decoding JSON from reCAPTCHA API : " .. rdata, nil
		end
		local success, score, reason
		if self.session_data.recaptcha_classic then
			success = rdata.success
			score = rdata.score or 0
		else
			success = rdata.tokenProperties and rdata.tokenProperties.valid
			score = rdata.riskAnalysis and rdata.riskAnalysis.score or 0
			reason = rdata.riskAnalysis and rdata.riskAnalysis.invalidReason
		end
		if not success then
			return false, "client failed challenge", nil
		end
		if score < tonumber(self.variables["ANTIBOT_RECAPTCHA_SCORE"]) then
			return false,
				"client failed challenge with score " .. tostring(score) .. (reason and " : " .. reason or ""),
				nil
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
		local httpc, err = get_http_client()
		if not httpc then
			return nil, err, nil, nil
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
		local httpc, err = get_http_client()
		if not httpc then
			return nil, err, nil, nil
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

	-- mCaptcha case
	if self.session_data.type == "mcaptcha" then
		read_body()
		local args, err = get_post_args(1)
		if err == "truncated" or not args or not args["mcaptcha__token"] then
			return nil, "missing challenge arg", nil
		end
		local httpc, err = get_http_client()
		if not httpc then
			return nil, err, nil, nil
		end
		local payload = {
			token = args["mcaptcha__token"],
			key = self.variables["ANTIBOT_MCAPTCHA_SITEKEY"],
			secret = self.variables["ANTIBOT_MCAPTCHA_SECRET"],
		}
		local json_payload = encode(payload)
		local res, err = httpc:request_uri(self.variables["ANTIBOT_MCAPTCHA_URL"] .. "/api/v1/pow/siteverify", {
			method = "POST",
			body = json_payload,
			headers = {
				["Content-Type"] = "application/json",
			},
		})
		httpc:close()
		if not res then
			return nil, "can't send request to mCaptcha API : " .. err, nil
		end
		local ok, mdata = pcall(decode, res.body)
		if not ok then
			return nil, "error while decoding JSON from mCaptcha API : " .. mdata, nil
		end
		if not mdata.valid then
			return false, "client failed challenge", nil
		end
		self.session_data.resolved = true
		self.session_data.time_valid = now()
		self:set_session_data()
		return true, "resolved", self.session_data.original_uri
	end

	-- ALTCHA case
	if self.session_data.type == "altcha" then
		read_body()
		local args, err = get_post_args(1)
		if err == "truncated" or not args or not args["altcha"] then
			return nil, "missing challenge arg", nil
		end
		local httpc, err = get_http_client()
		if not httpc then
			return nil, err, nil, nil
		end
		local payload = {
			payload = args["altcha"]
		}
		local json_payload = encode(payload)
		local res, err = httpc:request_uri(self.variables["ANTIBOT_ALTCHA_URL"] .. "/v1/verify/signature", {
			method = "POST",
			body = json_payload,
			headers = {
				["Content-Type"] = "application/json",
			},
		})
		httpc:close()
		if not res then
			return nil, "can't send request to ALTCHA API : " .. err, nil
		end
		local ok, mdata = pcall(decode, res.body)
		if not ok then
			return nil, "error while decoding JSON from ALTCHA API : " .. mdata, nil
		end
		if not mdata.verified then
			return false, "client failed challenge", nil
		end
		self.session_data.resolved = true
		self.session_data.time_valid = now()
		self:set_session_data()
		return true, "resolved", self.session_data.original_uri
	end

	return nil, "unknown", nil
end

function antibot:kind_to_ele(kind)
	if kind == "IP" then
		return "ip" .. self.ctx.bw.remote_addr
	elseif kind == "UA" then
		return "ua" .. self.ctx.bw.http_user_agent
	elseif kind == "URI" then
		return "uri" .. self.ctx.bw.uri
	elseif kind == "COUNTRY" then
		return "country" .. self.ctx.bw.remote_addr
	end
end

function antibot:is_in_cache(ele)
	local cache_key = CACHE_PREFIX .. self.ctx.bw.server_name .. ele
	local ok, data = self.cachestore_local:get(cache_key)
	if not ok then
		return false, data
	end
	return true, data
end

function antibot:add_to_cache(ele, value)
	local cache_key = CACHE_PREFIX .. self.ctx.bw.server_name .. ele
	local ok, err = self.cachestore_local:set(cache_key, value, 86400)
	if not ok then
		return false, err
	end
	return true
end

function antibot:is_ignored(kind)
	if kind == "IP" then
		return self:is_ignored_ip()
	elseif kind == "URI" then
		return self:is_ignored_uri()
	elseif kind == "UA" then
		return self:is_ignored_ua()
	elseif kind == "COUNTRY" then
		return self:is_ignored_country()
	end
	return false, "unknown kind " .. kind
end

function antibot:is_ignored_country()
	if not self.country_filter_enabled then
		return false, "ko"
	end
	if not self.ctx.bw.ip_is_global then
		if self.country_only_active then
			return true, "country local-ip"
		end
		return false, "ko"
	end
	local country_code, err = get_country(self.ctx.bw.remote_addr)
	if not country_code then
		self.logger:log(ERR, "can't get country for IP " .. self.ctx.bw.remote_addr .. " : " .. err)
		return false, "ko"
	end
	country_code = upper(country_code)
	if self.country_ignore_active and self.country_ignore[country_code] then
		return true, "country " .. country_code
	end
	if self.country_only_active and not self.country_only[country_code] then
		return true, "country " .. country_code
	end
	return false, "ko"
end

function antibot:is_ignored_ip()
	-- Use a pre-compiled IP matcher during initialization
	if not self.ip_matcher then
		local ipm, err = ipmatcher_new(self.lists["IGNORE_IP"])
		if not ipm then
			return nil, err
		end
		self.ip_matcher = ipm
	end

	-- Fast path check
	local match, err = self.ip_matcher:match(self.ctx.bw.remote_addr)
	if err then
		return nil, err
	end
	if match then
		return true, "ip"
	end

	-- Check if rDNS is needed
	local check_rdns = true
	if self.variables["ANTIBOT_RDNS_GLOBAL"] == "yes" and not self.ctx.bw.ip_is_global then
		check_rdns = false
	end
	if check_rdns then
		-- Get rDNS
		-- luacheck: ignore 421
		local rdns_list, err = get_rdns(self.ctx.bw.remote_addr, self.ctx, true)
		if rdns_list then
			-- Check if rDNS is in ignore list
			for _, rdns in ipairs(rdns_list) do
				for _, suffix in ipairs(self.lists["IGNORE_RDNS"]) do
					if rdns:sub(-#suffix) == suffix then
						return true, "rDNS " .. suffix
					end
				end
			end
		else
			self.logger:log(ERR, "error while getting rdns : " .. err)
		end
	end

	-- Check if ASN is in ignore list
	if self.ctx.bw.ip_is_global then
		local asn, err = get_asn(self.ctx.bw.remote_addr)
		if not asn then
			self.logger:log(ngx.ERR, "can't get ASN of IP " .. self.ctx.bw.remote_addr .. " : " .. err)
		else
			for _, ignore_asn in ipairs(self.lists["IGNORE_ASN"]) do
				if ignore_asn == tostring(asn) then
					return true, "ASN " .. ignore_asn
				end
			end
		end
	end

	-- Not ignored
	return false, "ko"
end

function antibot:is_ignored_uri()
	-- Check if URI is in ignore list
	for _, ignore_uri in ipairs(self.lists["IGNORE_URI"]) do
		if regex_match(self.ctx.bw.uri, ignore_uri) then
			return true, "URI " .. ignore_uri
		end
	end
	-- URI is not ignored
	return false, "ko"
end

function antibot:is_ignored_ua()
	-- Check if UA is in ignore list
	for _, ignore_ua in ipairs(self.lists["IGNORE_USER_AGENT"]) do
		if regex_match(self.ctx.bw.http_user_agent, ignore_ua) then
			return true, "UA " .. ignore_ua
		end
	end
	-- UA is not ignored
	return false, "ko"
end

return antibot
