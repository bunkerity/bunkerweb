local class = require "middleclass"
local ipmatcher = require "resty.ipmatcher"
local plugin = require "bunkerweb.plugin"
local rules = require "bunkerweb.rules"
local utils = require "bunkerweb.utils"

local blacklist = class("blacklist", plugin)

local ngx = ngx
local ERR = ngx.ERR
local INFO = ngx.INFO
local WARN = ngx.WARN
local get_phase = ngx.get_phase
local has_variable = utils.has_variable
local get_deny_status = utils.get_deny_status
local get_rdns = utils.get_rdns
local rdns_forward_confirmed = utils.rdns_forward_confirmed
local regex_match = utils.regex_match
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local deduplicate_list = utils.deduplicate_list
local ipmatcher_new = ipmatcher.new
local tostring = tostring
local open = io.open

-- A community list id is "<prefix>:<name>" and blacklist-download.py maps that prefix onto the
-- kind whose <KIND>.list the download lands in. The guard in init() needs the same mapping,
-- because the community lists are a SECOND producer of those files: BLACKLIST_COMMUNITY_LISTS
-- defaults to a non-empty value, so on a stock configuration IP.list and USER_AGENT.list exist
-- with no BLACKLIST_*_URLS set at all. Gating on the URLs alone would silently disable the
-- default community blocklists.
-- KEEP IN SYNC with blacklist-download.py: the COMMUNITY_LISTS table at :61 and the prefix chains
-- at :102 (multisite) / :135 (singlesite). If an entry with a NEW prefix is ever added to that
-- table, it has to be added here too -- the job would route it to a kind this map does not know,
-- and that kind's file would stop being read.
local COMMUNITY_PREFIX_KIND = {
	ip = "IP",
	ua = "USER_AGENT",
	rdns = "RDNS",
	asn = "ASN",
	uri = "URI",
}

-- The same literal blacklist-download.py passes to getenv(). It matters when the setting is
-- missing from variables.env entirely: "absent" has to mean "the job used its default", never
-- "nothing produces these files".
local COMMUNITY_LISTS_DEFAULT = "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"

-- Set of kinds the community lists configured for `server` produce a file for.
local function community_kinds(server)
	local setting = get_variable("BLACKLIST_COMMUNITY_LISTS", true, { bw = { server_name = server } })
	if setting == nil then
		setting = COMMUNITY_LISTS_DEFAULT
	end
	local kinds = {}
	for id in setting:gmatch("%S+") do
		-- No fallback kind, on purpose. The job's `else: kind = "IP"` reads like one but is not:
		-- it sits INSIDE `if community_id in COMMUNITY_LISTS` (blacklist-download.py:100), so an
		-- id the job does not recognise -- a typo, a list since removed -- only earns a warning
		-- (:118 multisite, :151 singlesite) and produces no file at all. Mapping such an id to IP
		-- here would mark IP.list live while the job wrote nothing, and a retired IP.list would go
		-- on being enforced -- reopening the very hole this guard closes, for the price of one
		-- typo in BLACKLIST_COMMUNITY_LISTS. An unrecognised prefix means no producer, as in the job.
		-- Known limit: the match is on the PREFIX, not on the whole id, so a typo that keeps a
		-- valid prefix ("ip:danmuek-tor-exit") still marks IP as produced and would keep a retired
		-- IP.list live. Closing that needs the four ids of blacklist-download.py's COMMUNITY_LISTS
		-- duplicated here, which trades this narrow case for a worse one -- a list added on the
		-- Python side only would stop being read, i.e. a live blocklist silently dropped. Upgrade
		-- path if it ever matters: duplicate the ids AND add a test asserting the two tables match.
		local prefix = id:match("^([^:]+):")
		local kind = prefix and COMMUNITY_PREFIX_KIND[prefix:lower()]
		if kind then
			kinds[kind] = true
		end
	end
	return kinds
end

