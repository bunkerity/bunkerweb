Name
====

lua-resty-redis - Lua redis client driver for the ngx_lua based on the cosocket API

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Description](#description)
* [Synopsis](#synopsis)
* [Methods](#methods)
    * [new](#new)
    * [connect](#connect)
    * [set_timeout](#set_timeout)
    * [set_timeouts](#set_timeouts)
    * [set_keepalive](#set_keepalive)
    * [get_reused_times](#get_reused_times)
    * [close](#close)
    * [init_pipeline](#init_pipeline)
    * [commit_pipeline](#commit_pipeline)
    * [cancel_pipeline](#cancel_pipeline)
    * [hmset](#hmset)
    * [array_to_hash](#array_to_hash)
    * [read_reply](#read_reply)
    * [add_commands](#add_commands)
* [Redis Authentication](#redis-authentication)
* [Redis Transactions](#redis-transactions)
* [Load Balancing and Failover](#load-balancing-and-failover)
* [Debugging](#debugging)
* [Automatic Error Logging](#automatic-error-logging)
* [Check List for Issues](#check-list-for-issues)
* [Limitations](#limitations)
* [Installation](#installation)
* [TODO](#todo)
* [Community](#community)
    * [English Mailing List](#english-mailing-list)
    * [Chinese Mailing List](#chinese-mailing-list)
* [Bugs and Patches](#bugs-and-patches)
* [Author](#author)
* [Copyright and License](#copyright-and-license)
* [See Also](#see-also)

Status
======

This library is considered production ready.

Description
===========

This Lua library is a Redis client driver for the ngx_lua nginx module:

https://github.com/openresty/lua-nginx-module/#readme

This Lua library takes advantage of ngx_lua's cosocket API, which ensures
100% nonblocking behavior.

Note that at least [ngx_lua 0.5.14](https://github.com/chaoslawful/lua-nginx-module/tags) or [OpenResty 1.2.1.14](http://openresty.org/#Download) is required.

Synopsis
========

```lua
    # you do not need the following line if you are using
    # the OpenResty bundle:
    lua_package_path "/path/to/lua-resty-redis/lib/?.lua;;";

    server {
        location /test {
            content_by_lua_block {
                local redis = require "resty.redis"
                local red = redis:new()

                red:set_timeouts(1000, 1000, 1000) -- 1 sec

                -- or connect to a unix domain socket file listened
                -- by a redis server:
                --     local ok, err = red:connect("unix:/path/to/redis.sock")

                local ok, err = red:connect("127.0.0.1", 6379)
                if not ok then
                    ngx.say("failed to connect: ", err)
                    return
                end

                ok, err = red:set("dog", "an animal")
                if not ok then
                    ngx.say("failed to set dog: ", err)
                    return
                end

                ngx.say("set result: ", ok)

                local res, err = red:get("dog")
                if not res then
                    ngx.say("failed to get dog: ", err)
                    return
                end

                if res == ngx.null then
                    ngx.say("dog not found.")
                    return
                end

                ngx.say("dog: ", res)

                red:init_pipeline()
                red:set("cat", "Marry")
                red:set("horse", "Bob")
                red:get("cat")
                red:get("horse")
                local results, err = red:commit_pipeline()
                if not results then
                    ngx.say("failed to commit the pipelined requests: ", err)
                    return
                end

                for i, res in ipairs(results) do
                    if type(res) == "table" then
                        if res[1] == false then
                            ngx.say("failed to run command ", i, ": ", res[2])
                        else
                            -- process the table value
                        end
                    else
                        -- process the scalar value
                    end
                end

                -- put it into the connection pool of size 100,
                -- with 10 seconds max idle time
                local ok, err = red:set_keepalive(10000, 100)
                if not ok then
                    ngx.say("failed to set keepalive: ", err)
                    return
                end

                -- or just close the connection right away:
                -- local ok, err = red:close()
                -- if not ok then
                --     ngx.say("failed to close: ", err)
                --     return
                -- end
            }
        }
    }
```

[Back to TOC](#table-of-contents)

Methods
=======

All of the Redis commands have their own methods with the same name except all in lower case.

You can find the complete list of Redis commands here:

http://redis.io/commands

You need to check out this Redis command reference to see what Redis command accepts what arguments.

The Redis command arguments can be directly fed into the corresponding method call. For example, the "GET" redis command accepts a single key argument, then you can just call the "get" method like this:

```lua
    local res, err = red:get("key")
```

Similarly, the "LRANGE" redis command accepts threee arguments, then you should call the "lrange" method like this:

```lua
    local res, err = red:lrange("nokey", 0, 1)
```

For example, "SET", "GET", "LRANGE", and "BLPOP" commands correspond to the methods "set", "get", "lrange", and "blpop".

Here are some more examples:

```lua
    -- HMGET myhash field1 field2 nofield
    local res, err = red:hmget("myhash", "field1", "field2", "nofield")
```

```lua
    -- HMSET myhash field1 "Hello" field2 "World"
    local res, err = red:hmset("myhash", "field1", "Hello", "field2", "World")
```

All these command methods returns a single result in success and `nil` otherwise. In case of errors or failures, it will also return a second value which is a string describing the error.

A Redis "status reply" results in a string typed return value with the "+" prefix stripped.

A Redis "integer reply" results in a Lua number typed return value.

A Redis "error reply" results in a `false` value *and* a string describing the error.

A non-nil Redis "bulk reply" results in a Lua string as the return value. A nil bulk reply results in a `ngx.null` return value.

A non-nil Redis "multi-bulk reply" results in a Lua table holding all the composing values (if any). If any of the composing value is a valid redis error value, then it will be a two element table `{false, err}`.

A nil multi-bulk reply returns in a `ngx.null` value.

See http://redis.io/topics/protocol for details regarding various Redis reply types.

In addition to all those redis command methods, the following methods are also provided:

[Back to TOC](#table-of-contents)

new
---
`syntax: red, err = redis:new()`

Creates a redis object. In case of failures, returns `nil` and a string describing the error.

[Back to TOC](#table-of-contents)

connect
-------
`syntax: ok, err = red:connect(host, port, options_table?)`

`syntax: ok, err = red:connect("unix:/path/to/unix.sock", options_table?)`

Attempts to connect to the remote host and port that the redis server is listening to or a local unix domain socket file listened by the redis server.

Before actually resolving the host name and connecting to the remote backend, this method will always look up the connection pool for matched idle connections created by previous calls of this method.

The optional `options_table` argument is a Lua table holding the following keys:

* `ssl`

    If set to true, then uses SSL to connect to redis (defaults to false).

* `ssl_verify`

    If set to true, then verifies the validity of the server SSL certificate (defaults to false). Note that you need to configure the lua_ssl_trusted_certificate to specify the CA (or server) certificate used by your redis server. You may also need to configure lua_ssl_verify_depth accordingly.

* `server_name`

    Specifies the server name for the new TLS extension Server Name Indication (SNI) when connecting over SSL.

* `pool`

    Specifies a custom name for the connection pool being used. If omitted, then the connection pool name will be generated from the string template `<host>:<port>` or `<unix-socket-path>`.

* `pool_size`

    Specifies the size of the connection pool. If omitted and no `backlog` option was provided, no pool will be created. If omitted but `backlog` was provided, the pool will be created with a default size equal to the value of the [lua_socket_pool_size](https://github.com/openresty/lua-nginx-module#lua_socket_pool_size) directive. The connection pool holds up to `pool_size` alive connections ready to be reused by subsequent calls to [connect](#connect), but note that there is no upper limit to the total number of opened connections outside of the pool. If you need to restrict the total number of opened connections, specify the `backlog` option. When the connection pool would exceed its size limit, the least recently used (kept-alive) connection already in the pool will be closed to make room for the current connection. Note that the cosocket connection pool is per Nginx worker process rather than per Nginx server instance, so the size limit specified here also applies to every single Nginx worker process. Also note that the size of the connection pool cannot be changed once it has been created. Note that at least [ngx_lua 0.10.14](https://github.com/openresty/lua-nginx-module/tags) is required to use this options.

* `backlog`

    If specified, this module will limit the total number of opened connections for this pool. No more connections than `pool_size` can be opened for this pool at any time. If the connection pool is full, subsequent connect operations will be queued into a queue equal to this option's value (the "backlog" queue). If the number of queued connect operations is equal to `backlog`, subsequent connect operations will fail and return nil plus the error string `"too many waiting connect operations"`. The queued connect operations will be resumed once the number of connections in the pool is less than `pool_size`. The queued connect operation will abort once they have been queued for more than `connect_timeout`, controlled by [set_timeout](#set_timeout), and will return nil plus the error string "timeout". Note that at least [ngx_lua 0.10.14](https://github.com/openresty/lua-nginx-module/tags) is required to use this options.

[Back to TOC](#table-of-contents)

set_timeout
-----------
`syntax: red:set_timeout(time)`

Sets the timeout (in ms) protection for subsequent operations, including the `connect` method.

Since version `v0.28` of this module, it is advised that
[set_timeouts](#set_timeouts) be used in favor of this method.

[Back to TOC](#table-of-contents)

set_timeouts
------------
`syntax: red:set_timeouts(connect_timeout, send_timeout, read_timeout)`

Respectively sets the connect, send, and read timeout thresholds (in ms), for
subsequent socket operations. Setting timeout thresholds with this method
offers more granularity than [set_timeout](#set_timeout). As such, it is
preferred to use [set_timeouts](#set_timeouts) over
[set_timeout](#set_timeout).

This method was added in the `v0.28` release.

[Back to TOC](#table-of-contents)

set_keepalive
-------------
`syntax: ok, err = red:set_keepalive(max_idle_timeout, pool_size)`

Puts the current Redis connection immediately into the ngx_lua cosocket connection pool.

You can specify the max idle timeout (in ms) when the connection is in the pool and the maximal size of the pool every nginx worker process.

In case of success, returns `1`. In case of errors, returns `nil` with a string describing the error.

Only call this method in the place you would have called the `close` method instead. Calling this method will immediately turn the current redis object into the `closed` state. Any subsequent operations other than `connect()` on the current object will return the `closed` error.

[Back to TOC](#table-of-contents)

get_reused_times
----------------
`syntax: times, err = red:get_reused_times()`

This method returns the (successfully) reused times for the current connection. In case of error, it returns `nil` and a string describing the error.

If the current connection does not come from the built-in connection pool, then this method always returns `0`, that is, the connection has never been reused (yet). If the connection comes from the connection pool, then the return value is always non-zero. So this method can also be used to determine if the current connection comes from the pool.

[Back to TOC](#table-of-contents)

close
-----
`syntax: ok, err = red:close()`

Closes the current redis connection and returns the status.

In case of success, returns `1`. In case of errors, returns `nil` with a string describing the error.

[Back to TOC](#table-of-contents)

init_pipeline
-------------
`syntax: red:init_pipeline()`

`syntax: red:init_pipeline(n)`

Enable the redis pipelining mode. All subsequent calls to Redis command methods will automatically get cached and will send to the server in one run when the `commit_pipeline` method is called or get cancelled by calling the `cancel_pipeline` method.

This method always succeeds.

If the redis object is already in the Redis pipelining mode, then calling this method will discard existing cached Redis queries.

The optional `n` argument specifies the (approximate) number of commands that are going to add to this pipeline, which can make things a little faster.

[Back to TOC](#table-of-contents)

commit_pipeline
---------------
`syntax: results, err = red:commit_pipeline()`

Quits the pipelining mode by committing all the cached Redis queries to the remote server in a single run. All the replies for these queries will be collected automatically and are returned as if a big multi-bulk reply at the highest level.

This method returns `nil` and a Lua string describing the error upon failures.

[Back to TOC](#table-of-contents)

cancel_pipeline
---------------
`syntax: red:cancel_pipeline()`

Quits the pipelining mode by discarding all existing cached Redis commands since the last call to the `init_pipeline` method.

This method always succeeds.

If the redis object is not in the Redis pipelining mode, then this method is a no-op.

[Back to TOC](#table-of-contents)

hmset
-----
`syntax: res, err = red:hmset(myhash, field1, value1, field2, value2, ...)`

`syntax: res, err = red:hmset(myhash, { field1 = value1, field2 = value2, ... })`

Special wrapper for the Redis "hmset" command.

When there are only three arguments (including the "red" object
itself), then the last argument must be a Lua table holding all the field/value pairs.

[Back to TOC](#table-of-contents)

array_to_hash
-------------
`syntax: hash = red:array_to_hash(array)`

Auxiliary function that converts an array-like Lua table into a hash-like table.

This method was first introduced in the `v0.11` release.

[Back to TOC](#table-of-contents)

read_reply
----------
`syntax: res, err = red:read_reply()`

Reading a reply from the redis server. This method is mostly useful for the [Redis Pub/Sub API](http://redis.io/topics/pubsub/), for example,

```lua
    local cjson = require "cjson"
    local redis = require "resty.redis"

    local red = redis:new()
    local red2 = redis:new()

    red:set_timeouts(1000, 1000, 1000) -- 1 sec
    red2:set_timeouts(1000, 1000, 1000) -- 1 sec

    local ok, err = red:connect("127.0.0.1", 6379)
    if not ok then
        ngx.say("1: failed to connect: ", err)
        return
    end

    ok, err = red2:connect("127.0.0.1", 6379)
    if not ok then
        ngx.say("2: failed to connect: ", err)
        return
    end

    local res, err = red:subscribe("dog")
    if not res then
        ngx.say("1: failed to subscribe: ", err)
        return
    end

    ngx.say("1: subscribe: ", cjson.encode(res))

    res, err = red2:publish("dog", "Hello")
    if not res then
        ngx.say("2: failed to publish: ", err)
        return
    end

    ngx.say("2: publish: ", cjson.encode(res))

    res, err = red:read_reply()
    if not res then
        ngx.say("1: failed to read reply: ", err)
        return
    end

    ngx.say("1: receive: ", cjson.encode(res))

    red:close()
    red2:close()
```

Running this example gives the output like this:

    1: subscribe: ["subscribe","dog",1]
    2: publish: 1
    1: receive: ["message","dog","Hello"]

The following class methods are provieded:

[Back to TOC](#table-of-contents)

add_commands
------------
`syntax: hash = redis.add_commands(cmd_name1, cmd_name2, ...)`

*WARNING* this method is now deprecated since we already do automatic Lua method generation
for any redis commands the user attempts to use and thus we no longer need this.

Adds new redis commands to the `resty.redis` class. Here is an example:

```lua
    local redis = require "resty.redis"

    redis.add_commands("foo", "bar")

    local red = redis:new()

    red:set_timeouts(1000, 1000, 1000) -- 1 sec

    local ok, err = red:connect("127.0.0.1", 6379)
    if not ok then
        ngx.say("failed to connect: ", err)
        return
    end

    local res, err = red:foo("a")
    if not res then
        ngx.say("failed to foo: ", err)
    end

    res, err = red:bar()
    if not res then
        ngx.say("failed to bar: ", err)
    end
```

[Back to TOC](#table-of-contents)

Redis Authentication
====================

Redis uses the `AUTH` command to do authentication: http://redis.io/commands/auth

There is nothing special for this command as compared to other Redis
commands like `GET` and `SET`. So one can just invoke the `auth` method on your `resty.redis` instance. Here is an example:

```lua
    local redis = require "resty.redis"
    local red = redis:new()

    red:set_timeouts(1000, 1000, 1000) -- 1 sec

    local ok, err = red:connect("127.0.0.1", 6379)
    if not ok then
        ngx.say("failed to connect: ", err)
        return
    end

    local res, err = red:auth("foobared")
    if not res then
        ngx.say("failed to authenticate: ", err)
        return
    end
```

where we assume that the Redis server is configured with the
password `foobared` in the `redis.conf` file:

    requirepass foobared

If the password specified is wrong, then the sample above will output the
following to the HTTP client:

    failed to authenticate: ERR invalid password

[Back to TOC](#table-of-contents)

Redis Transactions
==================

This library supports the [Redis transactions](http://redis.io/topics/transactions/). Here is an example:

```lua
    local cjson = require "cjson"
    local redis = require "resty.redis"
    local red = redis:new()

    red:set_timeouts(1000, 1000, 1000) -- 1 sec

    local ok, err = red:connect("127.0.0.1", 6379)
    if not ok then
        ngx.say("failed to connect: ", err)
        return
    end

    local ok, err = red:multi()
    if not ok then
        ngx.say("failed to run multi: ", err)
        return
    end
    ngx.say("multi ans: ", cjson.encode(ok))

    local ans, err = red:set("a", "abc")
    if not ans then
        ngx.say("failed to run sort: ", err)
        return
    end
    ngx.say("set ans: ", cjson.encode(ans))

    local ans, err = red:lpop("a")
    if not ans then
        ngx.say("failed to run sort: ", err)
        return
    end
    ngx.say("set ans: ", cjson.encode(ans))

    ans, err = red:exec()
    ngx.say("exec ans: ", cjson.encode(ans))

    red:close()
```

Then the output will be

    multi ans: "OK"
    set ans: "QUEUED"
    set ans: "QUEUED"
    exec ans: ["OK",[false,"ERR Operation against a key holding the wrong kind of value"]]

[Back to TOC](#table-of-contents)

Redis Module
==================

This library supports the Redis module. Here is an example with RedisBloom module:

```lua
    local cjson = require "cjson"
    local redis = require "resty.redis"
    -- register the module prefix "bf" for RedisBloom
    redis.register_module_prefix("bf")

    local red = redis:new()

    local ok, err = red:connect("127.0.0.1", 6379)
    if not ok then
        ngx.say("failed to connect: ", err)
        return
    end

    -- call BF.ADD command with the prefix 'bf'
    res, err = red:bf():add("dog", 1)
    if not res then
        ngx.say(err)
        return
    end
    ngx.say("receive: ", cjson.encode(res))

    -- call BF.EXISTS command
    res, err = red:bf():exists("dog")
    if not res then
        ngx.say(err)
        return
    end
    ngx.say("receive: ", cjson.encode(res))
```

Load Balancing and Failover
===========================

You can trivially implement your own Redis load balancing logic yourself in Lua. Just keep a Lua table of all available Redis backend information (like host name and port numbers) and pick one server according to some rule (like round-robin or key-based hashing) from the Lua table at every request. You can keep track of the current rule state in your own Lua module's data, see https://github.com/openresty/lua-nginx-module/#data-sharing-within-an-nginx-worker

Similarly, you can implement automatic failover logic in Lua at great flexibility.

[Back to TOC](#table-of-contents)

Debugging
=========

It is usually convenient to use the [lua-cjson](http://www.kyne.com.au/~mark/software/lua-cjson.php) library to encode the return values of the redis command methods to JSON. For example,

```lua
    local cjson = require "cjson"
    ...
    local res, err = red:mget("h1234", "h5678")
    if res then
        print("res: ", cjson.encode(res))
    end
```

[Back to TOC](#table-of-contents)

Automatic Error Logging
=======================

By default the underlying [ngx_lua](https://github.com/openresty/lua-nginx-module/#readme) module
does error logging when socket errors happen. If you are already doing proper error
handling in your own Lua code, then you are recommended to disable this automatic error logging by turning off [ngx_lua](https://github.com/openresty/lua-nginx-module/#readme)'s [lua_socket_log_errors](https://github.com/openresty/lua-nginx-module/#lua_socket_log_errors) directive, that is,

```nginx
    lua_socket_log_errors off;
```

[Back to TOC](#table-of-contents)

Check List for Issues
=====================

1. Ensure you configure the connection pool size properly in the [set_keepalive](#set_keepalive). Basically if your Redis can handle `n` concurrent connections and your NGINX has `m` workers, then the connection pool size should be configured as `n/m`. For example, if your Redis usually handles 1000 concurrent requests and you have 10 NGINX workers, then the connection pool size should be 100. Similarly if you have `p` different NGINX instances, then connection pool size should be `n/m/p`.
2. Ensure the backlog setting on the Redis side is large enough. For Redis 2.8+, you can directly tune the `tcp-backlog` parameter in the `redis.conf` file (and also tune the kernel parameter `SOMAXCONN` accordingly at least on Linux). You may also want to tune the `maxclients` parameter in `redis.conf`.
3. Ensure you are not using too short timeout setting in the [set_timeout](#set_timeout) or [set_timeouts](#set_timeouts) methods. If you have to, try redoing the operation upon timeout and turning off [automatic error logging](#automatic-error-logging) (because you are already doing proper error handling in your own Lua code).
4. If your NGINX worker processes' CPU usage is very high under load, then the NGINX event loop might be blocked by the CPU computation too much. Try sampling a [C-land on-CPU Flame Graph](https://github.com/agentzh/nginx-systemtap-toolkit#sample-bt) and [Lua-land on-CPU Flame Graph](https://github.com/agentzh/stapxx#ngx-lj-lua-stacks) for a typical NGINX worker process. You can optimize the CPU-bound things according to these Flame Graphs.
5. If your NGINX worker processes' CPU usage is very low under load, then the NGINX event loop might be blocked by some blocking system calls (like file IO system calls). You can confirm the issue by running the [epoll-loop-blocking-distr](https://github.com/agentzh/stapxx#epoll-loop-blocking-distr) tool against a typical NGINX worker process. If it is indeed the case, then you can further sample a [C-land off-CPU Flame Graph](https://github.com/agentzh/nginx-systemtap-toolkit#sample-bt-off-cpu) for a NGINX worker process to analyze the actual blockers.
6. If your `redis-server` process is running near 100% CPU usage, then you should consider scale your Redis backend by multiple nodes or use the [C-land on-CPU Flame Graph tool](https://github.com/agentzh/nginx-systemtap-toolkit#sample-bt) to analyze the internal bottlenecks within the Redis server process.

[Back to TOC](#table-of-contents)

Limitations
===========

* This library cannot be used in code contexts like init_by_lua*, set_by_lua*, log_by_lua*, and
header_filter_by_lua* where the ngx_lua cosocket API is not available.
* The `resty.redis` object instance cannot be stored in a Lua variable at the Lua module level,
because it will then be shared by all the concurrent requests handled by the same nginx
 worker process (see
https://github.com/openresty/lua-nginx-module/#data-sharing-within-an-nginx-worker ) and
result in bad race conditions when concurrent requests are trying to use the same `resty.redis` instance
(you would see the "bad request" or "socket busy" error to be returned from the method calls).
You should always initiate `resty.redis` objects in function local
variables or in the `ngx.ctx` table. These places all have their own data copies for
each request.

[Back to TOC](#table-of-contents)

Installation
============

If you are using the OpenResty bundle (http://openresty.org ), then
you do not need to do anything because it already includes and enables
lua-resty-redis by default. And you can just use it in your Lua code,
as in

```lua
    local redis = require "resty.redis"
    ...
```

If you are using your own nginx + ngx_lua build, then you need to configure
the lua_package_path directive to add the path of your lua-resty-redis source
tree to ngx_lua's LUA_PATH search path, as in

```nginx
    # nginx.conf
    http {
        lua_package_path "/path/to/lua-resty-redis/lib/?.lua;;";
        ...
    }
```

Ensure that the system account running your Nginx ''worker'' proceses have
enough permission to read the `.lua` file.

[Back to TOC](#table-of-contents)

TODO
====

[Back to TOC](#table-of-contents)

Community
=========

[Back to TOC](#table-of-contents)

English Mailing List
--------------------

The [openresty-en](https://groups.google.com/group/openresty-en) mailing list is for English speakers.

[Back to TOC](#table-of-contents)

Chinese Mailing List
--------------------

The [openresty](https://groups.google.com/group/openresty) mailing list is for Chinese speakers.

[Back to TOC](#table-of-contents)

Bugs and Patches
================

Please report bugs or submit patches by

1. creating a ticket on the [GitHub Issue Tracker](http://github.com/agentzh/lua-resty-redis/issues),
1. or posting to the [OpenResty community](#community).

[Back to TOC](#table-of-contents)

Author
======

Yichun "agentzh" Zhang (章亦春) <agentzh@gmail.com>, OpenResty Inc.

[Back to TOC](#table-of-contents)

Copyright and License
=====================

This module is licensed under the BSD license.

Copyright (C) 2012-2017, by Yichun Zhang (agentzh) <agentzh@gmail.com>, OpenResty Inc.

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

[Back to TOC](#table-of-contents)

See Also
========
* the ngx_lua module: https://github.com/openresty/lua-nginx-module/#readme
* the redis wired protocol specification: http://redis.io/topics/protocol
* the [lua-resty-memcached](https://github.com/agentzh/lua-resty-memcached) library
* the [lua-resty-mysql](https://github.com/agentzh/lua-resty-mysql) library

[Back to TOC](#table-of-contents)

