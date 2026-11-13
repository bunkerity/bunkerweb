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
-- Upper bound for one refresh of the slot cache. A refresh walks every address
-- with three connect attempts each, and a network that drops packets costs the
-- full connect timeout per attempt. A Redis 7 cluster that announces hostnames
-- lists an IP and a hostname per node, so a six node cluster has twelve
-- addresses. Bound the walk so one failed refresh cannot hold the caller for
-- minutes. The first fetch has no bound: a client that cannot read the slots
-- once cannot start at all.
local DEFAULT_MAX_CONNECTION_TIMEOUT = 10000
-- A failed scan refresh is skipped for this long. Two seconds is shorter than the
-- usual sync interval, so one failure does not make the next tick skip as well.
local SCAN_REFRESH_BACKOFF = 2

local LEFT_BRACKET = "{"
local RIGHT_BRACKET = "}"

local _M = {}
local mt = { __index = _M }

-- Redis 7.x and Redis 6.x use different slots format. One entry for each cluster
-- name, because one worker can hold clients for clusters of different versions.
local redis7_with_host = {}

-- IP of a node, keyed by "<hostname>:<port>". Only a cluster that announces
-- hostnames fills it. One entry for each cluster name.
local ask_ip_by_host = {}

local slot_cache = {}
local master_nodes = {}
-- Time of the last failed refresh, for each cluster name. A failed scan refreshes
-- at most once per window, so a cluster that is down does not cost one walk of
-- the whole address list per call.
local refresh_failed_at = {}

local cmds_for_all_master = {
    ["flushall"] = true,
    ["flushdb"] = true
}

local cluster_invalid_cmds = {
    ["config"] = true,
    ["shutdown"] = true
}

-- Commands that take more than one key. `keys` says where the keys are in the
-- argument list. A command with `split = true` sends one part for each slot and
-- combines the parts. A command with `split = false` is sent unchanged when all
-- keys are in one slot, and returns an error when the keys span slots.
local multi_key_cmds = {
    mget    = { keys = "all",     split = true,  combine = "array" },
    del     = { keys = "all",     split = true,  combine = "sum"   },
    unlink  = { keys = "all",     split = true,  combine = "sum"   },
    exists  = { keys = "all",     split = true,  combine = "sum"   },
    touch   = { keys = "all",     split = true,  combine = "sum"   },

    mset     = { keys = "stride2", split = false },
    msetnx   = { keys = "stride2", split = false },
    sinter   = { keys = "all",     split = false },
    sunion   = { keys = "all",     split = false },
    sdiff    = { keys = "all",     split = false },
    pfcount  = { keys = "all",     split = false },
    rename   = { keys = "all",     split = false, args = 2 },
    renamenx = { keys = "all",     split = false, args = 2 },
    smove    = { keys = "first2",  split = false, args = 3 },
}


-- Use the same text for a key and for its slot. resty.redis converts a
-- non-string argument with tostring() before it sends the argument.
local function normalize_key(arg)
    if type(arg) == "string" then
        return arg
    end

    return tostring(arg)
end


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
  if not conf.connect_opts then
    conf.connect_opts = {}
  end

  local opts = conf.connect_opts
  local base_pool
  if type(opts.pool) == "string" then
    base_pool = opts.pool

  else
    -- `check_auth` sends a field only when it is a string. A `nil` or an `ngx.null`
    -- password must not reach the hash, and a non-string field must not be concatenated.
    local auth = type(conf.auth) == "string" and conf.auth or nil
    local password = type(conf.password) == "string" and conf.password or nil
    local username = type(conf.username) == "string" and conf.username or nil
    local server_name = type(opts.server_name) == "string" and opts.server_name or nil

    local uses_auth = auth ~= nil
    local secret = uses_auth and auth or password

    local hashed_secret, err = hash_password(secret)
    if not hashed_secret then
      ngx_log(NGX_ERR, "failed to hash the credential: ", err)
      return nil, err
    end

    base_pool = tostring(opts.ssl)
                .. ":" .. tostring(opts.ssl_verify)
                .. ":" .. (server_name or "")
                .. ":" .. (uses_auth and "" or (username or ""))
                .. ":" .. hashed_secret

  end
  conf.base_pool = base_pool

  return true
end


-- Rebuild the pool name from the current credentials. The caller owns the name when it
-- sets `connect_opts.pool`, so leave that name alone.
local function refresh_base_pool_name(conf, user_pool)
    if user_pool then
        return true
    end

    return set_base_pool_name(conf)
end


-- Connect to a node with the pool name for that node. Copy the caller options, because
-- `sock:connect` yields for a new connection: another coroutine can read the caller
-- table while this call waits.
-- BW edit: share a short node-down window across workers and every connect path.
-- shortcut: fixed five-second window; make configurable if operators need tuning.
local NODE_DOWN_SECONDS = 5

-- BW edit: Redis advertises bare IPv6, but ngx cosockets require brackets.
local function socket_host(host)
    if host and string_find(host, ":", 1, true) and string_sub(host, 1, 1) ~= "[" then
        return "[" .. host .. "]"
    end
    return host
