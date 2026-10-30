-- Run from the repository root: lua tests/unit/test_lua_cors_credentials.lua
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
local cors, misc = load("cors"), load("misc")

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

it("real response to an allowed origin carries credentials", function()
	run_header({}, "http://app1.example.com")
	assert(headers["Access-Control-Allow-Credentials"] == "true")
	assert(headers["Access-Control-Allow-Origin"] == "http://app1.example.com")
end)

it("preflight to an allowed origin carries credentials", function()
	run_header({}, "http://app1.example.com", "OPTIONS")
	assert(headers["Access-Control-Allow-Credentials"] == "true")
	assert(headers["Access-Control-Allow-Methods"] == "GET, POST, OPTIONS")
end)

it("real response has no preflight-only headers", function()
	run_header({}, "http://app1.example.com")
	assert(headers["Access-Control-Allow-Methods"] == nil)
	assert(headers["Access-Control-Max-Age"] == nil)
end)

it("disallowed origin gets no credentials when CORS_DENY_REQUEST=no", function()
	run_header({ CORS_DENY_REQUEST = "no" }, "http://evil.example.net")
	assert(headers["Access-Control-Allow-Credentials"] == nil)
end)

it("disallowed origin gets no credentials on a preflight either", function()
	run_header({ CORS_DENY_REQUEST = "no" }, "http://evil.example.net", "OPTIONS")
	assert(headers["Access-Control-Allow-Credentials"] == nil)
end)

it("wildcard never comes with credentials", function()
	run_header({ CORS_ALLOW_ORIGIN = "*" }, "http://app1.example.com")
	assert(headers["Access-Control-Allow-Origin"] == "*")
	assert(headers["Access-Control-Allow-Credentials"] == nil)
	run_header({ CORS_ALLOW_ORIGIN = "*" }, "http://app1.example.com", "OPTIONS")
	assert(headers["Access-Control-Allow-Credentials"] == nil)
end)

it("CORS_ALLOW_CREDENTIALS=no sends no credentials header", function()
	run_header({ CORS_ALLOW_CREDENTIALS = "no" }, "http://app1.example.com")
	assert(headers["Access-Control-Allow-Credentials"] == nil)
end)

it("disallowed origin clears upstream credentials even when requests are not denied", function()
	for _, method in ipairs({ "GET", "OPTIONS" }) do
		for _, credentials in ipairs({ "yes", "no" }) do
			headers["Access-Control-Allow-Credentials"] = "true"
			run_header(
				{ CORS_DENY_REQUEST = "no", CORS_ALLOW_CREDENTIALS = credentials },
				"http://evil.example.net",
				method
			)
			assert(headers["Access-Control-Allow-Credentials"] == nil)
		end
	end
end)

it("wildcard clears upstream credentials", function()
	for _, method in ipairs({ "GET", "OPTIONS" }) do
		for _, credentials in ipairs({ "yes", "no" }) do
			headers["Access-Control-Allow-Credentials"] = "true"
			run_header(
				{ CORS_ALLOW_ORIGIN = "*", CORS_ALLOW_CREDENTIALS = credentials },
				"http://app1.example.com",
				method
			)
			assert(headers["Access-Control-Allow-Origin"] == "*")
			assert(headers["Access-Control-Allow-Credentials"] == nil)
		end
	end
end)

it("allowed origin preserves upstream credentials when CORS_ALLOW_CREDENTIALS=no", function()
	headers["Access-Control-Allow-Credentials"] = "true"
	run_header({ CORS_ALLOW_CREDENTIALS = "no" }, "http://app1.example.com")
	assert(headers["Access-Control-Allow-Credentials"] == "true")
end)

it("self matches the origin exactly", function()
	run_header({ CORS_ALLOW_ORIGIN = "self" }, "http://www.example.com")
	assert(headers["Access-Control-Allow-Credentials"] == "true")
	headers["Access-Control-Allow-Credentials"] = nil
	run_header({ CORS_ALLOW_ORIGIN = "self" }, "http://www.example.com.evil.net", "GET")
	assert(headers["Access-Control-Allow-Credentials"] == nil)
end)

it("access still denies a disallowed origin", function()
	local bw = { http_origin = "http://evil.example.net", request_method = "GET", server_name = "www.example.com" }
	local res = make(cors, cors_vars(), bw):access()
	assert(res.status == 403, "status " .. tostring(res.status))
end)

it("access lets an allowed preflight through with 204", function()
	local bw = { http_origin = "http://app1.example.com", request_method = "OPTIONS", server_name = "www.example.com" }
	local res = make(cors, cors_vars(), bw):access()
	assert(res.status == 204, "status " .. tostring(res.status))
end)

local function run_misc(method, preflight, use_cors, origin)
	variables_store.USE_CORS = use_cors
	ngx.var.http_access_control_request_method = preflight and "GET" or nil
	local bw = { request_method = method, http_origin = origin }
	return make(misc, { ALLOWED_METHODS = "GET|POST|HEAD|QUERY" }, bw):access()
end

it("misc lets a CORS preflight through when USE_CORS=yes", function()
	local res = run_misc("OPTIONS", true, "yes", "http://app1.example.com")
	assert(res.ret and res.status == nil, "status " .. tostring(res.status))
end)

it("misc keeps 405 for a preflight when USE_CORS=no", function()
	assert(run_misc("OPTIONS", true, "no", "http://app1.example.com").status == 405)
end)

it("misc keeps 405 for a plain OPTIONS", function()
	assert(run_misc("OPTIONS", false, "yes", nil).status == 405)
end)

it("misc keeps 405 for OPTIONS with Origin but no Access-Control-Request-Method", function()
	assert(run_misc("OPTIONS", false, "yes", "http://app1.example.com").status == 405)
end)

it("misc keeps 405 for OPTIONS with Access-Control-Request-Method but no Origin", function()
	assert(run_misc("OPTIONS", true, "yes", nil).status == 405)
end)

it("misc keeps 405 for another method carrying the preflight headers", function()
	assert(run_misc("PUT", true, "yes", "http://app1.example.com").status == 405)
end)

os.exit(failures == 0 and 0 or 1)
