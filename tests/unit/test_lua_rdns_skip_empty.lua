-- Run from the repository root: lua tests/unit/test_lua_rdns_skip_empty.lua
local source_root = arg[1] or "src/common/core"
local calls, confirmations = 0, 0
local confirmed = true
local suffix = ".example.com"
package.loaded["middleclass"] = function(_, parent)
	local cls = {}
	cls.__index = cls
	return setmetatable(cls, { __index = parent })
end
package.loaded["bunkerweb.plugin"] = {
	initialize = function(self, _, ctx)
		self.ctx = ctx
		self.variables = ctx.variables
		self.is_request = true
	end,
}
package.loaded["resty.ipmatcher"] = {
	new = function(list)
		return {
			match = function(_, ip)
				for _, entry in ipairs(list or {}) do
					if entry == ip then
						return true
					end
				end
				return false
			end,
		}
	end,
}
package.loaded["bunkerweb.utils"] = {
	get_rdns = function()
		calls = calls + 1
		return { "crawler.example.com" }
	end,
	rdns_forward_confirmed = function(ptrs, suffixes, ctx, ip)
		confirmations = confirmations + 1
		assert(ptrs[1] == "crawler.example.com" and ctx.bw.remote_addr == ip)
		if confirmed then
			for _, entry in ipairs(suffixes or {}) do
				if ptrs[1]:sub(-#entry) == entry then
					return entry
				end
			end
		end
	end,
	get_asn = function()
		return 64500
	end,
	deduplicate_list = function(list)
		return list
	end,
	pick_header_rules = function()
		return {}
	end,
}
for _, name in ipairs({
	"base64",
	"antibot.captcha",
	"cjson",
	"resty.http",
	"resty.sha256",
	"resty.string",
	"resty.env",
}) do
	package.loaded[name] = {}
end
ngx = {
	ERR = 3,
	INFO = 6,
	config = { subsystem = "stream" },
	get_phase = function()
		return "access"
	end,
}

local checks, failures = 0, 0
local function check(label, fn)
	checks = checks + 1
	local ok, err = pcall(fn)
	if ok then
		print("PASS: " .. label)
	else
		failures = failures + 1
		print("FAIL: " .. label .. ": " .. tostring(err))
	end
end

for _, name in ipairs({ "whitelist", "blacklist", "greylist", "antibot" }) do
	local plugin = assert(loadfile(source_root .. "/" .. name .. (arg[1] and ".lua" or "/" .. name .. ".lua")))()
	local key = name == "antibot" and "IGNORE_RDNS" or "RDNS"
	local method = name == "antibot" and "is_ignored_ip" or "is_" .. name:gsub("list$", "listed") .. "_ip"
	local miss = (name == "whitelist" or name == "blacklist") and "ok" or "ko"
	local function instance(list, global, global_only)
		local self = setmetatable({
			lists = { IP = {}, IGNORE_IP = {}, ASN = {}, IGNORE_ASN = {}, IGNORE_RDNS = {} },
			variables = { [name:upper() .. "_RDNS_GLOBAL"] = global_only or "yes" },
			ctx = { bw = { remote_addr = "203.0.113.10", ip_is_global = global ~= false, server_name = "example.com" } },
			logger = { log = function() end },
		}, plugin)
		self.lists[key] = list
		calls, confirmations, confirmed = 0, 0, true
		return self
	end
	local function expect(self, count, result, detail)
		local got, reason = self[method](self)
		assert(calls == count, "expected " .. count .. " PTR calls, got " .. calls)
		assert(got == result and reason == detail, "unexpected match: " .. tostring(got) .. ", " .. tostring(reason))
	end
	check(name .. " empty list", function()
		expect(instance({}), 0, false, miss)
	end)
	check(name .. " missing list", function()
		expect(instance(nil), 0, false, miss)
	end)
	check(name .. " configured match", function()
		expect(instance({ suffix }), 1, true, "rDNS " .. suffix)
		assert(confirmations == 1, "forward confirmation must still run")
	end)
	check(name .. " configured nonmatch", function()
		expect(instance({ ".other.example" }), 1, false, miss)
	end)
	check(name .. " local IP with global-only enabled", function()
		expect(instance({ suffix }, false), 0, false, miss)
	end)
	check(name .. " local IP with global-only disabled", function()
		expect(instance({ suffix }, false, "no"), 1, true, "rDNS " .. suffix)
	end)
	if name ~= "blacklist" then
		check(name .. " unconfirmed PTR does not grant bypass", function()
			local self = instance({ suffix })
			confirmed = false
			expect(self, 1, false, miss)
		end)
	else
		check("blacklist ignore-only skips lookup", function()
			local self = instance({})
			self.lists.IGNORE_RDNS = { suffix }
			expect(self, 0, false, miss)
		end)
		check("blacklist confirmed ignore wins", function()
			local self = instance({ suffix })
			self.lists.IGNORE_RDNS = { suffix }
			expect(self, 1, false, miss)
		end)
		check("blacklist unconfirmed ignore does not bypass", function()
			local self = instance({ suffix })
			self.lists.IGNORE_RDNS = { suffix }
			confirmed = false
			expect(self, 1, true, "rDNS " .. suffix)
		end)
	end
	if name ~= "antibot" then
		check(name .. " URL-only list survives request initialization", function()
			local self = instance(nil)
			local vars = { ["USE_" .. name:upper()] = "yes", [name:upper() .. "_RDNS_GLOBAL"] = "yes" }
			for _, kind in ipairs({
				"IP",
				"RDNS",
				"ASN",
				"USER_AGENT",
				"URI",
				"IGNORE_IP",
				"IGNORE_RDNS",
				"IGNORE_ASN",
				"IGNORE_USER_AGENT",
				"IGNORE_URI",
			}) do
				vars[name:upper() .. "_" .. kind] = ""
			end
			self.internalstore = {
				get = function(_, store_key)
					if store_key == "plugin_" .. name .. "_lists_example.com" then
						return { RDNS = { suffix } }
					end
				end,
			}
			self.ctx.variables = vars
			self:initialize(self.ctx)
			assert(vars[name:upper() .. "_RDNS"] == "")
			expect(self, 1, true, "rDNS " .. suffix)
		end)
	end
end
print(string.format("%d checks, %d failures", checks, failures))
os.exit(failures == 0 and 0 or 1)
