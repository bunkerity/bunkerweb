local clusterstore	= require "clusterstore"
local datastore		= require "datastore"
local utils         = require "utils"

local redisutils = {}

redisutils.ban = function(ip)
	-- Connect
	local redis_client, err = clusterstore:connect()
	if not redis_client then
		return nil, "can't connect to redis server : " .. err
	end
	-- Start transaction
	local ok, err = redis_client:multi()
	if not ok then
		clusterstore:close(redis_client)
		return nil, "MULTI failed : " .. err
	end
	-- Get ban
	ok, err = redis_client:get("ban_" .. ip)
	if not ok then
		clusterstore:close(redis_client)
		return nil, "GET failed : " .. err
	end
	-- Get ttl
	ok, err = redis_client:ttl("ban_" .. ip)
	if not ok then
		clusterstore:close(redis_client)
		return nil, "TTL failed : " .. err
	end
	-- Exec transaction
	local exec, err = redis_client:exec()
	if err then
		clusterstore:close(redis_client)
		return nil, "EXEC failed : " .. err
	end
	if type(exec) ~= "table" then
		clusterstore:close(redis_client)
		return nil, "EXEC result is not a table"
	end
	-- Extract ban reason
	local reason = exec[1]
	if type(reason) == "table" then
		clusterstore:close(redis_client)
		return nil, "GET failed : " .. reason[2]
	end
	if reason == ngx.null then
		clusterstore:close(redis_client)
		datastore:delete("bans_ip_" .. ip)
		return false
	end
	-- Extract ttl
	local ttl = exec[2]
	if type(ttl) == "table" then
		clusterstore:close(redis_client)
		return nil, "TTL failed : " .. ttl[2]
	end
	if ttl <= 0 then
		clusterstore:close(redis_client)
		return nil, "TTL returned invalid value : " .. tostring(ttl)
	end
	ok, err = datastore:set("bans_ip_" .. ip, reason, ttl)
	if not ok then
		clusterstore:close(redis_client)
		datastore:delete("bans_ip_" .. ip)
		return nil, "can't save ban to local datastore : " .. err
	end
	-- Return reason
	clusterstore:close(redis_client)
	return true, reason
end

return redisutils