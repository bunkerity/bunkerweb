-- How the shared CrowdSec decision cache is partitioned between the per-service
-- bouncer instances.
--
-- All instances share the single crowdsec_cache dict, so services pointing at
-- different Local APIs need disjoint key spaces or they read each other's decisions.
-- Partitioning is not free: the prefix costs a string concatenation on every lookup of
-- the netmask walk in csmod.allowIp, which runs on every request that misses the cache,
-- and it costs dict space on every cached decision in a fixed-size zone. So it is only
-- switched on when it is actually needed.

local cache_partition = {}

local insert = table.insert
local sort = table.sort

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

-- Map of Local API -> cache key prefix, plus how many distinct Local APIs were seen.
--
-- The map is empty when no partitioning is needed, which leaves upstream's exact cache
-- keys in place. Configurations without a Local API are never counted and never get a
-- prefix: they do no decision lookup at all, so they cannot bleed into anything, and
-- counting them would penalise the common "AppSec everywhere, Local API on a subset"
-- fleet with a partition it does not need.
function cache_partition.prefixes(api_urls)
	local distinct = {}
	local count = 0
	for _, api_url in ipairs(api_urls) do
		if api_url ~= "" and not distinct[api_url] then
			distinct[api_url] = true
			count = count + 1
		end
	end

	local prefixes = {}
	if count < 2 then
		return prefixes, count
	end

	-- Sorted so the assignment is stable across workers and reloads
	local sorted = {}
	for api_url in pairs(distinct) do
		insert(sorted, api_url)
	end
	sort(sorted)
	for index, api_url in ipairs(sorted) do
		prefixes[api_url] = index .. "|"
	end
	return prefixes, count
end

return cache_partition
