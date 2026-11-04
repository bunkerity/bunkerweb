-- Plain Lua check of the search_panes filter of metrics:api_requests_query (GET /metrics/requests/query).
-- Run: lua tests/unit/test_lua_metrics_search_panes.lua [path/to/metrics.lua]   (from the repo root)
local root = arg[0]:match("^(.*)/tests/unit/") or "."
local source = arg[1] or (root .. "/src/common/core/metrics/metrics.lua")

local failures = 0
local function it(name, fn)
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. tostring(err))))
	if not ok then
		failures = failures + 1
	end
end

-- ngx.unescape_uri: percent-decode, "+" becomes a space
local function unescape_uri(s)
	return (s:gsub("+", " "):gsub("%%(%x%x)", function(h)
		return string.char(tonumber(h, 16))
	end))
end

local uri_args = {}
ngx = {
	ERR = 1,
	WARN = 2,
	HTTP_OK = 200,
	null = {},
	shared = {},
	config = { subsystem = "http" },
	worker = {
		id = function()
			return 0
		end,
	},
	unescape_uri = unescape_uri,
	req = {
		get_uri_args = function()
			return uri_args
		end,
	},
}

package.loaded["cjson"] = {
	encode = function(v)
		return v
	end,
	decode = function(v)
		return v
	end,
}
package.loaded["middleclass"] = function(name)
	return { name = name }
end
package.loaded["bunkerweb.datastore"] = {}
package.loaded["resty.lrucache"] = {
	new = function()
		return {}
	end,
}
package.loaded["bunkerweb.plugin"] = {}
package.loaded["bunkerweb.rediskeys"] = {}
package.loaded["bunkerweb.utils"] = {}
package.loaded["bunkerweb.logger"] = {}

local metrics = dofile(source)

local REQUESTS = {
	{ id = "1", status = 403, ip = "1.2.3.4", url = "x,y", user_agent = "ua" },
	{ id = "2", status = 403, ip = "1.2.3.4", url = "p;q", user_agent = "ua" },
	{ id = "3", status = 403, ip = "5.6.7.8", url = "a&b", user_agent = "ua" },
	{ id = "4", status = 403, ip = "5.6.7.8", url = "plain", server_name = "www.example.com" },
}

local function query(args)
	args.length = "-1"
	uri_args = args
	local ds = {
		keys = function()
			return { "requests_1" }
		end,
		get = function()
			return REQUESTS
		end,
	}
	local self = setmetatable({
		metrics_datastore = ds,
		ret = function(_, _, data)
			return data
		end,
	}, { __index = metrics })
	local result = self:api_requests_query()
	local ids = {}
	for _, request in ipairs(result.data) do
		ids[#ids + 1] = request.id
	end
	table.sort(ids)
	return table.concat(ids, ",")
end

it("encoded comma stays inside its value", function()
	assert(query({ search_panes = "url:x%2Cy" }) == "1", "got " .. query({ search_panes = "url:x%2Cy" }))
end)

it("encoded semicolon stays inside its value", function()
	assert(query({ search_panes = "url:p%3Bq" }) == "2", "got " .. query({ search_panes = "url:p%3Bq" }))
end)

it("encoded ampersand matches the raw value", function()
	assert(query({ search_panes = "url:a%26b" }) == "3", "got " .. query({ search_panes = "url:a%26b" }))
end)

it("several encoded values and fields combine", function()
	local got = query({ search_panes = "url:x%2Cy,p%3Bq;ip:1.2.3.4" })
	assert(got == "1,2", "got " .. got)
end)

it("plain strings as the CrowdSec lookup sends them still parse", function()
	local got = query({ search_panes = "ip:1.2.3.4;server_name:www.example.com,other.example.com" })
	assert(got == "", "got " .. got)
	got = query({ search_panes = "ip:5.6.7.8;server_name:www.example.com,other.example.com" })
	assert(got == "4", "got " .. got)
	got = query({ search_panes = "ip:1.2.3.4" })
	assert(got == "1,2", "got " .. got)
end)

it("no panes returns everything", function()
	local got = query({})
	assert(got == "1,2,3,4", "got " .. got)
end)

if failures > 0 then
	print(failures .. " failure(s)")
	os.exit(1)
end
print("OK")
