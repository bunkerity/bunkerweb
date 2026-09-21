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

local sha256 = require "resty.sha256"
local to_hex = require("resty.string").to_hex

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

function cache_partition.hash(str)
	local hash = assert(sha256:new())
	assert(hash:update(str))
	return to_hex(assert(hash:final()))
end

-- The cache key prefix for one Local API URL, independent of every other API
-- configured elsewhere in the fleet.
function cache_partition.prefix_for(api_url)
	-- Never trust legacy 32-bit namespaces after a reload. Old decisions expire
	-- naturally; a dict-wide flush would disrupt other workers and endpoints.
	return "v2|" .. cache_partition.hash(cache_partition.normalize(api_url)) .. "|"
end

function cache_partition.challenge_prefix(scope, content, captcha_template)
	-- Length framing prevents ambiguous concatenation; configuration changes
	-- invalidate challenges when a provider, key or policy changes.
	return "captcha-v2|"
		.. cache_partition.hash(#scope .. ":" .. scope .. #content .. ":" .. content .. (captcha_template or ""))
		.. "|"
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
	local owners = {}
	local count = 0
	for _, api_url in ipairs(api_urls) do
		if api_url ~= "" and not prefixes[api_url] then
			local normalized = cache_partition.normalize(api_url)
			local prefix = cache_partition.prefix_for(normalized)
			if owners[prefix] and owners[prefix] ~= normalized then
				return nil, "CrowdSec cache namespace collision"
			end
			owners[prefix] = normalized
			if not distinct[normalized] then
				distinct[normalized] = true
				count = count + 1
			end
			prefixes[api_url] = prefix
		end
	end
	return prefixes, count
end

return cache_partition
