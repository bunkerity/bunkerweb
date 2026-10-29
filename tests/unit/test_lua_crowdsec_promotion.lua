-- Plain Lua tests for the CrowdSec plugin: lease promotion, refresh_ip, control changes, captcha crash.
-- Run from the repo root: lua tests/unit/test_lua_crowdsec_promotion.lua
local script_dir = arg[0]:match("^(.*)/[^/]+$") or "."
local root = script_dir .. "/../.."
local F = dofile(root .. "/tests/unit/lua_lease_fakes.lua")(root)
local H = dofile(root .. "/tests/unit/lua_crowdsec_fakes.lua")(root)
local real_banlease = require("bunkerweb.banlease")
H.banlease = real_banlease

local failures = 0
local function it(name, fn)
	F.reset()
	F.vars.REDIS_CLUSTER_NODES = ""
	H.clock = 1700000000
	H.logs = {}
	local ok, err = pcall(fn)
	if ok then
		print("PASS " .. name)
	else
		failures = failures + 1
		print("FAIL " .. name .. ": " .. tostring(err))
	end
end
local function eq(a, b, msg)
	assert(a == b, ("%sexpected %q got %q"):format(msg and (msg .. ": ") or "", tostring(b), tostring(a)))
end

local IP = "1.2.3.4"
local NOW = 1700000000

local function lapi_body(decisions)
	if #decisions == 0 then
		return "null"
	end
	local parts = {}
	for _, d in ipairs(decisions) do
		parts[#parts + 1] = string.format(
			'{"id":%d,"origin":"%s","scenario":"x/y","scope":"%s","type":"%s","value":"%s","duration":"%s"}',
			d.id,
			d.origin or "cscli",
			d.scope or "Ip",
			d.type or "ban",
			d.value or IP,
			d.duration or "1h"
		)
	end
	return "[" .. table.concat(parts, ",") .. "]"
end

local function conf(extra)
	local c = {
		API_URL = "http://lapi:8080",
		API_KEY = "key",
		MODE = "live",
		CACHE_EXPIRATION = 1,
		UPDATE_FREQUENCY = 10,
		BOUNCING_ON_TYPE = "ban",
		FALLBACK_REMEDIATION = "ban",
		REDIRECT_LOCATION = "",
		EXCLUDE_LOCATION = {},
		REQUEST_TIMEOUT = 500,
		STREAM_REQUEST_TIMEOUT = 15000,
		ENABLED = "true",
		ENABLE_INTERNAL = "false",
		APPSEC_URL = "",
		APPSEC_ENABLED = false,
	}
	for k, v in pairs(extra or {}) do
		c[k] = v
	end
	return c
end

local function decision_cache_ttl(bouncer_cache)
	for k, ttl in pairs(bouncer_cache.ttls) do
		if k:find("^v2_decisions_") then
			return ttl
		end
	end
end

------------------------------------------------------------------------------------------------------------------
-- Plugin: the pure promotion decision and access()
------------------------------------------------------------------------------------------------------------------

