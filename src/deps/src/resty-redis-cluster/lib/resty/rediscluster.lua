local redis = require "resty.redis"
local resty_lock = require "resty.lock"
local xmodem = require "resty.xmodem"
local new_tab = require "table.new"
local digest = require "resty.openssl.digest"
local resty_string = require "resty.string"

local setmetatable = setmetatable
local tostring = tostring
local string = string
local type = type
local table = table
local ngx = ngx
local math = math
local rawget = rawget
local pairs = pairs
local unpack = unpack
local ipairs = ipairs
local tonumber = tonumber
local string_sub = string.sub
local table_insert = table.insert
local table_concat = table.concat
local string_find = string.find
local redis_crc = xmodem.redis_crc

local re_match = ngx.re.match
local ngx_log = ngx.log
local NGX_ERR = ngx.ERR
local NGX_WARN = ngx.WARN
local NGX_NOTICE = ngx.NOTICE
local NGX_INFO = ngx.INFO
local NGX_DEBUG = ngx.DEBUG

-- cluster's key space is split into 16384 slots
local REDIS_SLOTS_TOTAL = 16384

local DEFAULT_SHARED_DICT_NAME = "redis_cluster_slot_locks"
local DEFAULT_REFRESH_DICT_NAME = "refresh_lock"
local DEFAULT_MAX_REDIRECTION = 5
local DEFAULT_MAX_CONNECTION_ATTEMPTS = 3
local DEFAULT_KEEPALIVE_TIMEOUT = 55000
local DEFAULT_KEEPALIVE_CONS = 1000
local DEFAULT_CONNECTION_TIMEOUT = 1000
local DEFAULT_SEND_TIMEOUT = 1000
local DEFAULT_READ_TIMEOUT = 1000

local LEFT_BRACKET = "{"
local RIGHT_BRACKET = "}"

local _M = {}
local mt = { __index = _M }

-- Redis 7.x and Redis 6.x use different slots format
local redis7_with_host

local slot_cache = {}
local master_nodes = {}

local cmds_for_all_master = {
    ["flushall"] = true,
    ["flushdb"] = true
}

local cluster_invalid_cmds = {
    ["config"] = true,
    ["shutdown"] = true
}


local CACHED_SHA256


local function hash_password(password)
  if not password or password == "" then
    return ""
  end

  local sha256, err
  if CACHED_SHA256 then
    sha256 = CACHED_SHA256

  else
    sha256, err = digest.new("sha256")
    if not sha256 then
      return nil, err
    end
    CACHED_SHA256 = sha256
  end

  local hash
  hash, err = sha256:final(password)
  if not hash then
    CACHED_SHA256 = nil
    return nil, err
  end

  local ok
  ok, err = sha256:reset()
  if not ok then
    CACHED_SHA256 = nil
    return nil, err
  end

  return resty_string.to_hex(hash)
end


local function set_base_pool_name(conf)
  -- BW edit: set_poolname rewrites connect_opts.pool on every connect; a second new() on the
  -- same options table would otherwise read that string back as the user's base pool and
  -- prefix it again. Compute the base once per options table.
  if conf.base_pool then
    return true
  end

  if not conf.connect_opts then
    conf.connect_opts = {}
  end

  local opts = conf.connect_opts
  local base_pool
  if type(opts.pool) == "string" then
    base_pool = opts.pool

  else
    local hashed_password, err = hash_password(conf.password)
    if not hashed_password then
      ngx_log(NGX_ERR, "failed to hash the password: ", err)
      return nil, err
    end

    base_pool = tostring(opts.ssl)
                .. ":" .. tostring(opts.ssl_verify)
                .. ":" .. (opts.server_name or "")
                .. ":" .. (conf.username or "")
                .. ":" .. (hashed_password or "")

  end
  conf.base_pool = base_pool

  return true
end


local function set_poolname(ip, port, config)
  -- concat the ip and port of the node to the base pool name
  local pool = (ip or "") .. ":" .. tostring(port or "") .. ":" .. config.base_pool
  config.connect_opts.pool = pool
  ngx_log(NGX_DEBUG, "set pool name: ", pool)
end


-- BW edit: remember, across workers, the nodes that just failed to connect. While a node is
-- down every command on its slots, and every slot refresh that reaches it, would otherwise wait
-- out the full connect timeout, once per worker, and one request makes several Redis calls.
-- ponytail: fixed window, make it a setting if operators need to tune it.
local NODE_DOWN_SECONDS = 5

local function connect_node(self, redis_client, ip, port)
    local node = "down:" .. tostring(ip) .. ":" .. tostring(port)
    local dict = ngx.shared[self.config.dict_name or DEFAULT_SHARED_DICT_NAME]
    if dict and dict:get(node) then
        return nil, "node marked down"
    end
    set_poolname(ip, port, self.config)
    local ok, err = redis_client:connect(ip, port, self.config.connect_opts)
    if not ok and dict then
        dict:set(node, true, NODE_DOWN_SECONDS)
    end
    return ok, err
end


-- According to the Redis documentation, the hash tag is found only if the '{' and '}'
-- are exist in the key, or it should use the whole key to calculate the slot.
-- See: https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/#hash-tags
--
-- For the Redis hash slot implemetation, see: https://github.com/redis/redis/blob/8a05f0092b0e291498b8fdb8dd93355467ceab25/src/cluster.c#L30-L49
local function parse_key(key_str)
    local left_index = string_find(key_str, LEFT_BRACKET, 1, true)
    if not left_index then
        return key_str
    end

    local right_index = string_find(key_str, RIGHT_BRACKET, left_index + 1, true)
    if right_index and right_index > left_index + 1 then
        return key_str:sub(left_index + 1, right_index - 1)
    end
    return key_str
