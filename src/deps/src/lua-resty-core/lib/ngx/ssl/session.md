Name
====

ngx.ssl.session - Lua API for manipulating SSL session data and IDs for NGINX downstream SSL connections.

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
* [Description](#description)
* [Methods](#methods)
    * [get_session_id](#get_session_id)
    * [get_serialized_session](#get_serialized_session)
    * [set_serialized_session](#set_serialized_session)
* [Community](#community)
    * [English Mailing List](#english-mailing-list)
    * [Chinese Mailing List](#chinese-mailing-list)
* [Bugs and Patches](#bugs-and-patches)
* [Author](#author)
* [Copyright and License](#copyright-and-license)
* [See Also](#see-also)

Status
======

This Lua module is production ready.

Synopsis
========

```nginx
# nginx.conf

# Note: you do not need the following line if you are using
# OpenResty 1.11.2.1+.
lua_package_path "/path/to/lua-resty-core/lib/?.lua;;";

ssl_session_fetch_by_lua_block {
    local ssl_sess = require "ngx.ssl.session"

    local sess_id, err = ssl_sess.get_session_id()
    if not sess_id then
        ngx.log(ngx.ERR, "failed to get session ID: ", err)
        -- considered a cache miss, and just return...
        return
    end

    -- the user is supposed to implement the my_lookup_ssl_session_by_id
    -- Lua function used below. She can look up an external memcached
    -- or redis cluster, for example. And she can also introduce a local
    -- cache layer at the same time...
    local sess, err = my_lookup_ssl_session_by_id(sess_id)
    if not sess then
        if err then
            ngx.log(ngx.ERR, "failed to look up the session by ID ",
                    sess_id, ": ", err)
            return
        end

        -- cache miss...just return
        return
    end

    local ok, err = ssl_sess.set_serialized_session(sess)
    if not ok then
        ngx.log(ngx.ERR, "failed to set SSL session for ID ", sess_id,
                ": ", err)
        -- consider it as a cache miss...
        return
    end

    -- done here, SSL session successfully set and should resume accordingly...
}

ssl_session_store_by_lua_block {
    local ssl_sess = require "ngx.ssl.session"

    local sess_id, err = ssl_sess.get_session_id()
    if not sess_id then
        ngx.log(ngx.ERR, "failed to get session ID: ", err)
        -- just give up
        return
    end

    local sess, err = ssl_sess.get_serialized_session()
    if not sess then
        ngx.log(ngx.ERR, "failed to get SSL session from the ",
                "current connection: ", err)
        -- just give up
        return
    end

    -- for the best performance, we should avoid creating a closure
    -- dynamically here on the hot code path. Instead, we should
    -- put this function in one of our own Lua module files. this
    -- example is just for demonstration purposes...
    local function save_it(premature, sess_id, sess)
        -- the user is supposed to implement the
        -- my_save_ssl_session_by_id Lua function used below.
        -- She can save to an external memcached
        -- or redis cluster, for example. And she can also introduce
        -- a local cache layer at the same time...
        local sess, err = my_save_ssl_session_by_id(sess_id, sess)
        if not sess then
            if err then
                ngx.log(ngx.ERR, "failed to save the session by ID ",
                        sess_id, ": ", err)
                return ngx.exit(ngx.ERROR)
            end

            -- cache miss...just return
            return
        end
    end

    -- create a 0-delay timer here...
    local ok, err = ngx.timer.at(0, save_it, sess_id, sess)
    if not ok then
        ngx.log(ngx.ERR, "failed to create a 0-delay timer: ", err)
        return
    end
}

server {
    listen 443 ssl;
    server_name test.com;

    # well, we could configure ssl_certificate_by_lua* here as well...
    ssl_certificate /path/to/server-cert.pem;
    ssl_certificate_key /path/to/server-priv-key.pem;
}
```

Description
===========

This Lua module provides API functions for manipulating SSL session data and IDs for NGINX
downstream connections. It is mostly for the contexts [ssl_session_fetch_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_session_fetch_by_lua_block)
and [ssl_session_store_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_session_store_by_lua_block).

This Lua API can be used to implement distributed SSL session caching for downstream SSL connections, thus saving a lot of full SSL handshakes which are very expensive.

To load the `ngx.ssl.session` module in Lua, just write

```lua
local ssl_sess = require "ngx.ssl.session"
```

[Back to TOC](#table-of-contents)

Methods
=======

get_session_id
--------------
**syntax:** *id, err = ssl_sess.get_session_id()*

**context:** *ssl_session_fetch_by_lua&#42;, ssl_session_store_by_lua&#42;*

Fetches the SSL session ID associated with the current downstream SSL connection.
The ID is returned as a Lua string.

In case of errors, it returns `nil` and a string describing the error.

This API function is usually called in the contexts of
[ssl_session_store_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_session_store_by_lua_block)
and [ssl_session_fetch_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_session_fetch_by_lua_block).

[Back to TOC](#table-of-contents)

get_serialized_session
----------------------
**syntax:** *session, err = ssl_sess.get_serialized_session()*

**context:** *ssl_session_store_by_lua&#42;*

Returns the serialized form of the SSL session data of the current SSL connection, in a Lua string.

This session can be cached in [lua-resty-lrucache](https://github.com/openresty/lua-resty-lrucache), [lua_shared_dict](https://github.com/openresty/lua-nginx-module#lua_shared_dict),
and/or external data storage services like `memcached` and `redis`. The SSL session ID returned
by the [get_session_id](#get_session_id) function is usually used as the cache key.

The returned SSL session data can later be loaded into other SSL connections using the same
session ID via the [set_serialized_session](#set_serialized_session) function.

In case of errors, it returns `nil` and a string describing the error.

This API function is usually called in the context of
[ssl_session_store_by_lua*](https://github.com/openresty/lua-nginx-module#ssl_session_store_by_lua_block)
where the SSL handshake has just completed.

[Back to TOC](#table-of-contents)

set_serialized_session
----------------------
**syntax:** *ok, err = ssl_sess.set_serialized_session(session)*

**context:** *ssl_session_fetch_by_lua&#42;*

Sets the serialized SSL session provided as the argument to the current SSL connection.
If the SSL session is successfully set, the current SSL connection can resume the session
directly without going through the full SSL handshake process (which is very expensive in terms of CPU time).

This API is usually used in the context of [ssl_session_fetch_by_lua*](https://github.com/openresty/lua-nginx-module#ssl_session_fetch_by_lua_block)
when a cache hit is found with the current SSL session ID.

The serialized SSL session used as the argument should be originally returned by the
[get_serialized_session](#get_serialized_session) function.

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

1. creating a ticket on the [GitHub Issue Tracker](https://github.com/openresty/lua-resty-core/issues),
1. or posting to the [OpenResty community](#community).

[Back to TOC](#table-of-contents)

Author
======

Yichun Zhang &lt;agentzh@gmail.com&gt; (agentzh), OpenResty Inc.

[Back to TOC](#table-of-contents)

Copyright and License
=====================

This module is licensed under the BSD license.

Copyright (C) 2016-2017, by Yichun "agentzh" Zhang, OpenResty Inc.

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

[Back to TOC](#table-of-contents)

See Also
========
* the ngx_lua module: https://github.com/openresty/lua-nginx-module
* the [ssl_session_fetch_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_session_fetch_by_lua_block) directive.
* the [ssl_session_store_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_session_store_by_lua_block) directive.
* the [lua-resty-core](https://github.com/openresty/lua-resty-core) library.
* OpenResty: https://openresty.org

[Back to TOC](#table-of-contents)
