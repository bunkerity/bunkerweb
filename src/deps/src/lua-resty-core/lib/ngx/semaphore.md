Name
====

ngx.semaphore - light thread semaphore for OpenResty/ngx_lua.

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
    * [Synchronizing threads in the same context](#synchronizing-threads-in-the-same-context)
    * [Synchronizing threads in different contexts](#synchronizing-threads-in-different-contexts)
* [Description](#description)
* [Methods](#methods)
    * [new](#new)
    * [post](#post)
    * [wait](#wait)
    * [count](#count)
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

Synchronizing threads in the same context
-----------------------------------------

```nginx
location = /t {
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sema = semaphore.new()

        local function handler()
            ngx.say("sub thread: waiting on sema...")

            local ok, err = sema:wait(1)  -- wait for a second at most
            if not ok then
                ngx.say("sub thread: failed to wait on sema: ", err)
            else
                ngx.say("sub thread: waited successfully.")
            end
        end

        local co = ngx.thread.spawn(handler)

        ngx.say("main thread: sleeping for a little while...")

        ngx.sleep(0.1)  -- wait a bit

        ngx.say("main thread: posting to sema...")

        sema:post(1)

        ngx.say("main thread: end.")
    }
}
```

The example location above produces a response output like this:

```
sub thread: waiting on sema...
main thread: sleeping for a little while...
main thread: posting to sema...
main thread: end.
sub thread: waited successfully.
```

[Back to TOC](#table-of-contents)

Synchronizing threads in different contexts
-------------------------------------------

```nginx
location = /t {
    content_by_lua_block {
        local semaphore = require "ngx.semaphore"
        local sema = semaphore.new()

        local outputs = {}
        local i = 1

        local function out(s)
            outputs[i] = s
            i = i + 1
        end

        local function handler()
            out("timer thread: sleeping for a little while...")

            ngx.sleep(0.1)  -- wait a bit

            out("timer thread: posting on sema...")

            sema:post(1)
        end

        assert(ngx.timer.at(0, handler))

        out("main thread: waiting on sema...")

        local ok, err = sema:wait(1)  -- wait for a second at most
        if not ok then
            out("main thread: failed to wait on sema: ", err)
        else
            out("main thread: waited successfully.")
        end

        out("main thread: end.")

        ngx.say(table.concat(outputs, "\n"))
    }
}
```

The example location above produces a response body like this

```
main thread: waiting on sema...
timer thread: sleeping for a little while...
timer thread: posting on sema...
main thread: waited successfully.
main thread: end.
```

The same applies to different request contexts as long as these requests are served
by the same nginx worker process.

[Back to TOC](#table-of-contents)

Description
===========

This module provides an efficient semaphore API for the OpenResty/ngx_lua module. With
semaphores, "light threads" (created by [ngx.thread.spawn](https://github.com/openresty/lua-nginx-module#ngxthreadspawn),
[ngx.timer.at](https://github.com/openresty/lua-nginx-module#ngxtimerat), and etc.) can
synchronize among each other very efficiently without constant polling and sleeping.

"Light threads" in different contexts (like in different requests) can share the same
semaphore instance as long as these "light threads" reside in the same NGINX worker
process and the [lua_code_cache](https://github.com/openresty/lua-nginx-module#lua_code_cache)
directive is turned on (which is the default). For inter-process "light thread" synchronization,
it is recommended to use the [lua-resty-lock](https://github.com/openresty/lua-resty-lock) library instead
(which is a bit less efficient than this semaphore API though).

This semaphore API has a pure userland implementation which does not involve any system calls nor
block any operating system threads. It works closely with the event model of NGINX without
introducing any extra delay.

Like other APIs provided by this `lua-resty-core` library, the LuaJIT FFI feature is required.

[Back to TOC](#table-of-contents)

Methods
=======

[Back to TOC](#table-of-contents)

new
---
**syntax:** *sema, err = semaphore_module.new(n?)*

**context:** *init_by_lua&#42;, init_worker_by_lua&#42;, set_by_lua&#42;, rewrite_by_lua&#42;, access_by_lua&#42;, content_by_lua&#42;, header_filter_by_lua&#42;, body_filter_by_lua&#42;, log_by_lua&#42;, ngx.timer.&#42;*

Creates and returns a new semaphore instance that has `n` (default to `0`) resources.

For example,

```lua
 local semaphore = require "ngx.semaphore"
 local sema, err = semaphore.new()
 if not sema then
     ngx.say("create semaphore failed: ", err)
 end
```

Often the semaphore object created is shared on the NGINX worker process by mounting in a custom Lua module, as
documented below:

https://github.com/openresty/lua-nginx-module#data-sharing-within-an-nginx-worker

[Back to TOC](#table-of-contents)

post
--------
**syntax:** *sema:post(n?)*

**context:** *init_by_lua&#42;, init_worker_by_lua&#42;, set_by_lua&#42;, rewrite_by_lua&#42;, access_by_lua&#42;, content_by_lua&#42;, header_filter_by_lua&#42;, body_filter_by_lua&#42;, log_by_lua&#42;, ngx.timer.&#42;*

Releases `n` (default to `1`) "resources" to the semaphore instance.

This will not yield the current running "light thread".

At most `n` "light threads" will be waken up when the current running "light thread" later yields (or terminates).

```lua
-- typically, we get the semaphore instance from upvalue or globally shared data
-- See https://github.com/openresty/lua-nginx-module#data-sharing-within-an-nginx-worker

local semaphore = require "ngx.semaphore"
local sema = semaphore.new()

sema:post(2)  -- releases 2 resources
```

[Back to TOC](#table-of-contents)

wait
----
**syntax:** *ok, err = sema:wait(timeout)*

**context:** *rewrite_by_lua&#42;, access_by_lua&#42;, content_by_lua&#42;, ngx.timer.&#42;*

Requests a resource from the semaphore instance.

Returns `true` immediately when there is resources available for the current running "light thread".
Otherwise the current "light thread" will enter the waiting queue and yield execution.
The current "light thread" will be automatically waken up and the `wait` function call
will return `true` when there is resources available for it, or return `nil` and a string describing
the error in case of failure (like `"timeout"`).

The `timeout` argument specifies the maximum time this function call should wait for (in seconds).

When the `timeout` argument is 0, it means "no wait", that is, when there is no readily available
"resources" for the current running "light thread", this `wait` function call returns immediately
`nil` and the error string `"timeout"`.

You can specify millisecond precision in the timeout value by using floating point numbers like 0.001 (which means 1ms).

"Light threads" created by different contexts (like request handlers) can wait on the
same semaphore instance without problem.

See [Synopsis](#synopsis) for code examples.

[Back to TOC](#table-of-contents)

count
--------
**syntax:** *count = sema:count()*

**context:** *init_by_lua&#42;, init_worker_by_lua&#42;, set_by_lua&#42;, rewrite_by_lua&#42;, access_by_lua&#42;,
content_by_lua&#42;, header_filter_by_lua&#42;, body_filter_by_lua&#42;, log_by_lua&#42;, ngx.timer.&#42;*

Returns the number of resources readily available in the `sema` semaphore instance (if any).

When the returned number is negative, it means the number of "light threads" waiting on
this semaphore.

Consider the following example,

```lua
local semaphore = require "ngx.semaphore"
local sema = semaphore.new(0)

ngx.say("count: ", sema:count())  -- count: 0

local function handler(id)
    local ok, err = sema:wait(1)
    if not ok then
        ngx.say("err: ", err)
    else
        ngx.say("wait success")
    end
end

local co1 = ngx.thread.spawn(handler)
local co2 = ngx.thread.spawn(handler)

ngx.say("count: ", sema:count())  -- count: -2

sema:post(1)

ngx.say("count: ", sema:count())  -- count: -1

sema:post(2)

ngx.say("count: ", sema:count())  -- count: 1
```

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

Weixie Cui, Kugou Inc.

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
* the [lua-resty-core](https://github.com/openresty/lua-resty-core) library.
* the ngx_lua module: https://github.com/openresty/lua-nginx-module
* OpenResty: https://openresty.org

[Back to TOC](#table-of-contents)