end
-- export for testing
_M.parse_key = parse_key


local function redis_slot(str)
    return redis_crc(parse_key(str))
end


local function release_connection(red, config)
    local ok,err = red:set_keepalive(config.keepalive_timeout
            or DEFAULT_KEEPALIVE_TIMEOUT, config.keepalive_cons or DEFAULT_KEEPALIVE_CONS)
    if not ok then
        ngx_log(NGX_ERR, "set keepalive failed: ", err)
    end
end


local check_auth
do
    local function check_reused(redis_client)
        local count, err = redis_client:get_reused_times()
        if err then
            return nil, "failed to get reused count: " .. tostring(err)
        end

        if count > 0 then
            return true, nil -- reusing the connection, so already authenticated
        else
            return nil, nil -- new connection
        end
    end

    check_auth = function(self, redis_client)
        if not redis_client then
            return nil, "redis_client can not be nil"
        end

        -- redis < 6.0
        if type(self.config.auth) == "string" then
            if self.config.force_auth ~= true then
                local ok, err = check_reused(redis_client)
                if err then
                    return nil, err
                end
                if ok then
                    return true, nil
                end
            end

            return redis_client:auth(self.config.auth)

        -- redis 6.x adds support for username+password combination
        elseif type(self.config.password) == "string" then
            if self.config.force_auth ~= true then
                local ok, err = check_reused(redis_client)
                if err then
                    return nil, err
                end
                if ok then
                    return true, nil
                end
            end

            if type(self.config.username) == "string" then
                return redis_client:auth(self.config.username, self.config.password)

            else
                return redis_client:auth(self.config.password)
            end

        else
            return true, nil
        end
    end
end


local function check_status(self, redis_client)
    if not redis_client then
        return nil, "redis_client can not be nil"
    end

    local info, err = redis_client:cluster("info")
    if err then
        return nil, "failed to fetch cluster info: " .. err
    end

    local state
    state, err = re_match(info, "cluster_state:([a-zA-Z]+)\r\n", "jo")
    if err then
        return nil, "PCRE regular expression error: " .. err
    end
    if not state then
        return nil, "failed to match cluster state"
    end

    if state[1] == "fail" then
        return nil, "cluster state: fail"
    end
    if state[1] == "ok" then
        return true, nil
    end
end


-- retrieve only the major.minor from a redis INFO server payload; the patch
-- component is optional since some managed Redis services report versions as
-- x.y rather than x.y.z (FTI-7672: AWS ElastiCache Serverless Valkey reports x.y)
local function parse_redis_version(server_info)
    local version, err = re_match(server_info, [[redis_version:(\d+\.\d+)(?:\.\d+)?.*?\r\n]], "jo")
    if err then
        return nil, "PCRE regular expression error: " .. err
    end
    if not version then
        return nil, "failed to match version info"
    end
    return version[1]
end
-- export for testing
_M.parse_redis_version = parse_redis_version


local function check_version(self, redis_client)
    if not redis_client then
        return nil, "redis_client can not be nil"
    end

    local server_info, err = redis_client:info("server")
    if err then
        return nil, "failed to fetch server info: " .. err
    end

    local version
    version, err = parse_redis_version(server_info)
    if not version then
        return nil, err
    end

    ngx_log(NGX_INFO, "redis version: ", version)
    if tonumber(version) >= 9.0 then
        ngx_log(NGX_WARN, "redis version 9.x or above detected, comptability not guaranteed")
    end

    return true, nil
end


local function split(s, delimiter)
    local result = {};
    for m in (s..delimiter):gmatch("(.-)"..delimiter) do
        table_insert(result, m);
    end
    return result;
end


-- cache only IPs
local function parse_masters(self, redis_client)
    if not redis_client then
        return nil, "redis_client can not be nil"
    end

    local nodes, err = redis_client:cluster("nodes")
    if not nodes then
        return nil, "failed to fetch nodes: " .. err
    end

    -- must be a fresh table
    local master_list = {}

    -- bf7d28ccd79ca000547b8d6dfc042ca08b5d8b1a 172.26.0.25:6379@16379 slave 86bc3b462782f48ee2b56939107744a792dc3575 0 1718355186000 1 connected
    -- 79f6be094052b48c63967bc494e493a739016305 172.26.0.26:6379@16379 slave 438d9bc4c865e342a0a6dd1b560ac5d3f0c92662 0 1718355186000 2 connected
    -- 72d111446f11ee900df33f8a91425bb6533be0b6 172.26.0.23:6379@16379 master - 0 1718355187000 3 connected 10923-16383
    -- 438d9bc4c865e342a0a6dd1b560ac5d3f0c92662 172.26.0.22:6379@16379 master - 0 1718355186902 2 connected 5461-10922
    -- 0e0da2991a4f713691c209ba2b7467d2a8223e9c 172.26.0.24:6379@16379 slave 72d111446f11ee900df33f8a91425bb6533be0b6 0 1718355187920 3 connected
    -- 86bc3b462782f48ee2b56939107744a792dc3575 172.26.0.21:6379@16379 myself,master - 0 1718355182000 1 connected 0-5460
    local node_list = split(nodes, "\n")
    for _, node in ipairs(node_list) do
        local node_info = split(node, " ")
        if #node_info > 2 then
            local is_master = string_find(node_info[3], "master", 1, true) ~= nil
            if is_master then
                -- 172.26.0.21:6379
                local ip_port_str = split(node_info[2], "@")[1]
                local ip_port = split(ip_port_str, ":")
                table_insert(master_list, {
                    ip = ip_port[1],
                    port = tonumber(ip_port[2])
                })
            end
        end
    end

    master_nodes[self.config.name .. "master_list"] = master_list

    return true
