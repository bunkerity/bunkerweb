Name
====

ngx.balancer - Lua API for defining dynamic upstream balancers in Lua

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
    * [http subsystem](#http-subsystem)
    * [stream subsystem](#stream-subsystem)
* [Description](#description)
* [Methods](#methods)
    * [set_current_peer](#set_current_peer)
    * [set_more_tries](#set_more_tries)
    * [get_last_failure](#get_last_failure)
    * [set_timeouts](#set_timeouts)
    * [recreate_request](#recreate_request)
* [Community](#community)
    * [English Mailing List](#english-mailing-list)
    * [Chinese Mailing List](#chinese-mailing-list)
* [Bugs and Patches](#bugs-and-patches)
* [Author](#author)
* [Copyright and License](#copyright-and-license)
* [See Also](#see-also)

Status
======

This Lua module is currently considered experimental.

Synopsis
========

http subsystem
--------------

```nginx
http {
    upstream backend {
        server 0.0.0.1;   # just an invalid address as a place holder

        balancer_by_lua_block {
            local balancer = require "ngx.balancer"

            -- well, usually we calculate the peer's host and port
            -- according to some balancing policies instead of using
            -- hard-coded values like below
            local host = "127.0.0.2"
            local port = 8080

            local ok, err = balancer.set_current_peer(host, port)
            if not ok then
                ngx.log(ngx.ERR, "failed to set the current peer: ", err)
                return ngx.exit(500)
            end
        }

        keepalive 10;  # connection pool
    }

    server {
        # this is the real entry point
        listen 80;

        location / {
            # make use of the upstream named "backend" defined above:
            proxy_pass http://backend/fake;
        }
    }

    server {
        # this server is just for mocking up a backend peer here...
        listen 127.0.0.2:8080;

        location = /fake {
            echo "this is the fake backend peer...";
        }
    }
}
```

[Back to TOC](#table-of-contents)

stream subsystem
----------------

```nginx
stream {
    upstream backend {
        server 0.0.0.1:1234;   # just an invalid address as a place holder

        balancer_by_lua_block {
            local balancer = require "ngx.balancer"

            -- well, usually we calculate the peer's host and port
            -- according to some balancing policies instead of using
            -- hard-coded values like below
            local host = "127.0.0.2"
            local port = 8080

            local ok, err = balancer.set_current_peer(host, port)
            if not ok then
                ngx.log(ngx.ERR, "failed to set the current peer: ", err)
                return ngx.exit(ngx.ERROR)
            end
        }
    }

    server {
        # this is the real entry point
        listen 10000;

        # make use of the upstream named "backend" defined above:
        proxy_pass backend;
    }

    server {
        # this server is just for mocking up a backend peer here...
        listen 127.0.0.2:8080;

        echo "this is the fake backend peer...";
    }
}
```

[Back to TOC](#table-of-contents)

Description
===========

This Lua module provides API functions to allow defining highly dynamic NGINX load balancers for
any existing nginx upstream modules like [ngx_http_proxy_module](http://nginx.org/en/docs/http/ngx_http_proxy_module.html),
[ngx_http_fastcgi_module](http://nginx.org/en/docs/http/ngx_http_fastcgi_module.html) and
[ngx_stream_proxy_module](https://nginx.org/en/docs/stream/ngx_stream_proxy_module.html).

It allows you to dynamically select a backend peer to connect to (or retry) on a per-request
basis from a list of backend peers which may also be dynamic.

[Back to TOC](#table-of-contents)

Methods
=======

All the methods of this module are static (or module-level). That is, you do not need an object (or instance)
to call these methods.

[Back to TOC](#table-of-contents)

set_current_peer
----------------
**syntax:** *ok, err = balancer.set_current_peer(host, port)*

**context:** *balancer_by_lua&#42;*

Sets the peer address (host and port) for the current backend query (which may be a retry).

Domain names in `host` do not make sense. You need to use OpenResty libraries like
[lua-resty-dns](https://github.com/openresty/lua-resty-dns) to obtain IP address(es) from
all the domain names before entering the `balancer_by_lua*` handler (for example,
you can perform DNS lookups in an earlier phase like [access_by_lua*](https://github.com/openresty/lua-nginx-module#access_by_lua)
and pass the results to the `balancer_by_lua*` handler via [ngx.ctx](https://github.com/openresty/lua-nginx-module#ngxctx).

[Back to TOC](#table-of-contents)

set_more_tries
--------------
**syntax:** *ok, err = balancer.set_more_tries(count)*

**context:** *balancer_by_lua&#42;*

Sets the tries performed when the current attempt (which may be a retry) fails (as determined
by directives like [proxy_next_upstream](http://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_next_upstream), depending on what
particular nginx uptream module you are currently using). Note that the current attempt is *excluded* in the `count` number set here.

Please note that, the total number of tries in a single downstream request cannot exceed the
hard limit configured by directives like [proxy_next_upstream_tries](http://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_next_upstream_tries),
depending on what concrete nginx upstream module you are using. When exceeding this limit,
the `count` value will get reduced to meet the limit and the second return value will be
the string `"reduced tries due to limit"`, which is a warning, while the first return value
is still a `true` value.

[Back to TOC](#table-of-contents)

get_last_failure
----------------
**syntax:** *state_name, status_code = balancer.get_last_failure()*

**context:** *balancer_by_lua&#42;*

Retrieves the failure details about the previous failed attempt (if any) when the `next_upstream` retrying
mechanism is in action. When there was indeed a failed previous attempt, it returned a string describing
that attempt's state name, as well as an integer describing the status code of that attempt.

Possible state names are as follows:
* `"next"`
    Failures due to bad status codes sent from the backend server. The origin's response is same though, which means the backend connection
can still be reused for future requests.
* `"failed"`
    Fatal errors while communicating to the backend server (like connection timeouts, connection resets, and etc). In this case,
the backend connection must be aborted and cannot get reused.

Possible status codes are those HTTP error status codes like `502` and `504`.

For stream module, `status_code` will always be 0 (ngx.OK) and is provided for compatibility reasons.

When the current attempt is the first attempt for the current downstream request (which means
there is no previous attempts at all), this
method always returns a single `nil` value.

[Back to TOC](#table-of-contents)

set_timeouts
------------
**syntax:** `ok, err = balancer.set_timeouts(connect_timeout, send_timeout, read_timeout)`

**context:** *balancer_by_lua&#42;*

Sets the upstream timeout (connect, send and read) in seconds for the current and any
subsequent backend requests (which might be a retry).

If you want to inherit the timeout value of the global `nginx.conf` configuration (like `proxy_connect_timeout`), then
just specify the `nil` value for the corresponding argument (like the `connect_timeout` argument).

Zero and negative timeout values are not allowed.

You can specify millisecond precision in the timeout values by using floating point numbers like 0.001 (which means 1ms).

**Note:** `send_timeout` and `read_timeout` are controlled by the same config
[`proxy_timeout`](https://nginx.org/en/docs/stream/ngx_stream_proxy_module.html#proxy_timeout)
for `ngx_stream_proxy_module`. To keep API compatibility, this function will use `max(send_timeout, read_timeout)`
as the value for setting `proxy_timeout`.

Returns `true` when the operation is successful; returns `nil` and a string describing the error
otherwise.

This only affects the current downstream request. It is not a global change.

For the best performance, you should use the [OpenResty](https://openresty.org/) bundle.

This function was first added in the `0.1.7` version of this library.

[Back to TOC](#table-of-contents)

recreate_request
----------------
**syntax:** `ok, err = balancer.recreate_request()`

**context:** *balancer_by_lua&#42;*

Recreates the request buffer for sending to the upstream server. This is useful, for example
if you want to change a request header field to the new upstream server on balancer retries.

Normally this does not work because the request buffer is created once during upstream module
initialization and won't be regenerated for subsequent retries. However you can use
`proxy_set_header My-Header $my_header` and set the `ngx.var.my_header` variable inside the
balancer phase. Calling `balancer.recreate_request()` after updating a header field will
cause the request buffer to be re-generated and the `My-Header` header will thus contain
the new value.

**Warning:** because the request buffer has to be recreated and such allocation occurs on the
request memory pool, the old buffer has to be thrown away and will only be freed after the request
finishes. Do not call this function too often or memory leaks may be noticeable. Even so, a call
to this function should be made **only** if you know the request buffer must be regenerated,
instead of unconditionally in each balancer retries.

This function was first added in the `0.1.20` version of this library.

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

Copyright (C) 2015-2017, by Yichun "agentzh" Zhang, OpenResty Inc.

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

[Back to TOC](#table-of-contents)

See Also
========
* the ngx_lua module: https://github.com/openresty/lua-nginx-module
* the [balancer_by_lua*](https://github.com/openresty/lua-nginx-module#balancer_by_lua_block) directive.
* the [lua-resty-core](https://github.com/openresty/lua-resty-core) library.
* OpenResty: https://openresty.org

[Back to TOC](#table-of-contents)
