local bit = require "bit"
local class = require "middleclass"
local kdf = require "resty.openssl.kdf"
local plugin = require "bunkerweb.plugin"
local random = require "resty.random"
local utils = require "bunkerweb.utils"

local authbasic = class("authbasic", plugin)

local ngx = ngx
local ERR = ngx.ERR
local WARN = ngx.WARN
local HTTP_UNAUTHORIZED = ngx.HTTP_UNAUTHORIZED
local get_phase = ngx.get_phase
local req_get_headers = ngx.req.get_headers
local decode_base64 = ngx.decode_base64
local encode_base64 = ngx.encode_base64
local get_multiple_variables = utils.get_multiple_variables
local has_variable = utils.has_variable
local regex_match = utils.regex_match
local time = os.time
local date = os.date
local tostring = tostring
local random_bytes = random.bytes
local bor = bit.bor
local bxor = bit.bxor

local PASSWORD_SALT_LENGTH = 16
local PASSWORD_HASH_PARAMS = {
	N = 32768,
	r = 8,
	p = 1,
	outlen = 32,
	maxmem = 64 * 1024 * 1024,
}

local function clone_params(params)
	return {
		N = params.N,
		r = params.r,
		p = params.p,
		outlen = params.outlen,
		maxmem = params.maxmem,
	}
end

