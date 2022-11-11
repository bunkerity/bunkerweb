Name
====

ngx.req - Lua API for HTTP request handling.

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
local ngx_req = require "ngx.req"

-- add_header
ngx_req.add_header("Foo", "bar")
ngx_req.add_header("Foo", "baz")

--> there will be two new headers in the HTTP request:
--> Foo: bar and Foo: baz
```

[Back to TOC](#table-of-contents)

Description
===========

This module provides a Lua API to handle HTTP requests.

[Back to TOC](#table-of-contents)

Methods
=======

All methods provided by this module are static (or module-level). That is, you
do not need an object (or instance) to call these methods.

[Back to TOC](#table-of-contents)

add_header
----------
**syntax:** *ngx_req.add_header(header_name, header_value)*

**context:** *set_by_lua&#42;, rewrite_by_lua&#42;, access_by_lua&#42;, content_by_lua&#42;, header_filter_by_lua&#42;, body_filter_by_lua&#42;*

This method adds the specified header and its value to the current
request. It works similarly as
[ngx.req.set_header](https://github.com/openresty/lua-nginx-module#ngxreqset_header),
with the exception that when the header already exists, the specified value(s)
will be appended instead of overriden.

The first argument `header_name` must be a non-empty string.

When the specified `header_name` is a builtin header (e.g. `User-Agent`), this
method will override its values.

The `header_value` argument can either be a string or a non-empty, array-like
table. A `nil` or empty table value will cause this function to throw an error.

This feature was first introduced in the `v0.1.18` release.

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

Copyright (C) 2016-2019, by Yichun "agentzh" Zhang, OpenResty Inc.

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

[Back to TOC](#table-of-contents)

See Also
========
* library [lua-resty-core](https://github.com/openresty/lua-resty-core)
* the ngx_lua module: https://github.com/openresty/lua-nginx-module
* OpenResty: https://openresty.org

[Back to TOC](#table-of-contents)

