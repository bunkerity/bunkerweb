Name
====

ngx.ssl - Lua API for controlling NGINX downstream SSL handshakes

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
* [Description](#description)
* [Methods](#methods)
    * [clear_certs](#clear_certs)
    * [cert_pem_to_der](#cert_pem_to_der)
    * [set_der_cert](#set_der_cert)
    * [priv_key_pem_to_der](#priv_key_pem_to_der)
    * [set_der_priv_key](#set_der_priv_key)
    * [server_name](#server_name)
    * [server_port](#server_port)
    * [raw_server_addr](#raw_server_addr)
    * [raw_client_addr](#raw_client_addr)
    * [get_tls1_version](#get_tls1_version)
    * [get_tls1_version_str](#get_tls1_version_str)
    * [parse_pem_cert](#parse_pem_cert)
    * [parse_pem_priv_key](#parse_pem_priv_key)
    * [set_cert](#set_cert)
    * [set_priv_key](#set_priv_key)
    * [verify_client](#verify_client)
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
# Note: you do not need the following line if you are using
# OpenResty 1.9.7.2+.
lua_package_path "/path/to/lua-resty-core/lib/?.lua;;";

server {
    listen 443 ssl;
    server_name   test.com;

    # useless placeholders: just to shut up NGINX configuration
    # loader errors:
    ssl_certificate /path/to/fallback.crt;
    ssl_certificate_key /path/to/fallback.key;

    ssl_certificate_by_lua_block {
        local ssl = require "ngx.ssl"

        -- clear the fallback certificates and private keys
        -- set by the ssl_certificate and ssl_certificate_key
        -- directives above:
        local ok, err = ssl.clear_certs()
        if not ok then
            ngx.log(ngx.ERR, "failed to clear existing (fallback) certificates")
            return ngx.exit(ngx.ERROR)
        end

        -- assuming the user already defines the my_load_certificate_chain()
        -- herself.
        local pem_cert_chain = assert(my_load_certificate_chain())

        local der_cert_chain, err = ssl.cert_pem_to_der(pem_cert_chain)
        if not der_cert_chain then
            ngx.log(ngx.ERR, "failed to convert certificate chain ",
                    "from PEM to DER: ", err)
            return ngx.exit(ngx.ERROR)
        end

        local ok, err = ssl.set_der_cert(der_cert_chain)
        if not ok then
            ngx.log(ngx.ERR, "failed to set DER cert: ", err)
            return ngx.exit(ngx.ERROR)
        end

        -- assuming the user already defines the my_load_private_key()
        -- function herself.
        local pem_pkey = assert(my_load_private_key())
        local passphrase = "password" -- or nil

        local der_pkey, err = ssl.priv_key_pem_to_der(pem_pkey, passphrase)
        if not der_pkey then
            ngx.log(ngx.ERR, "failed to convert private key ",
                    "from PEM to DER: ", err)
            return ngx.exit(ngx.ERROR)
        end

        local ok, err = ssl.set_der_priv_key(der_pkey)
        if not ok then
            ngx.log(ngx.ERR, "failed to set DER private key: ", err)
            return ngx.exit(ngx.ERROR)
        end
    }

    location / {
        root html;
    }
}
```

Description
===========

This Lua module provides API functions to control the SSL handshake process in contexts like
[ssl_certificate_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_certificate_by_lua_block)
(of the [ngx_lua](https://github.com/openresty/lua-nginx-module#readme) module).

For web servers serving many (like millions of) https sites, it is often desired to lazily
load and cache the SSL certificate chain and private key data for the https sites actually
being served by a particular server. This Lua module provides API to support such use cases
in the context of the [ssl_certificate_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_certificate_by_lua_block)
directive.

To load the `ngx.ssl` module in Lua, just write

```lua
local ssl = require "ngx.ssl"
```

[Back to TOC](#table-of-contents)

Methods
=======

clear_certs
-----------
**syntax:** *ok, err = ssl.clear_certs()*

**context:** *ssl_certificate_by_lua&#42;*

Clears any existing SSL certificates and/or private keys set on the current SSL connection.

Returns `true` on success, or a `nil` value and a string describing the error otherwise.

[Back to TOC](#table-of-contents)

cert_pem_to_der
---------------
**syntax:** *der_cert_chain, err = ssl.cert_pem_to_der(pem_cert_chain)*

**context:** *any*

Converts the PEM-formatted SSL certificate chain data into the DER format (for later uses
in the [set_der_cert](#set_der_cert)
function, for example).

In case of failures, returns `nil` and a string describing the error.

It is known that the `openssl` command-line utility may not convert the whole SSL
certificate chain from PEM to DER correctly. So always use this Lua function to do
the conversion. You can always use libraries like [lua-resty-lrucache](https://github.com/openresty/lua-resty-lrucache#readme)
and/or ngx_lua APIs like [lua_shared_dict](https://github.com/openresty/lua-nginx-module#lua_shared_dict)
to do the caching of the DER-formatted results, for example.

This function can be called in any context.

[Back to TOC](#table-of-contents)

set_der_cert
------------
**syntax:** *ok, err = ssl.set_der_cert(der_cert_chain)*

**context:** *ssl_certificate_by_lua&#42;*

Sets the DER-formatted SSL certificate chain data for the current SSL connection. Note that
the DER data is
directly in the Lua string argument. *No* external file names are supported here.

Returns `true` on success, or a `nil` value and a string describing the error otherwise.

Note that, the SSL certificate chain is usually encoded in the PEM format. So you need
to use the [cert_pem_to_der](#cert_pem_to_der)
function to do the conversion first.

[Back to TOC](#table-of-contents)

priv_key_pem_to_der
-------------------
**syntax:** *der_priv_key, err = ssl.priv_key_pem_to_der(pem_priv_key, passphrase)*

**context:** *any*

Converts the PEM-formatted SSL private key data into the DER format (for later uses
in the [set_der_priv_key](#set_der_priv_key)
function, for example).

The `passphrase` is the passphrase for `pem_priv_key` if the private key is password protected.

In case of failures, returns `nil` and a string describing the error.

Alternatively, you can do the PEM to DER conversion *offline* with the `openssl` command-line utility, like below

```bash
openssl rsa -in key.pem -outform DER -out key.der
```

This function can be called in any context.

[Back to TOC](#table-of-contents)

set_der_priv_key
----------------
**syntax:** *ok, err = ssl.set_der_priv_key(der_priv_key)*

**context:** *ssl_certificate_by_lua&#42;*

Sets the DER-formatted prviate key for the current SSL connection.

Returns `true` on success, or a `nil` value and a string describing the error otherwise.

Usually, the private keys are encoded in the PEM format. You can either use the
[priv_key_pem_to_der](#priv_key_pem_to_der) function
to do the PEM to DER conversion or just use
the `openssl` command-line utility offline, like below

```bash
openssl rsa -in key.pem -outform DER -out key.der
```

[Back to TOC](#table-of-contents)

server_name
-----------
**syntax:** *name, err = ssl.server_name()*

**context:** *any*

Returns the TLS SNI (Server Name Indication) name set by the client. Returns `nil`
when the client does not set it.

In case of failures, it returns `nil` *and* a string describing the error.

Usually we use this SNI name as the domain name (like `www.openresty.org`) to
identify the current web site while loading the corresponding SSL certificate
chain and private key for the site.

Please note that not all https clients set the SNI name, so when the SNI name is
missing from the client handshake request, we use the server IP address accessed
by the client to identify the site. See the [raw_server_addr](#raw_server_addr) method
for more details.

This function can be called in any context where downstream https is used.

[Back to TOC](#table-of-contents)

server_port
-----------
**syntax:** port, err = ssl.server_port()

**context:** *any*

Returns the server port. Returns `nil`
when server dont have a port.

In case of failures, it returns `nil` *and* a string describing the error.

This function can be called in any context where downstream https is used.

[Back to TOC](#table-of-contents)

raw_server_addr
---------------
**syntax:** *addr_data, addr_type, err = ssl.raw_server_addr()*

**context:** *any*

Returns the raw server address actually accessed by the client in the current SSL connection.

The first two return values are strings representing the address data and the address type, respectively.
The address values are interpreted differently according to the address type values:

* `unix`
: The address data is a file path for the UNIX domain socket.
* `inet`
: The address data is a binary IPv4 address of 4 bytes long.
* `inet6`
: The address data is a binary IPv6 address of 16 bytes long.

Returns two `nil` values and a Lua string describing the error.

The following code snippet shows how to print out the UNIX domain socket address and
the IPv4 address as human-readable strings:

```lua
local ssl = require "ngx.ssl"
local byte = string.byte

local addr, addrtyp, err = ssl.raw_server_addr()
if not addr then
    ngx.log(ngx.ERR, "failed to fetch raw server addr: ", err)
    return
end

if addrtyp == "inet" then  -- IPv4
    ip = string.format("%d.%d.%d.%d", byte(addr, 1), byte(addr, 2),
                       byte(addr, 3), byte(addr, 4))
    print("Using IPv4 address: ", ip)

elseif addrtyp == "unix" then  -- UNIX
    print("Using unix socket file ", addr)

else  -- IPv6
    -- leave as an exercise for the readers
end
```

This function can be called in any context where downstream https is used.

[Back to TOC](#table-of-contents)

raw_client_addr
---------------
**syntax:** *addr_data, addr_type, err = ssl.raw_client_addr()*

**context:** *any*

Returns the raw client address of the current SSL connection.

The first two return values are strings representing the address data and the address type, respectively.
The address values are interpreted differently according to the address type values:

* `unix`
: The address data is a file path for the UNIX domain socket.
* `inet`
: The address data is a binary IPv4 address of 4 bytes long.
* `inet6`
: The address data is a binary IPv6 address of 16 bytes long.

Returns two `nil` values and a Lua string describing the error.

The following code snippet shows how to print out the UNIX domain socket address and
the IPv4 address as human-readable strings:

```lua
local ssl = require "ngx.ssl"
local byte = string.byte

local addr, addrtyp, err = ssl.raw_client_addr()
if not addr then
    ngx.log(ngx.ERR, "failed to fetch raw client addr: ", err)
    return
end

if addrtyp == "inet" then  -- IPv4
    ip = string.format("%d.%d.%d.%d", byte(addr, 1), byte(addr, 2),
                       byte(addr, 3), byte(addr, 4))
    print("Client IPv4 address: ", ip)

elseif addrtyp == "unix" then  -- UNIX
    print("Client unix socket file ", addr)

else  -- IPv6
    -- leave as an exercise for the readers
end
```

This function can be called in any context where downstream https is used.

This function was first introduced in lua-resty-core 0.1.14.

[Back to TOC](#table-of-contents)

get_tls1_version
----------------
**syntax:** *ver, err = ssl.get_tls1_version()*

**context:** *any*

Returns the TLS 1.x version number used by the current SSL connection. Returns `nil` and
a string describing the error otherwise.

Typical return values are:

* `0x0300`(SSLv3)
* `0x0301`(TLSv1)
* `0x0302`(TLSv1.1)
* `0x0303`(TLSv1.2)
* `0x0304`(TLSv1.3)

This function can be called in any context where downstream https is used.

[Back to TOC](#table-of-contents)

get_tls1_version_str
--------------------
**syntax:** *ver, err = ssl.get_tls1_version_str()*

**context:** *any*

Returns the TLS 1.x version string used by the current SSL connection. Returns `nil` and
a string describing the error otherwise.

If the TLS 1.x version number used by the current SSL connection is not
recognized, the return values will be `nil` and the string "unknown version".

Typical return values are:

* `SSLv3`
* `TLSv1`
* `TLSv1.1`
* `TLSv1.2`
* `TLSv1.3`

This function can be called in any context where downstream https is used.

[Back to TOC](#table-of-contents)

parse_pem_cert
--------------
**syntax:** *cert_chain, err = ssl.parse_pem_cert(pem_cert_chain)*

**context:** *any*

Converts the PEM-formated SSL certificate chain data into an opaque cdata pointer (for later uses
in the [set_cert](#set_cert)
function, for example).

In case of failures, returns `nil` and a string describing the error.

You can always use libraries like [lua-resty-lrucache](https://github.com/openresty/lua-resty-lrucache#readme)
to cache the cdata result.

This function can be called in any context.

This function was first added in version `0.1.7`.

[Back to TOC](#table-of-contents)

parse_pem_priv_key
------------------
**syntax:** *priv_key, err = ssl.parse_pem_priv_key(pem_priv_key)*

**context:** *any*

Converts the PEM-formatted SSL private key data into an opaque cdata pointer (for later uses
in the [set_priv_key](#set_priv_key)
function, for example).

In case of failures, returns `nil` and a string describing the error.

This function can be called in any context.

This function was first added in version `0.1.7`.

[Back to TOC](#table-of-contents)

set_cert
--------
**syntax:** *ok, err = ssl.set_cert(cert_chain)*

**context:** *ssl_certificate_by_lua&#42;*

Sets the SSL certificate chain opaque pointer returned by the
[parse_pem_cert](#parse_pem_cert) function for the current SSL connection.

Returns `true` on success, or a `nil` value and a string describing the error otherwise.

Note that this `set_cert` function will run slightly faster, in terms of CPU cycles wasted, than the
[set_der_cert](#set_der_cert) variant, since the first function uses opaque cdata pointers
which do not require any additional conversion needed to be performed by the SSL library during the SSL handshake.

This function was first added in version `0.1.7`.

[Back to TOC](#table-of-contents)

set_priv_key
------------
**syntax:** *ok, err = ssl.set_priv_key(priv_key)*

**context:** *ssl_certificate_by_lua&#42;*

Sets the SSL private key opaque pointer returned by the
[parse_pem_priv_key](#parse_pem_priv_key) function for the current SSL connection.

Returns `true` on success, or a `nil` value and a string describing the error otherwise.

Note that this `set_priv_key` function will run slightly faster, in terms of CPU cycles wasted, than the
[set_der_priv_key](#set_der_priv_key) variant, since the first function uses opaque cdata pointers
which do not require any additional conversion needed to be performed by the SSL library during the SSL handshake.

This function was first added in version `0.1.7`.

[Back to TOC](#table-of-contents)

verify_client
-------------
**syntax:** *ok, err = ssl.verify_client(ca_certs?, depth?)*

**context:** *ssl_certificate_by_lua&#42;*

Requires a client certificate during TLS handshake.

The `ca_certs` is the CA certificate chain opaque pointer returned by the
[parse_pem_cert](#parse_pem_cert) function for the current SSL connection.
The list of certificates will be sent to clients. Also, they will be added to trusted store.
If omitted, will not send any CA certificate to clients.

The `depth` is the verification depth in the client certificates chain.
If omitted, will use the value specified by `ssl_verify_depth`.

Returns `true` on success, or a `nil` value and a string describing the error otherwise.

Note that TLS is not terminated when verification fails. You need to examine Nginx variable `$ssl_client_verify`
later to determine next steps.

This function was first added in version `0.1.20`.

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
* the [ngx.ocsp](ocsp.md) module.
* the [ssl_certificate_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_certificate_by_lua_block) directive.
* the [lua-resty-core](https://github.com/openresty/lua-resty-core) library.
* OpenResty: https://openresty.org

[Back to TOC](#table-of-contents)
