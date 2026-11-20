-- Plain Lua regression checks for metrics reload history and SHM retry limits.
-- Run: lua tests/unit/test_lua_metrics_seed.lua [path/to/metrics.lua]
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

-- Deterministic serialization preserves the cjson boundary: decoded rows are new objects.
local function encode(value)
	if type(value) == "string" then
		return string.format("%q", value)
	elseif type(value) ~= "table" then
		return tostring(value)
	end
	local entries = {}
	for key, item in pairs(value) do
		entries[#entries + 1] = "[" .. encode(key) .. "]=" .. encode(item)
	end
	table.sort(entries)
	return "{" .. table.concat(entries, ",") .. "}"
end
local function decode(value)
	return assert(load("return " .. value, "fixture", "t", {}))()
end

ngx = {
	ERR = 1,
	WARN = 2,
	HTTP_OK = 200,
	status = 403,
	null = {},
	shared = {},
	var = {},
	config = { subsystem = "http" },
	worker = {
		id = function()
			return 0
		end,
	},
}
package.loaded["cjson"] = { encode = encode, decode = decode }
package.loaded["middleclass"] = function()
	return {}
end
package.loaded["bunkerweb.datastore"] = {}
package.loaded["bunkerweb.plugin"] = {}
package.loaded["bunkerweb.rediskeys"] = {}
package.loaded["bunkerweb.utils"] = {
	get_reason = function()
		return "blacklist", {}, "block"
	end,
	has_variable = function()
		return true
	end,
	parse_duration = function()
		return nil
	end,
}

local cache
package.loaded["resty.lrucache"] = {
	new = function(capacity)
		local values, order = {}, {}
		local function detach(key)
			for i, name in ipairs(order) do
				if name == key then
					table.remove(order, i)
					break
				end
			end
		end
		cache = {
			capacity = function()
				return capacity
			end,
			get_keys = function()
				local keys = {}
				for i, key in ipairs(order) do
					keys[i] = key
				end
				return keys
			end,
			get = function(_, key)
				if values[key] ~= nil then
					detach(key)
					table.insert(order, 1, key)
				end
				return values[key]
			end,
			set = function(_, key, value)
				detach(key)
				values[key] = value
				table.insert(order, 1, key)
				if #order > capacity then
					values[table.remove(order)] = nil
				end
			end,
			delete = function(_, key)
				detach(key)
				values[key] = nil
			end,
		}
		return cache
	end,
}

local function instance(rows, cap, slots)
	local metrics = dofile(source)
	local shm = { requests_0 = encode(rows), requests_1 = encode({ { id = "other-worker" } }) }
	local writes, reject = {}, 0
	local self = setmetatable({
		variables = {
			USE_METRICS = "yes",
			MAX_LRU_HISTORY = slots or "1k",
			METRICS_MAX_BLOCKED_REQUESTS = cap or "10",
			METRICS_MEMORY_MAX_RETRIES = "2",
		},
		ctx = {
			bw = {
				request_id = "new",
				request_uri = "/new",
				server_name = "example.com",
				remote_addr = "1.2.3.4",
				request_method = "GET",
			},
		},
		metrics_datastore = {
			keys = function()
				return { "requests_1", "requests_0" }
			end,
			get = function(_, key)
				return shm[key]
			end,
			set_with_retries = function(_, key, value, _, retries)
				writes[#writes + 1] = retries or 5
				if reject > 0 then
					reject = reject - 1
					return false, "no memory"
				end
				shm[key] = value
				return true
			end,
		},
		logger = { log = function() end },
		log_throttled = function() end,
		flush_log_recaps = function() end,
		ret = function(_, ok, msg)
			return { ret = ok, msg = msg }
		end,
	}, { __index = metrics })
	return self, shm, writes, function(n)
		reject = n
	end
end

local function ids(rows)
	local out = {}
	for _, row in ipairs(rows) do
		out[#out + 1] = row.id
	end
	return table.concat(out, ",")
end

it("SHM history survives log before restore and the next two timer ticks", function()
	local self, shm = instance({ { id = "old-1", synced = true }, { id = "old-2", synced = true } })
	assert(self:log().ret)
	assert(self:init_workers().ret)
	assert(self:timer().ret)
	assert(self:timer().ret)
	assert(ids(decode(shm.requests_0)) == "old-1,old-2,new", "restore lost pre-reload rows")
	assert(ids(decode(shm.requests_1)) == "other-worker", "restore touched another worker")
end)

it("overlapping IDs restore once and keep the live row", function()
	local self, shm = instance({ { id = "old", synced = true }, { id = "new", synced = false, url = "/stale" } })
	self:log()
	self:init_workers()
	self:timer()
	local rows = decode(shm.requests_0)
	assert(ids(rows) == "old,new", "restore lost or duplicated overlapping rows")
	assert(rows[2].url == "/new" and rows[2].synced, "restored row overwrote live state")
end)

it("restore drops oldest rows at the configured request cap", function()
	local self, shm = instance({ { id = "old-1", synced = true }, { id = "old-2", synced = true } }, "2")
	self:log()
	self:init_workers()
	self:timer()
	assert(ids(decode(shm.requests_0)) == "old-2,new", "restore did not retain the newest rows within cap")
end)

it("restore merges an existing request slot even when LRU is full", function()
	local self = instance({ { id = "old", synced = true } })
	self:log()
	for i = 1, 999 do
		cache:set("counter-" .. i, i)
	end
	self:init_workers()
	assert(ids(cache:get("requests")) == "old,new", "slot budget prevented merge")
	assert(#cache:get_keys() == 1000 and cache:get("counter-1") == 1, "merge evicted a live slot")
end)

it("LRU resize preserves requests logged before restore", function()
	local self, shm = instance({ { id = "old", synced = true } }, "10", "2")
	self:log()
	self:init_workers()
	self:timer()
	assert(cache:capacity() == 2)
	assert(ids(decode(shm.requests_0)) == "old,new", "resize discarded the live report")
end)

it("untouched restore honors zero cap and keeps uncertain Redis payload", function()
	local self = instance({ { id = "old", synced = false } }, "0")
	self:init_workers()
	assert(#cache:get("requests") == 0, "zero cap retained restored rows")
	self = instance({ { id = "old", synced = false } })
	self:init_workers()
	assert(cache:get("requests")[1].redis_retry_json, "restore lost uncertain Redis retry payload")
end)

it("initial and shed writes honor configured retry limit", function()
	local self, _, writes, reject = instance({})
	self:log()
	self.ctx.bw.request_id = "new-2"
	self:log()
	reject(1)
	self:timer()
	assert(#writes == 2 and writes[1] == 2 and writes[2] == 2, "initial or shed write used default retries")
end)

if failures > 0 then
	os.exit(1)
end
print("OK")
