Name
====

ngx.resp - Lua API for HTTP response handling.

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
* [Description](#description)
* [Methods](#methods)
    * [add_header](#add_header)
* [Community](#community)
    * [English Mailing List](#english-mailing-list)
    * [Chinese Mailing List](#chinese-mailing-list)
* [Bugs and Patches](#bugs-and-patches)
* [Copyright and License](#copyright-and-license)
* [See Also](#see-also)

Status
======

This Lua module is currently considered experimental.

Synopsis
========

```lua
local ngx_resp = require "ngx.resp"

-- add_header
ngx_resp.add_header("Foo", "bar")
ngx_resp.add_header("Foo", "baz")
--> there will be two new headers in HTTP response:
--> Foo: bar and Foo: baz
```

[Back to TOC](#table-of-contents)

Description
===========

This Lua module provides Lua API which could be used to handle HTTP response.

[Back to TOC](#table-of-contents)

Methods
=======

All the methods of this module are static (or module-level). That is, you do
not need an object (or instance) to call these methods.

[Back to TOC](#table-of-contents)

add_header
----------
**syntax:** *ngx_resp.add_header(header_name, header_value)*

This function adds specified header with corresponding value to the response of
current request. The `header_value` could be either a string or a table.

The `ngx.resp.add_header` works mostly like:
* [ngx.header.HEADER](https://github.com/openresty/lua-nginx-module#ngxheaderheader)
* Nginx's [add_header](http://nginx.org/en/docs/http/ngx_http_headers_module.html#add_header) directive.

However, unlike `ngx.header.HEADER`, this method appends new header to the old
one instead of overriding it.

Unlike `add_header` directive, this method will override the builtin header
instead of appending it.

[Back to TOC](#table-of-contents)

Community
=========

[Back to TOC](#table-of-contents)

English Mailing List
--------------------

The [openresty-en](https://groups.google.com/group/openresty-en) mailing list
is for English speakers.

[Back to TOC](#table-of-contents)

Chinese Mailing List
--------------------

The [openresty](https://groups.google.com/group/openresty) mailing list is for
Chinese speakers.

[Back to TOC](#table-of-contents)

Bugs and Patches
================

Please report bugs or submit patches by

1. creating a ticket on the [GitHub Issue Tracker](https://github.com/openresty/lua-resty-core/issues),
1. or posting to the [OpenResty community](#community).

[Back to TOC](#table-of-contents)

Copyright and License
=====================

This module is licensed under the BSD license.

Copyright (C) 2018, by Yichun "agentzh" Zhang, OpenResty Inc.

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

[Back to TOC](#table-of-contents)

See Also
========
* the [lua-resty-core](https://github.com/openresty/lua-resty-core) library.
* the ngx_lua module: https://github.com/openresty/lua-nginx-module
* OpenResty: https://openresty.org

[Back to TOC](#table-of-contents)