end


local function parse_slots(self, redis_client)
    if not redis_client then
        return nil, "redis_client can not be nil"
    end

    local slots_data, err = redis_client:cluster("slots")
    if not slots_data then
        return nil, "failed to fetch slots: " .. err
    end

    -- mapping from slots to IPs and/or hostnames of servers
    -- Slot indices are integers 0-16383. Indices 1-16383 go into the array
    -- part for O(1) access; index 0 falls into the hash part (1 entry).
    local slots = new_tab(REDIS_SLOTS_TOTAL, 1)

    -- must be a fresh table
    local master_list = {}

    -- cache the complete list of servers present in cluster
    -- while the cluster is resharding (adding/removing nodes)
    -- this can differ from self.config.serv_list
    local servers = { serv_list = {} }

    for i = 1, #slots_data do
        -- Redis 6: { 0, 5460, { "172.26.0.21", 6379, "b050a28d860201c487891ecde77efc8a3935ea51" }, { "172.26.0.25", 6379, "20d96bc4a640fd244699e29274b2c94962def80e" } }
        -- Redis 7: { 0, 5460, { "rc-node-1", 6379, "3a4f2814802ca25a5c92dfc167674802126557d3", { "ip", "172.26.0.11" } }, { "rc-node-5", 6379, "f14b2cf710613f517374aefe7b84d9f013102ebe", { "ip", "172.26.0.15" } } }
        -- Redis 7: { 0, 5460, { "172.26.0.11", 6379, "64ff3bc4e8f4587c92bcfaa6c085e67417d44d5d", {} }, { "172.26.0.15", 6379, "9a63c473b928203b141d20a46be6784eb320ba0c", {} } }
        --
        -- data of a slots range like `[0, 5460]`
        local sub_range_data = slots_data[i]

        -- item 1 and 2 are the start slot and end slot
        local start_slot, end_slot = sub_range_data[1], sub_range_data[2]

        -- cache the servers responsible for [start_slot, end_slot]
        local sub_range_servers = { serv_list = {} }

        if #sub_range_data == 3 then
            ngx_log(NGX_INFO, "only master node present in slots info but able to continue")
        end
        -- retrieve the list of servers (including IPs and/or hostnames) for [start_slot, end_slot]
        for j = 3, #sub_range_data do
            -- Redis 6: { "172.26.0.21", 6379, "b050a28d860201c487891ecde77efc8a3935ea51" }
            -- Redis 7: { "rc-node-1", 6379, "3a4f2814802ca25a5c92dfc167674802126557d3", { "ip", "172.26.0.11" } }
            -- Redis 7: { "172.26.0.11", 6379, "64ff3bc4e8f4587c92bcfaa6c085e67417d44d5d", {} }
            local server_info = sub_range_data[j]

            local server_hostname_or_ip, server_port = server_info[1], tostring(server_info[2])

            local server_ip
            -- Redis 6: nil
            -- Redis 7: { "ip", "172.26.0.11" }
            -- Redis 7: {}
            local ip_tab = server_info[4]
            if ip_tab and type(ip_tab) == "table" and next(ip_tab) then
                server_ip = ip_tab[2]
            end
            if server_ip and server_ip ~= server_hostname_or_ip then
                redis7_with_host = true

                -- prioritize IP address over hostname as IP does not suffer from stale DNS cache
                local ip_port = { ip = server_ip, port = server_port }

                table_insert(sub_range_servers.serv_list, ip_port)
                table_insert(servers.serv_list, ip_port)

                -- master node is returned before slave nodes
                if j == 3 then
                    table_insert(master_list, ip_port)
                end

            else

                redis7_with_host = false
            end

            local hostname_port = { ip = server_hostname_or_ip, port = server_port }

            table_insert(sub_range_servers.serv_list, hostname_port)
            table_insert(servers.serv_list, hostname_port)

            -- master node is returned before slave nodes
            -- only insert this if not inserted above
            if not redis7_with_host and j == 3 then
                table_insert(master_list, hostname_port)
            end
        end

        -- sub_range_servers.serv_list:
        -- { { "172.26.0.11", 6379 }, { "rc-node-1", 6379 },
        --   { "172.26.0.14", 6379 }, { "rc-node-4", 6379 },
        --   { "172.26.0.17", 6379 }, { "rc-node-7", 6379 },
        -- }
        --
        -- ngx_log(NGX_NOTICE, "sub_range_servers.serv_list = ", require "inspect"(sub_range_servers.serv_list))

        for slot = start_slot, end_slot do
            slots[slot] = sub_range_servers
        end
    end

    slot_cache[self.config.name] = slots
    -- servers.serv_list is the sum of all sub_range_servers.serv_list
    slot_cache[self.config.name .. "serv_list"] = servers

    master_nodes[self.config.name .. "master_list"] = master_list

    ngx_log(NGX_DEBUG, "finished initializing slot cache")
    return true
end


