# resty-redis-cluster
Openresty lua client for redis cluster.

### Description

This fork of [steve0511/resty-redis-cluster](https://github.com/steve0511/resty-redis-cluster) includes a few bugfixes and improvements.

### Why we build this client?
Openresty has no official client which can support redis cluster. (We could see discussion at https://github.com/openresty/lua-resty-redis/issues/43). Also, looking around other 3rd party openresty redis cluster client , we do't find one can completely support redis cluster features as our project requirement.

Resty-redis-cluster is a new build openresty module which can currently support most of redis-cluster features.

While building the client, thanks for https://github.com/cuiweixie/lua-resty-redis-cluster which gave us some good reference.

### feature list
1. resty-redis-cluster will cache slot->redis node mapping relationship, and support to calculate slot of key by CRC16, then access data by the cached mapping. The way we calculate CRC16 and caching is somewhat similar with https://github.com/cuiweixie/lua-resty-redis-cluster.

2. Support usual redis cluster access and most command

3. Support pipe-line operation. in case key is seperated in multiple nodes, resty-redis-cluster will organize the slot which in same target nodes into groups, then commit them with several pipeline group.

4. Support hashtag. Just give your key like name{tag}

5. Support read from slave node by readonly mode, both usual command and pipeline. While enable slave node read, resty-redis-cluster will randomly pickup a node which is mapped to the request key, no matter it's master or slave.

6. Support online resharding of redis cluster(both for usual command and pipeline. resty-redis-cluster will handle the #MOVED signal by re-cache the slot mapping and retrying. resty-redis-cluster will handle the #ASK signal by retrying with asking to redirection target nodes

7. Support error handling for the different failure scenario of redis cluster. (etc.Singel slave, master fail, cluster down)

8. fix some critical issues of https://github.com/cuiweixie/lua-resty-redis-cluster.
   1) memory leak issues while there is high throughput. Socket request will cause the suspend and swith of coroutine, so there would be multiple requests still have reference to the big slot mapping cache. This will cause LUAJIT VM crashed.

   2) we must refresh slot cache mapping in case any redis nodes connection failure, otherwise we will not get the latest slot cache mapping and always get failure. Refer to Jedis, same behaviour to referesh cache mapping while any unknown connection issue.

   3) We must handle ASK redirection in usual/MOVED commands

   4) Pipeline must also handle MOVED signal with refreshing slot cache mapping and retry.

9.  Support authentication.

10. Support eval command with zero or one key

11. Also verified working properly in AWS elasticache.

12. Allows rolling replacement of redis cluster.
    Example) Redis Cluster with IPs 10.0.0.2, .3 and .4 is present. New nodes are introduced at IPs 10.0.0.5, .6 and .7. Slots are relocated fom node .2, .3 and .4 to .5, .6, and .7. The initial nodes can now be removed without downtime in nginx, since the initial configuration is not used anymore.

### installation

1. please add xmodem.lua and rediscluster.lua at lualib, Also please add library:lua-resty-redis and lua-resty-lock

   nginx.conf like:

   lua_package_path "/path/lualib/?.lua;";

2. nginx.conf add config:

   lua_shared_dict redis_cluster_slot_locks 100k;

3. or install by luarock, link: https://luarocks.org/modules/steve0511/resty-redis-cluster

### Sample usage

1. Use normal commands

