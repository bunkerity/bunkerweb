local acme = require "bunkerweb.acme"
local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local mtls = class("mtls", plugin)

local ngx = ngx
local ERR = ngx.ERR
local WARN = ngx.WARN
local HTTP_MOVED_PERMANENTLY = ngx.HTTP_MOVED_PERMANENTLY
local re_match = ngx.re.match
local get_phase = ngx.get_phase
local get_deny_status = utils.get_deny_status
local get_multiple_variables = utils.get_multiple_variables
local get_security_mode = utils.get_security_mode
local get_variable = utils.get_variable
local has_variable = utils.has_variable
local is_challenge_uri = acme.is_challenge_uri
local is_http_challenge = acme.is_http_challenge
local match = string.match
local sort = table.sort
local sub = string.sub
local tostring = tostring

-- ACME HTTP-01: one token-shaped segment (base64url, RFC 8555 section 8.3), the same shape the
-- passthrough handlers of letsencrypt and the PRO ACME plugin accept.
local ACME_TOKEN_URI = "^/%.well%-known/acme%-challenge/[A-Za-z0-9_%-]+$"

local function trim(value)
	if value == nil then
		return ""
	end
	return (value:gsub("^%s+", ""):gsub("%s+$", ""))
end

function mtls:initialize(ctx)
	plugin.initialize(self, "mtls", ctx)

	-- Only the request path needs the precomputed per-path rules.
	if get_phase() == "init" or not self.ctx then
		return
	end

	if self.variables["USE_MTLS"] ~= "yes" then
		return
	end

	local configs, err = self.internalstore:get("plugin_mtls_configs", true)
	if not configs then
		self.logger:log(ERR, err)
		return
	end

	-- Per-server rules replace the global ones (multisite scope is independent).
	local server_name = self.ctx.bw.server_name
	self.urls = (server_name and configs[server_name]) or configs.global or {}
end

function mtls:is_needed()
	if self.is_loading then
		return false
	end

	if self.is_request and (self.ctx.bw.server_name ~= "_") then
		return self.variables["USE_MTLS"] == "yes"
	end

	local enabled, err = has_variable("USE_MTLS", "yes")
	if enabled == nil then
		self.logger:log(ERR, "can't check USE_MTLS variable : " .. err)
	end
	return enabled
end

function mtls:init()
	local variables, err = get_multiple_variables({ "USE_MTLS", "MTLS_URL", "MTLS_VERIFY_CLIENT" })
	if not variables then
		return self:ret(false, err)
	end

	local configs = {}
	local total = 0
	for scope, vars in pairs(variables) do
		if vars["USE_MTLS"] == "yes" then
			local urls = {}
			for key, value in pairs(vars) do
				if key:find("^MTLS_URL_?%d*$") then
					local pattern = trim(value)
					if pattern ~= "" then
						table.insert(urls, pattern)
					end
				end
			end
			if #urls > 0 then
				-- Per-path enforcement needs the handshake to complete for
				-- non-matching paths; with MTLS_VERIFY_CLIENT=on NGINX rejects
				-- certificate-less clients before this plugin ever runs.
				if vars["MTLS_VERIFY_CLIENT"] == "on" then
					self.logger:log(
						WARN,
						"scope "
							.. scope
							.. " sets MTLS_URL but MTLS_VERIFY_CLIENT=on; NGINX rejects certificate-less clients during"
							.. " the handshake before per-path enforcement runs. Set MTLS_VERIFY_CLIENT=optional to enable"
							.. " per-path mTLS."
					)
				end
				configs[scope] = urls
				total = total + #urls
			end
		end
	end

	local ok, store_err = self.internalstore:set("plugin_mtls_configs", configs, nil, true)
	if not ok then
		return self:ret(false, store_err)
	end

	if total == 0 then
		return self:ret(true, "no per-path mTLS rules configured")
	end
	return self:ret(true, "loaded " .. tostring(total) .. " per-path mTLS rule(s)")
end