-- Spy banlease and stub bouncer
local function spy_banlease()
	local spy = {
		calls = { lease_epoch = {}, promote = {}, build = {} },
		epoch = 7,
		ttl = 300,
		promote_result = { true, "written" },
	}
	function spy.lease_epoch(ip, create)
		spy.calls.lease_epoch[#spy.calls.lease_epoch + 1] = { ip, create }
		return spy.epoch
	end
	function spy.build_lease(evidence, now, refresh)
		spy.calls.build[#spy.calls.build + 1] = { evidence, now, refresh }
		if not spy.ttl then
			return nil, "no live ban decision"
		end
		return spy.ttl, { version = 1, lease = true }
	end
	function spy.promote_lease(...)
		spy.calls.promote[#spy.calls.promote + 1] = { ... }
		if spy.promote_error then
			error(spy.promote_error)
		end
		return unpack(spy.promote_result)
	end
	return spy
end

local function stub_bouncer()
	local b = { info = { mode = "live", update_frequency = 10 }, excluded = false }
	function b.init()
		return true
	end
	function b.GetCaptchaTemplate()
		return nil
	end
	function b.ConnectionInfo()
		return b.info
	end
	function b.HasExcludedLocations()
		return b.excluded
	end
	function b.Health()
		return true
	end
	function b.Control(action, params)
		b.control_call = { action, params }
		return { ok = true }, nil, 200
	end
	function b.Allow()
		return
	end
	return b
end

local function evidence()
	return {
		source = "lapi",
		remediation = "ban",
		captured_at = NOW,
		decisions = {
			{
				id = 1,
				origin = "cscli",
				scenario = "s",
				type = "ban",
				scope = "Ip",
				value = IP,
				expires_at = NOW + 3600,
				remediation = "ban",
			},
		},
	}
end

local plugin_class

-- Builds the plugin with a stub bouncer, runs init() for the given scopes and returns plugin class + object factory
local function plugin_with(bouncer, banlease, scopes, multisite)
	H.settings.multisite = multisite and "yes" or "no"
	H.settings.services = scopes or { "global" }
	local cs = H.load_plugin({ banlease = banlease, bouncer = bouncer })
	plugin_class = cs
	local boot = cs:new(H.new_ctx({ security_mode = "block" }))
	boot.is_request = false
	local ret = boot:init()
	assert(ret.ret, "init failed: " .. tostring(ret.msg))
	return cs
end

it("refresh 0 never promotes", function()
	local cs = plugin_with(stub_bouncer(), spy_banlease())
	assert(not cs._should_promote({
		refresh = 0,
		security_mode = "block",
		exclude_location = false,
		mode = "live",
		now = 100,
	}))
end)

it("detect mode never promotes", function()
	local cs = plugin_with(stub_bouncer(), spy_banlease())
	assert(not cs._should_promote({
		refresh = 300,
		security_mode = "detect",
		exclude_location = false,
		mode = "live",
		now = 100,
	}))
end)

it("excluded locations never promote", function()
	local cs = plugin_with(stub_bouncer(), spy_banlease())
	assert(not cs._should_promote({
		refresh = 300,
		security_mode = "block",
		exclude_location = true,
		mode = "live",
		now = 100,
	}))
end)

it("stale stream sync never promotes", function()
	local cs = plugin_with(stub_bouncer(), spy_banlease())
	local p = {
		refresh = 300,
		security_mode = "block",
		exclude_location = false,
		mode = "stream",
		update_frequency = 10,
		now = 1000,
	}
	p.last_successful_sync = 1000 - 21
	assert(not cs._should_promote(p))
	p.last_successful_sync = 1000 - 20
	assert(cs._should_promote(p))
	p.last_successful_sync = nil
	local ok, why = cs._should_promote(p)
	assert(not ok and why, "a stream connection that never synchronized must not promote")
end)

it("live mode promotes without any sync information", function()
	local cs = plugin_with(stub_bouncer(), spy_banlease())
	assert(cs._should_promote({
		refresh = 300,
		security_mode = "block",
		exclude_location = false,
		mode = "live",
		now = 100,
	}))
end)

it("captcha render returns no error concat crash", function()
	local bouncer = stub_bouncer()
	local cs = plugin_with(bouncer, spy_banlease())
	-- bouncer.Allow returns nothing on a captcha render: access() must return a ret, not raise
	local plugin = cs:new(H.new_ctx())
	local ok, ret = pcall(plugin.access, plugin)
	assert(ok, tostring(ret))
	eq(ret.ret, true)
	eq(ret.status, 200, "the request must end once the challenge page was sent")
end)

it("a bouncer error still fails the access call with its message", function()
	local bouncer = stub_bouncer()
	function bouncer.Allow()
		return false, "missing CrowdSec challenge namespace"
	end
	local cs = plugin_with(bouncer, spy_banlease())
	local plugin = cs:new(H.new_ctx())
	local ret = plugin:access()
	eq(ret.ret, false)
	assert(ret.msg:find("missing CrowdSec challenge namespace", 1, true))
end)

local function run_access(opts)
	opts = opts or {}
	local banlease = opts.banlease or spy_banlease()
	local bouncer = stub_bouncer()
	if opts.info then
		bouncer.info = opts.info
	end
	bouncer.excluded = opts.excluded or false
	local ev = opts.evidence or evidence()
	function bouncer.Allow()
		if opts.during_allow then
			opts.during_allow()
		end
		return true, "denied", true, ev
	end
	local cs = plugin_with(bouncer, banlease, opts.scopes, opts.multisite)
	local ctx = H.new_ctx({ security_mode = opts.security_mode or "block" })
	ctx.bw.server_name = opts.server_name or "a.example.com"
	if opts.refresh ~= nil then
		ctx.vars.CROWDSEC_BAN_REFRESH = opts.refresh
	end
	ctx.bw.cs_redis_epoch = opts.redis_epoch
	local plugin = cs:new(ctx)
	return plugin:access(), banlease, ev, ctx
end

it("default settings change nothing: no epoch, no lease, deny kept", function()
	local ret, banlease = run_access({ refresh = "0" })
	eq(ret.status, 403)
	assert(not plugin_class._should_promote({
		refresh = 0,
		security_mode = "block",
		exclude_location = false,
		mode = "live",
		now = NOW,
	}))
	eq(#banlease.calls.lease_epoch, 0)
	eq(#banlease.calls.build, 0)
	eq(#banlease.calls.promote, 0)
end)

it("an unset refresh behaves like 0", function()
	local ret, banlease = run_access({ refresh = "" })
	eq(ret.status, 403)
	eq(#banlease.calls.lease_epoch, 0)
	eq(#banlease.calls.promote, 0)
end)

it("a deny with refresh promotes a global lease for the singlesite scope", function()
	local ret, banlease, ev = run_access({ refresh = "5m", redis_epoch = "inc:1" })
	eq(ret.status, 403)
	eq(#banlease.calls.lease_epoch, 1)
	eq(banlease.calls.lease_epoch[1][1], IP)
	eq(banlease.calls.lease_epoch[1][2], true, "the epoch is captured with create")
	eq(#banlease.calls.build, 1)
	eq(banlease.calls.build[1][1], ev)
	eq(banlease.calls.build[1][2], NOW)
	eq(banlease.calls.build[1][3], 300)
	local p = banlease.calls.promote[1]
	eq(p[1], IP)
	eq(p[2], nil, "a global lease carries no service")
	eq(p[3], "global")
	eq(p[4], 300)
	assert(type(p[5]) == "table")
	eq(p[6], "ZZ")
	eq(p[7].lease_epoch, 7)
	eq(p[7].redis_epoch, "inc:1")
	eq(ev.instance, "node-a")
	eq(ev.service_scope, "global")
end)

it("a multisite deny promotes a service lease", function()
	local ret, banlease = run_access({ refresh = "5m", scopes = { "a.example.com" }, multisite = true })
	eq(ret.status, 403)
	local p = banlease.calls.promote[1]
	eq(p[2], "a.example.com")
	eq(p[3], "service")
end)

it("detect mode captures the epoch but never promotes", function()
	local ret, banlease = run_access({ refresh = "5m", security_mode = "detect" })
	eq(ret.status, 403)
	eq(#banlease.calls.build, 0)
	eq(#banlease.calls.promote, 0)
end)

it("excluded locations never promote", function()
	local ret, banlease = run_access({ refresh = "5m", excluded = true })
	eq(ret.status, 403)
	eq(#banlease.calls.promote, 0)
end)

it("a stale stream connection never promotes", function()
	local ret, banlease = run_access({
		refresh = "5m",
		info = { mode = "stream", update_frequency = 10, last_successful_sync = NOW - 21 },
	})
	eq(ret.status, 403)
	eq(#banlease.calls.promote, 0)
	local ret2, banlease2 = run_access({
		refresh = "5m",
		info = { mode = "stream", update_frequency = 10, last_successful_sync = NOW - 20 },
	})
	eq(ret2.status, 403)
	eq(#banlease2.calls.promote, 1)
end)

it("no epoch means no promotion", function()
	local banlease = spy_banlease()
	banlease.epoch = nil
	local ret = run_access({ refresh = "5m", banlease = banlease })
	eq(ret.status, 403)
	eq(#banlease.calls.promote, 0)
end)

it("no live ban decision means no promotion", function()
	local banlease = spy_banlease()
	banlease.ttl = nil
	local ret = run_access({ refresh = "5m", banlease = banlease })
	eq(ret.status, 403)
	eq(#banlease.calls.promote, 0)
end)

it("a failing promotion never changes the deny", function()
	local banlease = spy_banlease()
	banlease.promote_error = "boom"
	local ret = run_access({ refresh = "5m", banlease = banlease })
	eq(ret.ret, true)
	eq(ret.status, 403)
	local logged = false
	for _, entry in ipairs(H.logs) do
		if entry[2]:find("boom", 1, true) then
			logged = true
		end
	end
	assert(logged, "the failure is logged")
end)

it("a stale promotion keeps the deny and logs the status", function()
	local banlease = spy_banlease()
	banlease.promote_result = { false, "stale" }
	local ret = run_access({ refresh = "5m", banlease = banlease })
	eq(ret.status, 403)
	local logged = false
	for _, entry in ipairs(H.logs) do
		if entry[2]:find("stale", 1, true) then
			logged = true
		end
	end
	assert(logged)
end)

------------------------------------------------------------------------------------------------------------------
-- Plugin API: route pattern, allow-list, node on connections
------------------------------------------------------------------------------------------------------------------

local function api_call(cs, uri, body)
	local ctx = H.new_ctx()
	ctx.bw.uri, ctx.bw.request_method = uri, "POST"
	ngx.req = {
		read_body = function() end,
		get_body_data = function()
			return body
		end,
		get_body_file = function()
			return nil
		end,
	}
	local plugin = cs:new(ctx)
	return plugin:api()
end

it("the instance route accepts refresh_ip and hands it to the bouncer", function()
	local bouncer = stub_bouncer()
	local cs = plugin_with(bouncer, spy_banlease())
	local connections = api_call(cs, "/crowdsec/connections", "{}")
	local id = connections.data.connections[1].id
	local ret = api_call(cs, "/crowdsec/refresh_ip", string.format('{"connection":"%s","ip":"%s"}', id, IP))
	eq(ret.ret, true)
	eq(ret.status, 200)
	eq(bouncer.control_call[1], "refresh_ip")
	eq(bouncer.control_call[2].ip, IP)
end)

it("the route still rejects an unknown operation", function()
	local cs = plugin_with(stub_bouncer(), spy_banlease())
	local ret = api_call(cs, "/crowdsec/do_something", "{}")
	eq(ret.ret, false)
end)

it("connections rows carry the node name", function()
	local cs = plugin_with(stub_bouncer(), spy_banlease())
	local ret = api_call(cs, "/crowdsec/connections", "{}")
	eq(ret.data.connections[1].node, "node-a")
end)

------------------------------------------------------------------------------------------------------------------
-- Bouncer: remediation in the evidence, HasExcludedLocations
------------------------------------------------------------------------------------------------------------------

it("live evidence carries the effective remediation of each decision", function()
	local bouncer = H.load_bouncer(conf({ BOUNCING_ON_TYPE = "all", FALLBACK_REMEDIATION = "captcha" }))
	H.lapi = function()
		return 200, lapi_body({ { id = 1, type = "ban" }, { id = 2, type = "throttle", value = IP } })
	end
	local ok, remediation, err, evidence_ = bouncer.allowIp(IP)
	eq(ok, false)
	eq(remediation, "ban")
	eq(err, nil)
	eq(evidence_.decisions[1].remediation, "ban")
	eq(evidence_.decisions[2].remediation, "captcha", "an unknown type takes the fallback")
end)

it("cached evidence carries the remediation too", function()
	local bouncer = H.load_bouncer(conf({ MODE = "stream" }))
	H.lapi = function()
		return 200, lapi_body({ { id = 1, type = "ban" } })
	end
	assert(bouncer.RefreshIp({ ip = IP }))
	local ok, remediation, err, evidence_ = bouncer.allowIp(IP)
	eq(ok, false)
	eq(remediation, "ban")
	eq(err, nil)
	eq(evidence_.decisions[1].remediation, "ban")
end)

it("HasExcludedLocations reflects the effective exclude list", function()
	eq(H.load_bouncer(conf()).HasExcludedLocations(), false)
	eq(H.load_bouncer(conf({ EXCLUDE_LOCATION = { "/.well-known" } })).HasExcludedLocations(), true)
	eq(
		H.load_bouncer(conf({ REDIRECT_LOCATION = "/captcha" })).HasExcludedLocations(),
		true,
		"the plugin's own location counts"
	)
end)

------------------------------------------------------------------------------------------------------------------
-- Bouncer: refresh_ip
------------------------------------------------------------------------------------------------------------------

it("refresh_ip rejects an invalid ip before touching anything", function()
	local bouncer = H.load_bouncer(conf())
	local data, err, status = bouncer.RefreshIp({ ip = "not-an-ip" })
	eq(data, nil)
	eq(err, "invalid ip")
	eq(status, 400)
	eq(#H.requests, 0)
	eq(select(3, bouncer.RefreshIp({})), 400)
end)

it("refresh_ip bumps the local lease epoch first and reports the folded remediation", function()
	local bouncer = H.load_bouncer(conf({ BOUNCING_ON_TYPE = "all" }))
	local before = real_banlease.lease_epoch(IP, true)
	local epoch_at_request
	H.hooks.before_response = function()
		epoch_at_request = real_banlease.lease_epoch(IP, false)
	end
	H.lapi = function()
		return 200, lapi_body({ { id = 5, type = "captcha" }, { id = 6, type = "ban" } })
	end
	local data, err, status = bouncer.RefreshIp({ ip = IP })
	eq(err, nil)
	eq(status, 200)
	eq(data.ip, IP)
	eq(data.remediation, "ban")
	eq(#data.decision_ids, 2)
	eq(data.observed_at, NOW)
	assert(epoch_at_request ~= before, "the bump happens before the Local API request")
	assert(H.requests[1]:find("/v1/decisions?ip=" .. IP .. "&contains=true", 1, true), H.requests[1])
end)

it("refresh_ip answers a nil remediation when nothing counts", function()
	local bouncer = H.load_bouncer(conf())
	H.lapi = function()
		return 200, "null"
	end
	local data, _, status = bouncer.RefreshIp({ ip = IP })
	eq(status, 200)
	eq(data.remediation, nil)
	eq(#data.decision_ids, 0)
end)

it("refresh_ip reports a Local API failure as 502 after the epoch moved", function()
	local bouncer = H.load_bouncer(conf())
	local before = real_banlease.lease_epoch(IP, true)
	H.lapi = function()
		return 500, "oops"
	end
	local data, err, status = bouncer.RefreshIp({ ip = IP })
	eq(data, nil)
	eq(status, 502)
	assert(err:find("HTTP 500", 1, true), err)
	assert(real_banlease.lease_epoch(IP, false) ~= before)
	H.lapi = function()
		return nil
	end
	eq(select(3, bouncer.RefreshIp({ ip = IP })), 502)
	H.lapi = function()
		return 200, "{}"
	end
	eq(select(3, bouncer.RefreshIp({ ip = IP })), 502, "a non-array reply is invalid")
end)

it("refresh_ip replaces stale cached entries, ranges included, and clears the negative entry", function()
	local bouncer = H.load_bouncer(conf({ MODE = "stream" }))
	-- Seed: an exact decision and a /24 range decision, plus a negative live entry
	H.lapi = function()
		return 200,
			lapi_body({ { id = 1, type = "ban" }, { id = 2, type = "ban", scope = "Range", value = "1.2.3.0/24" } })
	end
	assert(bouncer.RefreshIp({ ip = IP }))
	eq((bouncer.allowIp(IP)), false)
	ngx.shared.crowdsec_cache:set("v2_allowed_ipv4_4294967295_16909060", true)
	-- Decision 2 (the range) disappears, decision 1 stays
	H.lapi = function()
		return 200, lapi_body({ { id = 1, type = "ban" } })
	end
	local data = bouncer.RefreshIp({ ip = IP })
	eq(#data.decision_ids, 1)
	local ok, remediation, _, evidence_ = bouncer.allowIp(IP)
	eq(ok, false)
	eq(remediation, "ban")
	eq(#evidence_.decisions, 1, "the removed range decision is gone")
	eq(evidence_.decisions[1].id, 1)
	eq(ngx.shared.crowdsec_cache:get("v2_allowed_ipv4_4294967295_16909060"), nil)
	-- Everything removed
	H.lapi = function()
		return 200, "null"
	end
	bouncer.RefreshIp({ ip = IP })
	local allowed = bouncer.allowIp(IP)
	eq(allowed, true)
end)

it("refresh_ip keeps the live-mode cache expiration cap", function()
	local bouncer = H.load_bouncer(conf({ MODE = "live", CACHE_EXPIRATION = 1 }))
	H.lapi = function()
		return 200, lapi_body({ { id = 1, type = "ban", duration = "1h" } })
	end
	assert(bouncer.RefreshIp({ ip = IP }))
	local ttl = decision_cache_ttl(ngx.shared.crowdsec_cache)
	assert(ttl and ttl <= 1, "live refresh must expire within CACHE_EXPIRATION, got " .. tostring(ttl))
end)

it("refresh_ip keeps the decision lifetime in stream mode", function()
	local bouncer = H.load_bouncer(conf({ MODE = "stream", CACHE_EXPIRATION = 1 }))
	H.lapi = function()
		return 200, lapi_body({ { id = 1, type = "ban", duration = "1h" } })
	end
	assert(bouncer.RefreshIp({ ip = IP }))
	local ttl = decision_cache_ttl(ngx.shared.crowdsec_cache)
	assert(ttl and ttl >= 3500, "stream refresh keeps the decision lifetime, got " .. tostring(ttl))
end)

it("refresh_ip in stream mode retries the lock every 50 ms for 2 s, then answers busy", function()
	local bouncer = H.load_bouncer(conf({ MODE = "stream" }))
	H.lapi = function()
		return 200, lapi_body({ { id = 1, type = "ban" } })
	end
	H.lock_busy = 1000
	local data, err, status = bouncer.RefreshIp({ ip = IP })
	eq(data, nil)
	eq(err, "busy")
	eq(status, 503)
	assert(#H.sleeps >= 39 and #H.sleeps <= 41, "about 40 sleeps of 50 ms, got " .. #H.sleeps)
	eq(H.sleeps[1], 0.05)
	-- Contention that clears within the window
	H.sleeps, H.lock_busy = {}, 3
	eq(select(3, bouncer.RefreshIp({ ip = IP })), 200)
	eq(#H.sleeps, 3)
end)

it("refresh_ip in live mode never takes the stream lock", function()
	local bouncer = H.load_bouncer(conf({ MODE = "live" }))
	H.lapi = function()
		return 200, "null"
	end
	H.lock_busy = 1000
	local _, _, status = bouncer.RefreshIp({ ip = IP })
	eq(status, 200)
	eq(#H.sleeps, 0)
end)

it("refresh_ip reads the Local API only after taking the stream lock", function()
	local bouncer = H.load_bouncer(conf({ MODE = "stream" }))
	local runs_at_request
	H.lapi = function()
		runs_at_request = H.lock_runs
		return 200, "null"
	end
	H.lock_runs = 0
	assert(bouncer.RefreshIp({ ip = IP }))
	eq(runs_at_request, 1, "the request happens inside the lock")
end)

it("refresh_ip bumps the Redis epoch and reports a Redis failure", function()
	F.vars.USE_REDIS = "yes"
	F.redis["cs_epoch_" .. IP] = { value = "inc:1", ttl = 100 }
	local bouncer = H.load_bouncer(conf())
	H.lapi = function()
		return 200, "null"
	end
	local data, _, status = bouncer.RefreshIp({ ip = IP })
	eq(status, 200)
	eq(F.redis_get("cs_epoch_" .. IP), "inc:2")
	assert(data)
	F.flags.redis_call_fails = true
	local failed, err, failed_status = bouncer.RefreshIp({ ip = IP })
	eq(failed, nil)
	eq(failed_status, 502)
	assert(err:find("^redis: "), err)
end)

------------------------------------------------------------------------------------------------------------------
-- Concurrency contract: nothing captured before a refresh becomes effective after it
------------------------------------------------------------------------------------------------------------------

it("(a) a live query paused around refresh_ip publishes nothing and creates no lease", function()
	local bouncer = H.load_bouncer(conf({ MODE = "live", CACHE_EXPIRATION = 60 }))
	-- Epoch exists, as access() creates it before the query
	real_banlease.lease_epoch(IP, true)
	local nested = false
	H.lapi = function()
		if not nested then
			return 200, lapi_body({ { id = 1, type = "ban" } })
		end
		return 200, "null"
	end
	H.hooks.before_response = function()
		if not nested then
			nested = true
			-- Unban plus refresh_ip runs while the first query is in flight, and sees the decision gone
			local data, err = bouncer.RefreshIp({ ip = IP })
			assert(data, err)
		end
	end
	local ok, remediation, err = bouncer.allowIp(IP)
	eq(ok, true, "the paused query fails open")
	eq(remediation, nil)
	eq(err, "invalidated")
	-- The stale answer was not published to the cache, and no lease exists
	eq(decision_cache_ttl(ngx.shared.crowdsec_cache), nil)
	H.hooks.before_response = nil
	local allowed = bouncer.allowIp(IP)
	eq(allowed, true, "the next request resolves against the refreshed state")
	local row = real_banlease.lookup_lease(IP, nil, "global")
	eq(row, nil)
end)

it("(a) without any refresh the live query publishes as before", function()
	local bouncer = H.load_bouncer(conf({ MODE = "live", CACHE_EXPIRATION = 60 }))
	real_banlease.lease_epoch(IP, true)
	H.lapi = function()
		return 200, lapi_body({ { id = 1, type = "ban" } })
	end
	local ok, remediation, err = bouncer.allowIp(IP)
	eq(ok, false)
	eq(remediation, "ban")
	eq(err, nil)
	assert(decision_cache_ttl(ngx.shared.crowdsec_cache))
end)

it("(a) a live query with no epoch at all keeps publishing (defaults)", function()
	local bouncer = H.load_bouncer(conf({ MODE = "live", CACHE_EXPIRATION = 60 }))
	H.lapi = function()
		return 200, lapi_body({ { id = 1, type = "ban" } })
	end
	local ok, remediation = bouncer.allowIp(IP)
	eq(ok, false)
	eq(remediation, "ban")
	eq(F.ngx_meta_touched, nil)
	assert(ngx.shared.bans_meta:get("le_" .. IP) == nil, "defaults allocate no epoch")
end)

local promotions

-- Real banlease whose promote_lease outcome is recorded, so a test proves the promotion ran and was refused
local function recording_banlease()
	promotions = {}
	return setmetatable({
		promote_lease = function(...)
			local ok, status = real_banlease.promote_lease(...)
			promotions[#promotions + 1] = { ok, status }
			return ok, status
		end,
	}, { __index = real_banlease })
end

local function promotion_with_refresh(refresh_kind)
	local bouncer = H.load_bouncer(conf({ MODE = "live", CACHE_EXPIRATION = 60 }))
	local proxy = setmetatable({}, { __index = bouncer })
	local ev = evidence()
	proxy.Allow = function()
		if refresh_kind == "local" then
			H.lapi = function()
				return 200, "null"
			end
			local data, err = bouncer.RefreshIp({ ip = IP })
			assert(data, err)
		else
			-- Another instance's refresh_ip: only the shared Redis epoch moves
			assert(real_banlease.bump_redis_epoch(IP))
		end
		return true, "denied", true, ev
	end
	local cs = plugin_with(proxy, recording_banlease())
	local ctx = H.new_ctx({ security_mode = "block" })
	ctx.vars.CROWDSEC_BAN_REFRESH = "5m"
	ctx.bw.cs_redis_epoch = F.redis_get("cs_epoch_" .. IP) or false
	local plugin = cs:new(ctx)
	return plugin:access(), ev
end

it("(b) evidence captured before a local refresh_ip is not promoted", function()
	local ret = promotion_with_refresh("local")
	eq(ret.status, 403, "the current request is still denied")
	eq(#promotions, 1, "the promotion ran")
	eq(promotions[1][1], false)
	eq(promotions[1][2], "stale")
	eq(F.store["bans_cs_ip_" .. IP], nil)
	eq(F.stream_store["bans_cs_ip_" .. IP], nil)
end)

it("(b) evidence captured before another instance's refresh_ip is stale in Redis", function()
	F.vars.USE_REDIS = "yes"
	F.redis["cs_epoch_" .. IP] = { value = "inc:1", ttl = 100 }
	local ret = promotion_with_refresh("redis")
	eq(ret.status, 403)
	eq(#promotions, 1, "the promotion ran")
	eq(promotions[1][1], false)
	eq(promotions[1][2], "stale")
	eq(F.redis_get("cs_epoch_" .. IP), "inc:2")
	eq(F.redis["bans_cs_ip_" .. IP], nil, "the compare-and-set refused the old snapshot")
	eq(F.store["bans_cs_ip_" .. IP], nil, "and no local lease survives it")
end)

it("(b) with nothing in between the lease is written locally and in Redis", function()
	F.vars.USE_REDIS = "yes"
	F.redis["cs_epoch_" .. IP] = { value = "inc:1", ttl = 100 }
	local bouncer = H.load_bouncer(conf({ MODE = "live" }))
	local proxy = setmetatable({}, { __index = bouncer })
	local ev = evidence()
	proxy.Allow = function()
		return true, "denied", true, ev
	end
	local cs = plugin_with(proxy, recording_banlease())
	local ctx = H.new_ctx({ security_mode = "block" })
	ctx.bw.cs_redis_epoch = "inc:1"
	local ret = cs:new(ctx):access()
	eq(ret.status, 403)
	eq(promotions[1] and promotions[1][2], "written")
	assert(F.store["bans_cs_service_a.example.com_ip_" .. IP] == nil and F.store["bans_cs_ip_" .. IP] ~= nil)
	assert(F.redis["bans_cs_ip_" .. IP], "the lease reached Redis")
	eq(F.store["bans_cs_ip_" .. IP].ttl, 300)
end)

------------------------------------------------------------------------------------------------------------------
-- control.lua: remediation in decisions, an already gone decision on unban
------------------------------------------------------------------------------------------------------------------

local function control_conf()
	return conf({
		MANAGEMENT_LOGIN = "machine",
		MANAGEMENT_PASSWORD = "secret",
		MODE = "stream",
		API_URL = "http://lapi:8080",
	})
end

local function query_has(query, pair)
	return ("&" .. query .. "&"):find("&" .. pair .. "&", 1, true) ~= nil
end

it("decisions rows carry the effective remediation under BOUNCING_ON_TYPE=ban", function()
	local control = H.load_control()
	H.control_http = function(_, _, query)
		assert(query_has(query, "contains=true"), query)
		return 200,
			lapi_body({
				{ id = 1, type = "ban" },
				{ id = 2, type = "captcha" },
				{ id = 3, type = "ban", scope = "Country", value = "FR" },
			})
	end
	local data, err, status = control.run(control_conf(), nil, "decisions", { ip = IP })
	eq(err, nil)
	eq(status, 200)
	local by_id = {}
	for _, d in ipairs(data.decisions) do
		by_id[d.id] = d
	end
	eq(by_id[1].remediation, "ban")
	eq(by_id[2].remediation, nil, "a captcha decision is ignored when only bans are bounced")
	eq(by_id[3].remediation, nil, "a scope the bouncer never caches has no remediation")
end)

it("decisions rows follow BOUNCING_ON_TYPE=all with the fallback", function()
	local control = H.load_control()
	H.control_http = function()
		return 200, lapi_body({ { id = 1, type = "captcha" }, { id = 2, type = "throttle" }, { id = 3, type = "ban" } })
	end
	local c = control_conf()
	c.BOUNCING_ON_TYPE, c.FALLBACK_REMEDIATION = "all", "ban"
	local data = control.run(c, nil, "decisions", { ip = IP })
	local by_id = {}
	for _, d in ipairs(data.decisions) do
		by_id[d.id] = d
	end
	eq(by_id[1].remediation, "captcha")
	eq(by_id[2].remediation, "ban", "an unknown type takes the fallback")
	eq(by_id[3].remediation, "ban")
end)

it("decisions without an ip filter still answer", function()
	local control = H.load_control()
	H.control_http = function()
		return 200, lapi_body({ { id = 1, type = "ban" } })
	end
	local data, _, status = control.run(control_conf(), nil, "decisions", {})
	eq(status, 200)
	eq(data.decisions[1].remediation, "ban")
end)

local function unban_params(type_)
	return { decision_id = 5, scope = "Ip", value = IP, decision_type = type_ or "ban" }
end

it("unban of a decision that is already gone answers 200 with already_absent", function()
	local control = H.load_control()
	local calls = {}
	H.control_http = function(method, path, query)
		calls[#calls + 1] = method .. " " .. path
		if method == "GET" and query_has(query, "contains=false") then
			return 200, "null"
		end
		if method == "GET" then
			return 200, lapi_body({ { id = 9, type = "ban" } })
		end
		return 500, "unexpected"
	end
	local data, err, status = control.run(control_conf(), nil, "unban", unban_params())
	eq(err, nil)
	eq(status, 200)
	eq(data.removed, false)
	eq(data.already_absent, true)
	eq(data.decision, nil)
	eq(#data.remaining_decisions, 1)
	eq(data.remaining_decisions[1].id, 9)
	eq(type(data.observed_at), "number")
	eq(data.propagation.status, "pending")
	eq(data.propagation.mode, "stream")
	for _, call in ipairs(calls) do
		assert(
			not call:find("^DELETE") and not call:find("login"),
			"nothing is changed for an absent decision: " .. call
		)
	end
end)

it("unban of a decision that changed is still a 409", function()
	local control = H.load_control()
	H.control_http = function()
		return 200, lapi_body({ { id = 5, type = "captcha" } })
	end
	local data, err, status = control.run(control_conf(), nil, "unban", unban_params("ban"))
	eq(data, nil)
	eq(status, 409)
	assert(err:find("changed", 1, true))
end)

it("unban of a live decision still deletes it and verifies", function()
	local control = H.load_control()
	local deleted = false
	H.control_http = function(method, path)
		if method == "POST" and path:find("login") then
			return 200, '{"token":"tok"}'
		end
		if method == "DELETE" then
			deleted = true
			return 200, '{"nbDeleted":1}'
		end
		if deleted then
			return 200, "null"
		end
		return 200, lapi_body({ { id = 5, type = "ban" } })
	end
	local data, err, status = control.run(control_conf(), nil, "unban", unban_params())
	eq(err, nil)
	eq(status, 200)
	eq(data.removed, true)
	eq(data.already_absent, false)
	eq(data.decision.id, 5)
end)

if failures > 0 then
	print(failures .. " failed")
	os.exit(1)
end