local function trim(value)
	if value == nil then
		return ""
	end
	return (value:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function build_matcher(raw_location)
	local location = trim(raw_location)
	if location == "" or location == "sitewide" then
		return { kind = "sitewide" }
	end

	if location:sub(1, 1) == "=" then
		return { kind = "exact", value = trim(location:sub(2)) }
	end

	if location:sub(1, 2) == "^~" then
		return { kind = "prefix", value = trim(location:sub(3)) }
	end

	if location:sub(1, 2):lower() == "~*" then
		return { kind = "regex", value = trim(location:sub(3)), options = "i" }
	end

	if location:sub(1, 1) == "~" then
		return { kind = "regex", value = trim(location:sub(2)) }
	end

	return { kind = "prefix", value = location }
end

local function extract_credentials(vars)
	local credentials = {}
	local users_list = {}
	local count = 0
	for key, value in pairs(vars) do
		local suffix = key:match("^AUTH_BASIC_USER(_?%d*)$")
		if suffix and value ~= "" then
			local password_key = "AUTH_BASIC_PASSWORD" .. suffix
			local password = vars[password_key]
			if password and password ~= "" then
				credentials[value] = password
				table.insert(users_list, {
					username = value,
					password_set = true,
					password_length = #password,
				})
				count = count + 1
			end
		end
	end
	return credentials, count, users_list
end

local function generate_salt(length)
	local salt = random_bytes(length, true) or random_bytes(length, false)
	if not salt then
		return nil, "unable to generate cryptographically secure salt"
	end
	return salt
end

local function derive_secret(password, salt, params)
	params = params or PASSWORD_HASH_PARAMS
	return kdf.derive({
		type = kdf.SCRYPT,
		pass = password,
		salt = salt,
		outlen = params.outlen or PASSWORD_HASH_PARAMS.outlen,
		scrypt_N = params.N or PASSWORD_HASH_PARAMS.N,
		scrypt_r = params.r or PASSWORD_HASH_PARAMS.r,
		scrypt_p = params.p or PASSWORD_HASH_PARAMS.p,
		scrypt_maxmem = params.maxmem or PASSWORD_HASH_PARAMS.maxmem,
	})
end

local function hash_password(password)
	local salt, salt_err = generate_salt(PASSWORD_SALT_LENGTH)
	if not salt then
		return nil, salt_err
	end
	local derived, err = derive_secret(password, salt, PASSWORD_HASH_PARAMS)
	if not derived then
		return nil, err
	end
	return {
		algorithm = "scrypt",
		salt = encode_base64(salt),
		hash = encode_base64(derived),
		params = clone_params(PASSWORD_HASH_PARAMS),
	}
end

local function constant_time_equals(a, b)
	if not a or not b or #a ~= #b then
		return false
	end
	local diff = 0
	for i = 1, #a do
		diff = bor(diff, bxor(a:byte(i), b:byte(i)))
	end
	return diff == 0
end

local function verify_password(candidate, stored)
	if type(stored) == "table" and stored.hash and stored.salt then
		local salt = decode_base64(stored.salt)
		local expected = decode_base64(stored.hash)
		if not salt or not expected then
			return nil, "corrupted credential data"
		end
		local derived, err = derive_secret(candidate, salt, stored.params)
		if not derived then
			return nil, err
		end
		return constant_time_equals(derived, expected)
	end

	if type(stored) == "string" then
		return stored == candidate
	end

	return nil, "unsupported credential format"
end

function authbasic:initialize(ctx)
	plugin.initialize(self, "authbasic", ctx)

	if get_phase() == "init" or not self.ctx then
		return
	end

	if self.variables["USE_AUTH_BASIC"] ~= "yes" then
		return
	end

	local configs, err = self.internalstore:get("plugin_authbasic_configs", true)
	if not configs then
		self.logger:log(ERR, err)
		return
	end

	local server_config = {}
	if configs.global then
		for key, value in pairs(configs.global) do
			server_config[key] = value
		end
	end

	local server_name = self.ctx.bw.server_name
	if server_name and configs[server_name] then
		for key, value in pairs(configs[server_name]) do
			server_config[key] = value
		end
	end

	self.current_config = server_config
end

function authbasic:is_needed()
	if self.is_loading then
		return false
	end

	if self.is_request and (self.ctx.bw.server_name ~= "_") then
		return self.variables["USE_AUTH_BASIC"] == "yes"
	end

	local enabled, err = has_variable("USE_AUTH_BASIC", "yes")
	if enabled == nil then
		self.logger:log(ERR, "can't check USE_AUTH_BASIC variable : " .. err)
	end
	return enabled
end

function authbasic:init()
	local variables, err = get_multiple_variables({
		"USE_AUTH_BASIC",
		"AUTH_BASIC_LOCATION",
		"AUTH_BASIC_TEXT",
		"AUTH_BASIC_USER",
		"AUTH_BASIC_PASSWORD",
	})
	if not variables then
		return self:ret(false, err)
	end

	local configs = {}
	local configured = 0

	local users_summary = {}

	for scope, vars in pairs(variables) do
		if vars["USE_AUTH_BASIC"] == "yes" then
			local matcher = build_matcher(vars["AUTH_BASIC_LOCATION"])
			local raw_credentials, count, users_list = extract_credentials(vars)
			if count == 0 then
				self.logger:log(WARN, "no credentials configured for scope " .. scope .. ", skipping")
			else
				local credentials = {}
				local hashed = 0
				for username, password in pairs(raw_credentials) do
					local hashed_entry, hash_err = hash_password(password)
					if not hashed_entry then
						self.logger:log(
							WARN,
							string.format(
								"failed to hash password for user %s in scope %s: %s",
								username,
								scope,
								hash_err or "unknown error"
							)
						)
					else
						credentials[username] = hashed_entry
						hashed = hashed + 1
					end
				end
				if hashed == 0 then
					self.logger:log(WARN, "unable to hash credentials for scope " .. scope .. ", skipping")
				else
					configs[scope] = {
						realm = trim(vars["AUTH_BASIC_TEXT"]) ~= "" and trim(vars["AUTH_BASIC_TEXT"])
							or "Restricted area",
						matcher = matcher,
						credentials = credentials,
						credentials_count = hashed,
					}
					users_summary[scope] = {
						enabled = true,
						location = vars["AUTH_BASIC_LOCATION"] or "sitewide",
						realm = configs[scope].realm,
						users = users_list,
						users_count = hashed,
					}
					configured = configured + 1
				end
			end
		else
			users_summary[scope] = {
				enabled = false,
				users = {},
				users_count = 0,
			}
		end
	end

	-- Store users summary for metrics display (passwords hidden)
	local ok_summary, summary_err = self.internalstore:set("plugin_authbasic_users_summary", users_summary, nil, true)
	if not ok_summary then
		self.logger:log(WARN, "can't store users summary: " .. summary_err)
	end

	local ok, store_err = self.internalstore:set("plugin_authbasic_configs", configs, nil, true)
	if not ok then
		return self:ret(false, store_err)
	end

	local message
	if configured == 0 then
		message = "no auth basic scope enabled"
	else
		message = "loaded auth basic configuration for " .. tostring(configured) .. " scope(s)"
	end
	return self:ret(true, message)
end

function authbasic:matches_scope()
	local config = self.current_config
	if not config or not config.matcher then
		return false
	end

	local matcher = config.matcher
	if matcher.kind == "sitewide" then
		return true
	end

	local uri = self.ctx.bw.uri or ""

	if matcher.kind == "exact" then
		return uri == matcher.value
	end

	if matcher.kind == "prefix" then
		if matcher.value == "" then
			return true
		end
		return uri:sub(1, #matcher.value) == matcher.value
	end

	if matcher.kind == "regex" and matcher.value ~= "" then
		return regex_match(uri, matcher.value, matcher.options) ~= nil
	end

	return false
end

function authbasic:validate_credentials()
	local config = self.current_config
	if not config or not config.credentials then
		return false, "missing credentials"
	end

	local headers = req_get_headers()
	local auth_header = headers["authorization"] or headers["Authorization"]
	if not auth_header then
		return false, "missing Authorization header"
	end

	local encoded = auth_header:match("^[%s]*[Bb][Aa][Ss][Ii][Cc]%s+(.+)$")
	if not encoded then
		return false, "invalid Authorization scheme"
	end

	local decoded = decode_base64(trim(encoded))
	if not decoded then
		return false, "invalid base64 credential"
	end

	local separator = decoded:find(":", 1, true)
	if not separator then
		return false, "malformed credential"
	end

	local username = decoded:sub(1, separator - 1)
	local password = decoded:sub(separator + 1)
	local expected = config.credentials[username]
	if not expected then
		return false, "unknown user " .. username
	end

	local verified, err = verify_password(password, expected)
	if verified == nil then
		self.logger:log(
			ERR,
			string.format("unable to verify password for user %s: %s", username, err or "unknown error")
		)
		return false, "internal authentication error"
	end

	if not verified then
		return false, "invalid password for user " .. username
	end

	return true, username
end

function authbasic:access()
	if not self:is_needed() then
		return self:ret(true, "auth basic disabled")
	end

	if not self.current_config or not self.current_config.credentials then
		return self:ret(true, "no auth basic configuration for this server")
	end

	if not self:matches_scope() then
		return self:ret(true, "URI outside protected scope")
	end

	local ok, result = self:validate_credentials()
	local remote_addr = self.ctx.bw.remote_addr
	local server_name = self.ctx.bw.server_name
	local uri = self.ctx.bw.uri or ""

	if ok then
		self:set_metric("counters", "passed_authbasic", 1)
		self:set_metric("counters", "passed_user_" .. result, 1)
		self:set_metric("tables", "authentications", {
			date = time(date("!*t")),
			ip = remote_addr,
			server_name = server_name,
			uri = uri,
			username = result,
			success = true,
		})
		ngx.var.auth_user = result
		ngx.var.remote_user = result
		return self:ret(true, "authenticated user " .. result)
	end

	self:set_metric("counters", "failed_authbasic", 1)
	self:set_metric("counters", "failed_ip_" .. remote_addr, 1)

	-- Extract attempted username from result message if available
	local attempted_user = result:match("unknown user (.+)$") or result:match("invalid password for user (.+)$")
	if attempted_user then
		self:set_metric("counters", "failed_user_" .. attempted_user, 1)
	end

	self:set_metric("tables", "authentications", {
		date = time(date("!*t")),
		ip = remote_addr,
		server_name = server_name,
		uri = uri,
		username = attempted_user or "unknown",
		success = false,
		reason = result,
	})

	ngx.header["WWW-Authenticate"] =
		string.format('Basic realm="%s", charset="UTF-8"', self.current_config.realm or "Restricted area")
	return self:ret(true, result, HTTP_UNAUTHORIZED)
end

return authbasic