-- A Host header that cannot be pasted after "https://" without changing the authority (userinfo,
-- path, whitespace, control characters) is treated as no Host at all.
local function is_safe_host(host)
	return type(host) == "string" and #host > 0 and #host <= 255 and match(host, "^[%w%.%-_:%[%]]+$") ~= nil
end

-- Tries every rule on the URI. Returns true/false, or nil plus the offending pattern and the error.
-- ngx.re.match (not utils.regex_match) tells a non-match apart from a compile error.
local function match_urls(urls, uri)
	for _, pattern in ipairs(urls) do
		local m, re_err = re_match(uri, pattern, "o")
		if re_err then
			return nil, pattern, re_err
		end
		if m then
			return true
		end
	end
	return false
end

-- In SECURITY_MODE=detect the framework logs a denial and then stops the access chain, and a redirect is
-- still honoured. A detect-mode verdict is therefore only logged here: the request goes on and the plugins
-- after mtls still run. The handshake-level ssl_verify_client is not affected by the mode.
function mtls:verdict(msg, status, redirect, data)
	if get_security_mode(self.ctx) == "detect" then
		self.logger:log(WARN, "detected " .. (redirect and "redirect" or "deny") .. " access from mtls : " .. msg)
		return self:ret(true, "detect mode, not enforced : " .. msg)
	end
	return self:ret(true, msg, status, redirect, data)
end

-- A plain-HTTP ACME HTTP-01 request that a solver owns. mtls runs before the plugins that answer it, so
-- it must not deny a request those would serve: the local solver (a token present on this instance), and
-- the two passthrough switches (LETS_ENCRYPT_PASSTHROUGH, and ACME_PASSTHROUGH of the PRO ACME plugin,
-- read by name: absent means not enabled), which reach the backend by design. The PRO local solver owns
-- its path in a location of its own where no access code runs. GET and HEAD only, checked on every
-- branch because is_http_challenge looks at the token file and not at the method.
function mtls:is_acme_challenge()
	local bw = self.ctx.bw
	if bw.scheme ~= "http" or (bw.request_method ~= "GET" and bw.request_method ~= "HEAD") then
		return false
	end
	if not is_challenge_uri(self.ctx) or match(bw.uri, ACME_TOKEN_URI) == nil then
		return false
	end
	return is_http_challenge(self.ctx)
		or get_variable("LETS_ENCRYPT_PASSTHROUGH", true, self.ctx) == "yes"
		or get_variable("ACME_PASSTHROUGH", true, self.ctx) == "yes"
end

function mtls:deny_invalid_regex(pattern, re_err)
	-- A protection rule that does not compile leaves its intended path unprotected, so the request
	-- fails closed (deny) instead of being silently allowed; the throttled log names the bad pattern.
	self:log_throttled(ERR, "bad_regex", "invalid MTLS_URL regex (" .. pattern .. ") : " .. re_err)
	self:set_metric("counters", "failed_mtls", 1)
	return self:verdict(
		"invalid MTLS_URL regex (" .. pattern .. ")",
		get_deny_status(),
		nil,
		{ id = "mtls", error = "invalid_regex" }
	)
end

-- MTLS_HTTP_POLICY for a plain-HTTP request that is in mTLS scope.
function mtls:apply_http_policy(policy)
	local bw = self.ctx.bw
	local reason = "plain HTTP request to an mTLS service (MTLS_HTTP_POLICY=" .. policy .. ")"
	if policy == "redirect" then
		local host, request_uri = bw.http_host, bw.request_uri
		if is_safe_host(host) and type(request_uri) == "string" and sub(request_uri, 1, 1) == "/" then
			return self:verdict(
				reason .. ", redirect to HTTPS",
				HTTP_MOVED_PERMANENTLY,
				"https://" .. host .. request_uri,
				{ id = "mtls", policy = policy }
			)
		end
		reason = reason .. " without a usable Host or URI"
	end
	self:set_metric("counters", "failed_mtls", 1)
	return self:verdict(reason, get_deny_status(), nil, { id = "mtls", policy = policy })
end

