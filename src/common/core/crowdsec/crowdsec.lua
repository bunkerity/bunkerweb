local cache_partition = require("crowdsec.cache_partition")
local class = require("middleclass")
local plugin = require("bunkerweb.plugin")
local utils = require("bunkerweb.utils")

local crowdsec = class("crowdsec", plugin)

local ngx = ngx
local ERR = ngx.ERR
local WARN = ngx.WARN
local INFO = ngx.INFO
local OK = ngx.OK
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local HTTP_OK = ngx.HTTP_OK
local has_variable = utils.has_variable
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local get_deny_status = utils.get_deny_status
local get_security_mode = utils.get_security_mode
local parse_duration = utils.parse_duration
local set_reason = utils.set_reason
local open = io.open
local pairs = pairs
local ipairs = ipairs
local insert = table.insert
local sort = table.sort
local concat = table.concat
local floor = math.floor
local format = string.format
local byte = string.byte
local json = require("cjson.safe")

local USER_AGENT = "crowdsec-bunkerweb-bouncer/v1.8"
local CACHE_PATH = "/var/cache/bunkerweb/crowdsec/"
local CONF_NAME = "crowdsec.conf"
local BOUNCER_MODULE = "crowdsec.lib.bouncer"
local GLOBAL_SCOPE = "global"

-- The vendored bouncer keeps its whole configuration in a single module-level
-- runtime table, so per-service API and AppSec endpoints need one private copy of
-- the module per distinct configuration. A "current service" pointer swapped at
-- request time would race : csmod.Allow() yields on cosockets for both the LAPI
-- live query and the AppSec call, so interleaved requests on the same worker would
-- read a pointer another request moved. These instances are built once in the init
-- phase (init_by_lua, master process) and inherited by every worker on fork, so a
-- request only ever reads them.
local bouncers = {}
-- Kept in lockstep with `bouncers`: the per-service challenge namespace handed to Allow, and
-- the scopes whose configuration could not be loaded (so the health endpoint can report them
-- instead of leaving them silently unchecked until the next reload).
local challenge_prefixes = {}
local failed_scopes = {}

local function connection_id(scope, bouncer)
	local info = bouncer.ConnectionInfo()
	return cache_partition.hash(scope .. "\0" .. (info.lapi_url or "") .. "\0" .. (info.appsec_url or ""))
end

local function read_control_body()
	ngx.req.read_body()
	local body = ngx.req.get_body_data()
	if not body and ngx.req.get_body_file() then
		local file = open(ngx.req.get_body_file(), "r")
		if file then
			body = file:read(65537)
			file:close()
		end
	end
	if not body or #body > 65536 then
		return nil
	end
	local value = json.decode(body)
	if type(value) ~= "table" then
		return nil
	end
	return value
end

local function read_file(path)
	local file = open(path, "r")
	if not file then
		return nil
	end
	local content = file:read("*a")
	file:close()
	return content
end

-- require() caches by module name and would hand back one shared instance, so drop
-- the cache entry around the call to force a fresh chunk with its own runtime table.
-- Nothing else requires the bouncer, so leaving the entry cleared is safe.
local function new_bouncer()
	package.loaded[BOUNCER_MODULE] = nil
	local ok, instance = pcall(require, BOUNCER_MODULE)
	package.loaded[BOUNCER_MODULE] = nil
	if not ok then
		return nil, "can't load " .. BOUNCER_MODULE .. " : " .. tostring(instance)
	end
	return instance
end

function crowdsec:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "crowdsec", ctx)
end

function crowdsec:is_needed()
	-- Loading case
	if self.is_loading then
		return false
	end
	-- Request phases (no default)
	if self.is_request and (self.ctx.bw.server_name ~= "_") then
		return self.variables["USE_CROWDSEC"] == "yes"
	end
	-- Other cases : at least one service uses it
	local is_needed, err = has_variable("USE_CROWDSEC", "yes")
	if is_needed == nil then
		self.logger:log(ERR, "can't check USE_CROWDSEC variable : " .. err)
	end
	return is_needed
end

-- List the scopes that have CrowdSec enabled. In multisite that is one entry per
-- activated service, otherwise the single "global" scope. USE_CROWDSEC is read
-- across every scope here because the init phase resolves a multisite setting to
-- its global value, which would hide per-service activation.
local function get_scopes()
	local multisite, err = get_variable("MULTISITE", false)
	if not multisite then
		return nil, "can't get MULTISITE variable : " .. err
	end
	local variables, vars_err = get_multiple_variables({ "USE_CROWDSEC" })
	if not variables then
		return nil, "can't get USE_CROWDSEC variables : " .. vars_err
	end
	local scopes = {}
	if multisite ~= "yes" then
		if variables[GLOBAL_SCOPE] and variables[GLOBAL_SCOPE]["USE_CROWDSEC"] == "yes" then
			insert(scopes, GLOBAL_SCOPE)
		end
		return scopes
	end
	for scope, scope_variables in pairs(variables) do
		if scope ~= GLOBAL_SCOPE and scope_variables["USE_CROWDSEC"] == "yes" then
			insert(scopes, scope)
		end
	end
	-- Keep init logs stable across reloads
	sort(scopes)
	return scopes