```lua
local config = {
    dict_name = "test_locks",               --shared dictionary name for locks, if default value is not used
    refresh_lock_key = "refresh_lock",      --shared dictionary name prefix for lock of each worker, if default value is not used
    name = "testCluster",                   --rediscluster name
    serv_list = {                           --redis cluster node list(host and port),
        { ip = "127.0.0.1", port = 7001 },
        { ip = "127.0.0.1", port = 7002 },
        { ip = "127.0.0.1", port = 7003 },
        { ip = "127.0.0.1", port = 7004 },
        { ip = "127.0.0.1", port = 7005 },
        { ip = "127.0.0.1", port = 7006 }
    },
    keepalive_timeout = 60000,              --redis connection pool idle timeout
    keepalive_cons = 1000,                  --redis connection pool size
    connect_timeout = 1000,                 --timeout while connecting
    lock_timeout = 5,                       --timeout acquiring resty lock
    max_redirection = 5,                    --maximum retry attempts for redirection
    max_connection_attempts = 1             --maximum retry attempts for connection
}

local redis_cluster = require "rediscluster"
local red_c = redis_cluster:new(config)

local v, err = red_c:get("name")
if err then
    ngx.log(ngx.ERR, "err: ", err)
else
    ngx.say(v)
end
```

2. Authentication

```lua
local config = {
    dict_name = "test_locks",               --shared dictionary name for locks, if default value is not used
    refresh_lock_key = "refresh_lock",      --shared dictionary name prefix for lock of each worker, if default value is not used
    name = "testCluster",                   --rediscluster name
    serv_list = {                           --redis cluster node list(host and port),
        { ip = "127.0.0.1", port = 7001 },
        { ip = "127.0.0.1", port = 7002 },
        { ip = "127.0.0.1", port = 7003 },
        { ip = "127.0.0.1", port = 7004 },
        { ip = "127.0.0.1", port = 7005 },
        { ip = "127.0.0.1", port = 7006 }
    },
    keepalive_timeout = 60000,              --redis connection pool idle timeout
    keepalive_cons = 1000,                  --redis connection pool size
    connect_timeout = 1000,                 --timeout while connecting
    read_timeout = 1000,                    --timeout while reading
    send_timeout = 1000,                    --timeout while sending
    lock_timeout = 5,                       --timeout acquiring resty lock
    max_redirection = 5,                    --maximum retry attempts for redirection,
    max_connection_attempts = 1,            --maximum retry attempts for connection
    auth = "pass"                           --set password while setting auth
}

local redis_cluster = require "rediscluster"
local red_c = redis_cluster:new(config)

local v, err = red_c:get("name")
if err then
    ngx.log(ngx.ERR, "err: ", err)
else
    ngx.say(v)
end
```

`auth_config_reconfigurer` is optional. The library calls it when Redis rejects the credentials,
for example when the error contains `WRONGPASS` or `invalid password`. It does not call it for a
dead connection or a socket error, because a new secret cannot fix those. When the configuration
has no credential, the library does not call it either. When given, it **must** update
`config.auth`, `config.username` or `config.password` and return `true`. The library then repeats
AUTH once on the same connection. Any other return value, including `false`, `nil`, `0` and `""`,
keeps the original AUTH error. AUTH fails before the library sends a command, so no command runs
twice.

To disable the hook, pass `nil`, `false` or `ngx.null`. Any other non-function value makes `new()`
return an error.

The function runs once for each rejected connection. Do not put credentials in the error message;
the library logs that message.

Keep the caller side in mind:

- **Update both configurations.** `new()` copies `username` and `password` from the source
  configuration. The hook must update that source and `self.config`. When it updates only
  `self.config`, every new request fails AUTH once, calls the hook again, and does not pool the
  connection.
- **Keep the hook short.** The first `new()` and a slot refresh hold a lock while the hook runs.
  Other requests in the same worker wait for `lock_timeout`, which is 5 seconds by default. Other
  workers do not wait for the initial slot fetch. Each worker fetches the slots once, so N workers
  make N slot queries at cold start.
- **Throttle the reads.** The library does not rate-limit the hook. Add a cooldown, or the secret
  store sees one read for each rejected connection.
- **Do not send commands from the hook.** A command on the same instance can fail AUTH again, and
  the hook runs again.
- **Update `auth` when you set it.** `auth` wins over `username` and `password`.

When the function updates the credentials, the library does not return that connection to the pool
named after the previous password. The next connection uses the new name. The library changes
`config.base_pool` only; it never changes the `connect_opts` values that you set.

