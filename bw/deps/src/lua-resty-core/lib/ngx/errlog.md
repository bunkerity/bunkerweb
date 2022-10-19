Name
====

`ngx.errlog` - manage nginx error log data in Lua for OpenResty/ngx_lua.

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
    * [Capturing nginx error logs with specified log filtering level](#capturing-nginx-error-logs-with-specified-log-filtering-level)
* [Methods](#methods)
    * [set_filter_level](#set_filter_level)
    * [get_logs](#get_logs)
    * [get_sys_filter_level](#get_sys_filter_level)
    * [raw_log](#raw_log)
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

The API is still in flux and may change in the future without notice.

Synopsis
========

Capturing nginx error logs with specified log filtering level
-------------------------------------------------------------

```nginx
error_log logs/error.log info;

http {
    # enable capturing error logs
    lua_capture_error_log 32m;

    init_by_lua_block {
        local errlog = require "ngx.errlog"
        local status, err = errlog.set_filter_level(ngx.WARN)
        if not status then
            ngx.log(ngx.ERR, err)
            return
        end
        ngx.log(ngx.WARN, "set error filter level: WARN")
    }

    server {
        # ...
        location = /t {
            content_by_lua_block {
                local errlog = require "ngx.errlog"
                ngx.log(ngx.INFO, "test1")
                ngx.log(ngx.WARN, "test2")
                ngx.log(ngx.ERR, "test3")

                local logs, err = errlog.get_logs(10)
                if not logs then
                    ngx.say("FAILED ", err)
                    return
                end

                for i = 1, #logs, 3 do
                    ngx.say("level: ", logs[i], " time: ", logs[i + 1],
                            " data: ", logs[i + 2])
                end
            }
        }
    }
}

```

The example location above produces a response like this:

```
level: 5 time: 1498546995.304 data: 2017/06/27 15:03:15 [warn] 46877#0:
    [lua] init_by_lua:8: set error filter level: WARN
level: 5 time: 1498546999.178 data: 2017/06/27 15:03:19 [warn] 46879#0: *1
    [lua] test.lua:5: test2, client: 127.0.0.1, server: localhost, ......
level: 4 time: 1498546999.178 data: 2017/06/27 15:03:19 [error] 46879#0: *1
    [lua] test.lua:6: test3, client: 127.0.0.1, server: localhost, ......
```

[Back to TOC](#table-of-contents)

Methods
=======

set_filter_level
-----------------
**syntax:** *status, err = log_module.set_filter_level(log_level)*

**context:** *init_by_lua&#42;*

Specifies the filter log level, only to capture and buffer the error logs with a log level
no lower than the specified level.

If we don't call this API, all of the error logs will be captured by default.

In case of error, `nil` will be returned as well as a string describing the
error.

This API should always work with directive
[lua_capture_error_log](https://github.com/openresty/lua-nginx-module#lua_capture_error_log).

See [Nginx log level constants](https://github.com/openresty/lua-nginx-module#nginx-log-level-constants) for all nginx log levels.

For example,

```lua
 init_by_lua_block {
     local errlog = require "ngx.errlog"
     errlog.set_filter_level(ngx.WARN)
 }
```

*NOTE:* The debugging logs since when OpenResty or NGINX is not built with `--with-debug`, all the debug level logs are suppressed regardless.

[Back to TOC](#table-of-contents)

get_logs
--------
**syntax:** *res, err = log_module.get_logs(max?, res?)*

**context:** *any*

Fetches the captured nginx error log messages if any in the global data buffer
specified by `ngx_lua`'s
[lua_capture_error_log](https://github.com/openresty/lua-nginx-module#lua_capture_error_log)
directive. Upon return, this Lua function also *removes* those messages from
that global capturing buffer to make room for future new error log data.

In case of error, `nil` will be returned as well as a string describing the
error.

The optional `max` argument is a number that when specified, will prevent
`errlog.get_logs` from adding more than `max` messages to the `res` array.

```lua
for i = 1, 20 do
   ngx.log(ngx.ERR, "test")
end

local errlog = require "ngx.errlog"
local res = errlog.get_logs(10)
-- the number of messages in the `res` table is 10 and the `res` table
-- has 30 elements.
```

The resulting table has the following structure:

```lua
{ level1, time1, msg1, level2, time2, msg2, ... }
```

The `levelX` values are constants defined below:

https://github.com/openresty/lua-nginx-module/#nginx-log-level-constants

The `timeX` values are UNIX timestamps in seconds with millisecond precision. The sub-second part is presented as the decimal part.
The time format is exactly the same as the value returned by [ngx.now](https://github.com/openresty/lua-nginx-module/#ngxnow). It is
also subject to NGINX core's time caching.

The `msgX` values are the error log message texts.

So to traverse this array, the user can use a loop like this:

```lua
for i = 1, #res, 3 do
    local level = res[i]
    if not level then
        break
    end

    local time = res[i + 1]
    local msg = res[i + 2]

    -- handle the current message with log level in `level`,
    -- log time in `time`, and log message body in `msg`.
end
```

Specifying `max <= 0` disables this behavior, meaning that the number of
results won't be limited.

The optional 2th argument `res` can be a user-supplied Lua table
to hold the result instead of creating a brand new table. This can avoid
unnecessary table dynamic allocations on hot Lua code paths. It is used like this:

```lua
local errlog = require "ngx.errlog"
local new_tab = require "table.new"

local buffer = new_tab(100 * 3, 0)  -- for 100 messages

local errlog = require "ngx.errlog"
local res, err = errlog.get_logs(0, buffer)
if res then
    -- res is the same table as `buffer`
    for i = 1, #res, 3 do
        local level = res[i]
        if not level then
            break
        end
        local time = res[i + 1]
        local msg  = res[i + 2]
        ...
    end
end
```

When provided with a `res` table, `errlog.get_logs` won't clear the table
for performance reasons, but will rather insert a trailing `nil` value
after the last table element.

When the trailing `nil` is not enough for your purpose, you should
clear the table yourself before feeding it into the `errlog.get_logs` function.

[Back to TOC](#table-of-contents)

get_sys_filter_level
--------------------
**syntax:** *log_level = log_module.get_sys_filter_level()*

**context:** *any*

Return the nginx core's error log filter level (defined via the [error_log](http://nginx.org/r/error_log)
configuration directive in `nginx.conf`) as an integer value matching the nginx error log level
constants documented below:

https://github.com/openresty/lua-nginx-module/#nginx-log-level-constants

For example:

```lua
local errlog = require "ngx.errlog"
local log_level = errlog.get_sys_filter_level()
-- Now the filter level is always one level higher than system default log level on priority
local status, err = errlog.set_filter_level(log_level - 1)
if not status then
    ngx.log(ngx.ERR, err)
    return
end
```

[Back to TOC](#table-of-contents)

raw_log
-------
**syntax:** *log_module.raw_log(log_level, msg)*

**context:** *any*

Log `msg` to the error logs with the given logging level.

Just like the [ngx.log](https://github.com/openresty/lua-nginx-module#ngxlog)
API, the `log_level` argument can take constants like `ngx.ERR` and `ngx.WARN`.
Check out [Nginx log level constants for
details.](https://github.com/openresty/lua-nginx-module#nginx-log-level-constants)

However, unlike the `ngx.log` API which accepts variadic arguments, this
function only accepts a single string as its second argument `msg`.

This function differs from `ngx.log` in the way that it will not prefix the
written logs with any sort of debug information (such as the caller's file
and line number).

For example, while `ngx.log` would produce

```
2017/07/09 19:36:25 [notice] 25932#0: *1 [lua] content_by_lua(nginx.conf:51):5: hello world, client: 127.0.0.1, server: localhost, request: "GET /log HTTP/1.1", host: "localhost"
```

from

```lua
ngx.log(ngx.NOTICE, "hello world")
```

the `errlog.raw_log()` call produces

```
2017/07/09 19:36:25 [notice] 25932#0: *1 hello world, client: 127.0.0.1, server: localhost, request: "GET /log HTTP/1.1", host: "localhost"
```

from

```lua
local errlog = require "ngx.errlog"
errlog.raw_log(ngx.NOTICE, "hello world")
```

This function is best suited when the format and/or stack level of the debug
information proposed by `ngx.log` is not desired. A good example of this would
be a custom logging function which prefixes each log with a namespace in
an application:

```
1.  local function my_log(lvl, ...)
2.      ngx.log(lvl, "[prefix] ", ...)
3.  end
4.
5.  my_log(ngx.ERR, "error")
```

Here, the produced log would indicate that this error was logged at line `2.`,
when in reality, we wish the investigator of that log to realize it was logged
at line `5.` right away.

For such use cases (or other formatting reasons), one may use `raw_log` to
create a logging utility that supports such requirements. Here is a suggested
implementation:

```lua
local errlog = require "ngx.errlog"

local function my_log(lvl, ...)
  -- log to error logs with our custom prefix, stack level
  -- and separator
  local n = select("#", ...)
  local t = { ... }
  local info = debug.getinfo(2, "Sl")

  local prefix = string.format("(%s):%d:", info.short_src, info.currentline)
  local buf = { prefix }

  for i = 1, n do
    buf[i + 1] = tostring(t[i])
  end

  local msg = table.concat(buf, " ")

  errlog.raw_log(lvl, msg) -- line 19.
end

local function my_function()
  -- do something and log

  my_log(ngx.ERR, "hello from", "raw_log:", true) -- line 25.
end

my_function()
```

This utility function will produce the following log, explicitly stating that
the error was logged on line `25.`:

```
2017/07/09 20:03:07 [error] 26795#0: *2 (/path/to/file.lua):25: hello from raw_log: true, context: ngx.timer
```

As a reminder to the reader, one must be wary of the cost of string
concatenation on the Lua land, and should prefer the combined use of a buffer
table and `table.concat` to avoid unnecessary GC pressure.

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

Yuansheng Wang &lt;membphis@gmail.com&gt; (membphis), OpenResty Inc.

[Back to TOC](#table-of-contents)

Copyright and License
=====================

This module is licensed under the BSD license.

Copyright (C) 2017, by Yichun "agentzh" Zhang, OpenResty Inc.

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

