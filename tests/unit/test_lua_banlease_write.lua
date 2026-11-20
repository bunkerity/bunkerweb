-- Plain Lua check of lease building, promotion, removal and lookup in bunkerweb.banlease.
-- Run: lua tests/unit/test_lua_banlease_write.lua   (from the repo root)
local root = arg[0]:match("^(.*)/tests/unit/") or "."
local F = dofile(root .. "/tests/unit/lua_lease_fakes.lua")(root)
local json = F.json

local failures = 0
local function it(name, fn)
	F.reset()
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. tostring(err))))
	if not ok then
		failures = failures + 1
	end
end

local banlease = require("bunkerweb.banlease")

local function set_var(name, value)
	F.vars[name] = value
end
local function local_get(key)
	return F.store[key] and F.store[key].value or nil
end
local redis_get = F.redis_get
local function redis_put(key, value, ttl)
	F.redis[key] = { value = value, ttl = ttl }
end
local function lease_json(epoch)
	return json.encode({
		reason = "crowdsec",
		service = "www",
		date = 1700000000,
		country = "local",
		ban_scope = "global",
		reason_data = { lease = true },
		permanent = false,
		kind = "crowdsec_lease",
		lease_epoch = epoch,
	})
end

it("build_lease keeps only live ban decisions and caps the ttl", function()
	local ev = {
		source = "lapi",
		remediation = "ban",
		instance = "node1",
		connection = string.rep("a", 64),
		service_scope = "global",
		captured_at = 100,
		decisions = {
			{ id = 1, remediation = "ban", expires_at = 130 },
			{ id = 2, remediation = "captcha", expires_at = 9999 },
		},
	}
	local ttl, rd = banlease.build_lease(ev, 100, 300)
	assert(ttl == 30 and rd.lease == true and rd.instance == "node1" and rd.connection == ev.connection)
	assert(rd.version == 1 and rd.source == "lapi" and rd.remediation == "ban" and rd.captured_at == 100)
	assert(banlease.build_lease(ev, 100, 10) == 10)
	assert(banlease.build_lease({ source = "appsec", remediation = "ban", decisions = {} }, 100, 300) == nil)
	ev.decisions[1].expires_at = 100
	assert(banlease.build_lease(ev, 100, 300) == nil, "expired decision")
end)