function blacklist:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "blacklist", ctx)
	-- Decode lists
	if get_phase() ~= "init" and self:is_needed() then
		local internalstore_lists, err =
			self.internalstore:get("plugin_blacklist_lists_" .. self.ctx.bw.server_name, true)
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
			["IGNORE_IP"] = {},
			["IGNORE_RDNS"] = {},
			["IGNORE_ASN"] = {},
			["IGNORE_USER_AGENT"] = {},
			["IGNORE_URI"] = {},
		}
		for kind, _ in pairs(kinds) do
			if not self.lists[kind] then
				self.lists[kind] = {}
			end
			for data in self.variables["BLACKLIST_" .. kind]:gmatch("%S+") do
				if data ~= "" then
					table.insert(self.lists[kind], data)
				end
			end
			self.lists[kind] = deduplicate_list(self.lists[kind])
		end
		-- Composite rules, parsed once in init(). for_server() merges the scopes the way
		-- utils.get_variable does: a global rule holds unless the service declared that key.
		self.rules = {}
		local all_rules, rules_err = self.internalstore:get("plugin_blacklist_rules", true)
		if not all_rules then
			-- Throttled: the key is missing only when init() did not run for this subsystem,
			-- which is a per-request condition, not a per-request event.
			self:log_throttled(ERR, "missing_rules", "can't get blacklist rules : " .. rules_err)
		else
			self.rules = rules.for_server(all_rules, self.ctx.bw.server_name)
		end
	end
end

function blacklist:is_needed()
	-- Loading case
	if self.is_loading then
		return false
	end
	-- Request phases (no default)
	if self.is_request and (self.ctx.bw.server_name ~= "_") then
		return self.variables["USE_BLACKLIST"] == "yes"
	end
	-- Other cases : at least one service uses it
	local is_needed, err = has_variable("USE_BLACKLIST", "yes")
	if is_needed == nil then
		self.logger:log(ERR, "can't check USE_BLACKLIST variable : " .. err)
	end
	return is_needed
end

function blacklist:init()
	-- Check if init is needed
	if not self:is_needed() then
		return self:ret(true, "init not needed")
	end

	-- Read blacklists
	local blacklists = {
		["IP"] = {},
		["RDNS"] = {},
		["ASN"] = {},
		["USER_AGENT"] = {},
		["URI"] = {},
		["IGNORE_IP"] = {},
		["IGNORE_RDNS"] = {},
		["IGNORE_ASN"] = {},
		["IGNORE_USER_AGENT"] = {},
		["IGNORE_URI"] = {},
	}

	local server_name, err = get_variable("SERVER_NAME", false)
	if not server_name then
		return self:ret(false, "can't get SERVER_NAME variable : " .. err)
	end

	-- Iterate over each kind and server
	local i = 0
	for key in server_name:gmatch("%S+") do
		local from_community = community_kinds(key)
		for kind, _ in pairs(blacklists) do
			-- <KIND>.list only exists because something asked for it: BLACKLIST_<KIND>_URLS, or a
			-- BLACKLIST_COMMUNITY_LISTS entry that maps to this kind. Bind the file to the union of
			-- its producers rather than to its presence on disk -- a list withdrawn from the
			-- configuration used to stay enforced, because push-configs tars /var/cache/bunkerweb
			-- while the download job is still retiring the file and ships it to every instance.
			-- The IGNORE_* kinds have no community producer (the prefix mapping never yields one),
			-- so for them this is a URLs-only guard.
			local urls = get_variable("BLACKLIST_" .. kind .. "_URLS", true, { bw = { server_name = key } })
			local f = nil
			if (urls and urls:match("%S")) or from_community[kind] then
				f = open("/var/cache/bunkerweb/blacklist/" .. key .. "/" .. kind .. ".list", "r")
			end
			if f then
				for line in f:lines() do
					if line ~= "" then
						table.insert(blacklists[kind], line)
						i = i + 1
					end
				end
				f:close()
			end
			blacklists[kind] = deduplicate_list(blacklists[kind])
		end

		-- Load service specific ones into internalstore
		local ok
		ok, err = self.internalstore:set("plugin_blacklist_lists_" .. key, blacklists, nil, true)
		if not ok then
			return self:ret(false, "can't store blacklist " .. key .. " list into internalstore : " .. err)
		end

		self.logger:log(
			INFO,
			"successfully loaded " .. tostring(i) .. " IP/network/rDNS/ASN/User-Agent/URI for the service: " .. key
		)

		i = 0
		blacklists = {
			["IP"] = {},
			["RDNS"] = {},
			["ASN"] = {},
			["USER_AGENT"] = {},
			["URI"] = {},
			["IGNORE_IP"] = {},
			["IGNORE_RDNS"] = {},
			["IGNORE_ASN"] = {},
			["IGNORE_USER_AGENT"] = {},
			["IGNORE_URI"] = {},
		}
	end

	-- Composite rules : parsed here, once per configuration load, never per request.
	local ok, rules_err = self:init_rules()
	if not ok then
		return self:ret(false, rules_err)
	end

	return self:ret(true, "successfully loaded all IP/network/rDNS/ASN/User-Agent/URI")
