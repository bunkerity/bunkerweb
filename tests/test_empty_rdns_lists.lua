-- Run from the repository root: lua tests/test_empty_rdns_lists.lua
-- Exercise the real plugin methods without an NGINX instance or a DNS resolver.
ngx = {
	ERR = 1,
	INFO = 2,
	OK = 0,
	get_phase = function()
		return "access"
	end,
}
package.preload["middleclass"] = function()
	return function()
		return {}
	end
end
package.preload["resty.env"] = function()
	return { set = function() end }
end
package.preload["resty.ipmatcher"] = function()
	return {
		new = function()
			return {
				match = function()
					return false
				end,
			}
		end,
	}
end
package.preload["bunkerweb.plugin"] = function()
	return {}
end

local lookups = 0
package.preload["bunkerweb.utils"] = function()
	return {
		get_rdns = function()
			lookups = lookups + 1
			return { "host.example.org" }
		end,
		rdns_forward_confirmed = function(_, suffixes)
			if #suffixes > 0 then
				return suffixes[1]
			end
		end,
		get_asn = function()
			return 64512
		end,
	}
end

for _, name in ipairs({ "whitelist", "blacklist", "greylist" }) do
	local path = "src/common/core/" .. name .. "/" .. name .. ".lua"
	local plugin = assert(loadfile(path))()
	local method = "is_"
		.. ({ whitelist = "whitelisted", blacklist = "blacklisted", greylist = "greylisted" })[name]
		.. "_ip"
	local instance = {
		lists = { IP = {}, IGNORE_IP = {}, RDNS = {}, IGNORE_RDNS = {}, ASN = {}, IGNORE_ASN = {} },
		variables = { [name:upper() .. "_RDNS_GLOBAL"] = "no" },
		ctx = { bw = { remote_addr = "203.0.113.1", ip_is_global = false } },
		logger = { log = function() end },
	}
	local before = lookups
	local match = plugin[method](instance)
	assert(match == false, name .. ": empty rDNS list changed IP result")
	assert(lookups == before, name .. ": empty rDNS list triggered a DNS lookup")

	instance.lists.RDNS = { "example.org" }
	match = plugin[method](instance)
	assert(lookups == before + 1, name .. ": configured rDNS list skipped the DNS lookup")
	assert(match == true, name .. ": configured rDNS match was lost")

	instance.variables[name:upper() .. "_RDNS_GLOBAL"] = "yes"
	before = lookups
	plugin[method](instance)
	assert(lookups == before, name .. ": non-global IP triggered a DNS lookup")

	instance.ctx.bw.ip_is_global = true
	plugin[method](instance)
	assert(lookups == before + 1, name .. ": global IP with rDNS entries skipped the lookup")
end
print("empty and populated rDNS list checks passed for whitelist, blacklist, greylist")