it("build_lease never returns 0 and caps provenance at 10 decisions", function()
	local ev = { source = "lapi", remediation = "ban", decisions = {} }
	for i = 1, 15 do
		ev.decisions[i] = { id = i, remediation = "ban", expires_at = 100.4 }
	end
	local ttl, rd = banlease.build_lease(ev, 100, 300)
	assert(ttl == 1 and #rd.decisions == 10)
end)

it("build_lease refuses evidence that is not a LAPI ban and decisions without an id", function()
	local ttl, why = banlease.build_lease(nil, 100, 300)
	assert(ttl == nil and why)
	ttl, why = banlease.build_lease({ source = "lapi", remediation = "captcha", decisions = {} }, 100, 300)
	assert(ttl == nil and why == "not a LAPI ban")
	ttl, why = banlease.build_lease(
		{ source = "lapi", remediation = "ban", decisions = { { remediation = "ban", expires_at = 500 } } },
		100,
		300
	)
	assert(ttl == nil and why == "no live ban decision")
end)

it("build_lease keeps the provenance fields only", function()
	local ev = {
		source = "lapi",
		remediation = "ban",
		decisions = {
			{
				id = 7,
				origin = "crowdsec",
				scenario = "http-probing",
				type = "ban",
				scope = "Ip",
				value = "1.2.3.4",
				expires_at = 200,
				remediation = "ban",
				duration = "3h",
				simulated = false,
			},
		},
	}
	local _, rd = banlease.build_lease(ev, 100, 300)
	local d = rd.decisions[1]
	assert(d.id == 7 and d.origin == "crowdsec" and d.scenario == "http-probing" and d.type == "ban")
	assert(d.scope == "Ip" and d.value == "1.2.3.4" and d.expires_at == 200 and d.remediation == "ban")
	assert(d.duration == nil and d.simulated == nil)
end)

it("promotion without Redis writes the local lease when the lease epoch is unchanged", function()
	local e = banlease.lease_epoch("1.2.3.4", true)
	local ok, status = banlease.promote_lease(
		"1.2.3.4",
		nil,
		"global",
		30,
		{ lease = true },
		"local",
		{ lease_epoch = e }
	)
	assert(ok and status == "written" and local_get("bans_cs_ip_1.2.3.4"))
	local row = json.decode(local_get("bans_cs_ip_1.2.3.4"))
	assert(row.kind == "crowdsec_lease" and row.reason == "crowdsec" and row.service == "unknown")
	assert(row.ban_scope == "global" and row.permanent == false and row.lease_epoch == e and row.country == "local")
	assert(F.store["bans_cs_ip_1.2.3.4"].ttl == 30)
	assert(#F.calls == 0, "no Redis without USE_REDIS")
end)

it("promotion is skipped when the lease epoch moved", function()
	local e = banlease.lease_epoch("1.2.3.5", true)
	banlease.bump_lease_epoch("1.2.3.5")
	local ok, status = banlease.promote_lease("1.2.3.5", nil, "global", 30, {}, "local", { lease_epoch = e })
	assert(not ok and status == "stale" and not local_get("bans_cs_ip_1.2.3.5"))
end)

it("promotion is skipped when no lease epoch could be captured", function()
	local ok, status = banlease.promote_lease("1.2.3.5", nil, "global", 30, {}, "local", { lease_epoch = nil })
	assert(not ok and status == "stale" and not local_get("bans_cs_ip_1.2.3.5"))
end)

it("promotion with Redis: absent epoch creates it and writes, stale skips, match writes both", function()
	set_var("USE_REDIS", "yes")
	local e = banlease.lease_epoch("1.2.3.6", true)
	local ok, status = banlease.promote_lease(
		"1.2.3.6",
		"www",
		"service",
		30,
		{},
		"local",
		{ lease_epoch = e, redis_epoch = false }
	)
	assert(ok and status == "written" and redis_get("cs_epoch_1.2.3.6"):match("^%x+:1$"), "first deny writes the lease")
	assert(redis_get("bans_cs_service_www_ip_1.2.3.6") and F.redis["bans_cs_service_www_ip_1.2.3.6"].ttl == 30)
	F.redis["bans_cs_service_www_ip_1.2.3.6"] = nil
	ok, status = banlease.promote_lease(
		"1.2.3.6",
		"www",
		"service",
		30,
		{},
		"local",
		{ lease_epoch = e, redis_epoch = false }
	)
	assert(not ok and status == "stale", "absent at capture but created since (refresh/remove ran): fenced")
	ok, status = banlease.promote_lease(
		"1.2.3.6",
		"www",
		"service",
		30,
		{},
		"local",
		{ lease_epoch = e, redis_epoch = "old:1" }
	)
	assert(not ok and status == "stale")
	ok, status = banlease.promote_lease(
		"1.2.3.6",
		"www",
		"service",
		30,
		{},
		"local",
		{ lease_epoch = e, redis_epoch = redis_get("cs_epoch_1.2.3.6") }
	)
	assert(
		ok
			and status == "written"
			and redis_get("bans_cs_service_www_ip_1.2.3.6")
			and local_get("bans_cs_service_www_ip_1.2.3.6")
	)
end)

it("promotion with Redis unreachable keeps a local lease", function()
	set_var("USE_REDIS", "yes")
	F.flags.redis_down = true
	local e = banlease.lease_epoch("1.2.3.7", true)
	local ok, status = banlease.promote_lease(
		"1.2.3.7",
		nil,
		"global",
		30,
		{},
		"local",
		{ lease_epoch = e, redis_epoch = "x:1" }
	)
	assert(ok and status == "local_only" and local_get("bans_cs_ip_1.2.3.7"))
end)

it("promotion keeps a local lease on a Redis configuration error, a failed call or an error reply", function()
	set_var("USE_REDIS", "yes")
	local e = banlease.lease_epoch("1.2.3.7", true)
	local captured = { lease_epoch = e, redis_epoch = "x:1" }
	F.flags.config_error = "bad nodes"
	local ok, status = banlease.promote_lease("1.2.3.7", nil, "global", 30, {}, "local", captured)
	assert(ok and status == "local_only")
	F.flags.config_error = nil
	F.flags.redis_call_fails = true
	F.store["bans_cs_ip_1.2.3.7"] = nil
	ok, status = banlease.promote_lease("1.2.3.7", nil, "global", 30, {}, "local", captured)
	assert(ok and status == "local_only" and local_get("bans_cs_ip_1.2.3.7"))
	F.flags.redis_call_fails = nil
	F.flags.redis_error_reply = true
	F.store["bans_cs_ip_1.2.3.7"] = nil
	ok, status = banlease.promote_lease("1.2.3.7", nil, "global", 30, {}, "local", captured)
	assert(ok and status == "local_only" and local_get("bans_cs_ip_1.2.3.7"))
end)

it("promotion with Redis on but not checked at capture skips Redis", function()
	set_var("USE_REDIS", "yes")
	local e = banlease.lease_epoch("1.2.3.9", true)
	local ok, status = banlease.promote_lease("1.2.3.9", nil, "global", 30, {}, "local", { lease_epoch = e })
	assert(ok and status == "local_only" and local_get("bans_cs_ip_1.2.3.9") and #F.calls == 0)
end)

it("promotion without an incarnation changes nothing", function()
	set_var("USE_REDIS", "yes")
	local e = banlease.lease_epoch("1.2.3.9", true)
	local random = package.loaded["resty.random"]
	local saved = random.bytes
	random.bytes = function()
		return nil
	end
	local ok, status = banlease.promote_lease(
		"1.2.3.9",
		nil,
		"global",
		30,
		{},
		"local",
		{ lease_epoch = e, redis_epoch = false }
	)
	random.bytes = saved
	assert(not ok and status and status ~= "stale")
	assert(#F.calls == 0 and not local_get("bans_cs_ip_1.2.3.9") and next(F.redis) == nil)
end)

it("promotion discards the lease when the local epoch moved during the Redis call", function()
	set_var("USE_REDIS", "yes")
	local e = banlease.lease_epoch("1.2.3.10", true)
	F.hooks.on_call = function()
		banlease.bump_lease_epoch("1.2.3.10")
	end
	local ok, status = banlease.promote_lease(
		"1.2.3.10",
		nil,
		"global",
		30,
		{},
		"local",
		{ lease_epoch = e, redis_epoch = false }
	)
	assert(not ok and status == "stale" and not local_get("bans_cs_ip_1.2.3.10"))
end)

it("promotion reports a local datastore failure", function()
	local e = banlease.lease_epoch("1.2.3.11", true)
	F.flags.datastore_full = true
	local ok, status = banlease.promote_lease("1.2.3.11", nil, "global", 30, {}, "local", { lease_epoch = e })
	assert(not ok and type(status) == "string" and status:find("no memory", 1, true))
end)

it("promotion drops the resolved markers of the IP and never moves the marker epoch", function()
	local e = banlease.lease_epoch("1.2.3.12", true)
	local me = banlease.marker_epoch("1.2.3.12", true)
	assert(banlease.write_marker("www", "1.2.3.12", "manual", 2, me, 30))
	assert(banlease.write_marker("", "1.2.3.12", "manual", 2, me, 30))
	assert(banlease.write_marker("other", "1.2.3.12", "manual", 2, me, 30))
	local ok = banlease.promote_lease("1.2.3.12", "www", "service", 30, {}, "local", { lease_epoch = e })
	assert(ok)
	assert(banlease.read_marker("www", "1.2.3.12") == nil and banlease.read_marker("", "1.2.3.12") == nil)
	assert(banlease.read_marker("other", "1.2.3.12"), "another service keeps its marker")
	assert(banlease.marker_epoch("1.2.3.12", false) == me)
end)

it("remove_lease bumps both epochs, deletes local and Redis, and reports Redis failures", function()
	set_var("USE_REDIS", "yes")
	local e = banlease.lease_epoch("1.2.3.6", true)
	assert(
		banlease.promote_lease("1.2.3.6", "www", "service", 30, {}, "local", { lease_epoch = e, redis_epoch = false })
	)
	local le0, me0 = banlease.lease_epoch("1.2.3.6"), banlease.marker_epoch("1.2.3.6", true)
	local inc = redis_get("cs_epoch_1.2.3.6"):match("^(%x+):")
	local ok, detail = banlease.remove_lease("1.2.3.6", "www", "service")
	assert(ok and detail.redis == "deleted")
	assert(not local_get("bans_cs_service_www_ip_1.2.3.6") and not redis_get("bans_cs_service_www_ip_1.2.3.6"))
	assert(banlease.lease_epoch("1.2.3.6") ~= le0 and banlease.marker_epoch("1.2.3.6") ~= me0)
	assert(redis_get("cs_epoch_1.2.3.6") == inc .. ":2", "increment keeps the incarnation")
	F.flags.redis_down = true
	ok = banlease.remove_lease("1.2.3.6", "www", "service")
	assert(not ok)
end)

it("remove_lease without Redis reports it disabled and still deletes the local copy", function()
	local e = banlease.lease_epoch("1.2.3.13", true)
	assert(banlease.promote_lease("1.2.3.13", nil, "global", 30, {}, "local", { lease_epoch = e }))
	local ok, detail = banlease.remove_lease("1.2.3.13", nil, "global")
	assert(ok and detail.redis == "disabled" and not local_get("bans_cs_ip_1.2.3.13"))
	assert(banlease.lease_epoch("1.2.3.13") ~= e)
end)

it("remove_lease fences and deletes locally even when Redis fails, with the reason", function()
	set_var("USE_REDIS", "yes")
	local e = banlease.lease_epoch("1.2.3.14", true)
	assert(banlease.promote_lease("1.2.3.14", nil, "global", 30, {}, "local", { lease_epoch = e, redis_epoch = false }))
	for _, flag in ipairs({ "redis_down", "config_error", "redis_call_fails", "redis_error_reply" }) do
		F.flags[flag] = flag == "config_error" and "bad nodes" or true
		local ok, detail = banlease.remove_lease("1.2.3.14", nil, "global")
		assert(ok == false and type(detail) == "string" and detail:find("^redis: "), flag)
		assert(not local_get("bans_cs_ip_1.2.3.14"), flag)
		assert(banlease.lease_epoch("1.2.3.14") ~= e, flag)
		F.flags[flag] = nil
	end
	assert(redis_get("bans_cs_ip_1.2.3.14"), "a failed Redis removal leaves the Redis key for the retry")
end)

it("remove_lease moves both epochs again after the Redis call, for lookups that yielded around it", function()
	set_var("USE_REDIS", "yes")
	banlease.lease_epoch("1.2.3.21", true)
	banlease.marker_epoch("1.2.3.21", true)
	local seen_lease, seen_marker
	F.hooks.on_call = function()
		seen_lease, seen_marker = banlease.lease_epoch("1.2.3.21", false), banlease.marker_epoch("1.2.3.21", false)
	end
	assert(banlease.remove_lease("1.2.3.21", nil, "global"))
	assert(seen_lease and seen_marker, "both epochs exist before the Redis call")
	assert(banlease.lease_epoch("1.2.3.21", false) ~= seen_lease)
	assert(banlease.marker_epoch("1.2.3.21", false) ~= seen_marker)
end)

it("remove_lease only touches the lease key it was given, and never the explicit ban", function()
	local e = banlease.lease_epoch("1.2.3.15", true)
	banlease.promote_lease("1.2.3.15", nil, "global", 30, {}, "local", { lease_epoch = e })
	F.store["bans_ip_1.2.3.15"] = { value = "{}", ttl = 0 }
	F.stream_store["bans_cs_ip_1.2.3.15"] = { value = "{}", ttl = 5 }
	assert(banlease.remove_lease("1.2.3.15", nil, "global"))
	assert(F.store["bans_ip_1.2.3.15"], "explicit ban kept")
	assert(F.stream_store["bans_cs_ip_1.2.3.15"], "the stream dict is unreachable")
end)

it("bump_redis_epoch is a no-op without Redis and never succeeds silently with Redis", function()
	assert(banlease.bump_redis_epoch("1.2.3.16") == true and #F.calls == 0)
	set_var("USE_REDIS", "yes")
	assert(banlease.bump_redis_epoch("1.2.3.16") == true)
	assert(redis_get("cs_epoch_1.2.3.16"):match("^%x+:1$"))
	assert(banlease.bump_redis_epoch("1.2.3.16") == true and redis_get("cs_epoch_1.2.3.16"):match("^%x+:2$"))
	for _, flag in ipairs({ "redis_down", "config_error", "redis_call_fails", "redis_error_reply" }) do
		F.flags[flag] = flag == "config_error" and "bad nodes" or true
		local ok, err = banlease.bump_redis_epoch("1.2.3.16")
		assert(ok == false and type(err) == "string", flag)
		F.flags[flag] = nil
	end
end)

it("lookup_lease finds the local lease, epoch-valid, with the GET /bans row shape", function()
	local e = banlease.lease_epoch("1.2.3.17", true)
	F.store["bans_cs_ip_1.2.3.17"] = { value = lease_json(e), ttl = 25 }
	local row, err, checked = banlease.lookup_lease("1.2.3.17", nil, "global")
	assert(row and err == nil and checked == false)
	assert(row.ip == "1.2.3.17" and row.kind == "crowdsec_lease" and row.source == "local" and row.exp == 25)
	assert(row.reason == "crowdsec" and row.ban_scope == "global" and row.permanent == false)
	assert(type(row.reason_data) == "table" and row.reason_data.lease == true)
	banlease.bump_lease_epoch("1.2.3.17")
	row, err, checked = banlease.lookup_lease("1.2.3.17", nil, "global")
	assert(row == nil and err == nil and checked == false, "a stale copy counts as absent")
end)

it("lookup_lease finds a Redis-only lease without writing a local copy", function()
	set_var("USE_REDIS", "yes")
	redis_put("bans_cs_service_a_ip_b.example.com_ip_1.2.3.18", lease_json(99), 20)
	local row, err, checked = banlease.lookup_lease("1.2.3.18", "a_ip_b.example.com", "service")
	assert(row and err == nil and checked == true, "found")
	assert(
		row.source == "redis" and row.exp == 20 and row.service == "a_ip_b.example.com" and row.ban_scope == "service"
	)
	assert(row.ip == "1.2.3.18" and row.kind == "crowdsec_lease")
	assert(next(F.store) == nil, "no local copy is written")
	assert(banlease.lease_epoch("1.2.3.18", false) == nil, "no epoch is created")
end)

it("lookup_lease reports not found with Redis checked, and Redis errors", function()
	set_var("USE_REDIS", "yes")
	local row, err, checked = banlease.lookup_lease("1.2.3.19", nil, "global")
	assert(row == nil and err == nil and checked == true)
	redis_put("bans_cs_ip_1.2.3.19", lease_json(1), -2)
	row, err, checked = banlease.lookup_lease("1.2.3.19", nil, "global")
	assert(row == nil and err == nil and checked == true, "a key that expired between GET and TTL is absent")
	redis_put("bans_cs_ip_1.2.3.19", lease_json(1), 20)
	for _, flag in ipairs({ "redis_down", "config_error", "redis_call_fails", "redis_error_reply" }) do
		F.flags[flag] = flag == "config_error" and "bad nodes" or true
		row, err = banlease.lookup_lease("1.2.3.19", nil, "global")
		assert(row == nil and type(err) == "string", flag)
		F.flags[flag] = nil
	end
end)

it("lookup_lease prefers the local lease and never asks Redis then", function()
	set_var("USE_REDIS", "yes")
	local e = banlease.lease_epoch("1.2.3.20", true)
	F.store["bans_cs_ip_1.2.3.20"] = { value = lease_json(e), ttl = 25 }
	local row = banlease.lookup_lease("1.2.3.20", nil, "global")
	assert(row and row.source == "local" and #F.calls == 0)
end)

it("cap_reason_data keeps small data, trims decisions, then falls back to the minimal shape", function()
	local small = { version = 1, lease = true, decisions = { { id = 1 } } }
	assert(banlease.cap_reason_data(small).decisions[1].id == 1)
	assert(next(banlease.cap_reason_data(nil)) == nil and next(banlease.cap_reason_data("text")) == nil)
	local big =
		{ version = 1, lease = true, instance = "n1", connection = "c", service_scope = "global", decisions = {} }
	for i = 1, 10 do
		big.decisions[i] = { id = i, scenario = string.rep("s", 900) }
	end
	local capped = banlease.cap_reason_data(big)
	assert(#json.encode(capped) <= 4096 and #capped.decisions >= 1 and #capped.decisions < 10 and capped.lease == true)
	local huge = {
		version = 1,
		lease = true,
		instance = "n1",
		connection = string.rep("c", 5000),
		service_scope = "global",
		extra = "x",
		decisions = { { id = 1 } },
	}
	capped = banlease.cap_reason_data(huge)
	assert(capped.truncated == true and capped.lease == true and capped.instance == "n1" and capped.extra == nil)
	assert(capped.decisions == nil)
end)

os.exit(failures == 0 and 0 or 1)
