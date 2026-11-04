-- Run from the repository root: lua tests/unit/test_lua_cors_origin.lua
-- luacheck: ignore 122
local source_root = arg[1] or "src/common/core"
local variables_store = {}
package.loaded["middleclass"] = function(_, parent)
	local cls = {}
	cls.__index = cls
	return setmetatable(cls, { __index = parent })
end
package.loaded["bunkerweb.plugin"] = {
	initialize = function(self, _, ctx)
		self.ctx = ctx
		self.variables = ctx.variables
	end,
	ret = function(_, ret, msg, status)
		return { ret = ret, msg = msg, status = status }
	end,
	set_metric = function() end,
}
package.loaded["bunkerweb.utils"] = {
	-- Lua patterns stand in for PCRE here
	regex_match = function(value, pattern)
		if pattern == "^[A-Z][A-Z_-]{2,}$" then
			return value:match("^%u[%u_-][%u_-]+$") ~= nil
		end
		return value:match(pattern) ~= nil
	end,
	get_deny_status = function()
		return 403
	end,
	parse_duration = function()
		return 86400
	end,
	get_variable = function(name)
		return variables_store[name], "success"
	end,
	get_security_mode = function()
		return "block"
	end,
}
local headers = {}
ngx = {
	HTTP_NO_CONTENT = 204,
	HTTP_NOT_ALLOWED = 405,
	HTTP_BAD_REQUEST = 400,
	HTTP_CLOSE = 444,
	header = headers,
	var = {},
}

local function load(name)
	package.loaded[name] = nil
	return dofile(source_root .. "/" .. name .. "/" .. name .. ".lua")
end
local cors = load("cors")

local failures = 0
local function it(name, fn)
	for key in pairs(headers) do
		headers[key] = nil
	end
	ngx.var = {}
	variables_store = {}
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. tostring(err))))
	if not ok then
		failures = failures + 1
	end
end

local function make(cls, plugin_variables, bw)
	local ctx = { variables = plugin_variables, bw = bw }
	local obj = setmetatable({}, { __index = cls })
	cls.initialize(obj, ctx)
	return obj
end

local function cors_vars(extra)
	local vars = {
		USE_CORS = "yes",
		CORS_ALLOW_ORIGIN = "^http://app1%.example%.com$",
		CORS_DENY_REQUEST = "yes",
		CORS_ALLOW_CREDENTIALS = "yes",
		CORS_ALLOW_METHODS = "GET, POST, OPTIONS",
		CORS_ALLOW_HEADERS = "Content-Type",
		CORS_EXPOSE_HEADERS = "",
		CORS_MAX_AGE = "1d",
		CROSS_ORIGIN_OPENER_POLICY = "",
		CROSS_ORIGIN_EMBEDDER_POLICY = "",
		CROSS_ORIGIN_RESOURCE_POLICY = "",
	}
	for key, value in pairs(extra or {}) do
		vars[key] = value
	end
	return vars
end

local function run_header(extra, origin, method)
	local bw = { http_origin = origin, request_method = method or "GET", server_name = "www.example.com" }
	return make(cors, cors_vars(extra), bw):header()
end

local ACAO = "Access-Control-Allow-Origin"

it("regex mode echoes an allowed origin", function()
	for _, method in ipairs({ "GET", "OPTIONS" }) do
		run_header({}, "http://app1.example.com", method)
		assert(headers[ACAO] == "http://app1.example.com")
	end
end)

it("regex mode sends no Allow-Origin to a disallowed origin, denied or not", function()
	for _, method in ipairs({ "GET", "OPTIONS" }) do
		for _, deny in ipairs({ "yes", "no" }) do
			run_header({ CORS_DENY_REQUEST = deny }, "http://evil.example.net", method)
			assert(headers[ACAO] == nil, "echoed " .. tostring(headers[ACAO]))
			assert(headers["Access-Control-Allow-Credentials"] == nil)
		end
	end
end)

it("regex mode drops an upstream Allow-Origin for a disallowed origin", function()
	headers[ACAO] = "http://evil.example.net"
	run_header({ CORS_DENY_REQUEST = "no" }, "http://evil.example.net")
	assert(headers[ACAO] == nil)
end)

it("a disallowed origin still gets Vary: Origin", function()
	run_header({ CORS_DENY_REQUEST = "no" }, "http://evil.example.net")
	assert(headers.Vary == "Origin")
end)

it("wildcard and self keep their Allow-Origin", function()
	run_header({ CORS_ALLOW_ORIGIN = "*" }, "http://evil.example.net")
	assert(headers[ACAO] == "*")
	run_header({ CORS_ALLOW_ORIGIN = "self" }, "http://www.example.com")
	assert(headers[ACAO] == "http://www.example.com")
end)

os.exit(failures == 0 and 0 or 1)