end

-- The CrowdSec 1.8 bot-detection challenge page carries its own Content-Security-Policy
-- (AppSec always injects one, DefaultChallengeCSP if the config sets none) and needs it to
-- run its inline proof-of-work. The headers plugin keeps an upstream CSP by default -- it is
-- in KEEP_UPSTREAM_HEADERS -- but CUSTOM_HEADER and REMOVE_HEADERS are applied after that
-- loop and never consult the keep list (headers.lua), so those two can silently break a
-- challenge. Warn, do not change behaviour : the operator set those on purpose.
local CSP = "content-security-policy"

local function csp_overridden_by_headers_plugin()
	local variables, err = get_multiple_variables({ "CUSTOM_HEADER", "REMOVE_HEADERS" })
	if not variables then
		return nil, err
	end
	for _, scope_variables in pairs(variables) do
		for setting, value in pairs(scope_variables) do
			if setting == "REMOVE_HEADERS" then
				for header in value:gmatch("%S+") do
					if header:lower() == CSP then
						return "REMOVE_HEADERS"
					end
				end
			else
				-- CUSTOM_HEADER, CUSTOM_HEADER_1, ... : "Name: value", as headers:init() reads it
				local name = value:match("^%s*([%w_-]+)%s*:")
				if name and name:lower() == CSP then
					return "CUSTOM_HEADER"
				end
			end
		end
	end
	return false
end

function crowdsec:init()
	-- Check if init is needed
	if not self:is_needed() then
		return self:ret(true, "init not needed")
	end

	local scopes, err = get_scopes()
	if not scopes then
		bouncers, challenge_prefixes, failed_scopes = {}, {}, {}
		return self:ret(false, err)
	end

	-- Read every configuration first : whether the decision cache has to be partitioned
	-- depends on all of them, not on any single one.
	local failed = {}
	local loaded = {}
	local api_urls = {}
	for _, scope in ipairs(scopes) do
		local conf_file = CACHE_PATH .. (scope == GLOBAL_SCOPE and "" or (scope .. "/")) .. CONF_NAME
		local content = read_file(conf_file)
		if not content then
			insert(failed, scope)
			self.logger:log(
				ERR,
				"missing CrowdSec configuration " .. conf_file .. " for service " .. scope .. ", it will not be checked"
			)
		else
			local api_url = cache_partition.api_url(content)
			insert(loaded, { scope = scope, file = conf_file, content = content, api_url = api_url })
			insert(api_urls, api_url)
		end
	end

	local prefixes, distinct_apis = cache_partition.prefixes(api_urls)
	if not prefixes then
		-- Two Local APIs hashing to one namespace: `distinct_apis` carries the message, not a
		-- count. Reset every module-level table so a later health check cannot report stale
		-- services, and stop here -- `prefixes[entry.api_url]` below would index nil.
		bouncers, challenge_prefixes, failed_scopes = {}, {}, {}
		return self:ret(false, distinct_apis)
	end

	-- Services whose rendered configuration is byte-identical share one instance
	local by_conf = {}
	local resolved = {}
	local challenges = {}
	local instances = 0
	for _, entry in ipairs(loaded) do
		if by_conf[entry.content] then
			resolved[entry.scope] = by_conf[entry.content]
		else
			local bouncer, bouncer_err = new_bouncer()
			if not bouncer then
				insert(failed, entry.scope)
				self.logger:log(ERR, "can't create bouncer for service " .. entry.scope .. " : " .. bouncer_err)
			else
				local ok, init_err = bouncer.init(entry.file, USER_AGENT, prefixes[entry.api_url])
				if not ok then
					insert(failed, entry.scope)
					self.logger:log(
						ERR,
						"error while initializing bouncer for service " .. entry.scope .. " : " .. tostring(init_err)
					)
				else
					by_conf[entry.content] = bouncer
					resolved[entry.scope] = bouncer
					instances = instances + 1
				end
			end
		end
		if resolved[entry.scope] then
			challenges[entry.scope] =
				cache_partition.challenge_prefix(entry.scope, entry.content, resolved[entry.scope].GetCaptchaTemplate())
		end
	end

	bouncers = resolved
	challenge_prefixes = challenges
	failed_scopes = failed

	-- Only worth a line when AppSec is actually wired up : the challenge is an AppSec
	-- remediation, so without it there is no page whose CSP could matter.
	local appsec_enabled = false
	for _, entry in ipairs(loaded) do
		if entry.content:match("APPSEC_URL=%S") then
			appsec_enabled = true
			break
		end
	end
	if appsec_enabled then
		local culprit, csp_err = csp_overridden_by_headers_plugin()
		if culprit == nil then
			self.logger:log(ERR, "can't check the headers plugin settings : " .. csp_err)
		elseif culprit then
			self.logger:log(
				WARN,
				"CrowdSec AppSec is enabled and "
					.. culprit
					.. " overrides Content-Security-Policy : that path bypasses KEEP_UPSTREAM_HEADERS, so a "
					.. "CrowdSec 1.8 bot-detection challenge page would lose the CSP it ships with and fail to "
					.. "solve in the browser"
			)
		end
	end

	if instances == 0 then
		return self:ret(false, "no CrowdSec configuration could be loaded for service(s) " .. concat(failed, ", "))
	end
	-- A service that failed to load is skipped at request time, not fatal for the rest
	local msg = instances .. " bouncer(s) initialized for " .. (#scopes - #failed) .. " service(s)"
	if distinct_apis > 1 then
		msg = msg .. ", decision cache partitioned across " .. distinct_apis .. " local API(s)"
	end
	if #failed > 0 then
		msg = msg .. ", skipping service(s) " .. concat(failed, ", ")
	end
	return self:ret(true, msg)
end

-- ---- ban leases (CROWDSEC_BAN_REFRESH) -------------------------------------------------------
-- A CrowdSec `ban` that denies a request is also written as a short BunkerWeb ban, a lease: an ordinary
-- ban (reason "crowdsec") that the early ban check enforces without asking CrowdSec, and that the next
-- request after it lapses renews for as long as the decision lasts.

local MAX_DECISIONS = 10
-- The limit of db_methods/bans.py (MAX_REASON_DATA), measured on the text the database stores.
local MAX_REASON_DATA = 4096
-- Promotion refuses a lease whose identity set alone is longer, so the cap below can always keep it.
local MAX_IDENTITY = 1024
local MAX_RECENT = 1024
local PROVENANCE_FIELDS = { "id", "origin", "scenario", "type", "scope", "value", "expires_at", "remediation" }
local IDENTITY_FIELDS =
	{ "lease", "version", "lease_id", "instance", "connection", "service_scope", "remediation", "source" }
local KEPT_FIELDS = {}
for _, field in ipairs(IDENTITY_FIELDS) do
	KEPT_FIELDS[field] = true
end
local DROPPABLE_FIELDS = { "scenario", "origin", "action" }
for _, field in ipairs(DROPPABLE_FIELDS) do
	KEPT_FIELDS[field] = true
end

local function continuation_bytes(value, from, to)
	for j = from, to do
		local continuation = byte(value, j)
		if not continuation or continuation < 0x80 or continuation > 0xBF then
			return false
		end
	end
	return true
end

-- Characters Python's json.dumps writes for a string: non-ASCII is escaped (\uXXXX, a surrogate pair
-- outside the BMP), which is what the database stores and what the 4096 limit counts.
-- ponytail: invalid UTF-8 counts 6 per byte, a pessimistic guess; nothing validates overlong forms.
local function string_length(value)
	local length, i, size = 2, 1, #value
	while i <= size do
		local b = byte(value, i)
		if b < 0x80 then
			if b == 34 or b == 92 or b == 8 or b == 9 or b == 10 or b == 12 or b == 13 then
				length = length + 2
			elseif b < 32 or b == 127 then
				length = length + 6
			else
				length = length + 1
			end
			i = i + 1
		else
			local width, cost
			if b >= 0xC2 and b <= 0xDF then
				width, cost = 2, 6
			elseif b >= 0xE0 and b <= 0xEF then
				width, cost = 3, 6
			elseif b >= 0xF0 and b <= 0xF4 then
				width, cost = 4, 12
			end
			if width and not continuation_bytes(value, i + 1, i + width - 1) then
				width = nil
			end
			if width then
				length, i = length + cost, i + width
			else
				length, i = length + 6, i + 1
			end
		end
	end
	return length