function mtls:access()
	if not self:is_needed() then
		return self:ret(true, "mTLS not enabled")
	end

	local urls = self.urls
	local has_urls = urls ~= nil and #urls > 0
	-- optional and optional_no_ca enforce nothing on a path no MTLS_URL rule names, on HTTPS or on HTTP.
	-- A missing mode (settings out of sync) is treated as the default, on.
	local verify_mode = self.variables["MTLS_VERIFY_CLIENT"] or "on"
	local server_wide = verify_mode == "on"
	if not server_wide and not has_urls then
		return self:ret(true, "no per-path mTLS rules")
	end

	local uri = self.ctx.bw.uri or ""

	-- Plain HTTP never carries a client certificate, so ssl_verify_client cannot protect it.
	if self.ctx.bw.scheme == "http" then
		if self:is_acme_challenge() then
			return self:ret(true, "ACME HTTP-01 challenge reaches its solver without mTLS")
		end
		local policy = self.variables["MTLS_HTTP_POLICY"]
		if policy ~= "deny" and policy ~= "allow" then
			policy = "redirect"
		end
		-- allow restores the previous behaviour: server-wide mode is left open, MTLS_URL rules still deny.
		if policy ~= "allow" then
			local in_scope = server_wide
			if not in_scope then
				local matched, bad_pattern, re_err = match_urls(urls, uri)
				if matched == nil then
					return self:deny_invalid_regex(bad_pattern, re_err)
				end
				in_scope = matched
			end
			if in_scope then
				return self:apply_http_policy(policy)
			end
		end
	end

	-- No per-path rules: server-wide enforcement is handled at the TLS layer.
	if not has_urls then
		return self:ret(true, "no per-path mTLS rules")
	end

	local matched, bad_pattern, re_err = match_urls(urls, uri)
	if matched == nil then
		return self:deny_invalid_regex(bad_pattern, re_err)
	end
	if not matched then
		return self:ret(true, "URI outside mTLS scope")
	end

	-- nginx populates $ssl_client_verify during the TLS handshake; under
	-- optional / optional_no_ca a missing or invalid cert is not rejected
	-- there, so we enforce it here on the matching URLs.
	local verify = ngx.var.ssl_client_verify
	if verify == "SUCCESS" then
		self:set_metric("counters", "passed_mtls", 1)
		return self:ret(true, "valid client certificate for " .. uri)
	end

	self:set_metric("counters", "failed_mtls", 1)
	return self:verdict(
		"client certificate required for " .. uri .. " (ssl_client_verify=" .. tostring(verify) .. ")",
		get_deny_status(),
		nil,
		{ id = "mtls", verify = verify }
	)
end

-- Compiles every MTLS_URL rule once per reload (the dispatcher runs this once per reload, under its
-- readiness key) and reports each one that does not compile. ngx.re is not available in init(), so the
-- check lives here. Request-time handling of a bad rule is unchanged: matching requests fail closed.
function mtls:init_worker()
	-- MTLS_URL is an HTTP setting; the stream VM would report every rule a second time.
	if ngx.config.subsystem ~= "http" then
		return self:ret(true, "MTLS_URL rules are HTTP only")
	end
	local configs, err = self.internalstore:get("plugin_mtls_configs", true)
	if not configs then
		return self:ret(true, "no mTLS configuration to check : " .. tostring(err))
	end
	local scopes = {}
	for scope in pairs(configs) do
		scopes[#scopes + 1] = scope
	end
	sort(scopes)
	local invalid = 0
	for _, scope in ipairs(scopes) do
		for _, pattern in ipairs(configs[scope]) do
			local _, re_err = re_match("", pattern, "o")
			if re_err then
				invalid = invalid + 1
				self.logger:log(
					ERR,
					"invalid MTLS_URL regex for "
						.. (scope == "global" and "the global scope" or "service " .. scope)
						.. " ("
						.. pattern
						.. ") : "
						.. re_err
						.. "; the rule fails closed: a request that no earlier rule matched is denied until it is fixed"
				)
			end
		end
	end
	if invalid > 0 then
		return self:ret(true, tostring(invalid) .. " invalid MTLS_URL regex(es)")
	end
	return self:ret(true, "all MTLS_URL regexes compile")
end

return mtls
