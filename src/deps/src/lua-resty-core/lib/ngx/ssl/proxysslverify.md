Name
====

ngx.ssl.proxysslverify - Lua API for post-processing SSL server certificate message for NGINX upstream SSL connections.

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
* [Description](#description)
* [Methods](#methods)
    * [set_verify_result](#set_verify_result)
    * [get_verify_result](#get_verify_result)
    * [get_verify_cert](#get_verify_cert)
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

server {
    listen 443 ssl;
    server_name   test.com;
    ssl_certificate /path/to/cert.crt;
    ssl_certificate_key /path/to/key.key;

    location /t {
        proxy_ssl_certificate /path/to/cert.crt;
        proxy_ssl_certificate_key /path/to/key.key;
        proxy_pass https://upstream;

        proxy_ssl_verify_by_lua_block {
            local proxy_ssl_vfy = require "ngx.ssl.proxysslverify"

            local cert, err = proxy_ssl_vfy.get_verify_cert()

            -- ocsp to verify cert
            -- check crl

            proxy_ssl_vfy.set_verify_result(0)
        }
    }
    ...
 }
```

Description
===========

This Lua module provides API functions for post-processing SSL server certificate message for NGINX upstream connections.

It must be used in the context [proxy_ssl_verify_by_lua*](https://github.com/openresty/lua-nginx-module/#proxy_ssl_verify_by_lua_block).

This directive runs user Lua code when Nginx is about to post-process the SSL server certificate message for the upstream SSL (https) connections.

It is particularly useful to parse upstream server certificate and do some custom operations in pure lua.

To load the `ngx.ssl.proxysslverify` module in Lua, just write

```lua
local proxy_ssl_vfy = require "ngx.ssl.proxysslverify"
```

[Back to TOC](#table-of-contents)

Methods
=======

set_verify_result
-----------------
**syntax:** *ok, err = proxy_ssl_vfy.set_verify_result(0)*

**context:** *proxy_ssl_verify_by_lua&#42;*

According to openssl's doc of SSL_CTX_set_cert_verify_callback: In any case a viable verification result value must be reflected in the error member of x509_store_ctx, which can be done using X509_STORE_CTX_set_error. So after using Lua code to verify server certificate, we need to call this function to setup verify result. Please refers to openssl's `include/openssl/x509_vfy.h` to see which verify result code can be used.

In case of errors, it returns `nil` and a string describing the error.

This function can only be called in the context of [proxy_ssl_verify_by_lua*](https://github.com/openresty/lua-nginx-module/#proxy_ssl_verify_by_lua_block).

[Back to TOC](#table-of-contents)

get_verify_result
-----------------
**syntax:** *verify_result, err = proxy_ssl_vfy.get_verify_result()*

**context:** *proxy_ssl_verify_by_lua&#42;*

Returns the verify result code.

In case of errors, it returns `nil` and a string describing the error.

This function can only be called in the context of [proxy_ssl_verify_by_lua*](https://github.com/openresty/lua-nginx-module/#proxy_ssl_verify_by_lua_block).

[Back to TOC](#table-of-contents)

get_verify_cert
---------------
**syntax:** *cert, err = proxy_ssl_vfy.get_verify_cert()*

**context:** *proxy_ssl_verify_by_lua&#42;*

Returns the server certificate Nginx received from upstream SSL connection.

In case of errors, it returns `nil` and a string describing the error.

This function can only be called in the context of [proxy_ssl_verify_by_lua*](https://github.com/openresty/lua-nginx-module/#proxy_ssl_verify_by_lua_block).

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

Fuhong Ma &lt;willmafh@hotmail.com&gt; (willmafh)

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

See AlsoCopyright
========
* the ngx_lua module: https://github.com/openresty/lua-nginx-module
* the [proxy_ssl_verify_by_lua*](https://github.com/openresty/lua-nginx-module/#proxy_ssl_verify_by_lua_block) directive.
* the [lua-resty-core](https://github.com/openresty/lua-resty-core) library.
* OpenResty: https://openresty.org

[Back to TOC](#table-of-contents)