local function try_hosts_slots(self, serv_list)
    local start_time = ngx.now()
    local errors = {}
    local config = self.config
    if #serv_list < 1 then
        return nil, "failed to fetch slots, serv_list config is empty"
    end

    for i = 1, #serv_list do
        local ip = serv_list[i].ip
        local port = serv_list[i].port
        local redis_client = redis:new()
        local ok, err, max_connection_timeout_err
        redis_client:set_timeouts(config.connect_timeout or DEFAULT_CONNECTION_TIMEOUT,
                                  config.send_timeout or DEFAULT_SEND_TIMEOUT,
                                  config.read_timeout or DEFAULT_READ_TIMEOUT)

        -- attempt to connect DEFAULT_MAX_CONNECTION_ATTEMPTS times to redis
        -- Kong currently does not configure 'max_connection_attempts'
        for k = 1, config.max_connection_attempts or DEFAULT_MAX_CONNECTION_ATTEMPTS do
            -- for each ip:port pair, we try at least once before check total timeout
            ok, err = connect_node(self, redis_client, ip, port)
            if ok then break end
            -- BW edit: the failure that marked the node down was already logged.
            if err ~= "node marked down" then
                ngx_log(NGX_ERR, "unable to connect ip:port ", ip, ":", port, ", attempt ", k, ", error: ", err)
            end
            table_insert(errors, err)

            -- Kong currently does not configure 'max_connection_timeout'
            local total_connection_time_ms = (ngx.now() - start_time) * 1000
            if (config.max_connection_timeout and total_connection_time_ms > config.max_connection_timeout) then
                max_connection_timeout_err = "max_connection_timeout of " .. config.max_connection_timeout .. "ms reached."
                ngx_log(NGX_ERR, max_connection_timeout_err)
                table_insert(errors, max_connection_timeout_err)
                return nil, errors
            end
        end

        if ok then
            local _, auth_err = check_auth(self, redis_client)
            if auth_err then
                redis_client:close()
                table_insert(errors, auth_err)
                return nil, errors
            end

            -- ensure cluster status is ok
            local _, status_err = check_status(self, redis_client)
            if status_err then
                redis_client:close()
                table_insert(errors, status_err)
                return nil, errors
            end

            local _, version_err = check_version(self, redis_client)
            if version_err then
                redis_client:close()
                table_insert(errors, version_err)
                return nil, errors
            end

            -- cache master nodes before slots
            -- give the cluster a chance to spread gossip info
            -- todo: will deprecate this by function 'parse_slots()'
            local _, masters_err = parse_masters(self, redis_client)
            if masters_err then
                ngx_log(NGX_DEBUG, "failed to initialize masters cache")
                redis_client:close()
                table_insert(errors, masters_err)
                return nil, errors
            end

            -- cache slots
            local _, slots_err = parse_slots(self, redis_client)
            if slots_err then
                ngx_log(NGX_DEBUG, "failed to initialize slots cache")
                redis_client:close()
                table_insert(errors, slots_err)
                return nil, errors
            end

            -- only put back to connection pool when there are not errors
            release_connection(redis_client, config)

            -- refresh of slots and master nodes successful
            return true, nil
        end
    end

    return nil, errors
end


