-- Redis key names. Standalone and Sentinel keep the historical names. In Redis Cluster
-- mode the keys that scripts touch together share a hash tag, so they land on one slot:
-- every ban and bad behavior key of an IP is tagged with that IP, and the reports list
-- with its facet keys is tagged {requests}. Only Redis sees these names; local datastore
-- keys never change.
local gsub = string.gsub
local match = string.match
local tonumber = tonumber

local rediskeys = {}

local ESCAPES = { ["{"] = "%7B", ["}"] = "%7D", ["%"] = "%25" }

-- A value that is nil, empty, or whitespace-only means "no nodes configured".
function rediskeys.nodes_value(value)
	if value == nil or match(value, "^%s*$") then
		return nil
	end
	return value
end

function rediskeys.cluster_mode()
	-- Required lazily: bunkerweb.utils requires this module.
	local nodes = require("bunkerweb.utils").get_variable("REDIS_CLUSTER_NODES", false)
	return rediskeys.nodes_value(nodes) ~= nil
end

-- Untrusted text (URI, user agent, rDNS, service names) must not choose a hash slot.
function rediskeys.escape(key)
	return (gsub(key, "[{}%%]", ESCAPES))
end

function rediskeys.ban(local_key, cluster)
	if not cluster then
		return local_key
	end
	-- Greedy: the IP never contains "_ip_", a service name might.
	local prefix, ip = match(local_key, "^(.*_ip_)(.+)$")
	return rediskeys.escape(prefix) .. "{" .. ip .. "}"
end

function rediskeys.badbehavior(ip, server_name, cluster)
	if not cluster then
		if server_name then
			return "plugin_bad_behavior_" .. server_name .. "_" .. ip
		end
		return "plugin_bad_behavior_" .. ip
	end
	if server_name then
		return "plugin_bad_behavior_" .. rediskeys.escape(server_name) .. "_{" .. ip .. "}"
	end
	return "plugin_bad_behavior_{" .. ip .. "}"
end

-- CrowdSec lease epoch of one IP, in the same slot as that IP's ban keys
function rediskeys.cs_epoch(ip, cluster)
	if not cluster then
		return "cs_epoch_" .. ip
	end
	return "cs_epoch_{" .. ip .. "}"
end

-- KEYS layout shared with the metrics scripts: list, initialized, rebuilding, oomprobe,
-- then one facet hash per field in the given order.
function rediskeys.reports(cluster, fields)
	local base = cluster and "{requests}" or "requests"
	local keys = { base, base .. ":facets:initialized", base .. ":facets:rebuilding", base .. ":facets:oomprobe" }
	for i, field in ipairs(fields) do
		keys[4 + i] = base .. ":facet:" .. field
	end
	return keys
end

-- Redis Cluster has no Sentinel and only database 0: asking for both is a configuration
-- error, and Redis is left unused rather than guessing which one the operator meant.
function rediskeys.cluster_config_error(cluster_nodes, sentinel_hosts, database)
	if not rediskeys.nodes_value(cluster_nodes) then
		return nil
	end
	if sentinel_hosts and sentinel_hosts ~= "" then
		return "REDIS_CLUSTER_NODES and REDIS_SENTINEL_HOSTS are both set, remove one"
	end
	if database and database ~= "" and tonumber(database) ~= 0 then
		return "REDIS_CLUSTER_NODES requires REDIS_DATABASE 0 (got " .. database .. ")"
	end
	return nil
end

-- "host", "host:port" or "[ipv6]:port", space separated. Default port 6379.
-- The brackets stay in ip: tcpsock:connect() rejects a bare IPv6 literal.
function rediskeys.parse_nodes(value)
	local nodes = {}
	for node in (value or ""):gmatch("%S+") do
		local host, port = match(node, "^%[(.+)%]:(%d+)$")
		if host then
			host = "[" .. host .. "]"
		end
		if not host then
			host, port = match(node, "^([^:]+):(%d+)$")
		end
		if not host then
			host, port = node, "6379"
		end
		nodes[#nodes + 1] = { ip = host, port = tonumber(port) }
	end
	return nodes
end

return rediskeys
