Name
====

`resty.core.time` - utility functions for time operations.

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
* [Description](#description)
* [Methods](#methods)
    * [monotonic_msec](#monotonic_msec)
    * [monotonic_time](#monotonic_time)
* [Community](#community)
    * [English Mailing List](#english-mailing-list)
    * [Chinese Mailing List](#chinese-mailing-list)
* [Bugs and Patches](#bugs-and-patches)
* [Copyright and License](#copyright-and-license)
* [See Also](#see-also)

Status
======

This Lua module is currently considered production ready.

Synopsis
========

```nginx
location = /t {
    content_by_lua_block {
        local time = require "resty.core.time"
        ngx.say(time.monotonic_time())
        ngx.say(time.monotonic_msec())
    }
}
```

The value get by `"resty.core.time".monotonic_time` should equal to the value from /proc/uptime.

[Back to TOC](#table-of-contents)

Description
===========

This module provides utility functions for the time operations.

[Back to TOC](#table-of-contents)

Methods
=======

monotonic_msec
--------------

**syntax:** *monotonic_msec()*

Returns the elapsed time in microseconds from the machine boot for the current time stamp from the Nginx cached time (no syscall involved unlike Lua's date library).

```lua
local cur_msec = require "resty.core.time".monotonic_msec
ngx.say(cur_msec())

```

This api was first introduced in lua-resty-core v0.1.25.

[Back to TOC](#table-of-contents)

monotonic_time
--------------

**syntax:** *monotonic_time()*

Returns a floating-point number for the elapsed time in seconds (including milliseconds as the decimal part) from the machine boot for the current time stamp from the Nginx cached time (no syscall involved unlike Lua's date library).

```lua
local cur_time = require "resty.core.time".monotonic_time
ngx.say(cur_time())

```

This api was first introduced in lua-resty-core v0.1.25.

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

Copyright (C) 2018, by OpenResty Inc.

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
