local cjson = require "cjson"
local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local ssl = require "ngx.ssl"
local utils = require "bunkerweb.utils"

local letsencrypt = class("letsencrypt", plugin)

local ngx = ngx
local ERR = ngx.ERR
local NOTICE = ngx.NOTICE
local OK = ngx.OK
local HTTP_NOT_FOUND = ngx.HTTP_NOT_FOUND
local HTTP_OK = ngx.HTTP_OK
local HTTP_BAD_REQUEST = ngx.HTTP_BAD_REQUEST
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local parse_pem_cert = ssl.parse_pem_cert
local parse_pem_priv_key = ssl.parse_pem_priv_key
local ssl_server_name = ssl.server_name
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local has_variable = utils.has_variable
local read_files = utils.read_files
local open = io.open
local sub = string.sub
local match = string.match
local decode = cjson.decode
local execute = os.execute
local remove = os.remove
local insert = table.insert
local ipairs = ipairs
local pairs = pairs
local sort = table.sort
local lower = string.lower
local gsub = string.gsub

-- The one spelling of the challenge prefix and of the directory it is served from. `api()` used
-- to carry its own copy of the folder path; `ssl.lua` still carries its own copy of the prefix
-- (tests/unit/common/test_ssl_acme_challenge_not_redirected.py asserts the two agree).
local ACME_CHALLENGE_PREFIX = "/.well-known/acme-challenge/"
local ACME_CHALLENGE_DIR = "/var/tmp/bunkerweb/lets-encrypt" .. ACME_CHALLENGE_PREFIX
-- ACME HTTP-01 tokens are base64url ([A-Za-z0-9_-]+, RFC 8555 §8.3). Rejecting anything else is
-- what stops an attacker-controlled token from escaping ACME_CHALLENGE_DIR via "/", "\" or "..".
local ACME_TOKEN_PATTERN = "^[A-Za-z0-9_%-]+$"

-- SNI is client-supplied and the SERVER_NAME list is operator-supplied, so the two only compare
-- reliably once folded to the same shape. Same spelling as `customcert.lua`, since the two plugins
-- key the same internalstore namespace in the same phase.
local function normalize_hostname(hostname)
	if not hostname then
		return nil
	end
	return lower(gsub(hostname, "%.$", ""))
end

-- Mirror certbot-new wildcard grouping so certificate identifiers stay in sync.
local function sanitize_domain_labels(domain)
	if not domain or domain == "" then
		return nil
	end
	local cleaned = lower(gsub(domain, "^%*%.", ""))
	cleaned = gsub(cleaned, "%.+$", "")
	local labels = {}
	for label in cleaned:gmatch("[^.]+") do
		if label ~= "" then
			insert(labels, label)
		end
	end
	if #labels == 0 then
		return nil
	end
	return labels
end

