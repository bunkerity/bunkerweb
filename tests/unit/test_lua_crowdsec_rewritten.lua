-- Plain Lua test for the CrowdSec bouncer internal-request check: a request that was only rewritten is checked.
-- Run from the repo root: lua tests/unit/test_lua_crowdsec_rewritten.lua
local script_dir = arg[0]:match("^(.*)/[^/]+$") or "."
local root = script_dir .. "/../.."
local F = dofile(root .. "/tests/unit/lua_lease_fakes.lua")(root)
local H = dofile(root .. "/tests/unit/lua_crowdsec_fakes.lua")(root)
H.banlease = require("bunkerweb.banlease")

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
local flag = package.loaded["crowdsec.lib.flag"]
flag.Flags[flag.BOUNCER_SOURCE] = "bouncer"

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

-- Runs Allow() for an IP with a live ban decision; internal and rewritten set the request state
local function allow(extra_conf, internal, rewritten)
	local bouncer = H.load_bouncer(conf(extra_conf))
	H.lapi = function()
		return 200,
			'[{"id":1,"origin":"cscli","scenario":"x/y","scope":"Ip","type":"ban","value":"'
				.. IP
				.. '","duration":"1h"}]'
	end
	ngx.req = ngx.req or {}
	ngx.req.is_internal = function()
		return internal
	end
	ngx.ctx = { bw = { rewritten = rewritten } }
	local ok, status, banned = bouncer.Allow(IP, "svc")
	return ok, status, banned
end

it("internal request not marked rewritten is skipped", function()
	local ok, status, banned = allow(nil, true, nil)
	eq(ok, true)
	eq(status, "internal")
	eq(banned, nil)
end)

it("internal request marked rewritten is checked and the ban applied", function()
	local ok, status, banned = allow(nil, true, true)
	assert(status ~= "internal", "the rewritten request was skipped")
	eq(ok, true)
	eq(banned, true, "the ban decision was not applied")
end)

it("request that is not internal is checked", function()
	local ok, status, banned = allow(nil, false, nil)
	assert(status ~= "internal", "a plain request was skipped")
	eq(ok, true)
	eq(banned, true, "the ban decision was not applied")
end)

it("ENABLE_INTERNAL=true checks an internal request that is not marked", function()
	local ok, status, banned = allow({ ENABLE_INTERNAL = "true" }, true, nil)
	assert(status ~= "internal", "an internal request was skipped")
	eq(ok, true)
	eq(banned, true, "the ban decision was not applied")
end)

if failures > 0 then
	print(failures .. " failed")
	os.exit(1)
end
