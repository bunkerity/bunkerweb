Name
====

ngx.ocsp - Lua API for implementing OCSP stapling in ssl_certificate_by_lua*

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
* [Description](#description)
* [Methods](#methods)
    * [get_ocsp_responder_from_der_chain](#get_ocsp_responder_from_der_chain)
    * [create_ocsp_request](#create_ocsp_request)
    * [validate_ocsp_response](#validate_ocsp_response)
    * [set_ocsp_status_resp](#set_ocsp_status_resp)
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
        local ocsp = require "ngx.ocsp"
        local http = require "resty.http.simple"

        -- assuming the user already defines the my_load_certificate_chain()
        -- herself.
        local pem_cert_chain = assert(my_load_certificate_chain())

        local der_cert_chain, err = ssl.cert_pem_to_der(pem_cert_chain)
        if not der_cert_chain then
            ngx.log(ngx.ERR, "failed to convert certificate chain ",
                    "from PEM to DER: ", err)
            return ngx.exit(ngx.ERROR)
        end

        local ocsp_url, err = ocsp.get_ocsp_responder_from_der_chain(der_cert_chain)
        if not ocsp_url then
            ngx.log(ngx.ERR, "failed to get OCSP responder: ", err)
            return ngx.exit(ngx.ERROR)
        end

        print("ocsp_url: ", ocsp_url)

        -- use cosocket-based HTTP client libraries like lua-resty-http-simple
        -- to send the request (url + ocsp_req as POST params or URL args) to
        -- CA's OCSP server. assuming the server returns the OCSP response
        -- in the Lua variable, resp.

        local schema, host, port, ocsp_uri, err = parse_url(ocsp_url)

        local ocsp_req, err = ocsp.create_ocsp_request(der_cert_chain)
        if not ocsp_req then
            ngx.log(ngx.ERR, "failed to create OCSP request: ", err)
            return ngx.exit(ngx.ERROR)
        end

        local res, err = http.request(host, port, {
            path = ocsp_uri,
            headers = { Host = host,
                        ["Content-Type"] = "application/ocsp-request" },
            timeout = 10000,  -- 10 sec
            method = "POST",
            body = ocsp_req,
            maxsize = 102400,  -- 100KB
        })

        if not res then
            ngx.log(ngx.ERR, "OCSP responder query failed: ", err)
            return ngx.exit(ngx.ERROR)
        end

        local http_status = res.status

        if http_status ~= 200 then
            ngx.log(ngx.ERR, "OCSP responder returns bad HTTP status code ",
                    http_status)
            return ngx.exit(ngx.ERROR)
        end

        local ocsp_resp = res.body

        if ocsp_resp and #ocsp_resp > 0 then
            local ok, err = ocsp.validate_ocsp_response(ocsp_resp, der_cert_chain)
            if not ok then
                ngx.log(ngx.ERR, "failed to validate OCSP response: ", err)
                return ngx.exit(ngx.ERROR)
            end

            -- set the OCSP stapling
            ok, err = ocsp.set_ocsp_status_resp(ocsp_resp)
            if not ok then
                ngx.log(ngx.ERR, "failed to set ocsp status resp: ", err)
                return ngx.exit(ngx.ERROR)
            end
        end
    }

    location / {
        root html;
    }
}

```

Description
===========

This Lua module provides API to perform OCSP queries, OCSP response validations, and
OCSP stapling planting.

Usually, this module is used together with the [ngx.ssl](ssl.md) module in the
context of [ssl_certificate_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_certificate_by_lua_block)
(of the [ngx_lua](https://github.com/openresty/lua-nginx-module#readme) module).

To load the `ngx.ocsp` module in Lua, just write

```lua
local ocsp = require "ngx.ocsp"
```

[Back to TOC](#table-of-contents)

Methods
=======

get_ocsp_responder_from_der_chain
---------------------------------
**syntax:** *ocsp_url, err = ocsp.get_ocsp_responder_from_der_chain(der_cert_chain, max_len)*

**context:** *any*

Extracts the OCSP responder URL (like `"http://test.com/ocsp/"`) from the SSL server certificate chain in the DER format.

Usually the SSL server certificate chain is originally formatted in PEM. You can use the Lua API
provided by the [ngx.ssl](ssl.md) module to do the PEM to DER conversion.

The optional `max_len` argument specifies the maximum length of OCSP URL allowed. This determines
the buffer size; so do not specify an unnecessarily large value here. It defaults to the internal
string buffer size used throughout this `lua-resty-core` library (usually default to 4KB).

In case of failures, returns `nil` and a string describing the error.

[Back to TOC](#table-of-contents)

create_ocsp_request
-------------------
**syntax:** *ocsp_req, err = ocsp.create_ocsp_request(der_cert_chain, max_len)*

**context:** *any*

Builds an OCSP request from the SSL server certificate chain in the DER format, which
can be used to send to the OCSP server for validation.

The optional `max_len` argument specifies the maximum length of the OCSP request allowed.
This value determines the size of the internal buffer allocated, so do not specify an
unnecessarily large value here. It defaults to the internal string buffer size used
throughout this `lua-resty-core` library (usually defaults to 4KB).

In case of failures, returns `nil` and a string describing the error.

The raw OCSP response data can be used as the request body directly if the POST method
is used for the OCSP request. But for GET requests, you need to do base64 encoding and
then URL encoding on the data yourself before appending it to the OCSP URL obtained
by the [get_ocsp_responder_from_der_chain](#get_ocsp_responder_from_der_chain) function.

[Back to TOC](#table-of-contents)

validate_ocsp_response
----------------------
**syntax:** *ok, err = ocsp.validate_ocsp_response(ocsp_resp, der_cert_chain, max_err_msg_len)*

**context:** *any*

Validates the raw OCSP response data specified by the `ocsp_resp` argument using the SSL
server certificate chain in DER format as specified in the `der_cert_chain` argument.

Returns true when the validation is successful.

In case of failures, returns `nil` and a string
describing the failure. The maximum
length of the error string is controlled by the optional `max_err_msg` argument (which defaults
to the default internal string buffer size used throughout this `lua-resty-core` library, usually
being 4KB).

[Back to TOC](#table-of-contents)

set_ocsp_status_resp
--------------------
**syntax:** *ok, err = ocsp.set_ocsp_status_resp(ocsp_resp)*

**context:** *ssl_certificate_by_lua&#42;*

Sets the OCSP response as the OCSP stapling for the current SSL connection.

Returns `true` in case of successes. If the SSL client does not send a "status request"
at all, then this method still returns `true` but also with a string as the warning
`"no status req"`.

In case of failures, returns `nil` and a string describing the error.

The OCSP response is returned from CA's OCSP server. See the [create_ocsp_request](#create_ocsp_request)
function for how to create an OCSP request and also [validate_ocsp_response](#validate_ocsp_response)
for how to validate the OCSP response.

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
* the [ngx.ssl](ssl.md) module.
* the [ssl_certificate_by_lua*](https://github.com/openresty/lua-nginx-module/#ssl_certificate_by_lua_block) directive.
* the [lua-resty-core](https://github.com/openresty/lua-resty-core) library.
* OpenResty: https://openresty.org

[Back to TOC](#table-of-contents)