The pool name contains the secret that the library sends: `auth` for the legacy option, or
`username` and `password` for Redis 6. When you set `connect_opts.pool`, you own the pool name and
the isolation between credentials.

```lua
local config = {
    -- ...
    auth_config_reconfigurer = function(self, err)
        -- Read the current credentials from your store, then update both places.
        local password = read_password()
        if not password then
            return false
        end

        self.config.password = password   -- this client
        config.password = password        -- the source that the next new() copies
        return true
    end,
}
```

3. Use pipeline

```lua
local cjson = require "cjson"

local config = {
    dict_name = "test_locks",               --shared dictionary name for locks, if default value is not used
    refresh_lock_key = "refresh_lock",      --shared dictionary name prefix for lock of each worker, if default value is not used
    name = "testCluster",
    serv_list = {
        { ip = "127.0.0.1", port = 7001 },
        { ip = "127.0.0.1", port = 7002 },
        { ip = "127.0.0.1", port = 7003 },
        { ip = "127.0.0.1", port = 7004 },
        { ip = "127.0.0.1", port = 7005 },
        { ip = "127.0.0.1", port = 7006 }
    },
    keepalive_timeout = 60000,
    keepalive_cons = 1000,
    connect_timeout = 1000,
    read_timeout = 1000,
    send_timeout = 1000,
    lock_timeout = 5,
    max_redirection = 5,
    max_connection_attempts = 1
}

local redis_cluster = require "rediscluster"
local red_c = redis_cluster:new(config)


red_c:init_pipeline()
red_c:get("name")
red_c:get("name1")
red_c:get("name2")

local res, err = red_c:commit_pipeline()

if not res then
    ngx.log(ngx.ERR, "err: ", err)
else
    ngx.say(cjson.encode(res))
end
```

4. Enable slave node read

   Note: Currently enable_slave_read is only limited in pure read scenario.
   We don't support mixed read and write scenario(distingush read, write operation) in single config set with enable_slave_read now.
   If your scenario is mixed with write operation, please disable the option.

   Also, you can isolate pure read scenaro into another config set.

```lua
local cjson = require "cjson"

local config = {
    dict_name = "test_locks",               --shared dictionary name for locks, if default value is not used
    refresh_lock_key = "refresh_lock",      --shared dictionary name prefix for lock of each worker, if default value is not used
    name = "testCluster",
    enable_slave_read = true,
    serv_list = {
        { ip = "127.0.0.1", port = 7001 },
        { ip = "127.0.0.1", port = 7002 },
        { ip = "127.0.0.1", port = 7003 },
        { ip = "127.0.0.1", port = 7004 },
        { ip = "127.0.0.1", port = 7005 },
        { ip = "127.0.0.1", port = 7006 }
    },
    keepalive_timeout = 60000,
    keepalive_cons = 1000,
    connect_timeout = 1000,
    read_timeout = 1000,
    send_timeout = 1000,
    lock_timeout = 5,
    max_redirection = 5,
    max_connection_attempts = 1
}

local redis_cluster = require "rediscluster"
local red_c = redis_cluster:new(config)

local v, err = red_c:get("name")
if err then
    ngx.log(ngx.ERR, "err: ", err)
else
    ngx.say(v)
end
```

5. Hashtag

```lua
local cjson = require "cjson"

local config = {
    dict_name = "test_locks",               --shared dictionary name for locks, if default value is not used
    refresh_lock_key = "refresh_lock",      --shared dictionary name prefix for lock of each worker, if default value is not used
    name = "testCluster",
    enable_slave_read = true,
    serv_list = {
        { ip = "127.0.0.1", port = 7001 },
        { ip = "127.0.0.1", port = 7002 },
        { ip = "127.0.0.1", port = 7003 },
        { ip = "127.0.0.1", port = 7004 },
        { ip = "127.0.0.1", port = 7005 },
        { ip = "127.0.0.1", port = 7006 }
    },
    keepalive_timeout = 60000,
    keepalive_cons = 1000,
    connect_timeout = 1000,
    read_timeout = 1000,
    send_timeout = 1000,
    lock_timeout = 5,
    max_redirection = 5,
    max_connection_attempts = 1
}

local redis_cluster = require "rediscluster"
local red_c = redis_cluster:new(config)


red_c:init_pipeline()
red_c:get("item100:sub1{100}")
red_c:get("item100:sub2{100}")
red_c:get("item100:sub3{100}")

local res, err = red_c:commit_pipeline()

if not res then
    ngx.log(ngx.ERR, "err: ", err)
else
    ngx.say(cjson.encode(res))
end
```

