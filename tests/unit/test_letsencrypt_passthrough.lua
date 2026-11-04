-- Plain Lua check of the letsencrypt set/access hooks for a passed-through ACME challenge.
-- Run: lua tests/unit/test_letsencrypt_passthrough.lua   (from the repo root)
package.path = "src/bw/lua/?.lua;src/bw/lua/?/init.lua;src/common/core/letsencrypt/?.lua;" .. package.path

local env_values = {}
package.loaded["resty.env"] = {
	set = function(k, v)
		env_values[k] = v
	end,
	get = function(k)
		return env_values[k]
	end,
}
package.loaded["cjson"] = {
	decode = function()
		return {}
	end,
	encode = function()
		return ""
	end,
}
package.loaded["ngx.ssl"] =
	{ parse_pem_cert = function() end, parse_pem_priv_key = function() end, server_name = function() end }
package.loaded["middleclass"] = function(name, parent)
	local cls = { name = name }
	cls.__index = cls
	if parent then
		setmetatable(cls, { __index = parent })
	end
	return cls
end
package.loaded["bunkerweb.plugin"] = {
	initialize = function() end,
	ret = function(_, ok, msg, status)
		return { ret = ok, msg = msg, status = status }
	end,
}
package.loaded["bunkerweb.utils"] = {
	get_variable = function(name, _, ctx)
		return ctx.vars[name]
	end,
	get_multiple_variables = function()
		return {}
	end,
	has_variable = function()
		return false
	end,
	read_files = function()
		return {}
	end,
}
ngx = {
	var = {},
	ERR = 4,
	NOTICE = 5,
	OK = 0,
	HTTP_NOT_FOUND = 404,
	HTTP_OK = 200,
	HTTP_BAD_REQUEST = 400,
	HTTP_INTERNAL_SERVER_ERROR = 500,
	req = {},
}

local letsencrypt = require("letsencrypt")

local function plugin_for(uri, passthrough, method)
	local ctx = {
		bw = { uri = uri, request_method = method or "GET" },
		vars = { AUTO_LETS_ENCRYPT = "no", LETS_ENCRYPT_CHALLENGE = "http", LETS_ENCRYPT_PASSTHROUGH = passthrough },
	}
	local self = setmetatable({ ctx = ctx, variables = ctx.vars, logger = { log = function() end } }, letsencrypt)
	ngx.var = {}
	env_values = {}
	return self, ctx
end

local checks, failures = 0, 0
local function expect(cond, msg)
	checks = checks + 1
	if not cond then
		failures = failures + 1
		io.stderr:write("FAIL: " .. msg .. "\n")
	end
end

-- passthrough + challenge path: whitelisted in set, short-circuit in access
local self, ctx = plugin_for("/.well-known/acme-challenge/abc-123_XYZ", "yes")
self:set()
expect(ctx.bw.is_whitelisted == "yes", "passthrough challenge sets ctx is_whitelisted")
expect(ngx.var.is_whitelisted == "yes", "passthrough challenge sets ngx.var is_whitelisted")
expect(env_values.is_whitelisted == "yes", "passthrough challenge sets ENV is_whitelisted for the CRS kill switch")
expect(self:access().status == ngx.OK, "passthrough challenge access returns OK")

-- passthrough with a deeper path, a non token-shaped segment or a write method: untouched
for _, case in ipairs({
	{ "/.well-known/acme-challenge/deep/sub/path", "GET" },
	{ "/.well-known/acme-challenge/", "GET" },
	{ "/.well-known/acme-challenge/wp-admin.php", "GET" },
	{ "/.well-known/acme-challenge/abc", "POST" },
}) do
	self, ctx = plugin_for(case[1], "yes", case[2])
	self:set()
	expect(
		ctx.bw.is_whitelisted == nil and env_values.is_whitelisted == nil,
		case[2] .. " " .. case[1] .. " is not whitelisted"
	)
	expect(self:access().status == nil, case[2] .. " " .. case[1] .. " access has no status")
end
self, ctx = plugin_for("/.well-known/acme-challenge/abc", "yes", "HEAD")
self:set()
expect(ctx.bw.is_whitelisted == "yes", "HEAD of a token is whitelisted")

-- passthrough but another path: untouched
self, ctx = plugin_for("/admin/", "yes")
self:set()
expect(
	ctx.bw.is_whitelisted == nil and ngx.var.is_whitelisted == nil and env_values.is_whitelisted == nil,
	"other path is not whitelisted"
)
expect(self:access().status == nil, "other path access has no status")

-- challenge path without passthrough (no local token either): untouched
self, ctx = plugin_for("/.well-known/acme-challenge/abc", "no")
self:set()
expect(ctx.bw.is_whitelisted == nil, "challenge path without passthrough is not whitelisted by letsencrypt")
expect(self:access().status == nil, "challenge path without passthrough and without a local token has no status")

print(string.format("%d checks, %d failures", checks, failures))
os.exit(failures == 0 and 0 or 1)
