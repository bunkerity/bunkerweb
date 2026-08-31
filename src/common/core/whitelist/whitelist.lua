local class = require "middleclass"
local env = require "resty.env"
local ipmatcher = require "resty.ipmatcher"
local plugin = require "bunkerweb.plugin"
local rules = require "bunkerweb.rules"
local utils = require "bunkerweb.utils"

local whitelist = class("whitelist", plugin)

local ngx = ngx
local ERR = ngx.ERR
local INFO = ngx.INFO
local OK = ngx.OK
local WARN = ngx.WARN
local get_phase = ngx.get_phase
local has_variable = utils.has_variable
local get_ips = utils.get_ips
local get_rdns = utils.get_rdns
local regex_match = utils.regex_match
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local deduplicate_list = utils.deduplicate_list
local ipmatcher_new = ipmatcher.new
local tostring = tostring
local open = io.open
local env_set = env.set

function whitelist:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "whitelist", ctx)
	-- Decode lists
	if get_phase() ~= "init" and self:is_needed() then
		local internalstore_lists, err =
			self.internalstore:get("plugin_whitelist_lists_" .. self.ctx.bw.server_name, true)
		if not internalstore_lists then
			self.logger:log(ERR, err)
			self.lists = {}
		else
			-- Create a deep copy to avoid modifying the shared internalstore reference
			self.lists = {}
			for kind, list in pairs(internalstore_lists) do
				self.lists[kind] = {}
				for _, item in ipairs(list) do
					table.insert(self.lists[kind], item)
				end
			end
		end
		local kinds = {
			["IP"] = {},
			["RDNS"] = {},
			["ASN"] = {},
			["USER_AGENT"] = {},
			["URI"] = {},
		}
		for kind, _ in pairs(kinds) do
			if not self.lists[kind] then
				self.lists[kind] = {}
			end
			for data in self.variables["WHITELIST_" .. kind]:gmatch("%S+") do
				if data ~= "" then
					table.insert(self.lists[kind], data)
				end
			end
			self.lists[kind] = deduplicate_list(self.lists[kind])
		end
		-- Composite rules, parsed once in init(). for_server() merges the scopes the way
		-- utils.get_variable does: a global rule holds unless the service declared that key.
		self.rules = {}
		local all_rules, rules_err = self.internalstore:get("plugin_whitelist_rules", true)
		if not all_rules then
			-- Throttled: the key is missing only when init() did not run for this subsystem,
			-- which is a per-request condition, not a per-request event.
			self:log_throttled(ERR, "missing_rules", "can't get whitelist rules : " .. rules_err)
		else
			self.rules = rules.for_server(all_rules, self.ctx.bw.server_name)
		end
	end
end

function whitelist:is_needed()
	-- Loading case
	if self.is_loading then
		return false
	end
	-- Request phases (no default)
	if self.is_request and (self.ctx.bw.server_name ~= "_") then
		return self.variables["USE_WHITELIST"] == "yes"
	end
	-- Other cases : at least one service uses it
	local is_needed, err = has_variable("USE_WHITELIST", "yes")
	if is_needed == nil then
		self.logger:log(ERR, "can't check USE_WHITELIST variable : " .. err)
	end
	return is_needed
end

