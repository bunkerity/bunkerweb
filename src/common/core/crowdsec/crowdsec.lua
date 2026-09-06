local cache_partition = require("crowdsec.cache_partition")
local class = require("middleclass")
local plugin = require("bunkerweb.plugin")
local utils = require("bunkerweb.utils")

local crowdsec = class("crowdsec", plugin)

local ngx = ngx
local ERR = ngx.ERR
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local HTTP_OK = ngx.HTTP_OK
local has_variable = utils.has_variable
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local get_deny_status = utils.get_deny_status
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
local challenge_prefixes = {}
local failed_scopes = {}

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
		-- Reset every module-level table so a later health check cannot report stale services.
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
	local scope = bouncers[self.ctx.bw.server_name] and self.ctx.bw.server_name or GLOBAL_SCOPE
	local bouncer = bouncers[scope]
	if not bouncer then
		-- init() already logged why. Fail open rather than take the service down.
		return self:ret(true, "no CrowdSec bouncer loaded for this service")
	end
	-- Do the check
	local ok, err, banned = bouncer.Allow(self.ctx.bw.remote_addr, challenge_prefixes[scope])
	if not ok then
		return self:ret(false, "Error while executing CrowdSec bouncer : " .. err)
	end
	if banned then
		return self:ret(true, "CrowdSec bouncer denied request", get_deny_status())
	end

	return self:ret(true, "Not denied by CrowdSec bouncer")
end

function crowdsec:api()
	if self.ctx.bw.uri == "/crowdsec/ping" and self.ctx.bw.request_method == "POST" then
		-- The API vhost's settings do not describe the services being checked.
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
				local ok, err, checked_lapi = bouncer.Health()
				if not ok then
					bouncer_failure = "Error while executing CrowdSec bouncer for service " .. scope .. " : " .. err
					break
				end
				if checked_lapi then
					checked_lapis = checked_lapis + 1
				end
			end
		end
		-- Report a missing configuration and an unreachable Local API together, so fixing
		-- one does not hide the other until the next reload.
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
