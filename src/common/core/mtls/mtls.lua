local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local mtls = class("mtls", plugin)

local ngx = ngx
local ERR = ngx.ERR
local WARN = ngx.WARN
local re_match = ngx.re.match
local get_phase = ngx.get_phase
local get_deny_status = utils.get_deny_status
local get_multiple_variables = utils.get_multiple_variables
local has_variable = utils.has_variable
local tostring = tostring

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

function mtls:access()
	if not self:is_needed() then
		return self:ret(true, "mTLS not enabled")
	end

	-- No per-path rules: server-wide enforcement belongs to the TLS layer, and under a correct
	-- config NGINX has already rejected certificate-less clients during the handshake. This is a
	-- backstop for the case where it did not -- a config path that stopped emitting
	-- ssl_verify_client would otherwise serve the whole site unauthenticated, silently, while
	-- USE_MTLS still reads "yes". It never fires when the TLS layer is doing its job.
	--
	-- Scoped deliberately:
	--   * MTLS_VERIFY_CLIENT=on only. "optional" is meant to let anonymous clients through, and
	--     "optional_no_ca" performs no validation at all, so neither can be enforced here.
	--   * TLS connections only. A plain-HTTP request has no handshake and no $ssl_client_verify;
	--     denying those would break the HTTP-to-HTTPS redirect and the ACME http-01 challenge.
	local urls = self.urls
	if not urls or #urls == 0 then
		if self.variables["MTLS_VERIFY_CLIENT"] ~= "on" then
			return self:ret(true, "no per-path mTLS rules")
		end
		local ssl_protocol = ngx.var.ssl_protocol
		if not ssl_protocol or ssl_protocol == "" then
			return self:ret(true, "no per-path mTLS rules (plain HTTP)")
		end
		local verify = ngx.var.ssl_client_verify
		if verify == "SUCCESS" then
			self:set_metric("counters", "passed_mtls", 1)
			return self:ret(true, "valid client certificate")
		end
		-- Reaching here means ssl_verify_client did not run: NGINX would have rejected this
		-- connection otherwise. Fail closed and say so loudly -- it is a configuration fault,
		-- not a client fault.
		self:log_throttled(
			ERR,
			"tls_layer_not_enforcing",
			"USE_MTLS=yes and MTLS_VERIFY_CLIENT=on, but the TLS layer accepted a connection with"
				.. " ssl_client_verify="
				.. tostring(verify)
				.. "; refusing the request. Check that MTLS_CA_CERTIFICATE is set and readable on this instance."
		)
		self:set_metric("counters", "failed_mtls", 1)
		return self:ret(
			true,
			"mTLS is enabled but the TLS layer is not enforcing it (ssl_client_verify=" .. tostring(verify) .. ")",
			get_deny_status(),
			nil,
			{ id = "mtls", error = "tls_layer_not_enforcing", verify = verify }
		)
	end

	local uri = self.ctx.bw.uri or ""
	local matched = false
	for _, pattern in ipairs(urls) do
		-- ngx.re.match (not utils.regex_match) so we can tell a non-match apart
		-- from a compile error. A protection rule that does not compile leaves
		-- its intended path unprotected, so we fail closed (deny) instead of
		-- silently allowing the request; the throttled log names the bad pattern.
		local m, re_err = re_match(uri, pattern, "o")
		if re_err then
			self:log_throttled(ERR, "bad_regex", "invalid MTLS_URL regex (" .. pattern .. ") : " .. re_err)
			self:set_metric("counters", "failed_mtls", 1)
			return self:ret(
				true,
				"invalid MTLS_URL regex (" .. pattern .. ")",
				get_deny_status(),
				nil,
				{ id = "mtls", error = "invalid_regex" }
			)
		end
		if m then
			matched = true
			break
		end
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
	return self:ret(
		true,
		"client certificate required for " .. uri .. " (ssl_client_verify=" .. tostring(verify) .. ")",
		get_deny_status(),
		nil,
		{ id = "mtls", verify = verify }
	)
end

return mtls