function whitelist:init()
	-- Check if init is needed
	if not self:is_needed() then
		return self:ret(true, "init not needed")
	end

	-- Read whitelists
	local whitelists = {
		["IP"] = {},
		["RDNS"] = {},
		["ASN"] = {},
		["USER_AGENT"] = {},
		["URI"] = {},
	}

	local server_name, err = get_variable("SERVER_NAME", false)
	if not server_name then
		return self:ret(false, "can't get SERVER_NAME variable : " .. err)
	end

	-- Iterate over each kind and server
	local i = 0
	for key in server_name:gmatch("%S+") do
		for kind, _ in pairs(whitelists) do
			-- <KIND>.list is written by whitelist-download.py out of WHITELIST_<KIND>_URLS and by
			-- nothing else, so the setting is what makes the file meaningful -- not its presence on
			-- disk. Loading it unconditionally kept a *withdrawn* list enforced: the job cache
			-- directory is shared between push-configs and the download jobs, both dispatched in
			-- the same batch, so a push that tars the directory while the download job is still
			-- retiring the file ships the retired list to every instance and the next reload reads
			-- it back. Bind the file to the setting that produced it and the debris is inert.
			local urls = get_variable("WHITELIST_" .. kind .. "_URLS", true, { bw = { server_name = key } })
			local f = nil
			if urls and urls:match("%S") then
				f = open("/var/cache/bunkerweb/whitelist/" .. key .. "/" .. kind .. ".list", "r")
			end
			if f then
				for line in f:lines() do
					if line ~= "" then
						table.insert(whitelists[kind], line)
						i = i + 1
					end
				end
				f:close()
			end
			-- Merge the manually configured entries. The stored lists are what
			-- utils.is_ip_whitelisted and the default server read, and without this they
			-- only ever contain what the URL download job wrote.
			local setting = get_variable("WHITELIST_" .. kind, true, { bw = { server_name = key } })
			if setting then
				for data in setting:gmatch("%S+") do
					table.insert(whitelists[kind], data)
					i = i + 1
				end
			end
			whitelists[kind] = deduplicate_list(whitelists[kind])
		end

		-- Load service specific ones into internalstore
		local ok
		ok, err = self.internalstore:set("plugin_whitelist_lists_" .. key, whitelists, nil, true)
		if not ok then
			return self:ret(false, "can't store whitelist " .. key .. " list into internalstore : " .. err)
		end

		self.logger:log(
			INFO,
			"successfully loaded " .. tostring(i) .. " IP/network/rDNS/ASN/User-Agent/URI for the service: " .. key
		)

		i = 0
		whitelists = {
			["IP"] = {},
			["RDNS"] = {},
			["ASN"] = {},
			["USER_AGENT"] = {},
			["URI"] = {},
		}
	end

	-- Composite rules : parsed here, once per configuration load, never per request.
	local ok, rules_err = self:init_rules()
	if not ok then
		return self:ret(false, rules_err)
	end

	return self:ret(true, "successfully loaded all IP/network/rDNS/ASN/User-Agent/URI")
end

-- Parse the WHITELIST_RULE_<n> family for every scope and store it in the internalstore.
-- A rule that does not parse is dropped with an error : the others still apply, and refusing
-- to load the whole configuration over one bad row would take the service down.
function whitelist:init_rules()
	local variables, err = get_multiple_variables({ "WHITELIST_RULE" })
	if variables == nil then
		return false, err
	end
	local data = {}
	local count = 0
	for scope, scoped_vars in pairs(variables) do
		local parsed, errors = rules.parse_family(scoped_vars, "WHITELIST_RULE")
		for _, parse_err in ipairs(errors) do
			self.logger:log(ERR, "invalid whitelist rule for " .. scope .. " : " .. parse_err)
		end
		for _, warning in ipairs(rules.warnings(parsed)) do
			self.logger:log(WARN, "whitelist rule for " .. scope .. " : " .. warning)
		end
		if #parsed > 0 then
			data[scope] = parsed
			count = count + #parsed
		end
	end
	local ok
	ok, err = self.internalstore:set("plugin_whitelist_rules", data, nil, true)
	if not ok then
		return false, "can't store whitelist rules into internalstore : " .. err
	end
	if count > 0 then
		self.logger:log(INFO, "successfully loaded " .. tostring(count) .. " whitelist rule(s)")
	end
	return true
end

function whitelist:set()
	local ngx_var = ngx.var
	-- Set default value
	ngx_var.is_whitelisted = "no"
	self.ctx.bw.is_whitelisted = "no"
	env_set("is_whitelisted", "no")
	-- Check if set is needed
	if not self:is_needed() then
		return self:ret(true, "whitelist not activated")
	end
	-- Check cache
	local whitelisted, err = self:check_cache()
	if whitelisted == nil then
		return self:ret(false, err)
	elseif whitelisted then
		ngx_var.is_whitelisted = "yes"
		self.ctx.bw.is_whitelisted = "yes"
		env_set("is_whitelisted", "yes")
		return self:ret(true, err)
	end
	return self:ret(true, "not in whitelist cache")
end