end

-- Parse the BLACKLIST_RULE_<n> family for every scope and store it in the internalstore.
-- A rule that does not parse is dropped with an error : the others still apply, and refusing
-- to load the whole configuration over one bad row would take the service down.
function blacklist:init_rules()
	local variables, err = get_multiple_variables({ "BLACKLIST_RULE" })
	if variables == nil then
		return false, err
	end
	local data = {}
	local count = 0
	for scope, scoped_vars in pairs(variables) do
		local parsed, errors = rules.parse_family(scoped_vars, "BLACKLIST_RULE")
		for _, parse_err in ipairs(errors) do
			self.logger:log(ERR, "invalid blacklist rule for " .. scope .. " : " .. parse_err)
		end
		for _, warning in ipairs(rules.warnings(parsed)) do
			self.logger:log(WARN, "blacklist rule for " .. scope .. " : " .. warning)
		end
		if #parsed > 0 then
			data[scope] = parsed
			count = count + #parsed
		end
	end
	local ok
	ok, err = self.internalstore:set("plugin_blacklist_rules", data, nil, true)
	if not ok then
		return false, "can't store blacklist rules into internalstore : " .. err
	end
	if count > 0 then
		self.logger:log(INFO, "successfully loaded " .. tostring(count) .. " blacklist rule(s)")
	end
	return true
end

