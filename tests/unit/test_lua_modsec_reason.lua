local root = arg[0]:match("^(.*)/tests/unit/") or "."
package.path = root .. "/src/bw/lua/?.lua;" .. package.path

local failures = 0
local function it(name, fn)
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. tostring(err))))
	if not ok then
		failures = failures + 1
	end
end

local function noop() end

local var = {}
_G.ngx = {
	null = {},
	shared = { internalstore = {} },
	config = { subsystem = "http" },
	thread = { kill = noop },
	re = { match = noop },
	var = var,
	now = function()
		return 1700000000
	end,
	time = function()
		return 1700000000
	end,
	log = noop,
	get_phase = function()
		return "log"
	end,
	status = 400,
	ERR = 4,
	WARN = 5,
	INFO = 7,
	HTTP_FORBIDDEN = 403,
	HTTP_CLOSE = 444,
}
package.loaded["cjson"] = { encode = noop, decode = noop }
package.loaded["resty.random"] = { bytes = noop }
package.loaded["resty.string"] = { to_hex = noop }
package.loaded["bunkerweb.logger"] = {
	new = function()
		return { log = noop }
	end,
}
package.loaded["bunkerweb.mmdb"] = {}
package.loaded["resty.dns.resolver"] = {}
package.loaded["resty.session"] = { start = noop }
package.loaded["resty.ipmatcher"] = { parse_ipv4 = noop, parse_ipv6 = noop, new = noop }
local store = {
	new = function()
		return {
			get = function()
				return nil, "not found"
			end,
		}
	end,
}
package.loaded["bunkerweb.datastore"] = store
package.loaded["bunkerweb.clusterstore"] = store
package.loaded["bunkerweb.cachestore"] = store

local utils = require("bunkerweb.utils")
local ctx = { bw = { security_mode = "block", remote_addr = "192.0.2.1" } }

local function reason_for(vars)
	for k in pairs(var) do
		var[k] = nil
	end
	for k, v in pairs(vars) do
		var[k] = v
	end
	return utils.get_reason(ctx)
end

for _, id in ipairs({ "200002", "200003", "200004", "200005", "200006" }) do
	it("rule " .. id .. " denial is reported as modsecurity-body", function()
		local reason, data = reason_for({ modsecurity_reason = "modsecurity-body-" .. id })
		assert(reason == "modsecurity-body", "reason=" .. tostring(reason))
		assert(data.ids and data.ids[1] == id, "ids=" .. tostring(data.ids and data.ids[1]))
	end)
end

it("an unrelated body id is not claimed as modsecurity-body", function()
	local reason = reason_for({ modsecurity_reason = "modsecurity-body-200007" })
	assert(reason ~= "modsecurity-body", "reason=" .. tostring(reason))
end)

it("matched request data is bounded per item and per list", function()
	local sep = "UID"
	local function join(items)
		return "|" .. sep .. "|" .. table.concat(items, "|" .. sep .. "|")
	end
	local big, items = string.rep("<p>", 20000), {}
	for i = 1, 60 do
		items[i] = big
	end
	local reason, data = reason_for({
		modsecurity_reason = "modsecurity",
		modsecurity_unique_id = sep,
		modsecurity_rules = " 941100 941160",
		modsecurity_matched_vars = join(items),
		modsecurity_msgs = join({ "XSS" }),
	})
	assert(reason == "modsecurity")
	assert(#data.ids == 2)
	assert(#data.msgs == 1 and data.msgs[1] == "XSS", "short values must stay untouched")
	local total = 0
	for _, v in ipairs(data.matched_vars) do
		total = total + #v
	end
	assert(#data.matched_vars <= 32, "items=" .. #data.matched_vars)
	assert(total <= 32 * 600, "bytes=" .. total)
end)

it("truncation never splits a multi-byte character", function()
	local sep = "UID"
	local value = string.rep("é", 600)
	local _, data = reason_for({
		modsecurity_reason = "modsecurity",
		modsecurity_unique_id = sep,
		modsecurity_matched_vars = "|" .. sep .. "|" .. value,
	})
	local item = data.matched_vars[1]
	assert(#item < #value, "not truncated")
	local body = item:gsub("%.%.%.$", "")
	assert(#body % 2 == 0, "split a two-byte character")
end)

local function read(path)
	local f = assert(io.open(root .. "/" .. path, "r"))
	local text = f:read("*a")
	f:close()
	return text
end

for _, path in ipairs({
	"src/common/core/modsecurity/confs/http/modsecurity-rules-global-crs.conf.modsec",
	"src/common/core/modsecurity/confs/server-http/modsecurity-rules.conf.modsec",
}) do
	for _, id in ipairs({ "200003", "200004", "200006" }) do
		it(path:match("[^/]+/[^/]+$") .. " attributes rule " .. id, function()
			local text = read(path)
			-- the rule definition, up to the next blank line or comment
			local rule = text:match("id:'" .. id .. "'(.-)\n\n") or text:match("id:'" .. id .. "'(.-)\n#")
			assert(rule, "rule not found")
			assert(rule:find("bunkerweb_reason=modsecurity-body-" .. id, 1, true), "no reason setvar")
		end)
	end
end

if failures > 0 then
	print(failures .. " failure(s)")
	os.exit(1)
end
print("all passed")