function whitelist:access()
	-- Check if access is needed
	if not self:is_needed() then
		return self:ret(true, "whitelist not activated")
	end
	-- Check cache
	local ngx_var = ngx.var
	local whitelisted, err, already_cached = self:check_cache()
	if whitelisted == nil then
		return self:ret(false, err)
	elseif whitelisted then
		ngx_var.is_whitelisted = "yes"
		self.ctx.bw.is_whitelisted = "yes"
		env_set("is_whitelisted", "yes")
		self:set_metric("counters", "passed_whitelist", 1)
		return self:ret(true, err, OK)
	end
	-- Perform checks
	local ok
	for k, _ in pairs(already_cached) do
		if not already_cached[k] then
			ok, whitelisted = self:is_whitelisted(k)
			if ok == nil then
				self.logger:log(ERR, "error while checking if " .. k .. " is whitelisted : " .. whitelisted)
			else
				ok, err = self:add_to_cache(self:kind_to_ele(k), whitelisted)
				if not ok then
					self.logger:log(ERR, "error while adding element to cache : " .. err)
				end
				if whitelisted ~= "ok" then
					ngx_var.is_whitelisted = "yes"
					self.ctx.bw.is_whitelisted = "yes"
					env_set("is_whitelisted", "yes")
					self:set_metric("counters", "passed_whitelist", 1)
					return self:ret(true, k .. " is whitelisted (info : " .. whitelisted .. ")", OK)
				end
			end
		end
	end
	-- Composite rules, after the flat pass : the flat lists are cheaper and already cached,
	-- and a rule can only ever add a match (rules are OR'd with the lists and with each other).
	local matched = self:match_rules()
	if matched then
		ngx_var.is_whitelisted = "yes"
		self.ctx.bw.is_whitelisted = "yes"
		env_set("is_whitelisted", "yes")
		self:set_metric("counters", "passed_whitelist", 1)
		return self:ret(true, "rule " .. matched.id .. " matched (" .. matched.text .. ")", OK)
	end

	-- Not whitelisted
	return self:ret(true, "not whitelisted")
end

-- Fold the composite rules over this request. Term truths go through the same cachestore the
-- flat pass uses, under their own `rule_term:` namespace : a term's truth is cached, a rule's
-- verdict never is, so two rules disagreeing over one term cannot poison each other.
function whitelist:match_rules()
	if not self.rules or #self.rules == 0 then
		return nil
	end
	return rules.evaluate(self.rules, {
		ctx = self.ctx,
		logger = self.logger,
		rdns_global = self.variables["WHITELIST_RDNS_GLOBAL"] == "yes",
		rdns_forward_confirm = true,
		cache_get = function(key)
			local ok, cached = self:is_in_cache(key)
			if not ok then
				self.logger:log(ERR, "error while checking rule term cache : " .. cached)
				return nil
			elseif cached == "1" then
				return true
			elseif cached == "0" then
				return false
			end
			return nil
		end,
		cache_set = function(key, truth)
			local ok, err = self:add_to_cache(key, truth and "1" or "0")
			if not ok then
				self.logger:log(ERR, "error while caching rule term : " .. err)
			end
		end,
	})
end

function whitelist:preread()
	return self:access()
end

function whitelist:kind_to_ele(kind)
	if kind == "IP" then
		return "ip" .. self.ctx.bw.remote_addr
	elseif kind == "UA" then
		return "ua" .. self.ctx.bw.http_user_agent
	elseif kind == "URI" then
		return "uri" .. self.ctx.bw.uri
	end
end

function whitelist:check_cache()
	-- Check the caches
	local checks = {
		["IP"] = "ip" .. self.ctx.bw.remote_addr,
	}
	if self.ctx.bw.http_user_agent then
		checks["UA"] = "ua" .. self.ctx.bw.http_user_agent
	end
	if self.ctx.bw.uri then
		checks["URI"] = "uri" .. self.ctx.bw.uri
	end
	local already_cached = {}
	for k, _ in pairs(checks) do
		already_cached[k] = false
	end
	for k, v in pairs(checks) do
		local ok, cached = self:is_in_cache(v)
		if not ok then
			self.logger:log(ERR, "error while checking cache : " .. cached)
		elseif cached and cached ~= "ok" then
			return true, k .. " is in cached whitelist (info : " .. cached .. ")"
		end
		if ok and cached then
			already_cached[k] = true
		end
	end
	-- Check lists
	if not self.lists then
		return nil, "lists is nil"
	end
	-- Not cached/whitelisted
	return false, "not cached/whitelisted", already_cached
end

function whitelist:is_in_cache(ele)
	local ok, data = self.cachestore_local:get("plugin_whitelist_" .. self.ctx.bw.server_name .. ele)
	if not ok then
		return false, data
	end
	return true, data
end

function whitelist:add_to_cache(ele, value)
	local ok, err = self.cachestore_local:set("plugin_whitelist_" .. self.ctx.bw.server_name .. ele, value, 86400)
	if not ok then
		return false, err
	end
	return true
end

function whitelist:is_whitelisted(kind)
	if kind == "IP" then
		return self:is_whitelisted_ip()
	elseif kind == "URI" then
		return self:is_whitelisted_uri()
	elseif kind == "UA" then
		return self:is_whitelisted_ua()
	end
	return false, "unknown kind " .. kind
end

function whitelist:is_whitelisted_ip()
	-- Check if IP is in whitelist
	local ipm, err = ipmatcher_new(self.lists["IP"])
	if not ipm then
		return nil, err
	end
	local match, err = ipm:match(self.ctx.bw.remote_addr)
	if err then
		return nil, err
	end
	if match then
		return true, "ip"
	end

	-- Check if rDNS is needed
	local check_rdns = true
	if self.variables["WHITELIST_RDNS_GLOBAL"] == "yes" and not self.ctx.bw.ip_is_global then
		check_rdns = false
	end
	if check_rdns then
		-- Get rDNS
		-- luacheck: ignore 421
		local rdns_list, err = get_rdns(self.ctx.bw.remote_addr, self.ctx, true)
		-- Check if rDNS is in whitelist
		if rdns_list then
			local forward_check = nil
			local rdns_suffix = nil
			for _, rdns in ipairs(rdns_list) do
				for _, suffix in ipairs(self.lists["RDNS"]) do
					if rdns:sub(-#suffix) == suffix then
						forward_check = rdns
						rdns_suffix = suffix
						break
					end
				end
				if forward_check then
					break
				end
			end
			if forward_check then
				local ip_list, err = get_ips(forward_check, nil, self.ctx, true)
				if ip_list then
					for _, ip in ipairs(ip_list) do
						if ip == self.ctx.bw.remote_addr then
							return true, "rDNS " .. rdns_suffix
						end
					end
					self.logger:log(
						WARN,
						"IP " .. self.ctx.bw.remote_addr .. " may spoof reverse DNS " .. forward_check
					)
				else
					self.logger:log(ERR, "error while getting rdns (forward check) : " .. err)
				end
			end
		else
			self.logger:log(ERR, "error while getting rdns : " .. err)
		end
	end

	-- Check if ASN is in whitelist
	if self.ctx.bw.ip_is_global then
		local asn = self.ctx.bw.asn_number
		if not asn then
			self.logger:log(ERR, "can't get ASN of IP " .. self.ctx.bw.remote_addr)
		else
			for _, bl_asn in ipairs(self.lists["ASN"]) do
				if bl_asn == tostring(asn) then
					return true, "ASN " .. bl_asn
				end
			end
		end
	end

	-- Not whitelisted
	return false, "ok"
end

function whitelist:is_whitelisted_uri()
	-- Check if URI is in whitelist
	for _, uri in ipairs(self.lists["URI"]) do
		if regex_match(self.ctx.bw.uri, uri) then
			return true, "URI " .. uri
		end
	end
	-- URI is not whitelisted
	return false, "ok"
end

function whitelist:is_whitelisted_ua()
	-- Check if UA is in whitelist
	for _, ua in ipairs(self.lists["USER_AGENT"]) do
		if regex_match(self.ctx.bw.http_user_agent, ua) then
			return true, "UA " .. ua
		end
	end
	-- UA is not whiteklisted
	return false, "ok"
end

return whitelist