function _M.fetch_slots(self)
    local serv_list = self.config.serv_list
    local serv_list_cached = slot_cache[self.config.name .. "serv_list"]

    local serv_list_combined

    -- if a cached serv_list is present, add it to combined list
    if serv_list_cached then
        serv_list_combined = {}

        -- prioritize serv_list from config over cached serv_list
        -- in the event that the entire config serv_list no longer
        -- points to anything usable, try the cached serv_list
        for _, s in ipairs(serv_list) do
            serv_list_combined[#serv_list_combined + 1] = s
        end

        for _, s in ipairs(serv_list_cached.serv_list) do
            serv_list_combined[#serv_list_combined + 1] = s
        end

    else
        -- otherwise we bootstrap with our serv_list from config
        serv_list_combined = serv_list
    end

    ngx_log(NGX_DEBUG, "fetching slots from: ", #serv_list_combined, " servers")
    -- important!
    serv_list_cached = nil -- luacheck: ignore

    local _, errors = try_hosts_slots(self, serv_list_combined)
    if errors then
        local err = "failed to fetch slots: " .. table_concat(errors, ";")
        ngx_log(NGX_ERR, err)
        return nil, err
    end
end


local function unlock(self, lock, msg)
    if not lock then
        return nil, "lock can not be nil"
    end

    local ok, err = lock:unlock()
    if not ok then
        return nil, "failed to unlock in " .. msg .. " slot cache: " .. err
    end

    return true, nil
end


function _M.refresh_slots(self)
    local lock, err, elapsed
    -- BW edit: never queue behind another refresh of this worker. A request that fails during
    -- an outage must not wait up to 5 s on the lock; the refresh already running covers it.
    lock, err = resty_lock:new(self.config.dict_name or DEFAULT_SHARED_DICT_NAME, { timeout = 0 })
    if not lock then
        ngx_log(NGX_ERR, "failed to create lock in refreshing slot cache: ", err)
        return nil, err
    end

    local worker_id = ngx.worker.id()
    local refresh_lock_key = (self.config.refresh_lock_key or DEFAULT_REFRESH_DICT_NAME) .. worker_id
    elapsed, err = lock:lock(refresh_lock_key)
    if not elapsed then
        if err == "timeout" then
            return nil, "slot refresh already in progress"
        end
        ngx_log(NGX_ERR, "failed to acquire the lock in refreshing slot cache: ", err)
        return nil,  err
    end

    local _, fetch_err = self:fetch_slots()
    unlock(self, lock, "refreshing")
    if fetch_err then
        return nil, fetch_err
    end
end


function _M.init_slots(self)
    if slot_cache[self.config.name] then
        -- already initialized
        return true
    end

    local lock, elapsed, err, err_msg
    -- BW edit: lua-resty-session's cluster backend never sets lock_timeout, so an unset
    -- value defaulted to resty.lock's own 5s timeout and every waiter serialized behind it.
    -- Default it to the connect timeout instead (resty.lock wants seconds, connect_timeout is ms).
    local lock_timeout = self.config.lock_timeout or (self.config.connect_timeout or DEFAULT_CONNECTION_TIMEOUT) / 1000
    lock, err = resty_lock:new(self.config.dict_name or DEFAULT_SHARED_DICT_NAME, { timeout = lock_timeout })
    if not lock then
        err_msg = "failed to create lock in initializing slot cache: " .. tostring(err)
        ngx_log(NGX_ERR, err_msg)
        return nil, err_msg
    end

    -- BW edit: slot_cache is per worker, so a lock shared by every worker only made each
    -- worker wait for the others to fill their own caches after a reload.
    elapsed, err = lock:lock("redis_cluster_slot_" .. self.config.name .. ngx.worker.pid())
    if not elapsed then
        err_msg = "failed to acquire the lock in initializing slot cache: " .. tostring(err)
        ngx_log(NGX_ERR, err_msg)
        return nil, err_msg
    end

    if slot_cache[self.config.name] then
        unlock(self, lock, "initializing")
        -- already initialized
        return true
    end

    local errors = {}
    local ok
    ok, err = self:fetch_slots()
    if not ok then
        table_insert(errors, err)
    end

    ok, err = unlock(self, lock, "initializing")
    if not ok then
        table_insert(errors, err)
    end

    if #errors > 0 then
        return nil, table_concat(errors, ",")
    end
    -- initialized
    return true, nil
end


function _M.new(_, config)
    if not config.name then
        return nil, " redis cluster config name is empty"
    end
    if not config.serv_list or #config.serv_list < 1 then
        return nil, " redis cluster config serv_list is empty"
    end

    local inst = { config = config }
    inst = setmetatable(inst, mt)

    local ok, err = set_base_pool_name(inst.config)
    if not ok then
      return nil, err
    end

    local _, err = inst:init_slots()
    if err then
        return nil, err
    end

    return inst
end


local function pick_node(self, serv_list, slot, magic_random_seed, ip_host_index)
    local host
    local port
    local slave
    local index

    if not serv_list or #serv_list < 1 then
        if slot then
            ngx_log(NGX_DEBUG, "pick node for slot ", slot)
        end
        return nil, nil, nil, "serv_list is empty"
    end

    if magic_random_seed and type(magic_random_seed) ~= "number" then
        return nil, nil, nil, "magic_random_seed must be a number"
    end

    if ip_host_index then
        if type(ip_host_index) ~= "number" then
            return nil, nil, nil, "ip_host_index must be a number"
        end

        -- 1: pick IP first
        -- 2: then pick hostname
        ip_host_index = ip_host_index % 2
        if ip_host_index == 0 then
            ip_host_index = 2
        end

    else
        ip_host_index = 1
    end

    -- slave nodes can be picked; however
    -- Kong currently does not configure this option
    if self.config.enable_slave_read then
        if magic_random_seed then
            index = magic_random_seed % #serv_list
            if index == 0 then
                index = #serv_list
            end
        else
            index = math.random(#serv_list)
        end

        -- cluster slots will always put the master node before slave nodes
        -- serv_list:
        -- { { master_ip, master_port }, { master_host, master_port },
        --   { slave_ip, slave_port }, { slave_host, slave_port },
        --   { slave_ip, slave_port }, { slave_host, slave_port },
        -- }
        if redis7_with_host then
            -- pick IP
            if ip_host_index == 1 and index % 2 == 0 then
                index = index - 1
            end
            -- pick hostname
            if ip_host_index == 2 and index % 2 == 1 then
                index = index + 1
            end

            slave = index > 2

        else
            slave = index > 1
        end

    -- only pick the master node (IP or hostname)
    else
        if redis7_with_host then
            index = ip_host_index
        else
            index = 1
        end

        slave = false
    end

    host = serv_list[index].ip
    port = serv_list[index].port

    ngx_log(NGX_INFO, "index: ", index, ", pick node: ", host, ":", port)

    return host, port, slave
end


local ask_host_and_port = {}
local function parse_ask_signal(res)
    --ask signal sample:ASK 12191 127.0.0.1:7008, so we need to parse and get 127.0.0.1, 7008
    if res ~= ngx.null then
        if type(res) == "string" and string_sub(res, 1, 3) == "ASK" then
            local matched = re_match(res, [[^ASK [^ ]+ ([^:]+):([^ ]+)]], "jo", nil, ask_host_and_port)
            if not matched then
                return nil, nil
            end
            return matched[1], matched[2]
        end
        if type(res) == "table" then
            for i = 1, #res do
                if type(res[i]) == "string" and string_sub(res[i], 1, 3) == "ASK" then
                    local matched = re_match(res[i], [[^ASK [^ ]+ ([^:]+):([^ ]+)]], "jo", nil, ask_host_and_port)
                    if not matched then
                        return nil, nil
                    end
                    return matched[1], matched[2]
                end
            end
        end
    end
    return nil, nil
end


local function has_moved_signal(res)
    if res ~= ngx.null then
        if type(res) == "string" and string_sub(res, 1, 5) == "MOVED" then
            return true
        else
            if type(res) == "table" then
                for i = 1, #res do
                    if type(res[i]) == "string" and string_sub(res[i], 1, 5) == "MOVED" then
                        return true
                    end
                end
            end
        end
    end
    return false
end


local function generate_magic_seed(self)
    --For pipeline, We don't want request to be forwarded to all channels, eg. if we have 3*3 cluster(3 master 2 replicas) we
    --alway want pick up specific 3 nodes for pipeline requests, instead of 9.
    --Currently we simply use (num of allnode)%count as a randomly fetch. Might consider a better way in the future.
    -- use the dynamic serv_list instead of the static config serv_list
    local node_count = #slot_cache[self.config.name .. "serv_list"].serv_list
    return math.random(node_count)
end


local function handle_command_with_retry(self, target_ip, target_port, asking, cmd, key, ...)
    local config = self.config

    -- key will be passed to resty.redis
    local slot = redis_slot(tostring(key))

    local magic_random_seed = generate_magic_seed(self)
    local loop_counter = config.max_redirection or DEFAULT_MAX_REDIRECTION

    for k = 1, loop_counter do
        if k > 1 then
            ngx_log(NGX_NOTICE, "handle retry attempts:", k, " for cmd:", cmd, " key:", key)
        end

        local slots = slot_cache[self.config.name]
        if slots == nil or slots[slot] == nil then
            self:refresh_slots()
            return nil, "not slots information present, nginx might have never successfully executed cluster(\"slots\")"
        end
        local serv_list = slots[slot].serv_list

        -- We must empty local reference to slots cache, otherwise there will be memory issue while
        -- coroutine swich happens(eg. ngx.sleep, cosocket), very important!
        slots = nil -- luacheck: ignore

        local ip, port, slave, err
        local ok, connerr, first_ip

        local redis_client = redis:new()
        redis_client:set_timeouts(config.connect_timeout or DEFAULT_CONNECTION_TIMEOUT,
                                  config.send_timeout or DEFAULT_SEND_TIMEOUT,
                                  config.read_timeout or DEFAULT_READ_TIMEOUT)

        if target_ip ~= nil and target_port ~= nil then
            -- asking redirection should only happens at master nodes
            ip, port, slave = target_ip, target_port, false

            ok, connerr = connect_node(self, redis_client, ip, port)
            if ok then break end
        else
            -- Redis 7: try IP first and then hostname as IP does not suffer from stale DNS cache
            local tries = redis7_with_host and 2 or 1
            for i = 1, tries do
                ip, port, slave, err = pick_node(self, serv_list, slot, magic_random_seed, i)
                if err then
                    ngx_log(NGX_ERR, "pickup node failed, will return failed for this request, meanwhile refreshing slotcache ", err)
                    self:refresh_slots()
                    return nil, err
                end
                first_ip = first_ip or ip

                ok, connerr = connect_node(self, redis_client, ip, port)
                -- BW edit: the hostname names the same node, so after a timeout it would only
                -- wait out a second connect timeout.
                if ok or connerr == "timeout" or connerr == "node marked down" then break end
            end
        end

        if ok then
            local _, auth_err = check_auth(self, redis_client)
            if auth_err then
                redis_client:close()
                return nil, auth_err
            end
            if slave then
                --set readonly
                ok, err = redis_client:readonly()
                if not ok then
                    redis_client:close()
                    self:refresh_slots()
                    return nil, err
                end
            end

            if asking then
                --executing asking
                ok, err = redis_client:asking()
                if not ok then
                    redis_client:close()
                    self:refresh_slots()
                    return nil, err
                end
            end

            local need_to_retry = false
            local res
            if cmd == "eval" or cmd == "evalsha" then
                res, err = redis_client[cmd](redis_client, ...)
            else
                res, err = redis_client[cmd](redis_client, key, ...)
            end

            if err then
                -- todo: we can follow the moved target instead of refreshing the slots
                if has_moved_signal(res) then
                    ngx_log(NGX_DEBUG, "find MOVED signal, trigger retry for normal commands, cmd:", cmd, " key:", key)
                    -- if retry with moved, we will not asking to specific ip:port anymore
                    target_ip = nil
                    target_port = nil
                    local _, _, moved_ip, moved_port = string_find(err, "MOVED %d+ ([%w%.%-_]+):(%d+)")
                    if moved_ip == ip and moved_port == tostring(port) then
                        ngx_log(NGX_DEBUG, "nested moved redirection detected, refreshing slots ...")
                    end
                    redis_client:close()
                    self:refresh_slots()
                    need_to_retry = true

                elseif string_sub(err, 1, 3) == "ASK" then
                    ngx_log(NGX_DEBUG, "handle asking for normal commands, cmd:", cmd, " key:", key)
                    if asking then
                        -- Should not happen after asking target ip:port and still return ask, if so, return error.
                        redis_client:close()
                        self:refresh_slots()
                        return nil, "nested asking redirection occurred, client cannot retry "
                    else
                        local ask_host, ask_port = parse_ask_signal(err)

                        if ask_host ~= nil and ask_port ~= nil then
                            -- only put back to connection pool when there are no errors
                            release_connection(redis_client, config)
                            return handle_command_with_retry(self, ask_host, ask_port, true, cmd, key, ...)
                        else
                            redis_client:close()
                            self:refresh_slots()
                            return nil, " cannot parse ask redirection host and port: msg is " .. err
                        end
                    end

                elseif string_sub(err, 1, 11) == "CLUSTERDOWN" then
                    redis_client:close()
                    self:refresh_slots()
                    return nil, "Cannot executing command, cluster status is failed!"
                else
                    --There might be node fail, we should also refresh slot cache
                    redis_client:close()
                    self:refresh_slots()
                    return nil, err
                end
            end
            if not need_to_retry then
                -- only put back to connection pool when there are no errors
                release_connection(redis_client, config)
                return res, err
            end
        else
            --There might be node fail, we should also refresh slot cache
            self:refresh_slots()
            -- BW edit: retry only when the refresh moved the slot to another node. Retrying the
            -- same dead node doubled the connect timeout of every command during an outage.
            local fresh = slot_cache[self.config.name]
            local owner = fresh and fresh[slot] and fresh[slot].serv_list[1]
            fresh = nil -- luacheck: ignore
            if k == loop_counter or target_ip or not owner or owner.ip == first_ip then
                return nil, "tried " .. k .. " times: " .. connerr
            end
        end
    end
    return nil, "failed to execute command, reaches maximum redirection attempts"
end


local function _do_cmd_master(self, cmd, key, ...)
    local errors = {}

    for _, master in ipairs(master_nodes[self.config.name .. "master_list"]) do
        local redis_client = redis:new()
        redis_client:set_timeouts(self.config.connect_timeout or DEFAULT_CONNECTION_TIMEOUT,
                                  self.config.send_timeout or DEFAULT_SEND_TIMEOUT,
                                  self.config.read_timeout or DEFAULT_READ_TIMEOUT)
        set_poolname(master.ip, master.port, self.config)
        local ok, err = redis_client:connect(master.ip, master.port, self.config.connect_opts)
        if ok then
            local _, auth_err = check_auth(self, redis_client)
            if auth_err then
                redis_client:close()
                return nil, auth_err
            end

            _, err = redis_client[cmd](redis_client, key, ...)
            release_connection(redis_client, self.config)
        end
        if err then
            table_insert(errors, err)
        end
    end

    if #errors > 0 then
        return nil, table_concat(errors, ";")
    end
    return true, nil
end

local function _do_cmd(self, cmd, key, ...)
    if cluster_invalid_cmds[cmd] == true then
        return nil, "command not supported"
    end

    local _reqs = rawget(self, "_reqs")
    if _reqs then
        local args = { ... }
        local t = { cmd = cmd, key = key, args = args }
        table_insert(_reqs, t)
        return
    end

    if cmds_for_all_master[cmd] then
        return _do_cmd_master(self, cmd, key, ...)
    end

    local res, err = handle_command_with_retry(self, nil, nil, false, cmd, key, ...)
    return res, err
end


local function construct_final_pipeline_resp(self, node_res_map, node_req_map)
    --construct final result with origin index
    local finalret = {}
    for k, v in pairs(node_res_map) do
        local reqs = node_req_map[k].reqs
        local res = v
        local need_to_fetch_slots = true
        for i = 1, #reqs do
            --deal with redis cluster ask redirection
            local ask_host, ask_port = parse_ask_signal(res[i])
            if ask_host ~= nil and ask_port ~= nil then
                ngx_log(NGX_DEBUG, "handle ask signal for cmd:", reqs[i]["cmd"], " key:", reqs[i]["key"], " target host:", ask_host, " target port:", ask_port)
                local askres, err = handle_command_with_retry(self, ask_host, ask_port, true, reqs[i]["cmd"], reqs[i]["key"], unpack(reqs[i]["args"]))
                if err then
                    return nil, err
                else
                    finalret[reqs[i].origin_index] = askres
                end
            elseif has_moved_signal(res[i]) then
                ngx_log(NGX_DEBUG, "handle moved signal for cmd:", reqs[i]["cmd"], " key:", reqs[i]["key"])
                if need_to_fetch_slots then
                    -- if there is multiple signal for moved, we just need to fetch slot cache once, and do retry.
                    self:refresh_slots()
                    need_to_fetch_slots = false
                end
                local movedres, err = handle_command_with_retry(self, nil, nil, false, reqs[i]["cmd"], reqs[i]["key"], unpack(reqs[i]["args"]))
                if err then
                    return nil, err
                else
                    finalret[reqs[i].origin_index] = movedres
                end
            else
                finalret[reqs[i].origin_index] = res[i]
            end
        end
    end
    return finalret
end


local function has_cluster_fail_signal_in_pipeline(res)
    for i = 1, #res do
        if res[i] ~= ngx.null and type(res[i]) == "table" then
            for j = 1, #res[i] do
                if type(res[i][j]) == "string" and string_sub(res[i][j], 1, 11) == "CLUSTERDOWN" then
                    ngx_log(NGX_INFO, res[i][j])
                    return true
                end
            end
        end
    end
    return false
end


function _M.init_pipeline(self)
    self._reqs = {}
end


function _M.commit_pipeline(self)
    local _reqs = rawget(self, "_reqs")

    if not _reqs or #_reqs == 0 then return nil, "no pipeline"
    end

    self._reqs = nil
    local config = self.config

    local slots = slot_cache[config.name]
    if slots == nil then
        self:refresh_slots()
        return nil, "not slots information present, nginx might have never successfully executed cluster(\"slots\")"
    end

    local node_res_map = {}
    local node_req_map = {}

    --construct req to real node mapping
    for i = 1, #_reqs do
        -- Because we will forward req to different nodes, so the result will not be the origin order,
        -- we need to record the original index and finally we can construct the result with origin order
        _reqs[i].origin_index = i
        local key = _reqs[i].key
        local slot = redis_slot(tostring(key))
        if slots[slot] == nil then
            self:refresh_slots()
            return nil, "not slots information present, nginx might have never successfully executed cluster(\"slots\")"
        end
        local slot_item = slots[slot]

        local node = slot_item.serv_list[1].ip .. tostring(slot_item.serv_list[1].port)
        if not node_req_map[node] then
            node_req_map[node] = { serv_list = slot_item.serv_list, reqs = {} }
            node_res_map[node] = {}
        end
        local ins_req = node_req_map[node].reqs
        ins_req[#ins_req + 1] = _reqs[i]
    end

    -- We must empty local reference to slots cache, otherwise there will be memory issue while
    -- coroutine swich happens(eg. ngx.sleep, cosocket), very important!
    slots = nil -- luacheck: ignore

    local magic_random_seed = generate_magic_seed(self)

    for k, v in pairs(node_req_map) do
        local reqs = v.reqs

        local ip, port, slave
        local redis_client
        local ok, errors = nil, {}
        -- Redis 7: try IP first and then hostname as IP does not suffer from stale DNS cache
        local tries = redis7_with_host and 2 or 1
        for i = 1, tries do
            local err
            ip, port, slave, err = pick_node(self, v.serv_list, nil, magic_random_seed, i)
            if err then
                table_insert(errors, err)
                self:refresh_slots()
                return nil, table_concat(errors, ",")
            end

            redis_client = redis:new()
            redis_client:set_timeouts(config.connect_timeout or DEFAULT_CONNECTION_TIMEOUT,
                                      config.send_timeout or DEFAULT_SEND_TIMEOUT,
                                      config.read_timeout or DEFAULT_READ_TIMEOUT)
            ok, err = connect_node(self, redis_client, ip, port)
            if ok then break end
            table_insert(errors, ip .. ":" .. port .. " " .. err)
        end
        if not ok then
            self:refresh_slots()
            return nil, "failed to connect, err: " .. table_concat(errors, ",")
        end

        local _, auth_err = check_auth(self, redis_client)
        if auth_err then
            redis_client:close()
            return nil, auth_err
        end

        if slave then
            --set readonly
            local ok, err = redis_client:readonly()
            if not ok then
                redis_client:close()
                self:refresh_slots()
                return nil, err
            end
        end

        redis_client:init_pipeline()
        for i = 1, #reqs do
            local req = reqs[i]
            if #req.args > 0 then
                if req.cmd == "eval" or req.cmd == "evalsha" then
                    redis_client[req.cmd](redis_client, unpack(req.args))
                else
                    redis_client[req.cmd](redis_client, req.key, unpack(req.args))
                end
            else
                redis_client[req.cmd](redis_client, req.key)
            end
        end
        local res, err = redis_client:commit_pipeline()
        if err then
            redis_client:close()
            -- There might be node fail, we should also refresh slot cache
            self:refresh_slots()
            return nil, err .. " return from " .. tostring(ip) .. ":" .. tostring(port)
        end

        if has_cluster_fail_signal_in_pipeline(res) then
            redis_client:close()
            self:refresh_slots()
            return nil, "Cannot executing pipeline command, cluster status is failed!"
        end

        -- only put back to connection pool when there are not errors
        release_connection(redis_client, config)

        node_res_map[k] = res
    end

    --construct final result with origin index
    local final_res, err = construct_final_pipeline_resp(self, node_res_map, node_req_map)
    if not err then
        return final_res
    else
        return nil, err .. " failed to construct final pipeline result "
    end
end


-- BW edit: expose the cached primaries for keyless per-node commands such as DBSIZE.
function _M.masters(self)
    local list = master_nodes[self.config.name .. "master_list"]
    if not list then
        return nil, "no master list cached"
    end
    local copy = {}
    for i, master in ipairs(list) do
        copy[i] = { ip = master.ip, port = master.port }
    end
    return copy
end

function _M.cancel_pipeline(self)
    self._reqs = nil
end


-- BW edit: a multi-key EVAL is valid in Redis Cluster when every key hashes to one slot
-- (hash tags). Reject cross-slot key sets before sending instead of refusing all of them,
-- and route by the first key while forwarding the full key list.
local function eval_route_key(keys_num, ...)
    if type(keys_num) ~= "number" or keys_num < 0 or keys_num % 1 ~= 0 then
        return nil, "Cannot execute eval without a valid keys number"
    end
    if select("#", ...) < keys_num then
        return nil, "Cannot execute eval: fewer keys than keys number"
    end
    if keys_num == 0 then
        return "no_key"
    end
    local first = ...
    local slot = redis_slot(tostring(first))
    for i = 2, keys_num do
        if redis_slot(tostring((select(i, ...)))) ~= slot then
            return nil, "CROSSSLOT Keys in request don't hash to the same slot"
        end
    end
    return first
end
_M.eval_route_key = eval_route_key

local function _do_eval_cmd(self, cmd, ...)
--[[
eval command usage:
eval(script, 1, key, arg1, arg2 ...)
eval(script, 0, arg1, arg2 ...)
]]
    local key, err = eval_route_key(select(2, ...), select(3, ...))
    if not key then
        return nil, err
    end
    return _do_cmd(self, cmd, key, ...)
end
-- dynamic cmd
setmetatable(_M, {
    __index = function(_, cmd)
        local method =
        function(self, ...)
            if cmd == "eval" or cmd == "evalsha" then
                return _do_eval_cmd(self, cmd, ...)
            else
                return _do_cmd(self, cmd, ...)
            end
        end

        -- cache the lazily generated method in our
        -- module table
        _M[cmd] = method
        return method
    end
})

return _M
