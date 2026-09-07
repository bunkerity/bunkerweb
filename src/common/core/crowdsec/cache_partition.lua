-- How the shared CrowdSec decision cache is partitioned between the per-service
-- bouncer instances.
--
-- All instances share the single crowdsec_cache dict, so services pointing at
-- different Local APIs need disjoint key spaces or they read each other's decisions.
-- The prefix for a given Local API is derived from a hash of that API alone, never
-- from the position of that API among the others configured. Positional prefixes
-- (index 1, 2, ... in sorted order) shift for every service the moment any other
-- service's Local API is added, removed or replaced, so a reload can silently point
-- an untouched service at another service's cached decisions. A hash-derived prefix
-- for one Local API never changes because a sibling configuration changed, so no
-- flush of the shared dict is ever required on a mapping change either.

local cache_partition = {}

local byte = string.byte
local format = string.format

-- Kept below 2^32 so the hash stays representable as an exact double in Lua 5.1
-- (mantissa is 53 bits) and as a 64-bit integer in Lua 5.3+, with no risk of
-- overflow or precision loss in the accumulator below.
local HASH_MOD = 4294967291

-- The Local API a rendered configuration targets. Matched line by line, anchored, so
-- APPSEC_URL is never mistaken for it. Returns "" when the configuration has none.
function cache_partition.api_url(content)
	for line in content:gmatch("[^\n]+") do
		local value = line:match("^%s*API_URL%s*=%s*(.-)%s*$")
		if value then
			return value
		end
	end
	return ""
end

-- Trailing slashes are the only variance seen in practice between equivalent
-- Local API URLs (env value vs. rendered default), so they are the only thing
-- normalized before hashing.
function cache_partition.normalize(api_url)
	return (api_url:gsub("/+$", ""))
end

-- Plain djb2, pure arithmetic (no bitwise operators) so it behaves identically
-- across Lua 5.1, 5.3+ and LuaJIT.
function cache_partition.hash(str)
	local h = 5381
	for i = 1, #str do
		h = (h * 33 + byte(str, i)) % HASH_MOD
	end
	return h
end

-- The cache key prefix for one Local API URL, independent of every other API
-- configured elsewhere in the fleet.
function cache_partition.prefix_for(api_url)
	return format("%08x|", cache_partition.hash(cache_partition.normalize(api_url)))
end

-- Map of Local API -> cache key prefix, plus how many distinct Local APIs were seen.
--
-- Configurations without a Local API are never counted and never get a prefix: they
-- do no decision lookup at all, so they cannot bleed into anything, and counting them
-- would penalise the common "AppSec everywhere, Local API on a subset" fleet with a
-- partition it does not need. Every configuration that does have a Local API gets a
-- prefix, even when it is the only one configured, so adding a second Local API later
-- never changes the key space of the first.
function cache_partition.prefixes(api_urls)
	local prefixes = {}
	local distinct = {}
	local count = 0
	for _, api_url in ipairs(api_urls) do
		if api_url ~= "" and not distinct[api_url] then
			distinct[api_url] = true
			count = count + 1
			prefixes[api_url] = cache_partition.prefix_for(api_url)
		end
	end
	return prefixes, count
end

return cache_partition