6. eval

```lua
local config = {
    dict_name = "test_locks",               --shared dictionary name for locks, if default value is not used
    refresh_lock_key = "refresh_lock",      --shared dictionary name prefix for lock of each worker, if default value is not used
    name = "testCluster",                   --rediscluster name
    serv_list = {                           --redis cluster node list(host and port),
        { ip = "127.0.0.1", port = 7001 },
        { ip = "127.0.0.1", port = 7002 },
        { ip = "127.0.0.1", port = 7003 },
        { ip = "127.0.0.1", port = 7004 },
        { ip = "127.0.0.1", port = 7005 },
        { ip = "127.0.0.1", port = 7006 }
    },
    keepalive_timeout = 60000,              --redis connection pool idle timeout
    keepalive_cons = 1000,                  --redis connection pool size
    connect_timeout = 1000,                 --timeout while connecting
    read_timeout = 1000,                    --timeout while reading
    send_timeout = 1000,                    --timeout while sending
    lock_timeout = 5,                       --timeout acquiring resty lock
    max_redirection = 5,                    --maximum retry attempts for redirection
    max_connection_attempts = 1             --maximum retry attempts for connection
}

local redis_cluster = require "rediscluster"
local red_c = redis_cluster:new(config)
local step = 2
local v, err = red_c:eval("return redis.call('incrby',KEYS[1],ARGV[1])",1,"counter",step)
if err then
    ngx.log(ngx.ERR, "err: ", err)
else
    ngx.say(v)
end
```