function blacklist:access()
	-- Check if access is needed
	if not self:is_needed() then
		return self:ret(true, "access not needed")
	end
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
	local already_cached = {
		["IP"] = false,
		["URI"] = false,
		["UA"] = false,
	}
	for k, v in pairs(checks) do
		local ok, cached = self:is_in_cache(v)
		if not ok then
			self.logger:log(ERR, "error while checking cache : " .. cached)
		elseif cached and cached ~= "ok" then
			local data = self:get_data(cached)
			self:set_metric("counters", "failed_" .. data.id, 1)
			return self:ret(
				true,
				k .. " is in cached blacklist (info : " .. cached .. ")",
				get_deny_status(),
				nil,
				data
			)
		end
		if ok and cached then
			already_cached[k] = true
		end
	end
	-- Check lists
	if not self.lists then
		return self:ret(false, "lists is nil")
	end
	-- Perform checks
	for k, _ in pairs(checks) do
		if not already_cached[k] then
			local ok, blacklisted = self:is_blacklisted(k)
			if ok == nil then
				self.logger:log(ERR, "error while checking if " .. k .. " is blacklisted : " .. blacklisted)
			else
				-- luacheck: ignore 421
				local ok, err = self:add_to_cache(self:kind_to_ele(k), blacklisted)
				if not ok then
					self.logger:log(ERR, "error while adding element to cache : " .. err)
				end
				if blacklisted ~= "ok" then
					local data = self:get_data(blacklisted)
					self:set_metric("counters", "failed_" .. data.id, 1)
					return self:ret(
						true,
						k .. " is blacklisted (info : " .. blacklisted .. ")",
						get_deny_status(),
						nil,
						data
					)
				end
			end
		end
	end

	-- Composite rules, after the flat pass : the flat lists are cheaper and already cached,
	-- and a rule can only ever add a match (rules are OR'd with the lists and with each other).
	local matched = self:match_rules()
	if matched then
		-- Ignore lists apply to a rule verdict exactly as they apply to a flat-list one: per
		-- kind. The flat pass suppresses per kind (IGNORE_IP shields the IP check only), so a
		-- rule is waived only by an ignore whose kind it actually tests -- see is_ignored().
		local ignored, ignore_reason = self:is_ignored(matched)
		if ignored then
			self.logger:log(INFO, "rule " .. matched.id .. " matched but request is ignored (" .. ignore_reason .. ")")
		else
			local data = { id = "rule", rule = matched.text }
			self:set_metric("counters", "failed_rule", 1)
			return self:ret(
				true,
				"rule " .. matched.id .. " matched (" .. matched.text .. ")",
				get_deny_status(),
				nil,
				data
			)
		end
	end

	-- Return
	return self:ret(true, "not blacklisted")
end

-- Fold the composite rules over this request. Term truths go through the same cachestore the
-- flat pass uses, under their own `rule_term:` namespace : a term's truth is cached, a rule's
-- verdict never is, so two rules disagreeing over one term cannot poison each other.
function blacklist:match_rules()
	if not self.rules or #self.rules == 0 then
		return nil
	end
	return rules.evaluate(self.rules, {
		ctx = self.ctx,
		logger = self.logger,
		rdns_global = self.variables["BLACKLIST_RDNS_GLOBAL"] == "yes",
		-- No forward confirmation, mirroring the flat BLACKLIST_RDNS pass : spoofing a PTR
		-- into a deny list is not an attack, and requiring the forward lookup would let an
		-- IP with no A record out of the rule. Safe to differ from greylist/whitelist because
		-- is_in_cache/add_to_cache prefix every key with "plugin_blacklist_<server>", so this
		-- looser rDNS answer can never land in a slot they read.
		rdns_forward_confirm = false,
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

-- True when a BLACKLIST_IGNORE_* entry **of a kind the matched rule actually tests** matches
-- this request. Only ever called after a rule matched, so the rDNS lookup it may trigger is
-- paid on the deny path alone.
--
-- Scope is a security property, not a nicety. The flat pass suppresses per kind : IGNORE_URI
-- shields the URI check and nothing else (is_blacklisted_uri), IGNORE_IP shields the IP/rDNS/ASN
-- checks (is_blacklisted_ip), IGNORE_USER_AGENT shields the UA check (is_blacklisted_ua). Waiving
-- a rule on ANY ignore entry would be strictly weaker than the flat lists it mirrors : with
-- BLACKLIST_RULE_1 = "ip:203.0.113.0/24 AND country:CN" and BLACKLIST_IGNORE_URI = "^/static",
-- every request to /static bypasses the rule -- and the URI is attacker-chosen, so the deny is
-- one path away from off. Only an ignore whose kind appears among the rule's terms may waive it.
--
-- `country:` has no ignore counterpart (there is no BLACKLIST_IGNORE_COUNTRY), so a rule made
-- only of country terms is never waived. That is the fail-closed side and it matches the flat
-- lists, which have no country list either.
--
-- Each block below mirrors the flat pass's own ignore block; they are copies on purpose (the
-- flat ones are entangled with their list checks and cannot be called for the ignore half
-- alone). Originals, keep in sync : IGNORE_IP + IGNORE_RDNS + IGNORE_ASN in
-- is_blacklisted_ip(), IGNORE_URI in is_blacklisted_uri(), IGNORE_USER_AGENT in
-- is_blacklisted_ua().
--
-- @param rule the matched rule ({id, text, terms}) whose term kinds bound the scope
function blacklist:is_ignored(rule)
	local kinds = {}
	for _, term in ipairs(rule.terms) do
		kinds[term.kind] = true
	end

	if kinds.ip then
		local ipm, err = ipmatcher_new(self.lists["IGNORE_IP"])
		if not ipm then
			self.logger:log(ERR, "error while instantiating ignore ipmatcher : " .. err)
		else
			local match, match_err = ipm:match(self.ctx.bw.remote_addr)
			if match_err then
				self.logger:log(ERR, "error while matching ignore ip : " .. match_err)
			elseif match then
				return true, "ignore ip"
			end
		end
	end

	if kinds.asn and self.ctx.bw.ip_is_global then
		local asn = self.ctx.bw.asn_number
		if asn then
			for _, ignore_asn in ipairs(self.lists["IGNORE_ASN"]) do
				if ignore_asn == tostring(asn) then
					return true, "ignore ASN " .. ignore_asn
				end
			end
		end
	end

	if kinds.ua and self.ctx.bw.http_user_agent then
		for _, ignore_ua in ipairs(self.lists["IGNORE_USER_AGENT"]) do
			if regex_match(self.ctx.bw.http_user_agent, ignore_ua) then
				return true, "ignore UA " .. ignore_ua
			end
		end
	end

	if kinds.uri and self.ctx.bw.uri then
		for _, ignore_uri in ipairs(self.lists["IGNORE_URI"]) do
			if regex_match(self.ctx.bw.uri, ignore_uri) then
				return true, "ignore URI " .. ignore_uri
			end
		end
	end

	if kinds.rdns and #self.lists["IGNORE_RDNS"] > 0 then
		local check_rdns = true
		if self.variables["BLACKLIST_RDNS_GLOBAL"] == "yes" and not self.ctx.bw.ip_is_global then
			check_rdns = false
		end
		if check_rdns then
			local rdns_list, rdns_err = get_rdns(self.ctx.bw.remote_addr, self.ctx, true)
			if not rdns_list then
				self.logger:log(ERR, "error while getting rdns : " .. rdns_err)
			else
				-- Forward-confirmed, fail-closed : same guard the flat pass puts on its own
				-- ignore bypass, since an unconfirmed PTR here would waive a deny verdict.
				local suffix = rdns_forward_confirmed(
					rdns_list,
					self.lists["IGNORE_RDNS"],
					self.ctx,
					self.ctx.bw.remote_addr,
					self.logger
				)
				if suffix then
					return true, "ignore rDNS " .. suffix
				end
			end
		end
	end

	return false
end

function blacklist:preread()
	return self:access()
end

function blacklist:kind_to_ele(kind)
	if kind == "IP" then
		return "ip" .. self.ctx.bw.remote_addr
	elseif kind == "UA" then
		return "ua" .. self.ctx.bw.http_user_agent
	elseif kind == "URI" then
		return "uri" .. self.ctx.bw.uri
	end
end

function blacklist:is_in_cache(ele)
	local ok, data = self.cachestore_local:get("plugin_blacklist_" .. self.ctx.bw.server_name .. ele)
	if not ok then
		return false, data
	end
	return true, data
end

function blacklist:add_to_cache(ele, value)
	local ok, err = self.cachestore_local:set("plugin_blacklist_" .. self.ctx.bw.server_name .. ele, value, 86400)
	if not ok then
		return false, err
	end
	return true
end

function blacklist:is_blacklisted(kind)
	if kind == "IP" then
		return self:is_blacklisted_ip()
	elseif kind == "URI" then
		return self:is_blacklisted_uri()
	elseif kind == "UA" then
		return self:is_blacklisted_ua()
	end
	return false, "unknown kind " .. kind
end

function blacklist:is_blacklisted_ip()
	-- Check if IP is in ignore list
	local ipm, err = ipmatcher_new(self.lists["IGNORE_IP"])
	if not ipm then
		return nil, err
	end
	local match, err = ipm:match(self.ctx.bw.remote_addr)
	if err then
		return nil, err
	end
	if not match then
		-- Check if IP is in blacklist
		ipm, err = ipmatcher.new(self.lists["IP"])
		if not ipm then
			return nil, err
		end
		match, err = ipm:match(self.ctx.bw.remote_addr)
		if err then
			return nil, err
		end
		if match then
			return true, "ip"
		end
	end

	-- Check if rDNS is needed
	local check_rdns = true
	if self.variables["BLACKLIST_RDNS_GLOBAL"] == "yes" and not self.ctx.bw.ip_is_global then
		check_rdns = false
	end
	if check_rdns then
		-- Get rDNS
		-- luacheck: ignore 421
		local rdns_list, err = get_rdns(self.ctx.bw.remote_addr, self.ctx, true)
		if rdns_list then
			-- Check if rDNS is in ignore list (forward-confirmed before honoring the bypass, fail-closed)
			local ignore = rdns_forward_confirmed(
				rdns_list,
				self.lists["IGNORE_RDNS"],
				self.ctx,
				self.ctx.bw.remote_addr,
				self.logger
			) ~= nil
			-- Check if rDNS is in blacklist
			if not ignore then
				for _, rdns in ipairs(rdns_list) do
					for _, suffix in ipairs(self.lists["RDNS"]) do
						if rdns:sub(-#suffix) == suffix then
							return true, "rDNS " .. suffix
						end
					end
				end
			end
		else
			self.logger:log(ERR, "error while getting rdns : " .. err)
		end
	end

	-- Check if ASN is in ignore list
	if self.ctx.bw.ip_is_global then
		local asn = self.ctx.bw.asn_number
		if not asn then
			self.logger:log(ngx.ERR, "can't get ASN of IP " .. self.ctx.bw.remote_addr)
		else
			local ignore = false
			for _, ignore_asn in ipairs(self.lists["IGNORE_ASN"]) do
				if ignore_asn == tostring(asn) then
					ignore = true
					break
				end
			end
			-- Check if ASN is in blacklist
			if not ignore then
				for _, bl_asn in ipairs(self.lists["ASN"]) do
					if bl_asn == tostring(asn) then
						return true, "ASN " .. bl_asn
					end
				end
			end
		end
	end

	-- Not blacklisted
	return false, "ok"
end

function blacklist:is_blacklisted_uri()
	-- Check if URI is in ignore list
	local ignore = false
	for _, ignore_uri in ipairs(self.lists["IGNORE_URI"]) do
		if regex_match(self.ctx.bw.uri, ignore_uri) then
			ignore = true
			break
		end
	end
	-- Check if URI is in blacklist
	if not ignore then
		for _, uri in ipairs(self.lists["URI"]) do
			if regex_match(self.ctx.bw.uri, uri) then
				return true, "URI " .. uri
			end
		end
	end
	-- URI is not blacklisted
	return false, "ok"
end

function blacklist:is_blacklisted_ua()
	-- Check if UA is in ignore list
	local ignore = false
	for _, ignore_ua in ipairs(self.lists["IGNORE_USER_AGENT"]) do
		if regex_match(self.ctx.bw.http_user_agent, ignore_ua) then
			ignore = true
			break
		end
	end
	-- Check if UA is in blacklist
	if not ignore then
		for _, ua in ipairs(self.lists["USER_AGENT"]) do
			if regex_match(self.ctx.bw.http_user_agent, ua) then
				return true, "UA " .. ua
			end
		end
	end
	-- UA is not blacklisted
	return false, "ok"
end

-- luacheck: ignore 212
function blacklist:get_data(blacklisted)
	local data = {}
	if blacklisted:lower() == "ip" then
		data["id"] = "ip"
	else
		local id, value = blacklisted:match("^(%w+) (.+)$")
		if id and value then
			id = id:lower()
			data["id"] = id
			data[id] = value
		end
	end
	return data
end

return blacklist
