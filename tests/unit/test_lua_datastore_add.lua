-- Plain Lua check of datastore:add_with_retries, the atomic create-only write behind add_ban's if_absent option.
-- Run: lua tests/unit/test_lua_datastore_add.lua   (from the repo root)
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

_G.ngx = {
	shared = { datastore = {}, internalstore = {} },
	config = { subsystem = "http" },
	now = function()
		return 1700000000
	end,
	time = function()
		return 1700000000
	end,
	log = function() end,
	ERR = 4,
	WARN = 5,
}
package.loaded["bunkerweb.logger"] = {
	new = function()
		return { log = function() end }
	end,
}
package.loaded["resty.lrucache"] = {
	new = function()
		return {
			get = function() end,
			set = function() end,
			get_keys = function()
				return {}
			end,
		}
	end,
}

local datastore = require("bunkerweb.datastore")

-- A shared dict with the semantics of lua-nginx-module: add fails with "exists" on a live key, and with "no memory"
-- while the dict is full (the first `full_for` attempts)
local function new_dict()
	local dict = { data = {}, ttls = {}, add_calls = 0, full_for = 0, forcible = false }
	function dict:add(key, value, exptime)
		self.add_calls = self.add_calls + 1
		if self.data[key] ~= nil then
			return false, "exists", false
		end
		if self.full_for > 0 then
			self.full_for = self.full_for - 1
			return false, "no memory", false
		end
		self.data[key], self.ttls[key] = value, exptime
		return true, nil, self.forcible
	end
	function dict:get(key)
		return self.data[key]
	end
	return dict
end

it("add_with_retries creates a missing key with its ttl", function()
	local dict = new_dict()
	local ds = datastore:new(dict)
	local ok, msg = ds:add_with_retries("k", "v", 30)
	assert(ok == true and msg == "success", tostring(msg))
	assert(dict.data.k == "v" and dict.ttls.k == 30)
end)

it("add_with_retries never replaces a live key and reports it as exists", function()
	local dict = new_dict()
	dict.data.k = "old"
	local ds = datastore:new(dict)
	local ok, msg = ds:add_with_retries("k", "new", 30)
	assert(ok == false and msg == "exists", tostring(msg))
	assert(dict.data.k == "old")
	assert(dict.add_calls == 1, "an existing key is final, no retry")
end)

it("add_with_retries without a ttl, or with 0 or a negative one, stores no expiry", function()
	for _, exptime in ipairs({ "nil", 0, -1 }) do
		local dict = new_dict()
		local ds = datastore:new(dict)
		local ok = ds:add_with_retries("k", "v", exptime ~= "nil" and exptime or nil)
		assert(ok and dict.ttls.k == nil, "exptime " .. tostring(exptime) .. " stored as " .. tostring(dict.ttls.k))
	end
end)

it("add_with_retries retries a full dict and succeeds once there is room", function()
	local dict = new_dict()
	dict.full_for = 2
	local ds = datastore:new(dict)
	local ok = ds:add_with_retries("k", "v", 30)
	assert(ok and dict.data.k == "v" and dict.add_calls == 3)
end)

it("add_with_retries gives up on a dict that stays full", function()
	local dict = new_dict()
	dict.full_for = 100
	local ds = datastore:new(dict)
	local ok, msg = ds:add_with_retries("k", "v", 30)
	assert(ok == false and msg == "no memory", tostring(msg))
	assert(dict.data.k == nil and dict.add_calls == 5)
end)

it("add_with_retries returns any other dict error at once", function()
	local dict = new_dict()
	function dict.add()
		return false, "value too large"
	end
	local ds = datastore:new(dict)
	local ok, msg = ds:add_with_retries("k", "v", 30)
	assert(ok == false and msg == "value too large")
end)

os.exit(failures == 0 and 0 or 1)
