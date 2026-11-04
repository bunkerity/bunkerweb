-- Plain Lua check of the lease routes of the instance API (bunkerweb.api): GET /bans, POST /lease_lookup and
-- POST /remove_lease.
-- Run: lua tests/unit/test_lua_api_leases.lua   (from the repo root)
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

-- Everything api.lua requires that the routes under test never use
local request_body
ngx.req = {
	read_body = function() end,
	get_body_data = function()
		return request_body
	end,
	get_body_file = function() end,
	get_headers = function()
		return {}
	end,
}
package.loaded["bit"] = {}
package.loaded["ffi"] = {
	cdef = function() end,
	C = {},
	errno = function()
		return 0
	end,
}
package.loaded["middleclass"] = function(name)
	return { name = name }
end
package.loaded["bunkerweb.helpers"] = {}
package.loaded["ngx.process"] = {}
package.loaded["bunkerweb.pushswap"] = {}
package.loaded["resty.lock"] = {}
package.loaded["resty.signal"] = {}
package.loaded["resty.upload"] = {}

local api = require("bunkerweb.api")
local banlease = require("bunkerweb.banlease")
local self = setmetatable({ ctx = { bw = {} } }, { __index = api })

local function post(route, body)
	request_body = type(body) == "table" and json.encode(body) or body
	local status, resp = api.global.POST[route](self)
	return status, resp
end
local function list_bans()
	local status, resp = api.global.GET["^/bans$"](self)
	assert(status == 200, "GET /bans status " .. tostring(status))
	return resp.msg
end
local function find(rows, ip, kind)
	for _, row in ipairs(rows) do
		if row.ip == ip and row.kind == kind then
			return row
		end
	end
end
local function lease_json(epoch, extra)
	local row = {
		reason = "crowdsec",
		service = "unknown",
		date = 1700000000,
		country = "local",
		ban_scope = "global",
		reason_data = { lease = true },
		permanent = false,
		kind = "crowdsec_lease",
		lease_epoch = epoch,
	}
	for k, v in pairs(extra or {}) do
		row[k] = v
	end
	return json.encode(row)
end
local function ban_json(extra)
	local row = {
		reason = "manual",
		service = "unknown",
		date = 1700000000,
		country = "local",
		ban_scope = "global",
		reason_data = {},
		permanent = false,
	}
	for k, v in pairs(extra or {}) do
		row[k] = v
	end
	return json.encode(row)
end
local SERVICE = "a_ip_b.example.com"