end

-- NODES and redirects join a host (possibly bare IPv6) and a numeric port.
local function parse_endpoint(address)
    local host, port = string.match(address, "^(.*):(%d+)$")
    if host then
        host = string.match(host, "^%[(.+)%]$") or host
    end
    return host, port
end

local function connect_with_pool(redis_client, ip, port, config)
    local node = "down:" .. tostring(ip) .. ":" .. tostring(port)
    local dict = ngx.shared[config.dict_name or DEFAULT_SHARED_DICT_NAME]
    if dict and dict:get(node) then
        return nil, "node marked down"
    end
    local connect_opts = new_tab(0, 8)
    local opts = config.connect_opts
    if opts then
        for key, value in pairs(opts) do
            connect_opts[key] = value
        end
    end

    connect_opts.pool = (ip or "") .. ":" .. tostring(port or "") .. ":" .. config.base_pool

    -- Remember which credentials produced this pool name. The credentials can change
    -- while `connect` waits on the network.
    redis_client.pool_base = config.base_pool

    local ok, err = redis_client:connect(socket_host(ip), port, connect_opts)
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
    -- The pool name covers the credential, so it changes when the caller replaces one.
    -- A refresh in another coroutine can change the name while this connection waits on
    -- the network. Do not pool a connection from the previous generation.
    if rawget(red, "pool_base") ~= config.base_pool then
        red:close()
        return
    end

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
                local ip, port = parse_endpoint(ip_port_str)
                if not ip then
                    return nil, "invalid cluster node address: " .. ip_port_str
                end
                table_insert(master_list, {
                    ip = ip,
                    port = tonumber(port)
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

    -- Set when a node report carries the IP next to the hostname.
    local cluster_uses_ip = false
    local host_ip = {}

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
            local uses_ip = server_ip ~= nil and server_ip ~= server_hostname_or_ip
            if uses_ip then
                cluster_uses_ip = true
                host_ip[server_hostname_or_ip .. ":" .. server_port] = server_ip

                -- prioritize IP address over hostname as IP does not suffer from stale DNS cache
                local ip_port = { ip = server_ip, port = server_port }

                table_insert(sub_range_servers.serv_list, ip_port)
                table_insert(servers.serv_list, ip_port)

                -- master node is returned before slave nodes
                if j == 3 then
                    table_insert(master_list, ip_port)
                end
            end

            local hostname_port = { ip = server_hostname_or_ip, port = server_port }

            table_insert(sub_range_servers.serv_list, hostname_port)
            table_insert(servers.serv_list, hostname_port)

            -- master node is returned before slave nodes
            -- only insert this if not inserted above
            if not uses_ip and j == 3 then
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
    redis7_with_host[self.config.name] = cluster_uses_ip
    ask_ip_by_host[self.config.name] = host_ip

    ngx_log(NGX_DEBUG, "finished initializing slot cache")
    return true
end


-- Redis texts that mean the server rejected the credentials. A dead connection or a
-- socket error does not match: a new secret cannot fix those.
local AUTH_REJECTED_MARKERS = {
    "WRONGPASS",                    -- Redis 6 and later
    "invalid username-password",    -- the WRONGPASS text on some compatible servers
    "invalid password",             -- Redis 5 and earlier: "ERR invalid password"
    "NOAUTH",                       -- a command reply; kept for future command-level checks
    -- The server removed the password. The caller may clear its credential.
    "called without any password configured",
    "Client sent AUTH, but no password is set",
}


local function is_auth_rejected(err)
    if type(err) ~= "string" then
        return false
    end

    for i = 1, #AUTH_REJECTED_MARKERS do
        if string_find(err, AUTH_REJECTED_MARKERS[i], 1, true) then
            return true
        end
    end

    return false
end


-- Redis replies to these with "-ERR <text>", which resty.redis reports as
-- `false, err`, the same shape as a malformed command. They mean the cluster view
-- may be stale, so a scan must refresh the slot cache before it gives up. A
-- syntax error or a WRONGTYPE does not: the cluster is healthy, and a caller that
-- repeats the bad call must not pay a CLUSTER SLOTS walk every time.
local CLUSTER_LEVEL_ERRORS = {
    "CLUSTERDOWN",
    "MASTERDOWN",
    "TRYAGAIN",
    "READONLY",
}


local function is_cluster_level_error(err)
    if type(err) ~= "string" then
        return false
    end

    for i = 1, #CLUSTER_LEVEL_ERRORS do
        if string_find(err, CLUSTER_LEVEL_ERRORS[i], 1, true) then
            return true
        end
    end

    return false
end


-- `ngx.log` rejects a table without `__tostring`, a function and a thread. A hook can
-- raise those, and the log call must not raise a second error.
local function to_string(value)
    local ok, str = pcall(tostring, value)
    if ok then
        return str
    end

    return "unknown error"
end


-- Repeat AUTH once when the caller can change the credentials:
-- `config.auth_config_reconfigurer(self, err)` returns `true` after it updated `self.config`.
-- AUTH fails before the library sends a command to this node, so no command runs twice.
-- An error in the function must not stop the request, so the library logs it and reports the
-- original AUTH error.
local function check_auth_with_retry(self, redis_client)
    local ok, auth_err = check_auth(self, redis_client)
    if not auth_err then
        return ok, auth_err
    end

    local reconfigure = self.config.auth_config_reconfigurer
    if type(reconfigure) ~= "function" or not is_auth_rejected(auth_err) then
        return ok, auth_err
    end

    -- Read the caller pool name before the hook runs: the hook may change the config.
    -- `set_base_pool_name` treats only a string as a caller pool name.
    local pool = self.config.connect_opts and self.config.connect_opts.pool
    local user_pool = type(pool) == "string" and pool or nil

    local called, retry = pcall(reconfigure, self, auth_err)
    if not called then
        ngx_log(NGX_ERR, "auth_config_reconfigurer failed: ", to_string(retry))
        return ok, auth_err
    end

    if retry == true then
        if not user_pool then
            -- Move the pool name before the retry: another coroutine can connect while
            -- the retry waits on the network.
            local refreshed, refresh_err = refresh_base_pool_name(self.config, user_pool)
            if not refreshed then
                ngx_log(NGX_ERR, "failed to refresh the pool name: ", refresh_err)
            end
        end

        ok, auth_err = check_auth(self, redis_client)
    end

    return ok, auth_err
end


local function try_hosts_slots(self, serv_list, max_connection_timeout)
    local start_time = ngx.now()
    local errors = {}
    local config = self.config
    local timeout = max_connection_timeout or config.max_connection_timeout
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
            ok, err = connect_with_pool(redis_client, ip, port, self.config)
            if ok then break end
            -- BW edit: the failure that marked the node down was already logged.
            if err ~= "node marked down" then
                ngx_log(NGX_ERR, "unable to connect ip:port ", ip, ":", port, ", attempt ", k, ", error: ", err)
            end
            table_insert(errors, err)

            local total_connection_time_ms = (ngx.now() - start_time) * 1000
            if timeout and total_connection_time_ms > timeout then
                max_connection_timeout_err = "max_connection_timeout of " .. timeout .. "ms reached."
                ngx_log(NGX_ERR, max_connection_timeout_err)
                table_insert(errors, max_connection_timeout_err)
                return nil, errors
            end
        end

        if ok then
            local _, auth_err = check_auth_with_retry(self, redis_client)
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


-- `opts.max_connection_timeout` bounds the whole walk over the address list.
-- A refresh passes one; the first fetch leaves it nil.
function _M.fetch_slots(self, opts)
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

    local _, errors = try_hosts_slots(self, serv_list_combined,
                                      opts and opts.max_connection_timeout)
    if errors then
        local err = "failed to fetch slots: " .. table_concat(errors, ";")
        ngx_log(NGX_ERR, err)
        return nil, err
    end
end


-- ngx.worker.id() is nil in the master process and in a privileged agent.
local function worker_key()
    local id = ngx.worker.id()
    if id == nil then
        return "p" .. ngx.worker.pid()
    end
    return id
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
    -- BW edit: an in-progress refresh already covers this worker; never queue behind it.
    lock, err = resty_lock:new(self.config.dict_name or DEFAULT_SHARED_DICT_NAME, { timeout = 0 })
    if not lock then
        ngx_log(NGX_ERR, "failed to create lock in refreshing slot cache: ", err)
        return nil, err
    end

    local refresh_lock_key = (self.config.refresh_lock_key or DEFAULT_REFRESH_DICT_NAME) .. worker_key()
    elapsed, err = lock:lock(refresh_lock_key)
    if not elapsed then
        if err == "timeout" then
            return nil, "slot refresh already in progress"
        end
        ngx_log(NGX_ERR, "failed to acquire the lock in refreshing slot cache: ", err)
        return nil,  err
    end

    local _, fetch_err = self:fetch_slots({
        max_connection_timeout = self.config.max_connection_timeout
                                 or DEFAULT_MAX_CONNECTION_TIMEOUT,
    })
    unlock(self, lock, "refreshing")
    if fetch_err then
        ngx.update_time()
        refresh_failed_at[self.config.name] = ngx.now()
        return nil, fetch_err
    end

    refresh_failed_at[self.config.name] = nil
end


function _M.init_slots(self)
    if slot_cache[self.config.name] then
        -- already initialized
        return true
    end

    local lock, elapsed, err, err_msg
    -- BW edit: session storage leaves lock_timeout unset; use connect timeout, not resty.lock's 5s default.
    local lock_timeout = self.config.lock_timeout or (self.config.connect_timeout or DEFAULT_CONNECTION_TIMEOUT) / 1000
    lock, err = resty_lock:new(self.config.dict_name or DEFAULT_SHARED_DICT_NAME, { timeout = lock_timeout })
    if not lock then
        err_msg = "failed to create lock in initializing slot cache: " .. tostring(err)
        ngx_log(NGX_ERR, err_msg)
        return nil, err_msg
    end

    -- The slot cache is per worker. A slow hook in one worker must not block the others.
    elapsed, err = lock:lock("redis_cluster_slot_" .. self.config.name .. "_" .. worker_key())
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
    -- A hook that is not a function never fires, so the caller gets no clue.
    local reconfigurer = config.auth_config_reconfigurer
    if reconfigurer ~= nil and reconfigurer ~= false and reconfigurer ~= ngx.null
       and type(reconfigurer) ~= "function" then
        return nil, "auth_config_reconfigurer must be a function"
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
        if redis7_with_host[self.config.name] then
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
        if redis7_with_host[self.config.name] then
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


local function parse_ask_signal(res)
    --ask signal sample:ASK 12191 127.0.0.1:7008, so we need to parse and get 127.0.0.1, 7008
    if res ~= ngx.null then
        if type(res) == "string" and string_sub(res, 1, 3) == "ASK" then
            return parse_endpoint(string.match(res, "^ASK %d+ (.+)$") or "")
        end
        if type(res) == "table" then
            for i = 1, #res do
                if type(res[i]) == "string" and string_sub(res[i], 1, 3) == "ASK" then
                    return parse_endpoint(string.match(res[i], "^ASK %d+ (.+)$") or "")
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


-- An ASK reply names the address to use. On a Redis 7 cluster that announces
-- hostnames, that address is a hostname and the slot map also holds the IP of
-- the same node. Return the IP first, then the address of the reply.
local function ask_targets(self, host, port)
    local map = ask_ip_by_host[self.config.name]
    local ip = map and map[host .. ":" .. tostring(port)]
    if ip and ip ~= host then
        return { { ip = ip, port = port }, { ip = host, port = port } }
    end
    return { { ip = host, port = port } }
end


local function handle_command_with_retry(self, target_ip, target_port, asking, cmd, key, ...)
    local config = self.config

    -- key will be passed to resty.redis
    local slot = redis_slot(normalize_key(key))

    local magic_random_seed = generate_magic_seed(self)
    local loop_counter = config.max_redirection or DEFAULT_MAX_REDIRECTION

    -- `asking` says that the next attempt sends ASKING, and a MOVED clears it.
    -- `followed_ask` says that this call came from an ASK and never changes: when the
    -- target answers MOVED and the source answers ASK again, a second ASK must end the
    -- request instead of recursing for ever.
    local followed_ask = asking

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
            slave = false

            -- A hostname cluster names the target with a hostname. The slot map holds
            -- its IP, and the IP does not suffer from a stale DNS cache. Only the
            -- connect falls back: the command is sent once.
            local targets = ask_targets(self, target_ip, target_port)
            for i = 1, #targets do
                ip, port = targets[i].ip, targets[i].port
                ok, connerr = connect_with_pool(redis_client, ip, port, self.config)
                if ok then break end
            end
        else
            -- Redis 7: try IP first and then hostname as IP does not suffer from stale DNS cache
            local tries = redis7_with_host[self.config.name] and 2 or 1
            for i = 1, tries do
                ip, port, slave, err = pick_node(self, serv_list, slot, magic_random_seed, i)
                if err then
                    ngx_log(NGX_ERR, "pickup node failed, will return failed for this request, meanwhile refreshing slotcache ", err)
                    self:refresh_slots()
                    return nil, err
                end

                first_ip = first_ip or ip
                ok, connerr = connect_with_pool(redis_client, ip, port, self.config)
                -- BW edit: the hostname names the same node; do not pay a second timeout.
                if ok or connerr == "timeout" or connerr == "node marked down" then break end
            end
        end

        if ok then
            local _, auth_err = check_auth_with_retry(self, redis_client)
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
                if string_sub(err, 1, 5) == "MOVED" or has_moved_signal(res) then
                    ngx_log(NGX_DEBUG, "find MOVED signal, trigger retry for normal commands, cmd:", cmd, " key:", key)
                    -- if retry with moved, we will not asking to specific ip:port anymore
                    target_ip = nil
                    target_port = nil
                    asking = false
                    local moved_ip, moved_port = parse_endpoint(string.match(err, "^MOVED %d+ (.+)$") or "")
                    if socket_host(moved_ip) == socket_host(ip) and moved_port == tostring(port) then
                        ngx_log(NGX_DEBUG, "nested moved redirection detected, refreshing slots ...")
                    end
                    redis_client:close()
                    self:refresh_slots()
                    need_to_retry = true

                elseif string_sub(err, 1, 3) == "ASK" then
                    ngx_log(NGX_DEBUG, "handle asking for normal commands, cmd:", cmd, " key:", key)
                    if followed_ask then
                        -- Should not happen after asking target ip:port and still return ask, if so, return error.
                        redis_client:close()
                        self:refresh_slots()
                        return nil, "nested asking redirection occurred, client cannot retry"
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
            -- BW edit: retry only when the refresh moved the slot away from the failed node.
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
        local node = master.ip .. ":" .. tostring(master.port)
        local ok, err = connect_with_pool(redis_client, master.ip, master.port, self.config)
        if ok then
            local _, auth_err = check_auth_with_retry(self, redis_client)
            if auth_err then
                redis_client:close()
                err = auth_err

            else
                _, err = redis_client[cmd](redis_client, key, ...)
                release_connection(redis_client, self.config)
            end
        end
        if err then
            table_insert(errors, node .. " " .. tostring(err))
        end
    end

    if #errors > 0 then
        return nil, "failed on " .. #errors .. " master(s): " .. table_concat(errors, "; ")
    end
    return true, nil
end

-- A pipeline result holds { false, message } for a command that Redis rejected.
-- A string, or a string inside an array, is a value that a caller stored: it must
-- not be read as a redirect or a cluster failure, or a stored value could send the
-- client to another host.
local function pipeline_error(result)
    if type(result) == "table" and result[1] == false
       and type(result[2]) == "string" then
        return result[2]
    end
end


local function construct_final_pipeline_resp(self, node_res_map, node_req_map)
    --construct final result with origin index
    local finalret = {}
    for k, v in pairs(node_res_map) do
        local reqs = node_req_map[k].reqs
        local res = v
        local need_to_fetch_slots = true
        for i = 1, #reqs do
            -- Read a redirect from the error reply only. A value in the reply is
            -- caller data, not a signal.
            local reply_err = pipeline_error(res[i])
            local ask_host, ask_port = parse_ask_signal(reply_err)
            if ask_host ~= nil and ask_port ~= nil then
                ngx_log(NGX_DEBUG, "handle ask signal for cmd:", reqs[i]["cmd"], " key:", reqs[i]["key"], " target host:", ask_host, " target port:", ask_port)
                local askres, err = handle_command_with_retry(self, ask_host, ask_port, true, reqs[i]["cmd"], reqs[i]["key"], unpack(reqs[i]["args"]))
                if err then
                    return nil, err
                else
                    finalret[reqs[i].origin_index] = askres
                end
            elseif has_moved_signal(reply_err) then
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
        local reply_err = pipeline_error(res[i])
        if reply_err and string_sub(reply_err, 1, 11) == "CLUSTERDOWN" then
            ngx_log(NGX_INFO, reply_err)
            return true
        end
    end
    return false
end


function _M.init_pipeline(self)
    self._reqs = {}
end


-- Send pre-built requests to the nodes that own their keys. Return the results in the
-- order of `reqs`. This function does not touch `self._reqs`, so a caller can use it
-- while another coroutine uses the same instance.
local function run_requests(self, reqs)
    local config = self.config

    local slots = slot_cache[config.name]
    if slots == nil then
        self:refresh_slots()
        return nil, "not slots information present, nginx might have never successfully executed cluster(\"slots\")"
    end

    local node_res_map = {}
    local node_req_map = {}

    --construct req to real node mapping
    for i = 1, #reqs do
        -- Because we will forward req to different nodes, so the result will not be the origin order,
        -- we need to record the original index and finally we can construct the result with origin order
        reqs[i].origin_index = i
        local key = reqs[i].key
        -- commit_pipeline builds its requests without a slot, so keep the lookup
        -- for that path.
        local slot = reqs[i].slot or redis_slot(normalize_key(key))
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
        ins_req[#ins_req + 1] = reqs[i]
    end

    -- We must empty local reference to slots cache, otherwise there will be memory issue while
    -- coroutine swich happens(eg. ngx.sleep, cosocket), very important!
    slots = nil -- luacheck: ignore

    local magic_random_seed = generate_magic_seed(self)

    for k, v in pairs(node_req_map) do
        local node_reqs = v.reqs

        local ip, port, slave
        local redis_client
        local ok, errors = nil, {}
        -- Redis 7: try IP first and then hostname as IP does not suffer from stale DNS cache
        local tries = redis7_with_host[self.config.name] and 2 or 1
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
            ok, err = connect_with_pool(redis_client, ip, port, self.config)
            if ok then break end
            table_insert(errors, ip .. ":" .. port .. " " .. err)
        end
        if not ok then
            self:refresh_slots()
            return nil, "failed to connect, err: " .. table_concat(errors, ",")
        end

        local _, auth_err = check_auth_with_retry(self, redis_client)
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
        for i = 1, #node_reqs do
            local req = node_reqs[i]
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


local function group_keys_by_slot(keys)
    local groups = {}
    local order = {}

    for i = 1, #keys do
        local slot = redis_slot(normalize_key(keys[i]))
        local group = groups[slot]
        if not group then
            group = new_tab(2, 0)
            groups[slot] = group
            order[#order + 1] = slot
        end
        group[#group + 1] = { index = i, key = keys[i] }
    end

    return order, groups
end


-- Build one request for each slot. Each request holds the first key of the slot
-- and the remaining keys of that slot.
local function build_slot_requests(cmd, order, groups)
    local reqs = new_tab(#order, 0)

    for i = 1, #order do
        local slot = order[i]
        local group = groups[slot]
        local args = new_tab(#group - 1, 0)
        for j = 2, #group do
            args[j - 1] = group[j].key
        end
        -- The slot is known here. Carrying it spares run_requests a second hash
        -- tag parse and CRC16 pass over the same key.
        reqs[i] = { cmd = cmd, key = group[1].key, args = args, slot = slot }
    end

    return reqs
end


-- True when all keys land in one slot. Check before grouping: the common case
-- is a batch of related keys, and grouping builds a record for every key.
local function keys_share_one_slot(keys)
    if #keys < 2 then
        return true
    end

    local slot = redis_slot(normalize_key(keys[1]))
    for i = 2, #keys do
        if redis_slot(normalize_key(keys[i])) ~= slot then
            return false
        end
    end

    return true
end


-- MGET-like commands: the reply is one value for each key, in the order of the
-- keys. Send one part for each slot, then put the values back in that order.
local function split_array_command(self, cmd, keys)
    if keys_share_one_slot(keys) then
        return handle_command_with_retry(self, nil, nil, false, cmd, unpack(keys))
    end

    local order, groups = group_keys_by_slot(keys)

    ngx_log(NGX_DEBUG, "split ", cmd, ": ", #keys, " keys in ", #order, " slots")

    local results, err = run_requests(self, build_slot_requests(cmd, order, groups))
    if not results then
        return nil, err
    end

    local values = new_tab(#keys, 0)
    for i = 1, #order do
        local group = groups[order[i]]
        local part = results[i]
        local part_err = pipeline_error(part)
        if part_err then
            return nil, cmd .. " failed for slot " .. order[i] .. ": " .. tostring(part_err)
        end

        if type(part) ~= "table" then
            return nil, "unexpected " .. cmd .. " reply for slot " .. order[i]
        end

        for j = 1, #group do
            values[group[j].index] = part[j]
        end
    end

    return values
end


-- DEL-like commands: the reply is a count. Send one part for each slot and add
-- the counts.
local function split_sum_command(self, cmd, keys)
    if keys_share_one_slot(keys) then
        return handle_command_with_retry(self, nil, nil, false, cmd, unpack(keys))
    end

    local order, groups = group_keys_by_slot(keys)

    ngx_log(NGX_DEBUG, "split ", cmd, ": ", #keys, " keys in ", #order, " slots")

    local results, err = run_requests(self, build_slot_requests(cmd, order, groups))
    if not results then
        return nil, err
    end

    local total = 0
    for i = 1, #order do
        local count = results[i]
        local count_err = pipeline_error(count)
        if count_err then
            return nil, cmd .. " failed for slot " .. order[i] .. ": " .. tostring(count_err)
        end

        if type(count) ~= "number" then
            return nil, "unexpected " .. cmd .. " reply for slot " .. order[i]
        end

        total = total + count
    end

    return total
end


-- Validate the arguments and return the keys that take part in the slot check.
-- A nil argument is an error: `{ ... }` truncates at the first hole, so a length
-- check on the table cannot see it.
local function collect_command_keys(cmd, spec, key, ...)
    local rest = select("#", ...)
    local nargs = key == nil and rest or rest + 1
    local args = { key, ... }
    local step = spec.keys == "stride2" and 2 or 1

    if spec.args then
        if nargs ~= spec.args then
            return nil, "wrong number of arguments for '" .. cmd .. "' command"
        end
    elseif nargs == 0 or nargs % step ~= 0 then
        return nil, "wrong number of arguments for '" .. cmd .. "' command"
    end
    for i = 1, nargs do
        if args[i] == nil then
            return nil, "nil argument for '" .. cmd .. "' command"
        end
    end

    if spec.keys == "stride2" then
        local keys = new_tab(math.ceil(nargs / 2), 0)
        for i = 1, nargs, 2 do
            keys[#keys + 1] = args[i]
        end

        return keys
    end

    -- SMOVE takes two keys and a member.
    if spec.keys == "first2" then
        local keys = new_tab(2, 0)
        keys[1] = args[1]
        keys[2] = args[2]

        return keys
    end

    return args
end


-- A command that cannot be split only works when all of its keys share a slot.
local function check_keys_in_one_slot(cmd, keys)
    if keys_share_one_slot(keys) then
        return true
    end

    return nil, "command '" .. cmd .. "' needs all keys in one slot; " ..
                "use a hash tag or split the call"
end


-- A cluster-wide SCAN uses a cursor with four parts: the index of the master to
-- visit, the number of masters seen when the iteration started, a fingerprint of
-- that master list, and the cursor of that master. "0" means that the whole
-- iteration is complete.
local SCAN_CURSOR_PATTERN = "^(%d+):(%d+):(%d+):(%d+)$"

-- One scan_all call stops when it reaches the key budget or the round-trip cap,
-- whichever comes first, so a sparse MATCH cannot scan the whole keyspace.
local SCAN_ALL_DEFAULT_COUNT = 100
local SCAN_ALL_MAX_ROUNDS = 16


local function scan_master_list(self)
    local list = master_nodes[self.config.name .. "master_list"]
    if not list or #list == 0 then
        local ok, err = self:init_slots()
        if not ok then
            return nil, err
        end

        list = master_nodes[self.config.name .. "master_list"]
        if not list or #list == 0 then
            return nil, "no master nodes in the slot cache"
        end
    end

    -- One master can own several slot ranges, so the list can hold duplicates.
    local seen = {}
    local masters = new_tab(#list, 0)
    for i = 1, #list do
        local node = list[i]
        local id = tostring(node.ip) .. ":" .. tostring(node.port)
        if not seen[id] then
            seen[id] = true
            masters[#masters + 1] = node
        end
    end

    -- Sort by address. The index in a cursor keeps its meaning when CLUSTER SLOTS
    -- returns the same nodes in a different order.
    table.sort(masters, function(a, b)
        local ka = tostring(a.ip) .. ":" .. tostring(a.port)
        local kb = tostring(b.ip) .. ":" .. tostring(b.port)
        return ka < kb
    end)

    return masters
end


-- A fingerprint of the sorted master list. The cursor carries it, so a changed
-- set of masters with the same count is detected as well.
local function scan_master_fingerprint(masters)
    local ids = new_tab(#masters, 0)
    for i = 1, #masters do
        ids[i] = tostring(masters[i].ip) .. ":" .. tostring(masters[i].port)
    end

    return ngx.crc32_long(table_concat(ids, ","))
end


-- Refresh from the scan path. A plain command must refresh at once, or recovery
-- waits for the window; a scan runs on a timer, so one walk per window is enough.
local function scan_refresh_slots(self)
    ngx.update_time()
    local now = ngx.now()
    local last = refresh_failed_at[self.config.name]
    if last and now - last < SCAN_REFRESH_BACKOFF then
        return nil, "slot refresh is in backoff, retry later"
    end

    return self:refresh_slots()
end


-- SCAN on one master. This path cannot use handle_command_with_retry, because
-- that function uses the cursor as the routing key.
local function scan_one_master(self, master, cursor, ...)
    local config = self.config
    local redis_client = redis:new()
    redis_client:set_timeouts(config.connect_timeout or DEFAULT_CONNECTION_TIMEOUT,
                              config.send_timeout or DEFAULT_SEND_TIMEOUT,
                              config.read_timeout or DEFAULT_READ_TIMEOUT)

    local ok, err = connect_with_pool(redis_client, master.ip, master.port, config)
    if not ok then
        -- The cached master list can still name a node that failed over. Every
        -- other command path refreshes the slot cache on a connection error.
        scan_refresh_slots(self)
        return nil, "failed to connect to " .. tostring(master.ip) .. ":" ..
                    tostring(master.port) .. ": " .. tostring(err)
    end

    local _, auth_err = check_auth_with_retry(self, redis_client)
    if auth_err then
        redis_client:close()
        return nil, auth_err
    end

    local res, scan_err = redis_client:scan(cursor, ...)
    if not res then
        -- `nil` is a socket or connection error. `false` is a reply from Redis: a
        -- cluster level error still means the topology may be stale, but a
        -- rejected command does not justify a walk over the address list.
        if res == nil or is_cluster_level_error(scan_err) then
            redis_client:close()
            scan_refresh_slots(self)
        else
            -- The connection answered, so it is healthy. Return it to the pool.
            release_connection(redis_client, config)
        end

        return nil, scan_err
    end

    release_connection(redis_client, config)

    return res
end


-- Return the COUNT option of SCAN, so one call does not return the keys of many
-- masters at the same time. The options are pairs of a keyword and a value, so
-- walk them in pairs: a MATCH value that reads "COUNT" is a value, not a keyword.
-- An unusable COUNT is an error: a silent fall back to the default page size
-- hides a caller mistake.
local function scan_count(...)
    local total = select("#", ...)
    local i = 1

    while i + 1 <= total do
        local option = select(i, ...)
        if type(option) ~= "string" then
            return nil
        end

        local value = select(i + 1, ...)
        if string.upper(option) == "COUNT" then
            local count = tonumber(value)
            if not count then
                return nil, "COUNT needs a number, got " .. tostring(value)
            end

            return count
        end

        i = i + 2
    end
end


local function _do_cmd(self, raw_cmd, key, ...)
    -- Redis takes a command name in any case, and the metatable builds a method
    -- for any field name, so red:DEL(...) reaches here too. The tables below
    -- hold lower case names: normalize once, or an upper case call skips the
    -- slot check, the split and the blocklist.
    local cmd = string.lower(raw_cmd)

    if cluster_invalid_cmds[cmd] == true then
        return nil, "command not supported"
    end

    local spec = multi_key_cmds[cmd]
    local keys

    if spec then
        local kerr
        keys, kerr = collect_command_keys(cmd, spec, key, ...)
        if not keys then
            return nil, kerr
        end
    end

    local _reqs = rawget(self, "_reqs")
    if _reqs then
        if spec and not check_keys_in_one_slot(cmd, keys) then
            return nil, "command '" .. cmd .. "' needs one slot inside a pipeline; " ..
                        "call it directly or use a hash tag"
        end

        local args = { ... }
        local t = { cmd = cmd, key = key, args = args }
        table_insert(_reqs, t)
        return
    end

    if spec then
        if spec.split then
            if spec.combine == "array" then
                return split_array_command(self, cmd, keys)
            end

            return split_sum_command(self, cmd, keys)
        end

        local ok, err = check_keys_in_one_slot(cmd, keys)
        if not ok then
            return nil, err
        end
    end

    if cmds_for_all_master[cmd] then
        return _do_cmd_master(self, cmd, key, ...)
    end

    local res, err = handle_command_with_retry(self, nil, nil, false, cmd, key, ...)
    return res, err
end


function _M.commit_pipeline(self)
    local _reqs = rawget(self, "_reqs")

    if not _reqs or #_reqs == 0 then return nil, "no pipeline"
    end

    self._reqs = nil

    return run_requests(self, _reqs)
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


-- BW edit: permit multi-key EVAL only when every key hashes to one slot.
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

--- Scan every master of the cluster.
-- Pass the same options on every call, as with the Redis SCAN command. The
-- result has the same shape as the single-node `scan`: `{ cursor, keys }`.
--
-- One call is bounded: it returns after `COUNT` keys (default 100) or after 16
-- SCAN round trips, whichever comes first. Call again until the cursor is "0".
-- @tparam string|number cursor The cursor of the previous call, or "0" to start.
-- @treturn table|nil `{ cursor, keys }`. `cursor` is `"0"` at the end.
-- @treturn string|nil The error message. On a failure the first value is nil.
function _M.scan_all(self, cursor, ...)
    local masters, err = scan_master_list(self)
    if not masters then
        return nil, err
    end

    local total = #masters
    local fingerprint = scan_master_fingerprint(masters)
    local index, node_cursor

    if cursor == "0" or cursor == 0 then
        index, node_cursor = 1, "0"
    else
        local i, seen_total, seen_fingerprint, node =
            string.match(tostring(cursor), SCAN_CURSOR_PATTERN)
        if not i then
            return nil, "invalid scan cursor: " .. tostring(cursor)
        end

        i, seen_total = tonumber(i), tonumber(seen_total)
        -- The pattern captures the fingerprint as a string; the current one is a number.
        if seen_total ~= total or seen_fingerprint ~= tostring(fingerprint) then
            return nil, "scan cursor is stale: the set of masters changed; " ..
                       "restart with cursor 0"
        end

        if i < 1 or i > total then
            return nil, "invalid scan cursor: " .. tostring(cursor)
        end

        index, node_cursor = i, node
    end

    local budget, budget_err = scan_count(...)
    if budget_err then
        return nil, budget_err
    end
    budget = budget or SCAN_ALL_DEFAULT_COUNT

    local keys = {}
    local rounds = 0

    while index <= total do
        rounds = rounds + 1
        local res, scan_err = scan_one_master(self, masters[index], node_cursor, ...)
        if not res then
            return nil, scan_err
        end

        node_cursor = tostring(res[1])
        local page = res[2] or {}
        for i = 1, #page do
            keys[#keys + 1] = page[i]
        end

        if node_cursor == "0" then
            index = index + 1
            node_cursor = "0"
        end

        if #keys >= budget or rounds >= SCAN_ALL_MAX_ROUNDS then
            break
        end
    end

    if index > total then
        return { "0", keys }, nil
    end

    return { index .. ":" .. total .. ":" .. fingerprint .. ":" .. node_cursor, keys }, nil
end


--- The library returns each connection to the pool after its command.
-- This method exists so that a caller can use one code path for a single-node
-- client and a cluster client.
function _M.set_keepalive(self)
    ngx_log(NGX_DEBUG, "set_keepalive() is a no-op on a cluster client")
    return 1
end


--- Drop a pipeline that the caller started and abandoned.
-- A multi-key command that spans slots is rejected when it is queued, so it does
-- not add a request. Check the return value of every queued call: `commit_pipeline`
-- returns one result for each request that was queued.
-- Pooled connections stay open: the library releases each connection after its
-- command.
function _M.close(self)
    ngx_log(NGX_DEBUG, "close() does not close pooled cluster connections")
    if rawget(self, "_reqs") then
        self._reqs = nil
    end

    return 1
end


--- Return the number of times the current connection was reused.
-- A cluster client keeps one pool for each node, so it cannot answer this for a
-- single connection. Zero tells the caller not to skip the first command.
function _M.get_reused_times(self)
    return 0
end


--- Convert a flat array of field and value pairs to a table.
-- resty.redis provides this helper. The cluster client needs its own copy,
-- because it does not inherit from resty.redis.
function _M.array_to_hash(self, t)
    local n = #t
    local h = new_tab(0, n / 2)
    for i = 1, n, 2 do
        h[t[i]] = t[i + 1]
    end

    return h
end


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
            -- A command name is matched without regard to case, so EVAL must take
            -- this path too. _do_eval_cmd and _do_cmd compare the lower case name.
            local lower = string.lower(cmd)
            if lower == "eval" or lower == "evalsha" then
                return _do_eval_cmd(self, lower, ...)
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