7. Use SSL

   Note: `connect_opts` is optional config field that can be set and will be passed to underlying redis connect call.
   More information about these options can be found in [lua-resty-redis](https://github.com/openresty/lua-resty-redis#connect) documentation.

```lua
local config = {
    dict_name = "test_locks",               --shared dictionary name for locks, if default value is not used
    refresh_lock_key = "refresh_lock",      --shared dictionary name prefix for lock of each worker, if default value is not used
    name = "testCluster",                   --rediscluster name
    serv_list = {                           --redis cluster node list(host and port),
        { ip = "127.0.0.1", port = 7001 },
        { ip = "127.0.0.1", port = 7002 },
        { ip = "127.0.0.1", port = 7003 },
        { ip = "127.0.0.1", port = 7004 },
        { ip = "127.0.0.1", port = 7005 },
        { ip = "127.0.0.1", port = 7006 }
    },
    keepalive_timeout = 60000,              --redis connection pool idle timeout
    keepalive_cons = 1000,                  --redis connection pool size
    connect_timeout = 1000,                 --timeout while connecting
    lock_timeout = 5,                       --timeout acquiring resty lock
    max_redirection = 5,                    --maximum retry attempts for redirection
    max_connection_attempts = 1,            --maximum retry attempts for connection
    connect_opts = {
        ssl = true,
        ssl_verify = true,
        server_name = "test-cluster.redis.myhost.com",
        pool = "redis-cluster-connection-pool",
        pool_size = 20,
        backlog = 10
    }
}

local redis_cluster = require "rediscluster"
local red_c = redis_cluster:new(config)

local v, err = red_c:get("name")
if err then
    ngx.log(ngx.ERR, "err: ", err)
else
    ngx.say(v)
end
```

### Flush commands

`flushall` and `flushdb` run on every master. When a master fails, the command continues on the
other masters and returns an error that lists the failed nodes. Both commands are idempotent, so a
later call can finish the work.

### Limitation

1. Doesn't support MSET, MGET operations yet

2. Doesn't support transactions operations: MULTI DISCARD EXEC WATCH

3. Doesn't support pub sub. Actually redis cluster didn't check slot for pub sub commands, so using normal resty redis client to conenct with specific node in a cluster still works.

4. Limitation only for turn on enable slave read: If we need to discover new slave node(but without adding new master), must retrigger new slot mapping cache refresh, otherwise slot mapping still record the last version of node tables.(easiest way is rebooting nginx nodes)

5. Limitation only for turn on enable slave read: If slave -> master link is down(maybe still under sync and recovery), resty-redis-cluster will not filter these nodes out. Thus, read from slave may return unexpected response. Suggest always catch the response parsing exception while enable slave read.
   This is because client depends on cluster slots command.

6. An instance is not reentrant for pipelines. `init_pipeline()` stores the queue on the instance, and every command on that instance joins the queue until `commit_pipeline()` or `cancel_pipeline()`. Do not let two coroutines start a pipeline on the same instance. Simple commands are safe to run from several coroutines on one instance while no pipeline is active on it.

7. The client reads the IP of a node from `CLUSTER SLOTS`, which lists only the nodes that hold a slot. When a slot moves to a new node that holds no slot yet, the client reaches the ASK target by hostname only.

8. The client reads an `ASK` or `MOVED` address as `host:port`. An IPv6 literal such as `[::1]:6379` does not parse.

### Compatibilty

Currently, this library is tested with Redis `6.2` and `7.2`. CI runs the same suite on both versions. It leaves out only `t/z-recover.t`, which starts its own fixture.

### Changelog

#### Unreleased

1. TBD

#### 1.7.0

1. Add the `auth_config_reconfigurer` option. When Redis rejects AUTH, the library calls it and repeats AUTH once on the same connection after it updates the credentials.
2. Return normal connections to the pool. A connection that replaced its credentials is closed instead. A caller pool name is the exception: when you set `connect_opts.pool`, you own the name and the isolation between credentials.
3. Include the `auth` value in the pool name. A configuration that uses the legacy `auth` option gets a new pool name after the upgrade, so its idle connections are not reused once. The `config.base_pool` value changes with it.
4. Follow ASK and MOVED redirects for a single command, and for a pipeline that receives ASK.
5. Run `flushall` and `flushdb` on every master and list the failed nodes in the error.
6. Remove the pool name from the DEBUG log. The name contains a hash of the credential.
7. Use one slot fetch lock for each worker. A slow auth hook in one worker no longer blocks the others.

#### 1.6.1

1. Support Redis/Valkey versions reported as `x.y` (without a patch component), e.g. AWS ElastiCache Serverless Valkey, and accept Redis 8.x (warn only on `>= 9.0`).

#### 1.6.0

1. Performance optimization on the slots data structure and logging
2. Fixed a (breaking change) issue that the refresh_slot's lock timeout was implicitly changed to 0 in 1.5.5.

#### 1.5.7

1. Add `force_auth` flag to control whether to call `auth` after each `connect`.

#### 1.5.6

1. Set pool name before connect so that connetions won't be reused incorrectly.

#### 1.5.5

1. Currently, the timeout for acquiring a lock is fixed to `5s`.
   We add a new option `lock_timeout` to make it configurable.
2. The lock timeout parameter was incorrectly set to `time_out = 0`.
   We fix it to `timeout = 0`. This would improve perf as there is no
   need for everyone to refresh the slots.

   This is a breaking change when there is network issues and the clients
   tries to refresh the slot info. Before the fix, all clients will refresh
   once, and after the fix only one client is refreshing it.
3. Return detailed error message to downstream component (e.g. Kong Gateway)
   for better debuggability.

## Copyright and License

This module is licensed under the Apache License Version 2.0 .

Copyright (C) 2017, by steve.xu stevehui0511@gmail.com

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
