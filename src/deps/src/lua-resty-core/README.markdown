Name
====

lua-resty-core - New FFI-based Lua API for ngx_http_lua_module and/or ngx_stream_lua_module

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
* [Description](#description)
* [Prerequisites](#prerequisites)
* [API Implemented](#api-implemented)
    * [resty.core.hash](#restycorehash)
    * [resty.core.base64](#restycorebase64)
    * [resty.core.uri](#restycoreuri)
    * [resty.core.regex](#restycoreregex)
    * [resty.core.exit](#restycoreexit)
    * [resty.core.shdict](#restycoreshdict)
    * [resty.core.var](#restycorevar)
    * [resty.core.ctx](#restycorectx)
    * [get_ctx_table](#get_ctx_table)
    * [resty.core.request](#restycorerequest)
    * [resty.core.response](#restycoreresponse)
    * [resty.core.misc](#restycoremisc)
    * [resty.core.time](#restycoretime)
    * [resty.core.worker](#restycoreworker)
    * [resty.core.phase](#restycorephase)
    * [resty.core.ndk](#restycorendk)
    * [resty.core.socket](#restycoresocket)
    * [resty.core.param](#restycoreparam)
    * [ngx.semaphore](#ngxsemaphore)
    * [ngx.balancer](#ngxbalancer)
    * [ngx.ssl](#ngxssl)
    * [ngx.ssl.clienthello](#ngxsslclienthello)
    * [ngx.ssl.session](#ngxsslsession)
    * [ngx.re](#ngxre)
    * [ngx.resp](#ngxresp)
    * [ngx.pipe](#ngxpipe)
    * [ngx.process](#ngxprocess)
    * [ngx.errlog](#ngxerrlog)
    * [ngx.base64](#ngxbase64)
* [Caveat](#caveat)
* [TODO](#todo)
* [Author](#author)
* [Copyright and License](#copyright-and-license)
* [See Also](#see-also)

Status
======

This library is production ready.

Synopsis
========

This library is automatically loaded by default in OpenResty 1.15.8.1. This
behavior can be disabled via the
[lua_load_resty_core](https://github.com/openresty/lua-nginx-module#lua_load_resty_core)
directive, but note that the use of this library is vividly recommended, as its
FFI implementation is both faster, safer, and more complete than the Lua C API
of the ngx_lua module.

If you are using an older version of OpenResty, you must load this library like
so:

```nginx
    # nginx.conf

    http {
        # you do NOT need to configure the following line when you
        # are using the OpenResty bundle 1.4.3.9+.
        lua_package_path "/path/to/lua-resty-core/lib/?.lua;;";

        init_by_lua_block {
            require "resty.core"
            collectgarbage("collect")  -- just to collect any garbage
        }

        ...
    }
```

Description
===========

This pure Lua library reimplements part of the [ngx_lua](https://github.com/openresty/lua-nginx-module#readme) module's
[Nginx API for Lua](https://github.com/openresty/lua-nginx-module#nginx-api-for-lua)
with LuaJIT FFI and installs the new FFI-based Lua API into the ngx.* and ndk.* namespaces
used by the ngx_lua module.

In addition, this Lua library implements any significant new Lua APIs of
the [ngx_lua](https://github.com/openresty/lua-nginx-module#readme) module
as proper Lua modules, like [ngx.semaphore](#ngxsemaphore) and [ngx.balancer](#ngxbalancer).

The FFI-based Lua API can work with LuaJIT's JIT compiler. ngx_lua's default API is based on the standard
Lua C API, which will never be JIT compiled and the user Lua code is always interpreted (slowly).

Support for the new [ngx_stream_lua_module](https://github.com/openresty/stream-lua-nginx-module) has also begun.

This library is shipped with the OpenResty bundle by default. So you do not really need to worry about the dependencies
and requirements.

[Back to TOC](#table-of-contents)

Prerequisites
=============

**WARNING** This library is included with every OpenResty release. You should use the bundled version
of this library in the particular OpenResty release you are using. Otherwise you may run
into serious compatibility issues.

* LuaJIT 2.1 (for now, it is the v2.1 git branch in the official luajit-2.0 git repository: http://luajit.org/download.html )
* [ngx_http_lua_module](https://github.com/openresty/lua-nginx-module) v0.10.21.
* [ngx_stream_lua_module](https://github.com/openresty/stream-lua-nginx-module) v0.0.11.
* [lua-resty-lrucache](https://github.com/openresty/lua-resty-lrucache)

[Back to TOC](#table-of-contents)

API Implemented
===============

[Back to TOC](#table-of-contents)

## resty.core.hash

* [ngx.md5](https://github.com/openresty/lua-nginx-module#ngxmd5)
* [ngx.md5_bin](https://github.com/openresty/lua-nginx-module#ngxmd5_bin)
* [ngx.sha1_bin](https://github.com/openresty/lua-nginx-module#ngxsha1_bin)

[Back to TOC](#table-of-contents)

## resty.core.base64

* [ngx.encode_base64](https://github.com/openresty/lua-nginx-module#ngxencode_base64)
* [ngx.decode_base64](https://github.com/openresty/lua-nginx-module#ngxdecode_base64)

[Back to TOC](#table-of-contents)

## resty.core.uri

* [ngx.escape_uri](https://github.com/openresty/lua-nginx-module#ngxescape_uri)
* [ngx.unescape_uri](https://github.com/openresty/lua-nginx-module#ngxunescape_uri)

[Back to TOC](#table-of-contents)

## resty.core.regex

* [ngx.re.match](https://github.com/openresty/lua-nginx-module#ngxrematch)
* [ngx.re.gmatch](https://github.com/openresty/lua-nginx-module#ngxregmatch)
* [ngx.re.find](https://github.com/openresty/lua-nginx-module#ngxrefind)
* [ngx.re.sub](https://github.com/openresty/lua-nginx-module#ngxresub)
* [ngx.re.gsub](https://github.com/openresty/lua-nginx-module#ngxregsub)

[Back to TOC](#table-of-contents)

## resty.core.exit

* [ngx.exit](https://github.com/openresty/lua-nginx-module#ngxexit)

[Back to TOC](#table-of-contents)

## resty.core.shdict

* [ngx.shared.DICT.get](https://github.com/openresty/lua-nginx-module#ngxshareddictget)
* [ngx.shared.DICT.get_stale](https://github.com/openresty/lua-nginx-module#ngxshareddictget_stale)
* [ngx.shared.DICT.incr](https://github.com/openresty/lua-nginx-module#ngxshareddictincr)
* [ngx.shared.DICT.set](https://github.com/openresty/lua-nginx-module#ngxshareddictset)
* [ngx.shared.DICT.safe_set](https://github.com/openresty/lua-nginx-module#ngxshareddictsafe_set)
* [ngx.shared.DICT.add](https://github.com/openresty/lua-nginx-module#ngxshareddictadd)
* [ngx.shared.DICT.safe_add](https://github.com/openresty/lua-nginx-module#ngxshareddictsafe_add)
* [ngx.shared.DICT.replace](https://github.com/openresty/lua-nginx-module#ngxshareddictreplace)
* [ngx.shared.DICT.delete](https://github.com/openresty/lua-nginx-module#ngxshareddictdelete)
* [ngx.shared.DICT.ttl](https://github.com/openresty/lua-nginx-module#ngxshareddictttl)
* [ngx.shared.DICT.expire](https://github.com/openresty/lua-nginx-module#ngxshareddictexpire)
* [ngx.shared.DICT.flush_all](https://github.com/openresty/lua-nginx-module#ngxshareddictflush_all)
* [ngx.shared.DICT.free_space](https://github.com/openresty/lua-nginx-module#ngxshareddictfree_space)
* [ngx.shared.DICT.capacity](https://github.com/openresty/lua-nginx-module#ngxshareddictcapacity)

[Back to TOC](#table-of-contents)

## resty.core.var

* [ngx.var.VARIABLE](https://github.com/openresty/lua-nginx-module#ngxvarvariable)

[Back to TOC](#table-of-contents)

## resty.core.ctx

* [ngx.ctx](https://github.com/openresty/lua-nginx-module#ngxctx)

[Back to TOC](#table-of-contents)

## get_ctx_table

**syntax:** *ctx = resty.core.ctx.get_ctx_table(ctx?)*

Similar to [ngx.ctx](#restycorectx) but it accepts an optional `ctx` argument.
It will use the `ctx` from caller instead of creating a new table
when the `ctx` table does not exist.

Notice: the `ctx` table will be used in the current request's whole life cycle.
Please be very careful when you try to reuse the `ctx` table.
You need to make sure there is no Lua code using or going to use the `ctx` table
in the current request before you reusing the `ctx` table in some other place.

[Back to TOC](#table-of-contents)

## resty.core.request

* [ngx.req.get_headers](https://github.com/openresty/lua-nginx-module#ngxreqget_headers)
* [ngx.req.get_uri_args](https://github.com/openresty/lua-nginx-module#ngxreqget_uri_args)
* [ngx.req.start_time](https://github.com/openresty/lua-nginx-module#ngxreqstart_time)
* [ngx.req.get_method](https://github.com/openresty/lua-nginx-module#ngxreqget_method)
* [ngx.req.set_method](https://github.com/openresty/lua-nginx-module#ngxreqset_method)
* [ngx.req.set_header](https://github.com/openresty/lua-nginx-module#ngxreqset_header)
* [ngx.req.clear_header](https://github.com/openresty/lua-nginx-module#ngxreqclear_header)

[Back to TOC](#table-of-contents)

## resty.core.response

* [ngx.header.HEADER](https://github.com/openresty/lua-nginx-module#ngxheaderheader)

[Back to TOC](#table-of-contents)

## resty.core.misc

* [ngx.status](https://github.com/openresty/lua-nginx-module#ngxstatus)
* [ngx.is_subrequest](https://github.com/openresty/lua-nginx-module#ngxis_subrequest)
* [ngx.headers_sent](https://github.com/openresty/lua-nginx-module#ngxheaders_sent)
* [ngx.req.is_internal](https://github.com/openresty/lua-nginx-module#ngxreqis_internal)

[Back to TOC](#table-of-contents)

## resty.core.time

* [ngx.time](https://github.com/openresty/lua-nginx-module#ngxtime)
* [ngx.now](https://github.com/openresty/lua-nginx-module#ngxnow)
* [ngx.update_time](https://github.com/openresty/lua-nginx-module#ngxupdate_time)
* [ngx.localtime](https://github.com/openresty/lua-nginx-module#ngxlocaltime)
* [ngx.utctime](https://github.com/openresty/lua-nginx-module#ngxutctime)
* [ngx.cookie_time](https://github.com/openresty/lua-nginx-module#ngxcookie_time)
* [ngx.http_time](https://github.com/openresty/lua-nginx-module#ngxhttp_time)
* [ngx.parse_http_time](https://github.com/openresty/lua-nginx-module#ngxparse_http_time)
* [monotonic_msec](./lib/resty/core/time.md#monotonic_msec)
* [monotonic_time](./lib/resty/core/time.md#monotonic_time)

[Back to TOC](#table-of-contents)

## resty.core.worker

* [ngx.worker.exiting](https://github.com/openresty/lua-nginx-module#ngxworkerexiting)
* [ngx.worker.pid](https://github.com/openresty/lua-nginx-module#ngxworkerpid)
* [ngx.worker.id](https://github.com/openresty/lua-nginx-module#ngxworkerid)
* [ngx.worker.count](https://github.com/openresty/lua-nginx-module#ngxworkercount)

[Back to TOC](#table-of-contents)

## resty.core.phase

* [ngx.get_phase](https://github.com/openresty/lua-nginx-module#ngxget_phase)

[Back to TOC](#table-of-contents)

## resty.core.ndk

* [ndk.set_var](https://github.com/openresty/lua-nginx-module#ndkset_vardirective)

[Back to TOC](#table-of-contents)

## resty.core.socket

* [socket.setoption](https://github.com/openresty/lua-nginx-module#tcpsocksetoption)
* [socket.setclientcert](https://github.com/openresty/lua-nginx-module#tcpsocksetclientcert)
* [socket.sslhandshake](https://github.com/openresty/lua-nginx-module#tcpsocksslhandshake)

[Back to TOC](#table-of-contents)

## resty.core.param

* [ngx.arg](https://github.com/openresty/lua-nginx-module#ngxarg) (getter only)

[Back to TOC](#table-of-contents)

## ngx.semaphore

This Lua module implements a semaphore API for efficient "light thread" synchronization,
which can work across different requests (but not across nginx worker processes).

See the [documentation](./lib/ngx/semaphore.md) for this Lua module for more details.

[Back to TOC](#table-of-contents)

## ngx.balancer

This Lua module implements for defining dynamic upstream balancers in Lua.

See the [documentation](./lib/ngx/balancer.md) for this Lua module for more details.

[Back to TOC](#table-of-contents)

## ngx.ssl

This Lua module provides a Lua API for controlling SSL certificates, private keys,
SSL protocol versions, and etc in NGINX downstream SSL handshakes.

See the [documentation](./lib/ngx/ssl.md) for this Lua module for more details.

[Back to TOC](#table-of-contents)

## ngx.ssl.clienthello

This Lua module provides a Lua API for post-processing SSL client hello message
for NGINX downstream SSL connections.

See the [documentation](./lib/ngx/ssl/clienthello.md) for this Lua module for more details.

[Back to TOC](#table-of-contents)

## ngx.ssl.session

This Lua module provides a Lua API for manipulating SSL session data and IDs
for NGINX downstream SSL connections.

See the [documentation](./lib/ngx/ssl/session.md) for this Lua module for more details.

[Back to TOC](#table-of-contents)

## ngx.re

This Lua module provides a Lua API which implements convenience utilities for
the `ngx.re` API.

See the [documentation](./lib/ngx/re.md) for this Lua module for more details.

[Back to TOC](#table-of-contents)

## ngx.resp

This Lua module provides Lua API which could be used to handle HTTP response.

See the [documentation](./lib/ngx/resp.md) for this Lua module for more details.

[Back to TOC](#table-of-contents)

## ngx.pipe

This module provides a Lua API to spawn processes and communicate with them in
a non-blocking fashion.

See the [documentation](./lib/ngx/pipe.md) for this Lua module for more
details.

This module was first introduced in lua-resty-core v0.1.16.

[Back to TOC](#table-of-contents)

## ngx.process

This Lua module is used to manage the nginx process in Lua.

See the [documentation](./lib/ngx/process.md) for this Lua module for more details.

This module was first introduced in lua-resty-core v0.1.12.

[Back to TOC](#table-of-contents)

## ngx.errlog

This Lua module provides Lua API to capture and manage nginx error log messages.

See the [documentation](./lib/ngx/errlog.md) for this Lua module for more details.

This module was first introduced in lua-resty-core v0.1.12.

[Back to TOC](#table-of-contents)

## ngx.base64

This Lua module provides Lua API to urlsafe base64 encode/decode.

See the [documentation](./lib/ngx/base64.md) for this Lua module for more details.

This module was first introduced in lua-resty-core v0.1.14.

[Back to TOC](#table-of-contents)

Caveat
======

If the user Lua code is not JIT compiled, then use of this library may
lead to performance drop in interpreted mode. You will only observe
speedup when you get a good part of your user Lua code JIT compiled.

[Back to TOC](#table-of-contents)

TODO
====

* Re-implement `ngx_lua`'s cosocket API with FFI.
* Re-implement `ngx_lua`'s `ngx.eof` and `ngx.flush` API functions with FFI.

[Back to TOC](#table-of-contents)

Author
======

Yichun "agentzh" Zhang (章亦春) <agentzh@gmail.com>, OpenResty Inc.

[Back to TOC](#table-of-contents)

Copyright and License
=====================

This module is licensed under the BSD license.

Copyright (C) 2013-2019, by Yichun "agentzh" Zhang, OpenResty Inc.

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

[Back to TOC](#table-of-contents)

See Also
========
* the ngx_lua module: https://github.com/openresty/lua-nginx-module#readme
* LuaJIT FFI: http://luajit.org/ext_ffi.html

[Back to TOC](#table-of-contents)

