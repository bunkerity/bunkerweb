local cache_partition = require("crowdsec.cache_partition")
local class = require("middleclass")
local plugin = require("bunkerweb.plugin")
local utils = require("bunkerweb.utils")

local crowdsec = class("crowdsec", plugin)

local ngx = ngx
local ERR = ngx.ERR
local WARN = ngx.WARN
local OK = ngx.OK
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local HTTP_OK = ngx.HTTP_OK
local has_variable = utils.has_variable
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local get_deny_status = utils.get_deny_status
local get_security_mode = utils.get_security_mode
local set_reason = utils.set_reason
local open = io.open
local pairs = pairs
local ipairs = ipairs
local insert = table.insert
local sort = table.sort
local concat = table.concat

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

	-- Services whose rendered configuration is byte-identical share one instance
	local by_conf = {}
	local resolved = {}
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
	end

	bouncers = resolved

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

function crowdsec:access()
	-- Check if CS is activated
	if not self:is_needed() then
		return self:ret(true, "CrowdSec plugin not enabled")
	end
	-- Pick the bouncer of this service, falling back to the singlesite one
	local bouncer = bouncers[self.ctx.bw.server_name] or bouncers[GLOBAL_SCOPE]
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
	local ok, err, banned, served, verdict, antibot_provider =
		bouncer.Allow(self.ctx.bw.remote_addr, detect, self.variables["CROWDSEC_CAPTCHA_PROVIDER"])
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
	if self.ctx.bw.uri == "/crowdsec/ping" and self.ctx.bw.request_method == "POST" then
		-- Check crowdsec connection
		if not self:is_needed() then
			return self:ret(true, "CrowdSec plugin is not enabled", HTTP_OK)
		end

		-- Services can point at different endpoints, so there is no single connection
		-- to test : ping every distinct bouncer and report the first failure.
		local tested = {}
		local checked = 0
		for scope, bouncer in pairs(bouncers) do
			if not tested[bouncer] then
				tested[bouncer] = true
				checked = checked + 1
				local ok, err = bouncer.Allow("127.0.0.1", true)
				if not ok then
					return self:ret(
						true,
						"Error while executing CrowdSec bouncer for service " .. scope .. " : " .. tostring(err),
						HTTP_INTERNAL_SERVER_ERROR
					)
				end
			end
		end
		if checked == 0 then
			return self:ret(true, "No CrowdSec bouncer loaded", HTTP_INTERNAL_SERVER_ERROR)
		end
		return self:ret(true, "The test request is successful", HTTP_OK)
	end
	return self:ret(false, "success")
end

return crowdsec