local function determine_wildcard_bases(labels_list)
	local count = #labels_list
	if count == 0 then
		return {}
	end
	if count == 1 then
		local labels = labels_list[1]
		if #labels > 2 then
			return { table.concat(labels, ".", 2) }
		end
		return { table.concat(labels, ".") }
	end
	local min_len = #labels_list[1]
	for i = 2, count do
		if #labels_list[i] < min_len then
			min_len = #labels_list[i]
		end
	end
	local common_suffix = {}
	for idx = 1, min_len do
		local label = labels_list[1][#labels_list[1] - idx + 1]
		local match_all = true
		for j = 2, count do
			if labels_list[j][#labels_list[j] - idx + 1] ~= label then
				match_all = false
				break
			end
		end
		if not match_all then
			break
		end
		insert(common_suffix, 1, label)
	end
	if #common_suffix >= 2 and #common_suffix >= (min_len - 1) then
		return { table.concat(common_suffix, ".") }
	end
	local bases = {}
	local seen = {}
	for _, labels in ipairs(labels_list) do
		local base
		if #labels > 2 then
			base = table.concat(labels, ".", 2)
		else
			base = table.concat(labels, ".")
		end
		if base ~= "" and not seen[base] then
			seen[base] = true
			insert(bases, base)
		end
	end
	return bases
end

local function build_wildcard_groups(domains)
	local grouped = {}
	local has_entries = false
	for _, domain in ipairs(domains) do
		local labels = sanitize_domain_labels(domain)
		if labels then
			has_entries = true
			local len = #labels
			local key
			if len >= 2 then
				key = labels[len - 1] .. "." .. labels[len]
			else
				key = labels[1]
			end
			grouped[key] = grouped[key] or {}
			insert(grouped[key], labels)
		end
	end
	if not has_entries then
		return {}
	end
	local groups = {}
	for _, labels_list in pairs(grouped) do
		local bases = determine_wildcard_bases(labels_list)
		for _, base in ipairs(bases) do
			if base ~= "" then
				groups[base] = groups[base] or {}
				groups[base]["*." .. base] = true
				groups[base][base] = true
			end
		end
	end
	local result = {}
	for base, names_set in pairs(groups) do
		local names = {}
		for name, _ in pairs(names_set) do
			insert(names, name)
		end
		sort(names, function(a, b)
			local a_wildcard = sub(a, 1, 2) == "*."
			local b_wildcard = sub(b, 1, 2) == "*."
			if a_wildcard == b_wildcard then
				return a < b
			end
			return a_wildcard and not b_wildcard
		end)
		result[base] = names
	end
	return result
end

-- Resolve a hostname to the wildcard base whose certificate covers it, or nil.
--
-- RFC 6125 section 6.4.3: a `*.example.com` certificate covers exactly ONE label under the base,
-- so `deep.app.example.com` is NOT covered by `*.example.com` and must fall through instead of
-- being handed a certificate its own validation rejects. This used to test the suffix alone,
-- which matched at any depth -- and `customcert.lua` (`resolve_wildcard_base` there) already
-- applies the single-label rule, so the two plugins answered the same question differently in
-- the same phase.
--
-- The exact-base branch is NOT the wildcard rule and is deliberately kept: in wildcard mode the
-- lineage for `example.com` carries both `*.example.com` and `example.com` (see
-- `build_wildcard_groups`), so the apex is genuinely covered by that certificate. customcert has
-- no equivalent because it derives its bases from `*.` SAN entries alone.
--
-- `bases` is published longest-first, so a deeper base still wins where one exists; a base whose
-- suffix matches but whose label test fails must keep looking rather than stop the search.
local function resolve_wildcard_base(host, bases)
	if not host or host == "" then
		return nil
	end
	for _, base in ipairs(bases) do
		if host == base then
			return base
		end
		local suffix = "." .. base
		if #host > #suffix and host:sub(-#suffix) == suffix then
			local wildcard_label = host:sub(1, #host - #suffix)
			if wildcard_label ~= "" and not wildcard_label:find(".", 1, true) then
				return base
			end
		end
	end
	return nil
end

function letsencrypt:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "letsencrypt", ctx)
end

function letsencrypt:set()
	local https_configured = self.variables["AUTO_LETS_ENCRYPT"]
	if https_configured == "yes" then
		self.ctx.bw.https_configured = "yes"
	end
	return self:ret(true, "set https_configured to " .. https_configured)
end

function letsencrypt:init()
	local ret_ok, ret_err = true, "success"
	local wildcard_servers = {}
	local wildcard_bases_set = {}

	if has_variable("AUTO_LETS_ENCRYPT", "yes") then
		local multisite, err = get_variable("MULTISITE", false)
		if not multisite then
			return self:ret(false, "can't get MULTISITE variable : " .. err)
		end
		if multisite == "yes" then
			local vars
			vars, err = get_multiple_variables({
				"AUTO_LETS_ENCRYPT",
				"LETS_ENCRYPT_CHALLENGE",
				"LETS_ENCRYPT_DNS_PROVIDER",
				"USE_LETS_ENCRYPT_WILDCARD",
				"SERVER_NAME",
			})
			if not vars then
				return self:ret(false, "can't get required variables : " .. err)
			end
			local credential_items
			credential_items, err = get_multiple_variables({ "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" })
			if not credential_items then
				return self:ret(false, "can't get credential items : " .. err)
			end
			for server_name, multisite_vars in pairs(vars) do
				if
					multisite_vars["AUTO_LETS_ENCRYPT"] == "yes"
					and server_name ~= "global"
					and (
						multisite_vars["LETS_ENCRYPT_CHALLENGE"] == "http"
						or (
							multisite_vars["LETS_ENCRYPT_CHALLENGE"] == "dns"
							and multisite_vars["LETS_ENCRYPT_DNS_PROVIDER"] ~= ""
							and credential_items[server_name]
						)
					)
				then
					local data
					local server_names = multisite_vars["SERVER_NAME"]
					local cert_identifier = server_names:match("%S+")
					local server_list = {}
					for part in server_names:gmatch("%S+") do
						insert(server_list, part)
					end

					if
						multisite_vars["LETS_ENCRYPT_CHALLENGE"] == "dns"
						and multisite_vars["USE_LETS_ENCRYPT_WILDCARD"] == "yes"
					then
						local wildcard_groups = build_wildcard_groups(server_list)
						local bases = {}
						for base, _ in pairs(wildcard_groups) do
							insert(bases, base)
							wildcard_bases_set[base] = true
							if wildcard_servers[base] == nil then
								wildcard_servers[base] = base
							end
						end
						sort(bases, function(a, b)
							if #a == #b then
								return a < b
							end
							return #a > #b
						end)
						for _, part in ipairs(server_list) do
							local host = normalize_hostname(part)
							-- A name of a service that uses Let's Encrypt maps to its wildcard base,
							-- or to itself. Only a service that does not use it maps to false.
							wildcard_servers[host] = resolve_wildcard_base(host, bases) or host
						end
						for _, base in ipairs(bases) do
							data = self.internalstore:get("plugin_letsencrypt_" .. base, true)
							if not data then
								local check
								check, data = read_files({
									"/var/cache/bunkerweb/letsencrypt/etc/live/" .. base .. "/fullchain.pem",
									"/var/cache/bunkerweb/letsencrypt/etc/live/" .. base .. "/privkey.pem",
								})
								if not check then
									self.logger:log(ERR, "error while reading files : " .. data)
									ret_ok = false
									ret_err = "error reading files"
								else
									check, err = self:load_data(data, base)
									if not check then
										self.logger:log(ERR, "error while loading data : " .. err)
										ret_ok = false
										ret_err = "error loading data"
									end
								end
							end
						end
					else
						for _, part in ipairs(server_list) do
							local host = normalize_hostname(part)
							wildcard_servers[host] = host
						end
						data =
							self.internalstore:get("plugin_letsencrypt_" .. normalize_hostname(cert_identifier), true)
						if not data then
							local check
							check, data = read_files({
								"/var/cache/bunkerweb/letsencrypt/etc/live/" .. cert_identifier .. "/fullchain.pem",
								"/var/cache/bunkerweb/letsencrypt/etc/live/" .. cert_identifier .. "/privkey.pem",
							})
							if not check then
								self.logger:log(ERR, "error while reading files : " .. data)
								ret_ok = false
								ret_err = "error reading files"
							else
								check, err = self:load_data(data, multisite_vars["SERVER_NAME"])
								if not check then
									self.logger:log(ERR, "error while loading data : " .. err)
									ret_ok = false
									ret_err = "error loading data"
								end
							end
						end
					end
				elseif server_name ~= "global" then
					-- The service does not use Let's Encrypt : its names must never resolve to
					-- another service's wildcard certificate.
					for part in (multisite_vars["SERVER_NAME"] or server_name):gmatch("%S+") do
						local host = normalize_hostname(part)
						wildcard_servers[host] = false
					end
				end
			end
		else
			local server_name
			server_name, err = get_variable("SERVER_NAME", false)
			if not server_name then
				return self:ret(false, "can't get SERVER_NAME variable : " .. err)
			end
			local use_wildcard
			use_wildcard, err = get_variable("USE_LETS_ENCRYPT_WILDCARD", false)
			if not use_wildcard then
				return self:ret(false, "can't get USE_LETS_ENCRYPT_WILDCARD variable : " .. err)
			end
			local challenge
			challenge, err = get_variable("LETS_ENCRYPT_CHALLENGE", false)
			if not challenge then
				return self:ret(false, "can't get LETS_ENCRYPT_CHALLENGE variable : " .. err)
			end
			local server_names = server_name
			local cert_identifier = server_names:match("%S+")
			local server_list = {}
			for part in server_names:gmatch("%S+") do
				insert(server_list, part)
			end
			local use_wildcard_mode = challenge == "dns" and use_wildcard == "yes"
			if use_wildcard_mode then
				local wildcard_groups = build_wildcard_groups(server_list)
				local bases = {}
				for base, _ in pairs(wildcard_groups) do
					insert(bases, base)
					wildcard_bases_set[base] = true
					if wildcard_servers[base] == nil then
						wildcard_servers[base] = base
					end
				end
				sort(bases, function(a, b)
					if #a == #b then
						return a < b
					end
					return #a > #b
				end)
				for _, part in ipairs(server_list) do
					local host = normalize_hostname(part)
					wildcard_servers[host] = resolve_wildcard_base(host, bases) or host
				end
				for _, base in ipairs(bases) do
					local data = self.internalstore:get("plugin_letsencrypt_" .. base, true)
					if not data then
						local check
						check, data = read_files({
							"/var/cache/bunkerweb/letsencrypt/etc/live/" .. base .. "/fullchain.pem",
							"/var/cache/bunkerweb/letsencrypt/etc/live/" .. base .. "/privkey.pem",
						})
						if not check then
							self.logger:log(ERR, "error while reading files : " .. data)
							ret_ok = false
							ret_err = "error reading files"
						else
							check, err = self:load_data(data, base)
							if not check then
								self.logger:log(ERR, "error while loading data : " .. err)
								ret_ok = false
								ret_err = "error loading data"
							end
						end
					end
				end
			else
				for _, part in ipairs(server_list) do
					local host = normalize_hostname(part)
					wildcard_servers[host] = host
				end
				local check, data = read_files({
					"/var/cache/bunkerweb/letsencrypt/etc/live/" .. cert_identifier .. "/fullchain.pem",
					"/var/cache/bunkerweb/letsencrypt/etc/live/" .. cert_identifier .. "/privkey.pem",
				})
				if not check then
					self.logger:log(ERR, "error while reading files : " .. data)
					ret_ok = false
					ret_err = "error reading files"
				else
					check, err = self:load_data(data, server_names)
					if not check then
						self.logger:log(ERR, "error while loading data : " .. err)
						ret_ok = false
						ret_err = "error loading data"
					end
				end
			end
		end
	else
		ret_err = "let's encrypt is not used"
	end

	local wildcard_bases = {}
	for base, _ in pairs(wildcard_bases_set) do
		insert(wildcard_bases, base)
	end
	sort(wildcard_bases, function(a, b)
		if #a == #b then
			return a < b
		end
		return #a > #b
	end)

	local ok, err = self.internalstore:set("plugin_letsencrypt_wildcard_bases", wildcard_bases, nil, true)
	if not ok then
		return self:ret(false, "error while setting wildcard bases into internalstore : " .. err)
	end

	ok, err = self.internalstore:set("plugin_letsencrypt_wildcard_servers", wildcard_servers, nil, true)
	if not ok then
		return self:ret(false, "error while setting wildcard servers into internalstore : " .. err)
	end

	return self:ret(ret_ok, ret_err)
end

function letsencrypt:ssl_certificate()
	local server_name, err = ssl_server_name()
	if not server_name then
		if err then
			return self:ret(false, "can't get server_name : " .. err)
		end
		return self:ret(true, "no SNI provided")
	end
	server_name = normalize_hostname(server_name)
	local wildcard_servers, err = self.internalstore:get("plugin_letsencrypt_wildcard_servers", true)
	if not wildcard_servers then
		return self:ret(false, "can't get wildcard servers : " .. err)
	end
	local wildcard_bases = {}
	local stored_bases, bases_err = self.internalstore:get("plugin_letsencrypt_wildcard_bases", true)
	if stored_bases then
		wildcard_bases = stored_bases
	elseif bases_err ~= "not found" then
		return self:ret(false, "can't get wildcard bases : " .. bases_err)
	end
	local alias = wildcard_servers[server_name]
	if type(alias) == "string" and alias ~= "" then
		server_name = alias
	elseif alias == false then
		-- The host belongs to a service that does not use Let's Encrypt : it must not be served
		-- another service's certificate, including one cached under its own name as a base.
		return self:ret(true, "let's encrypt is not used")
	else
		-- Only a host that belongs to no configured service may fall back to a wildcard base.
		--
		-- Same resolver `init()` uses, rather than a second copy of the rule: the copy that used
		-- to live here had drifted -- it matched a wildcard base at any depth, so a
		-- `*.example.com` certificate was selected for `deep.app.example.com`.
		local base = resolve_wildcard_base(server_name, wildcard_bases)
		if base then
			server_name = base
		end
	end
	local data
	data, err = self.internalstore:get("plugin_letsencrypt_" .. server_name, true)
	if not data and err ~= "not found" then
		return self:ret(
			false,
			"error while getting plugin_letsencrypt_" .. server_name .. " from internalstore : " .. err
		)
	elseif data then
		return self:ret(true, "certificate/key data found", data)
	end
	return self:ret(true, "let's encrypt is not used")
end

function letsencrypt:load_data(data, server_name)
	-- Load certificate
	local cert_chain, err = parse_pem_cert(data[1])
	if not cert_chain then
		return false, "error while parsing pem cert : " .. err
	end
	-- Load key
	local priv_key
	priv_key, err = parse_pem_priv_key(data[2])
	if not priv_key then
		return false, "error while parsing pem priv key : " .. err
	end
	-- Cache data
	for key in server_name:gmatch("%S+") do
		local cache_key = "plugin_letsencrypt_" .. normalize_hostname(key)
		local ok
		ok, err = self.internalstore:set(cache_key, { cert_chain, priv_key }, nil, true)
		if not ok then
			return false, "error while setting data into internalstore : " .. err
		end
	end
	return true
end

function letsencrypt:access()
	-- ARMED only for a service that is really going to be validated over http-01. It used to be
	-- armed for every service whose LETS_ENCRYPT_PASSTHROUGH was "no" -- the default -- so on a
	-- fleet that never asked for a certificate, and on every service using the dns challenge, any
	-- URI under the challenge prefix ended the access chain right here: a returned status breaks
	-- the loop in access-lua.conf, so blacklist, greylist, country, dnsbl, crowdsec, bunkernet,
	-- reversescan, limit, authbasic, misc, cors, workflows and antibot were all skipped. Nothing
	-- released that bypass after issuance because nothing armed it in the first place.
	if
		self.variables["LETS_ENCRYPT_PASSTHROUGH"] ~= "no"
		or self.variables["AUTO_LETS_ENCRYPT"] ~= "yes"
		or self.variables["LETS_ENCRYPT_CHALLENGE"] ~= "http"
		or sub(self.ctx.bw.uri, 1, #ACME_CHALLENGE_PREFIX) ~= ACME_CHALLENGE_PREFIX
	then
		return self:ret(true, "success")
	end
	-- RELEASED as soon as certbot-cleanup.py removes the token. The file has to be there for the
	-- validation to succeed at all -- certbot-auth.py writes it to every instance before telling
	-- the ACME server to come and get it -- so requiring it costs the legitimate flow nothing and
	-- keeps the prefix behind the full access chain for the ~89 days between renewals. A miss is
	-- not a refusal either: the request simply carries on through the chain, and the location
	-- still serves the file if it is there. Same charset gate as api(), for the same reason.
	local token = sub(self.ctx.bw.uri, #ACME_CHALLENGE_PREFIX + 1)
	if not match(token, ACME_TOKEN_PATTERN) then
		return self:ret(true, "not an ACME token")
	end
	local file = open(ACME_CHALLENGE_DIR .. token, "r")
	if not file then
		return self:ret(true, "no challenge pending for this token")
	end
	file:close()
	self.logger:log(NOTICE, "got a visit from Let's Encrypt, let's whitelist it")
	return self:ret(true, "visit from LE", OK)
end

-- luacheck: ignore 212
function letsencrypt:api()
	if
		not match(self.ctx.bw.uri, "^/lets%-encrypt/challenge$")
		or (self.ctx.bw.request_method ~= "POST" and self.ctx.bw.request_method ~= "DELETE")
	then
		return self:ret(false, "success")
	end
	local ngx_req = ngx.req
	ngx_req.read_body()
	local ret, data = pcall(decode, ngx_req.get_body_data())
	if not ret then
		return self:ret(true, "json body decoding failed", HTTP_BAD_REQUEST)
	end
	if type(data) ~= "table" or type(data.token) ~= "string" or not match(data.token, ACME_TOKEN_PATTERN) then
		return self:ret(true, "invalid challenge token", HTTP_BAD_REQUEST)
	end
	execute("mkdir -p " .. ACME_CHALLENGE_DIR)
	if self.ctx.bw.request_method == "POST" then
		if type(data.validation) ~= "string" then
			return self:ret(true, "invalid challenge validation", HTTP_BAD_REQUEST)
		end
		local file, err = open(ACME_CHALLENGE_DIR .. data.token, "w+")
		if not file then
			return self:ret(true, "can't write validation token : " .. err, HTTP_INTERNAL_SERVER_ERROR)
		end
		file:write(data.validation)
		file:close()
		return self:ret(true, "validation token written", HTTP_OK)
	elseif self.ctx.bw.request_method == "DELETE" then
		local ok, err = remove(ACME_CHALLENGE_DIR .. data.token)
		if not ok then
			return self:ret(true, "can't remove validation token : " .. err, HTTP_INTERNAL_SERVER_ERROR)
		end
		return self:ret(true, "validation token removed", HTTP_OK)
	end
	return self:ret(true, "unknown request", HTTP_NOT_FOUND)
end

return letsencrypt