it("GET /bans lists explicit bans and leases with kind, splitting at the last _ip_", function()
	local e = banlease.lease_epoch("1.1.1.1", true)
	local e2 = banlease.lease_epoch("1.1.1.2", true)
	F.store["bans_ip_1.1.1.1"] = { value = ban_json({ reason = "ui" }), ttl = 50 }
	F.store["bans_service_" .. SERVICE .. "_ip_1.1.1.2"] = { value = ban_json({ ban_scope = "service" }), ttl = 60 }
	F.store["bans_cs_ip_1.1.1.1"] = { value = lease_json(e), ttl = 20 }
	F.store["bans_cs_service_" .. SERVICE .. "_ip_1.1.1.2"] =
		{ value = lease_json(e2, { ban_scope = "service" }), ttl = 30 }
	local rows = list_bans()
	assert(#rows == 4, "rows: " .. #rows)
	local explicit_global = find(rows, "1.1.1.1", "ban")
	assert(explicit_global.reason == "ui" and explicit_global.exp == 50 and explicit_global.ban_scope == "global")
	assert(type(explicit_global.reason_data) == "table")
	local explicit_service = find(rows, "1.1.1.2", "ban")
	assert(
		explicit_service.service == SERVICE and explicit_service.ban_scope == "service" and explicit_service.exp == 60
	)
	local lease_global = find(rows, "1.1.1.1", "crowdsec_lease")
	assert(lease_global.reason == "crowdsec" and lease_global.exp == 20 and lease_global.permanent == false)
	assert(lease_global.reason_data.lease == true and lease_global.ban_scope == "global")
	local lease_service = find(rows, "1.1.1.2", "crowdsec_lease")
	assert(lease_service.service == SERVICE and lease_service.ban_scope == "service" and lease_service.exp == 30)
end)

it("GET /bans skips a lease whose epoch moved or never existed, never an explicit ban", function()
	local e = banlease.lease_epoch("2.2.2.2", true)
	F.store["bans_cs_ip_2.2.2.2"] = { value = lease_json(e), ttl = 20 }
	F.store["bans_cs_ip_2.2.2.3"] = { value = lease_json(5), ttl = 20 }
	F.store["bans_ip_2.2.2.2"] = { value = ban_json(), ttl = 20 }
	assert(find(list_bans(), "2.2.2.2", "crowdsec_lease"))
	assert(find(list_bans(), "2.2.2.3", "crowdsec_lease") == nil, "no epoch for the IP")
	banlease.bump_lease_epoch("2.2.2.2")
	local rows = list_bans()
	assert(find(rows, "2.2.2.2", "crowdsec_lease") == nil, "stale epoch")
	assert(find(rows, "2.2.2.2", "ban"), "explicit ban stays")
end)

it("GET /bans keeps the legacy plain-string row and the permanent flag", function()
	F.store["bans_ip_3.3.3.3"] = { value = "manual", ttl = 0 }
	F.store["bans_ip_3.3.3.4"] = { value = ban_json({ permanent = true }), ttl = 77 }
	local rows = list_bans()
	local legacy = find(rows, "3.3.3.3", "ban")
	assert(
		legacy.reason == "manual" and legacy.service == "unknown" and legacy.date == 0 and legacy.ban_scope == "global"
	)
	local permanent = find(rows, "3.3.3.4", "ban")
	assert(permanent.permanent == true and permanent.exp == 0)
end)

it("GET /bans skips a key that vanished between the listing and the read", function()
	F.store["bans_ip_4.4.4.4"] = { value = ban_json(), ttl = 10 }
	F.flags.ghost_keys = { "bans_cs_ip_4.4.4.5", "bans_ip_4.4.4.6", "bans_service_www_ip_4.4.4.7" }
	local rows = list_bans()
	assert(#rows == 1 and rows[1].ip == "4.4.4.4")
end)

it("GET /bans caps reason_data at 4096 bytes", function()
	local e = banlease.lease_epoch("5.5.5.5", true)
	local decisions = {}
	for i = 1, 10 do
		decisions[i] = { id = i, scenario = string.rep("s", 900) }
	end
	F.store["bans_cs_ip_5.5.5.5"] = {
		value = lease_json(e, { reason_data = { version = 1, lease = true, instance = "n1", decisions = decisions } }),
		ttl = 20,
	}
	local row = find(list_bans(), "5.5.5.5", "crowdsec_lease")
	assert(#json.encode(row.reason_data) <= 4096 and row.reason_data.lease == true)
	assert(#row.reason_data.decisions < 10)
end)

it("POST /remove_lease deletes the lease of a service with _ip_ in its name, locally and in Redis", function()
	F.vars.USE_REDIS = "yes"
	local e = banlease.lease_epoch("6.6.6.6", true)
	local key = "bans_cs_service_" .. SERVICE .. "_ip_6.6.6.6"
	F.store[key] = { value = lease_json(e, { ban_scope = "service" }), ttl = 20 }
	F.redis[key] = { value = "x", ttl = 20 }
	F.store["bans_cs_ip_6.6.6.6"] = { value = lease_json(e), ttl = 20 }
	assert(#list_bans() == 2)
	local status, resp = post("^/remove_lease$", { ip = "6.6.6.6", ban_scope = "service", service = SERVICE })
	assert(status == 200 and resp.status == "success" and resp.msg == "success", tostring(status))
	assert(resp.data.redis == "deleted")
	assert(F.store[key] == nil and F.redis[key] == nil)
	assert(F.store["bans_cs_ip_6.6.6.6"], "only the addressed lease key is deleted")
	assert(#list_bans() == 0, "the epoch moved, so the global copy counts as absent as well")
end)

it("POST /remove_lease answers on the wire with status, msg and data", function()
	F.store["bans_cs_ip_6.6.6.7"] = { value = lease_json(banlease.lease_epoch("6.6.6.7", true)), ttl = 20 }
	self.ctx.bw.request_method, self.ctx.bw.uri = "POST", "/remove_lease"
	request_body = json.encode({ ip = "6.6.6.7" })
	local ok, msg, status, body = api.do_api_call(self)
	assert(ok == true and msg == "success" and status == 200)
	assert(body:find('"data":{"redis":"disabled"}', 1, true) and body:find('"status":"success"', 1, true), body)
end)

it("POST /remove_lease rejects bad input with 400 and reports Redis failures as 502", function()
	local cases = {
		{ "not json" },
		{ { ban_scope = "global" } },
		{ { ip = "nope" } },
		{ { ip = 5 } },
		{ { ip = "1.2.3.4", ban_scope = "everywhere" } },
		{ { ip = "1.2.3.4", ban_scope = "service" } },
		{ { ip = "1.2.3.4", ban_scope = "service", service = 5 } },
	}
	for i, case in ipairs(cases) do
		local status, resp = post("^/remove_lease$", case[1])
		assert(status == 400 and resp.status == "error", "case " .. i .. " status " .. tostring(status))
	end
	F.vars.USE_REDIS = "yes"
	F.flags.redis_down = true
	local status, resp = post("^/remove_lease$", { ip = "1.2.3.4" })
	assert(status == 502 and resp.status == "error" and resp.msg:find("redis", 1, true), tostring(status))
end)

it("a reserved service name downgrades to the global lease, as /unban does", function()
	local e = banlease.lease_epoch("7.7.7.7", true)
	F.store["bans_cs_ip_7.7.7.7"] = { value = lease_json(e), ttl = 20 }
	local status, resp = post("^/lease_lookup$", { ip = "7.7.7.7", ban_scope = "service", service = "Web UI" })
	assert(status == 200 and resp.data.found == true and resp.data.row.ban_scope == "global")
	status = post("^/remove_lease$", { ip = "7.7.7.7", ban_scope = "service", service = "unknown" })
	assert(status == 200 and F.store["bans_cs_ip_7.7.7.7"] == nil)
end)

it("POST /lease_lookup finds a local lease and reports Redis as not checked", function()
	local e = banlease.lease_epoch("8.8.8.8", true)
	F.store["bans_cs_service_" .. SERVICE .. "_ip_8.8.8.8"] = {
		value = lease_json(e, { ban_scope = "service" }),
		ttl = 15,
	}
	local status, resp = post("^/lease_lookup$", { ip = "8.8.8.8", ban_scope = "service", service = SERVICE })
	assert(status == 200 and resp.status == "success" and resp.data.found == true)
	local row = resp.data.row
	assert(row.source == "local" and row.exp == 15 and row.kind == "crowdsec_lease" and row.service == SERVICE)
	status, resp = post("^/lease_lookup$", { ip = "8.8.8.9" })
	assert(status == 200 and resp.data.found == false and resp.data.redis_checked == false and resp.data.row == nil)
end)

it("POST /lease_lookup finds a Redis-only lease", function()
	F.vars.USE_REDIS = "yes"
	F.redis["bans_cs_ip_9.9.9.9"] = { value = lease_json(12), ttl = 40 }
	local status, resp = post("^/lease_lookup$", { ip = "9.9.9.9" })
	assert(status == 200 and resp.data.found == true and resp.data.row.source == "redis" and resp.data.row.exp == 40)
	assert(next(F.store) == nil, "no local copy written")
	status, resp = post("^/lease_lookup$", { ip = "9.9.9.8" })
	assert(status == 200 and resp.data.found == false and resp.data.redis_checked == true)
end)

it("POST /lease_lookup answers 502 when Redis is on but cannot be read, 400 on bad input", function()
	F.vars.USE_REDIS = "yes"
	F.flags.redis_down = true
	local status, resp = post("^/lease_lookup$", { ip = "9.9.9.9" })
	assert(status == 502 and resp.status == "error" and resp.data == nil, tostring(status))
	status = post("^/lease_lookup$", { ip = "bad" })
	assert(status == 400)
end)

os.exit(failures == 0 and 0 or 1)