end

-- Length of json.dumps(value): ", " between items, ": " between a key and its value.
local function stored_length(value)
	local kind = type(value)
	if kind == "string" then
		return string_length(value)
	elseif kind == "boolean" then
		return value and 4 or 5
	elseif kind == "number" then
		local integral = value == floor(value) and value > -2 ^ 53 and value < 2 ^ 53
		return #(integral and format("%d", value) or format("%.14g", value))
	elseif kind ~= "table" then
		return 4
	end
	local length, count = 2, 0
	if value[1] ~= nil then
		for _, item in ipairs(value) do
			length, count = length + stored_length(item) + (count > 0 and 2 or 0), count + 1
		end
	else
		for key, item in pairs(value) do
			length = length + string_length(tostring(key)) + 2 + stored_length(item) + (count > 0 and 2 or 0)
			count = count + 1
		end
	end
	return length
end
crowdsec._stored_length = stored_length

local function identity_fits(reason_data)
	local identity = {}
	for _, field in ipairs(IDENTITY_FIELDS) do
		identity[field] = reason_data[field]
	end
	return stored_length(identity) <= MAX_IDENTITY
end
crowdsec._identity_fits = identity_fits

-- Same rule and order as db_methods/bans.py `_reason_data_text`: the last decisions go first, then the
-- keys outside the identity set (largest first), then scenario, origin and action, one by one. A value is
-- dropped, never cut, and the identity set is never shortened.
local function cap_reason_data(reason_data)
	local function fits()
		return stored_length(reason_data) <= MAX_REASON_DATA
	end
	if fits() then
		return reason_data
	end
	local decisions = reason_data.decisions
	while type(decisions) == "table" and #decisions > 0 and not fits() do
		decisions[#decisions] = nil
	end
	if type(decisions) ~= "table" or #decisions == 0 then
		reason_data.decisions = nil
	end
	if fits() then
		return reason_data
	end
	local extras = {}
	for key, value in pairs(reason_data) do
		if not KEPT_FIELDS[key] then
			extras[#extras + 1] = { key = key, size = stored_length(value) }
		end
	end
	sort(extras, function(a, b)
		return a.size > b.size or (a.size == b.size and a.key < b.key)
	end)
	for _, extra in ipairs(extras) do
		reason_data[extra.key] = nil
		if fits() then
			return reason_data
		end
	end
	for _, key in ipairs(DROPPABLE_FIELDS) do
		reason_data[key] = nil
		if fits() then
			return reason_data
		end
	end
	return reason_data
end
crowdsec._cap_reason_data = cap_reason_data

local function new_lease_id()
	local random = require("resty.random")
	local raw = random.bytes(8, true) or random.bytes(8)
	if not raw then
		return nil
	end
	return (raw:gsub(".", function(char)
		return format("%02x", byte(char))
	end))
end

-- The TTL and the reason_data of the lease for this deny. The TTL is the longest live ban decision's
-- remaining time capped at the refresh, and never 0: add_ban reads 0 as permanent.
local function build_lease(verdict, evidence, now, refresh)
	if type(evidence) ~= "table" or evidence.source ~= "lapi" or verdict.action ~= "ban" then
		return nil, "not a Local API ban"
	end
	local decisions = type(evidence.decisions) == "table" and evidence.decisions or {}
	local ban_expires
	for _, decision in ipairs(decisions) do
		if
			decision.remediation == "ban"
			and decision.id ~= nil
			and type(decision.expires_at) == "number"
			and decision.expires_at > now
			and (not ban_expires or decision.expires_at > ban_expires)
		then
			ban_expires = decision.expires_at
		end
	end
	if not ban_expires then
		return nil, "no live ban decision"
	end
	local lease_id = new_lease_id()
	if not lease_id then
		return nil, "no random bytes for the lease id"
	end
	local provenance = {}
	for i = 1, math.min(#decisions, MAX_DECISIONS) do
		local row = {}
		for _, field in ipairs(PROVENANCE_FIELDS) do
			row[field] = decisions[i][field]
		end
		provenance[i] = row
	end
	return math.max(1, floor(math.min(ban_expires - now, refresh))),
		{
			lease = true,
			version = 1,
			lease_id = lease_id,
			instance = evidence.instance,
			connection = evidence.connection,
			service_scope = evidence.service_scope,
			remediation = "ban",
			source = "lapi",
			action = verdict.action,
			scenario = verdict.scenario,
			origin = verdict.origin,
			duration = verdict.duration,
			captured_at = evidence.captured_at,
			decisions = provenance,
		}
end
crowdsec._build_lease = build_lease

-- Whether a CrowdSec deny may become a lease. Pure, so each refusal is testable on its own.
-- A stream connection that stopped synchronizing never renews bans: its cached decisions may be stale.
local function should_promote(params)
	if not params.refresh or params.refresh <= 0 then
		return false, "CROWDSEC_BAN_REFRESH is 0"
	end
	if params.security_mode ~= "block" then
		return false, "security mode is not block"
	end
	if params.deferred then
		return false, "the verdict is deferred to the security workflows"
	end
	if params.served then
		return false, "the response was already served"
	end
	if params.source ~= "lapi" then
		return false, "the verdict is not from the Local API"
	end
	if params.action ~= "ban" then
		return false, "the remediation is not a ban"
	end
	if params.exclude_location then
		return false, "the service has excluded locations"
	end
	if params.mode == "stream" then
		local last, frequency = params.last_successful_sync, params.update_frequency
		if not last or not frequency or params.now - last > 2 * frequency then
			return false, "the stream synchronization is stale"
		end
	end
	return true
end
crowdsec._should_promote = should_promote

-- One promotion per scope and IP per second per worker: a burst from one attacker is one ban write.
local recent, recent_count = {}, 0

local function seen_recently(key, now)
	local at = recent[key]
	if at and now - at < 1 then
		return true
	end
	if recent_count >= MAX_RECENT then
		recent, recent_count = {}, 0
		at = nil
	end
	if not at then
		recent_count = recent_count + 1
	end
	recent[key] = now
	return false
end
crowdsec._dedupe_size = function()
	return recent_count
end

-- Promotion never changes the deny: every refusal and every failure only means no lease.
function crowdsec:promote(bouncer, scope, verdict, evidence, refresh)
	local ip = self.ctx.bw.remote_addr
	local info = bouncer.ConnectionInfo()
	local now = ngx.time()
	local promote, why = should_promote({
		refresh = refresh,
		security_mode = get_security_mode(self.ctx),
		source = verdict.source,
		action = verdict.action,
		exclude_location = bouncer.HasExcludedLocations(),
		mode = info.mode,
		last_successful_sync = info.last_successful_sync,
		update_frequency = info.update_frequency,
		now = now,
	})
	if not promote then
		return self.logger:log(INFO, "no CrowdSec ban lease : " .. why)
	end
	if seen_recently(scope .. "|" .. ip, ngx.now()) then
		return
	end
	local ttl, reason_data = build_lease(verdict, evidence, now, refresh)
	if not ttl then
		return self.logger:log(INFO, "no CrowdSec ban lease : " .. tostring(reason_data))
	end
	if not identity_fits(reason_data) then
		return self:log_throttled(
			WARN,
			"lease_identity_bound",
			"no CrowdSec ban lease for service "
				.. scope
				.. " : its identity (instance, connection, service) is over "
				.. MAX_IDENTITY
				.. " characters, the request is still denied"
		)
	end
	local country = utils.get_country(ip)
	if type(country) ~= "string" then
		country = "unknown"
	end
	-- Service-scoped in multisite, so one attacked service does not block the others (some of which may
	-- not use CrowdSec at all); global only in single-site, where the one scope is "global".
	local global = scope == GLOBAL_SCOPE
	local ok, status = utils.add_ban(
		ip,
		"crowdsec",
		ttl,
		not global and scope or nil,
		country,
		global and "global" or "service",
		cap_reason_data(reason_data),
		nil,
		{ keep_existing = true }
	)
	self.logger:log(INFO, "CrowdSec ban lease " .. (ok and "written" or "not written") .. " : " .. tostring(status))
end

function crowdsec:access()
	-- Check if CS is activated
	if not self:is_needed() then
		return self:ret(true, "CrowdSec plugin not enabled")
	end
	-- Pick the bouncer of this service, falling back to the singlesite one. The scope is kept,
	-- not just the bouncer: `challenge_prefixes` is keyed by it, and two services sharing one
	-- rendered configuration share a bouncer but never a challenge namespace.
	local scope = bouncers[self.ctx.bw.server_name] and self.ctx.bw.server_name or GLOBAL_SCOPE
	local bouncer = bouncers[scope]
	if not bouncer then
		-- Fail open rather than take the service down -- but say so, on every request.
		-- Upstream of this port returned silently here on the strength of "init() already
		-- logged why", and the init channel is precisely the one that drops NOTICE lines
		-- during init_by_lua: a request served unchecked would then leave no trace anywhere,
		-- which is how this plugin managed to be inert for a whole run without anyone
		-- noticing. Throttled to one line per minute per plugin (plugin.lua:195) so a fleet
		-- failing open cannot flood the error log. The service name goes in the message, not
		-- in the key, because the throttle table is keyed for life and must stay bounded.
		self:log_throttled(
			ERR,
			"no_bouncer",
			"no CrowdSec bouncer loaded for service "
				.. (self.ctx.bw.server_name or "?")
				.. ", request served UNCHECKED (see the init logs for why)"
		)
		return self:ret(true, "no CrowdSec bouncer loaded for this service")
	end
	-- Do the check. In detect mode the bouncer must not write a body: the dispatcher can drop a
	-- deny STATUS to honour SECURITY_MODE=detect (access-lua.conf), but it cannot un-send a
	-- challenge page. Without this, a `challenge` verdict would replace the origin's response
	-- and record no reason -- detect mode silently blocking, which is exactly what it is not.
	local detect = get_security_mode(self.ctx) == "detect"
	-- CROWDSEC_CAPTCHA_PROVIDER is handed to the bouncer, not read by it : it is what keeps a
	-- `captcha` remediation from being rewritten into FALLBACK_REMEDIATION, and it comes back as
	-- the sixth return value when the bouncer decided to delegate. Passed unconditionally -- the
	-- USE_ANTIBOT lookup that decides whether the antibot can actually answer is done below, on
	-- the delegation itself, so an ordinary request pays nothing for a feature it never reaches.
	local ok, err, banned, served, verdict, antibot_provider, evidence = bouncer.Allow(
		self.ctx.bw.remote_addr,
		detect,
		self.variables["CROWDSEC_CAPTCHA_PROVIDER"],
		challenge_prefixes[scope]
	)
	if not ok then
		-- tostring() and not a bare concatenation : a bouncer branch that forgets to return a
		-- message used to raise here, under helpers.lua's pcall, and the dispatcher then logged
		-- an ERR and served the request UNCHECKED.
		return self:ret(false, "Error while executing CrowdSec bouncer : " .. tostring(err))
	end
	-- Publish the verdict for the security-workflow engine, which runs later in the same access
	-- phase (core/order.json). Publication is unconditional and completely inert : every arm
	-- below still returns exactly what it returned before this feature existed, so a workflow
	-- can READ what CrowdSec decided without CrowdSec losing any authority. The opt-in part is
	-- the deferral further down, and only that.
	--
	-- `crowdsec_ok` is the "the bouncer answered" flag the workflow leaf needs to tell a service
	-- CrowdSec never judged (UNKNOWN) from a request CrowdSec had nothing against (FALSE). Every
	-- earlier return above -- plugin disabled, no bouncer, bouncer error -- deliberately leaves
	-- it unset.
	self.ctx.bw.crowdsec_ok = true
	if verdict then
		self.ctx.bw.crowdsec_source = verdict.source
		self.ctx.bw.crowdsec_remediation = verdict.action
	end
	if type(evidence) == "table" then
		evidence.connection = connection_id(scope, bouncer)
		evidence.service_scope = scope
		evidence.instance = ngx.var.hostname
		if verdict then
			for key, value in pairs(evidence) do
				verdict[key] = value
			end
		end
	end
	if antibot_provider then
		-- A `captcha` decision, rendered by BunkerWeb's own antibot instead of CrowdSec's captcha
		-- template. The antibot plugin runs after this one in the access phase (core/order.json), so
		-- flagging the request here is enough : antibot:access() reads the field, challenges with
		-- this provider whatever USE_ANTIBOT says, and skips the ANTIBOT_IGNORE_* lists -- the same
		-- three behaviours a workflow challenge rule asks for, which is why this reuses that field
		-- rather than adding a second one. A non-navigation request (an API call, a preflight) is
		-- denied by the antibot instead of being bounced to a page it could never complete.
		local use_antibot = get_variable("USE_ANTIBOT", true, self.ctx)
		if use_antibot == nil or use_antibot == "no" then
			-- The antibot's challenge location is only rendered for a service that has USE_ANTIBOT
			-- set or a workflow challenge rule (core/antibot/confs/server-http/antibot.conf), so
			-- flagging here would redirect the client to a 404 rather than to a challenge. Fall back
			-- to the bouncer's FALLBACK_REMEDIATION -- `ban` in the shipped misc/crowdsec.conf, which
			-- is get_deny_status() here -- exactly as this deployment behaved before the feature
			-- existed. Throttled to one line per minute (plugin.lua) : the service goes in the
			-- message, not in the key, so the throttle table stays bounded.
			self:log_throttled(
				WARN,
				"captcha_no_antibot",
				"CrowdSec asked for a captcha on service "
					.. (self.ctx.bw.server_name or "?")
					.. " but the antibot is disabled there (USE_ANTIBOT=no), so the request was banned instead : set "
					.. "USE_ANTIBOT to a challenge provider to let CROWDSEC_CAPTCHA_PROVIDER='"
					.. antibot_provider
					.. "' render the challenge, or set CROWDSEC_CAPTCHA_PROVIDER=no to keep banning silently"
			)
			-- `action` is what was APPLIED, not what CrowdSec asked for : the Reports page, the
			-- BunkerNet guard and the "ban all matching reports" filter all read it to tell a
			-- challenged visitor from a blocked one, and leaving "captcha" there would describe a
			-- banned client as merely challenged. What was asked for survives as `suppressed`.
			-- `verdict` is built by the same bouncer arm that returns `antibot_provider`, so it is
			-- never nil here. Guarded anyway: a nil index raised in the access phase is caught by
			-- helpers.lua's pcall, which logs an ERR and serves the request UNCHECKED -- a fail-open
			-- in the one branch whose whole job is to deny.
			verdict = verdict or {}
			verdict.suppressed = verdict.action or "captcha"
			verdict.action = "ban"
			return self:ret(
				true,
				"CrowdSec asked for a captcha but the antibot is disabled on this service, banning instead",
				get_deny_status(),
				nil,
				verdict
			)
		end
		self.ctx.bw.workflow_antibot_provider = antibot_provider
		-- Record WHY before the antibot answers. antibot:set_challenge_reason() keeps an existing
		-- reason rather than overwriting it (antibot.lua), so the Reports row names the LAPI
		-- scenario or the AppSec verdict that asked for the challenge instead of a bare "antibot".
		set_reason(self.id, verdict, self.ctx)
		return self:ret(true, "CrowdSec captcha delegated to the antibot (" .. antibot_provider .. ")")
	end
	if served then
		-- The bouncer already wrote status, headers and body : the CrowdSec 1.8 AppSec
		-- challenge page, or the captcha template. ngx.OK ends the access phase without
		-- generating a second response -- the dispatcher's ngx.exit(ngx.OK) lands on
		-- ngx_http_lua_accessby.c's `r->header_sent` branch, which returns NGX_HTTP_OK and
		-- skips the content phase. Unlike an ngx.exit() from here, save_session() and
		-- save_ctx() still run. Same pattern as robotstxt:access().
		-- Record the reason by hand. The dispatcher only calls set_reason() for a status in its
		-- reason_statuses set (access-lua.conf : the deny status, 400, 405, 429) and ngx.OK is not
		-- one, so a served challenge -- a security action that answered the request in place of the
		-- origin -- would leave no Reports row at all. Same reason workflows:apply() does it for its
		-- own redirect branch.
		set_reason(self.id, verdict, self.ctx)
		return self:ret(true, "CrowdSec served a response : " .. tostring(err), OK)
	end
	if banned then
		-- Also the detect path: `banned` is what the bouncer reports for every non-allow
		-- remediation when rendering is suppressed, so the dispatcher records the reason and
		-- lets the request through exactly as it already did for a `ban`. The bouncer's own
		-- message is carried through rather than dropped : in detect mode the ALERT lines inside
		-- Allow() never fire (rendering is suppressed before them), so this is the only place
		-- left that says WHICH remediation was suppressed.
		-- `verdict` rides along as ret.data : the dispatcher stores it as the report's reason_data
		-- on both its block and its detect arm, which is the only place the suppressed remediation
		-- (ban / captcha / challenge) and the LAPI scenario behind it are still visible in detect.
		if self:defer_verdict(verdict, detect) then
			-- No status : the dispatcher keeps walking the chain, workflows:access() evaluates its
			-- rules with the verdict in hand, and applies this deny itself unless one of them
			-- overrode it. No reason is recorded here on purpose -- a reason set now would buffer
			-- a Reports row for a request that may end up allowed by an explicit workflow rule.
			return self:ret(true, "CrowdSec verdict deferred to the security workflows : " .. tostring(err))
		end
		-- CROWDSEC_BAN_REFRESH in seconds, 0 when off; a service without leases pays one string read
		local setting = self.variables["CROWDSEC_BAN_REFRESH"]
		local refresh = setting and setting ~= "" and setting ~= "0" and parse_duration(setting, "s") or 0
		if refresh > 0 then
			local promoted, promote_err = pcall(self.promote, self, bouncer, scope, verdict, evidence, refresh)
			if not promoted then
				self.logger:log(ERR, "can't promote the CrowdSec ban to a lease : " .. tostring(promote_err))
			end
		end
		return self:ret(true, "CrowdSec bouncer denied request : " .. tostring(err), get_deny_status(), nil, verdict)
	end

	return self:ret(true, "Not denied by CrowdSec bouncer")
end

-- Hand this deny over to the security-workflow engine instead of applying it here -- but only
-- when the operator asked for it AND the engine is actually there to apply it. Anything else
-- enforces immediately: a deferral nobody enforces is a fail-open, which is the exact failure
-- this whole feature must not have.
--
-- Never in detect mode: the dispatcher breaks its plugin loop on any status in detect
-- (access-lua.conf), so crowdsec keeps its own detect behaviour and workflows keeps its own.
--
-- The module name is `workflows/workflows`, with a SLASH, because that is the name
-- helpers.require_plugin uses (helpers.lua:244) and require() caches by name : the dotted
-- spelling loads a SECOND copy of the module whose PLAN was never filled by init(), so
-- attached() would answer false forever and the setting would look broken.
function crowdsec:defer_verdict(verdict, detect)
	if detect or self.variables["CROWDSEC_DEFER_TO_WORKFLOWS"] ~= "yes" then
		return false
	end
	-- The engine ALREADY ran for this request, so nothing is left to enforce a deferral and the
	-- ban would reach the origin. Reachable through PLUGINS_ORDER_ACCESS (src/common/settings.json,
	-- multisite), whose per-service value is inserted ahead of core/order.json
	-- (helpers.lua:183-191): `<service>_PLUGINS_ORDER_ACCESS=workflows` puts workflows:access()
	-- before this plugin. A separate check because attached() answers about the ARTEFACT -- is a
	-- policy attached to this service -- and never about ordering.
	if self.ctx.bw.workflows_ran then
		self:log_throttled(
			WARN,
			"defer_after_workflows",
			"CROWDSEC_DEFER_TO_WORKFLOWS is set on service "
				.. (self.ctx.bw.server_name or "?")
				.. " but the security workflows already ran for this request, so the CrowdSec verdict was "
				.. "applied here as usual : remove `workflows` from PLUGINS_ORDER_ACCESS (or put it after "
				.. "`crowdsec` there) so the workflows can answer for it"
		)
		return false
	end
	-- One pcall around both the require and the call: a workflows module that fails to load, or
	-- an attached() that raises, must leave this request denied rather than served.
	local ok, attached = pcall(function()
		return require("workflows/workflows").attached(self.ctx.bw.server_name)
	end)
	if not ok or not attached then
		self:log_throttled(
			WARN,
			"defer_no_workflow",
			"CROWDSEC_DEFER_TO_WORKFLOWS is set on service "
				.. (self.ctx.bw.server_name or "?")
				.. " but no security workflow is attached to it"
				.. (ok and "" or " (workflows engine unavailable : " .. tostring(attached) .. ")")
				.. ", so the CrowdSec verdict was applied here as usual : attach a workflow holding a "
				.. "CrowdSec condition, or set CROWDSEC_DEFER_TO_WORKFLOWS to no"
		)
		return false
	end
	-- The verdict itself, not a copy of two of its fields : workflows:enforce_deferred() passes it
	-- on as the report data, which is exactly what the deny arm below does with it, so a deferred
	-- ban and an immediate one leave the SAME Reports row (source, action and the LAPI scenario)
	-- and render through the same security-reason.js sentence. The workflow leaf reads
	-- ctx.bw.crowdsec_source / crowdsec_remediation, published above, not this table.
	self.ctx.bw.crowdsec_deferred = {
		status = get_deny_status(),
		verdict = verdict,
	}
	return true
end

function crowdsec:api()
	local operation = self.ctx.bw.uri:match("^/crowdsec/([%a_]+)$")
	if
		self.ctx.bw.request_method == "POST"
		and (
			operation == "connections"
			or operation == "decisions"
			or operation == "alerts"
			or operation == "unban"
			or operation == "allowlists"
			or operation == "allowlistcheck"
			or operation == "refresh_ip"
		)
	then
		if operation == "connections" then
			local params = read_control_body() or {}
			local wanted = params.connection
			if wanted ~= nil and (type(wanted) ~= "string" or #wanted ~= 64) then
				return self:ret(true, "Invalid CrowdSec connection", 400)
			end
			local connections, checked = setmetatable({}, json.array_mt), {}
			for scope, bouncer in pairs(bouncers) do
				local info = bouncer.ConnectionInfo()
				info.id = connection_id(scope, bouncer)
				if not wanted or info.id == wanted then
					info.services = { scope }
					-- Configuration errors must not echo user information embedded in URLs.
					for _, key in ipairs({ "lapi_url", "appsec_url" }) do
						info[key] = (info[key] or ""):gsub("(https?://)[^/]*@", "%1[redacted]@")
					end
					if not checked[bouncer] then
						local healthy = bouncer.Health()
						checked[bouncer] = { status = healthy and "success" or "error" }
					end
					info.status = checked[bouncer].status
					if info.status == "error" then
						info.error = "Authenticated Local API check failed"
					end
					info.sync_status = info.last_successful_sync and "current" or "not_synchronized"
					if
						info.mode == "stream"
						and info.last_successful_sync
						and ngx.time() - info.last_successful_sync > math.max(30, 2 * (info.update_frequency or 10))
					then
						info.sync_status = "stale"
					end
					insert(connections, info)
				end
			end
			if not wanted then
				for _, scope in ipairs(failed_scopes) do
					insert(
						connections,
						{ services = { scope }, status = "error", error = "CrowdSec configuration is not loaded" }
					)
				end
			end
			if wanted and #connections == 0 then
				return self:ret(true, "CrowdSec connection is no longer configured", 404)
			end
			sort(connections, function(a, b)
				return a.services[1] < b.services[1]
			end)
			return self:ret(true, "CrowdSec connections", HTTP_OK, nil, { connections = connections })
		end
		local params = read_control_body()
		if not params or type(params.connection) ~= "string" or #params.connection ~= 64 then
			return self:ret(true, "A configured CrowdSec connection is required", 400)
		end
		for scope, bouncer in pairs(bouncers) do
			if connection_id(scope, bouncer) == params.connection then
				local data, err, status = bouncer.Control(operation, params)
				return self:ret(true, err or "CrowdSec operation completed", status or 502, nil, data)
			end
		end
		return self:ret(true, "CrowdSec connection is no longer configured", 404)
	end
	if self.ctx.bw.uri == "/crowdsec/ping" and self.ctx.bw.request_method == "POST" then
		-- has_variable, not is_needed() : this runs in a request phase, where is_needed() reads
		-- `self.variables["USE_CROWDSEC"]` -- the API vhost's own setting, which says nothing
		-- about the services being checked. A fleet with CrowdSec on every service reported
		-- "not enabled" because the vhost answering /crowdsec/ping did not have it set.
		local enabled, enable_err = has_variable("USE_CROWDSEC", "yes")
		if enabled == nil then
			return self:ret(
				true,
				"Can't check CrowdSec enablement : " .. tostring(enable_err),
				HTTP_INTERNAL_SERVER_ERROR
			)
		end
		if not enabled then
			return self:ret(true, "CrowdSec plugin is not enabled", HTTP_OK)
		end

		-- Services can point at different endpoints, so there is no single connection
		-- to test : ping every distinct bouncer and report the first failure.
		local tested = {}
		local checked = 0
		local checked_lapis = 0
		local bouncer_failure
		for scope, bouncer in pairs(bouncers) do
			if not tested[bouncer] then
				tested[bouncer] = true
				checked = checked + 1
				-- Health(), not Allow("127.0.0.1") : Allow answers from the decision cache, so a
				-- Local API that had gone away still reported healthy, and it now needs a
				-- per-service challenge namespace this endpoint has no business inventing.
				local ok, err, checked_lapi = bouncer.Health()
				if not ok then
					bouncer_failure = "Error while executing CrowdSec bouncer for service "
						.. scope
						.. " : "
						.. tostring(err)
					break
				end
				if checked_lapi then
					checked_lapis = checked_lapis + 1
				end
			end
		end
		-- Report a missing configuration and an unreachable Local API together, so fixing one
		-- does not hide the other until the next reload. A scope in `failed_scopes` is served
		-- UNCHECKED, which is exactly what a health endpoint exists to surface.
		if #failed_scopes > 0 then
			local message = "No CrowdSec configuration loaded for service(s) "
				.. concat(failed_scopes, ", ")
				.. "; their requests bypass CrowdSec until the next reload"
			if bouncer_failure then
				message = message .. ". " .. bouncer_failure
			end
			return self:ret(true, message, HTTP_INTERNAL_SERVER_ERROR)
		end
		if bouncer_failure then
			return self:ret(true, bouncer_failure, HTTP_INTERNAL_SERVER_ERROR)
		end
		if checked == 0 then
			return self:ret(true, "No CrowdSec bouncer loaded", HTTP_INTERNAL_SERVER_ERROR)
		end
		if checked_lapis == 0 then
			return self:ret(
				true,
				"CrowdSec configuration loaded; no Local API configured; AppSec health is not checked",
				HTTP_OK
			)
		end
		return self:ret(true, "Authenticated Local API checks succeeded; AppSec health is not checked", HTTP_OK)
	end
	return self:ret(false, "success")
end

return crowdsec
