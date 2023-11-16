Name
====

ngx.ssl.clienthello - Lua API for post-processing SSL client hello message for NGINX downstream SSL connections.

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
* [Description](#description)
* [Methods](#methods)
    * [get_client_hello_server_name](#get_client_hello_server_name)
    * [get_client_hello_ext](#get_client_hello_ext)
    * [set_protocols](#set_protocols)
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

```nginx
# nginx.conf

server {
    listen 443 ssl;
    server_name   test.com;
    ssl_certificate /path/to/cert.crt;
    ssl_certificate_key /path/to/key.key;
    ssl_client_hello_by_lua_block {
        local ssl_clt = require "ngx.ssl.clienthello"
        local host, err = ssl_clt.get_client_hello_server_name()
        if host == "test.com" then
            ssl_clt.set_protocols({"TLSv1", "TLSv1.1"})
        elseif host == "test2.com" then
            ssl_clt.set_protocols({"TLSv1.2", "TLSv1.3"})
        elseif not host then
            ngx.log(ngx.ERR, "failed to get the SNI name: ", err)
            ngx.exit(ngx.ERROR)
        else
            ngx.log(ngx.ERR, "unknown SNI name: ", host)
            ngx.exit(ngx.ERROR)
        end
    }
    ...
}
server {
    listen 443 ssl;
    server_name   test2.com;
    ssl_certificate /path/to/cert.crt;
    ssl_certificate_key /path/to/key.key;
    ...
}
```

Description
===========

This Lua module provides API functions for post-processing SSL client hello message for NGINX downstream connections.

It must to be used in the contexts [ssl_client_hello_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_client_hello_by_lua_block).

This Lua API is particularly useful for dynamically setting the SSL protocols according to the SNI.

It is also useful to do some custom operations according to the per-connection information in the client hello message.

For example, one can parse the custom client hello extension and do the corresponding handling in pure Lua.

To load the `ngx.ssl.clienthello` module in Lua, just write

```lua
local ssl_clt = require "ngx.ssl.clienthello"
```

[Back to TOC](#table-of-contents)

Methods
=======

get_client_hello_server_name
--------------
**syntax:** *host, err = ssl_clt.get_client_hello_server_name()*

**context:** *ssl_client_hello_by_lua&#42;*

Returns the TLS SNI (Server Name Indication) name set by the client.

Return `nil` when then the extension does not exist.

In case of errors, it returns `nil` and a string describing the error.

Note that the SNI name is gotten from the raw extensions of the client hello message associated with the current downstream SSL connection.

So this function can only be called in the context of [ssl_client_hello_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_client_hello_by_lua_block).

[Back to TOC](#table-of-contents)

get_supported_versions
--------------
**syntax:** *types, err = ssl_clt.get_supported_versions()*

**context:** *ssl_client_hello_by_lua&#42;*

Returns the table of ssl hello supported versions set by the client.

Return `nil` when then the extension does not exist.

In case of errors, it returns `nil` and a string describing the error.

Note that the types is gotten from the raw extensions of the client hello message associated with the current downstream SSL connection.

So this function can only be called in the context of [ssl_client_hello_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_client_hello_by_lua_block).

[Back to TOC](#table-of-contents)

get_client_hello_ext
----------------------
**syntax:** *ext, err = ssl_clt.get_client_hello_ext(ext_type)*

**context:** *ssl_client_hello_by_lua&#42;*

Returns raw data of arbitrary SSL client hello extension including custom extensions.

Returns `nil` if the specified extension type does not exist.

In case of errors, it returns `nil` and a string describing the error.

Note that the ext is gotten from the raw extensions of the client hello message associated with the current downstream SSL connection.

So this function can only be called in the context of [ssl_client_hello_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_client_hello_by_lua_block).

Example:

Gets server name from raw extension data. The `0` in `ssl_clt.get_client_hello_ext(0)` denotes `TLSEXT_TYPE_server_name`, and the `0` in `byte(ext, 3) ~= 0` denotes `TLSEXT_NAMETYPE_host_name`.

```nginx
# nginx.conf
server {
    listen 443 ssl;
    server_name   test.com;
    ssl_client_hello_by_lua_block {
        local ssl_clt = require "ngx.ssl.clienthello"
        local byte = string.byte
        local ext = ssl_clt.get_client_hello_ext(0)
        if not ext then
            print("failed to get_client_hello_ext(0)")
            ngx.exit(ngx.ERROR)
        end
        local total_len = string.len(ext)
        if total_len <= 2 then
            print("bad SSL Client Hello Extension")
            ngx.exit(ngx.ERROR)
        end
        local len = byte(ext, 1) * 256 + byte(ext, 2)
        if len + 2 ~= total_len then
            print("bad SSL Client Hello Extension")
            ngx.exit(ngx.ERROR)
        end
        if byte(ext, 3) ~= 0 then
            print("bad SSL Client Hello Extension")
            ngx.exit(ngx.ERROR)
        end
        if total_len <= 5 then
            print("bad SSL Client Hello Extension")
            ngx.exit(ngx.ERROR)
        end
        len = byte(ext, 4) * 256 + byte(ext, 5)
        if len + 5 > total_len then
            print("bad SSL Client Hello Extension")
            ngx.exit(ngx.ERROR)
        end
        local name = string.sub(ext, 6, 6 + len -1)

        print("read SNI name from Lua: ", name)
    }
    ssl_certificate test.crt;
    ssl_certificate_key test.key;
}
```

[Back to TOC](#table-of-contents)

set_protocols
----------------------
**syntax:** *ok, err = ssl_clt.set_protocols(protocols)*

**context:** *ssl_client_hello_by_lua&#42;*

Sets the SSL protocols supported by the current downstream SSL connection.

Returns `true` on success, or a `nil` value and a string describing the error otherwise.

Considering it is meaningless to set ssl protocols after the protocol is determined,
so this function may only be called in the context of [ssl_client_hello_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_client_hello_by_lua_block).

Example: `ssl_clt.set_protocols({"TLSv1.1", "TLSv1.2", "TLSv1.3"})`

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

Zhefeng Chen &lt;chzf\_zju@163.com&gt; (catbro666)

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
* the [ssl_client_hello_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_client_hello_by_lua_block) directive.
* the [lua-resty-core](https://github.com/openresty/lua-resty-core) library.
* OpenResty: https://openresty.org

[Back to TOC](#table-of-contents)
