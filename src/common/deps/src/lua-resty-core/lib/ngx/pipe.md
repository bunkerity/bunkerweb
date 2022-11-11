Name
====

`ngx.pipe` - spawn and communicate with OS processes via stdin/stdout/stderr in
a non-blocking fashion.

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
* [Description](#description)
* [Methods](#methods)
    * [spawn](#spawn)
    * [set_timeouts](#set_timeouts)
    * [wait](#wait)
    * [pid](#pid)
    * [kill](#kill)
    * [shutdown](#shutdown)
    * [write](#write)
    * [stderr_read_all](#stderr_read_all)
    * [stdout_read_all](#stdout_read_all)
    * [stderr_read_line](#stderr_read_line)
    * [stdout_read_line](#stdout_read_line)
    * [stderr_read_bytes](#stderr_read_bytes)
    * [stdout_read_bytes](#stdout_read_bytes)
    * [stderr_read_any](#stderr_read_any)
    * [stdout_read_any](#stdout_read_any)
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

```nginx
location = /t {
    content_by_lua_block {
        local ngx_pipe = require "ngx.pipe"
        local select = select

        local function count_char(...)
            local proc = ngx_pipe.spawn({'wc', '-c'})
            local n = select('#', ...)
            for i = 1, n do
                local arg = select(i, ...)
                local bytes, err = proc:write(arg)
                if not bytes then
                    ngx.say(err)
                    return
                end
            end

            local ok, err = proc:shutdown('stdin')
            if not ok then
                ngx.say(err)
                return
            end

            local data, err = proc:stdout_read_line()
            if not data then
                ngx.say(err)
                return
            end

            ngx.say(data)
        end

        count_char(("1234"):rep(2048))
    }
}
```

This example counts characters (bytes) directly fed by OpenResty to the UNIX
command `wc`.

You could not do this with either `io.popen` or `os.execute` because `wc` will
not output the result until its stdin is closed.

[Back to TOC](#table-of-contents)

Description
===========

This module does not support non-POSIX operating systems like Windows yet.

If you are not using the Nginx core shipped with OpenResty, you will need to
apply the `socket_cloexec` patch to the standard Nginx core.

Under the hood, this module uses `fork` and `execvp` with the user-specified
command, and communicate with such spawned processes via the POSIX `pipe` API,
which contributes to the name of this module.

A signal handler for `SIGCHLD` is registered so that we can receive a
notification once the spawned processes exited.

We combine the above implementation with Nginx's event mechanism and
OpenResty's Lua coroutine scheduler, in order to ensure communication with the
spawned processes is non-blocking.

The communication APIs do not work in phases which do not support yielding,
such as `init_worker_by_lua*` or `log_by_lua*`, because there is no way to
yield the current light thread to avoid blocking the OS thread when
communicating with processes in those phases.

[Back to TOC](#table-of-contents)

Methods
=======

spawn
-----
**syntax:** *proc, err = pipe_module.spawn(args, opts?)*

**context:** *all phases except init_by_lua&#42;*

Creates and returns a new sub-process instance we can communicate with later.

For example:

```lua
local ngx_pipe = require "ngx.pipe"
local proc, err = ngx_pipe.spawn({"sh", "-c", "sleep 0.1 && exit 2"})
if not proc then
    ngx.say(err)
    return
end
```

In case of failure, this function returns `nil` and a string describing the
error.

The sub-process will be killed via `SIGKILL` if it is still alive when the
instance is collected by the garbage collector.

Note that `args` should either be a single level array-like Lua table with
string values, or just a single string.

Some more examples:

```lua
local proc, err = ngx_pipe.spawn({"ls", "-l"})

local proc, err = ngx_pipe.spawn({"perl", "-e", "print 'hello, wolrd'"})
```

If `args` is specified as a string, it will be executed by the operating system
shell, just like `os.execute`. The above example could thus be rewritten as:

```lua
local ngx_pipe = require "ngx.pipe"
local proc, err = ngx_pipe.spawn("sleep 0.1 && exit 2")
if not proc then
    ngx.say(err)
    return
end
```

In the shell mode, you should be very careful about shell injection attacks
when interpolating variables into command string, especially variables from
untrusted sources. Please make sure that you escape those variables while
assembling the command string. For this reason, it is highly recommended to use
the multi-arguments form (`args` as a table) to specify each command-line
argument explicitly.

Since by default, Nginx does not pass along the `PATH` system environment
variable, you will need to configure the `env PATH` directive if you wish for
it to be respected during the searching of sub-processes:

```nginx
env PATH;
...
content_by_lua_block {
    local ngx_pipe = require "ngx.pipe"

    local proc = ngx_pipe.spawn({'ls'})
}
```

The optional table argument `opts` can be used to control the behavior of
spawned processes. For instance:

```lua
local opts = {
    merge_stderr = true,
    buffer_size = 256,
    environ = {"PATH=/tmp/bin", "CWD=/tmp/work"}
}
local proc, err = ngx_pipe.spawn({"sh", "-c", ">&2 echo data"}, opts)
if not proc then
    ngx.say(err)
    return
end
```

The following options are supported:

* `merge_stderr`: when set to `true`, the output to stderr will be redirected
  to stdout in the spawned process. This is similar to doing `2>&1` in a shell.
* `buffer_size`: specifies the buffer size used by reading operations, in
  bytes. The default buffer size is `4096`.
* `environ`: specifies environment variables for the spawned process. The value
  must be a single-level, array-like Lua table with string values. If the
  current platform does not support this option, `nil` plus a string `"environ
  option not supported"` will be returned.
* `write_timeout`: specifies the write timeout threshold, in milliseconds. The
  default threshold is `10000`. If the threshold is `0`, the write operation
  will never time out.
* `stdout_read_timeout`: specifies the stdout read timeout threshold, in
  milliseconds. The default threshold is `10000`. If the threshold is `0`, the
  stdout read operation will never time out.
* `stderr_read_timeout`: specifies the stderr read timeout threshold, in
  milliseconds. The default threshold is `10000`. If the threshold is `0`, the
  stderr read operation will never time out.
* `wait_timeout`: specifies the wait timeout threshold, in milliseconds. The
  default threshold is `10000`. If the threshold is `0`, the wait operation
  will never time out.

[Back to TOC](#table-of-contents)

set_timeouts
------------
**syntax:** *proc:set_timeouts(write_timeout?, stdout_read_timeout?, stderr_read_timeout?, wait_timeout?)*

Respectively sets: the write timeout threshold, stdout read timeout threshold,
stderr read timeout threshold, and wait timeout threshold. All timeouts are in
milliseconds.

The default threshold for each timeout is 10 seconds.

If the specified timeout argument is `nil`, the corresponding timeout threshold
will not be changed. For example:

```lua
local proc, err = ngx_pipe.spawn({"sleep", "10s"})

-- only change the wait_timeout to 0.1 second.
proc:set_timeouts(nil, nil, nil, 100)

-- only change the send_timeout to 0.1 second.
proc:set_timeouts(100)
```

If the specified timeout argument is `0`, the corresponding operation will
never time out.

[Back to TOC](#table-of-contents)

wait
----
**syntax:** *ok, reason, status = proc:wait()*

**context:** *phases that support yielding*

Waits until the current sub-process exits.

It is possible to control how long to wait via [set_timeouts](#set_timeouts).
The default timeout is 10 seconds.

If process exited with status code zero, the `ok` return value will be `true`.

If process exited abnormally, the `ok` return value will be `false`.

The second return value, `reason`, will be a string. Its values may be:

* `exit`: the process exited by calling `exit(3)`, `_exit(2)`, or by
  returning from `main()`. In this case, `status` will be the exit code.
* `signal`: the process was terminated by a signal. In this case, `status` will
  be the signal number.

Note that only one light thread can wait on a process at a time. If another
light thread tries to wait on a process, the return values will be `nil` and
the error string `"pipe busy waiting"`.

If a thread tries to wait an exited process, the return values will be `nil`
and the error string `"exited"`.

[Back to TOC](#table-of-contents)

pid
---
**syntax:** *pid = proc:pid()*

Returns the pid number of the sub-process.

[Back to TOC](#table-of-contents)

kill
----
**syntax:** *ok, err = proc:kill(signum)*

Sends a signal to the sub-process.

Note that the `signum` argument should be signal's numerical value. If the
specified `signum` is not a number, an error will be thrown.

You should use [lua-resty-signal's signum()
function](https://github.com/openresty/lua-resty-signal#signum) to convert
signal names to signal numbers in order to ensure portability of your
application.

In case of success, this method returns `true`. Otherwise, it returns `nil` and
a string describing the error.

Killing an exited sub-process will return `nil` and the error string
`"exited"`.

Sending an invalid signal to the process will return `nil` and the error string
`"invalid signal"`.

[Back to TOC](#table-of-contents)

shutdown
--------
**syntax:** *ok, err = proc:shutdown(direction)*

Closes the specified direction of the current sub-process.

The `direction` argument should be one of these three values: `stdin`, `stdout`
and `stderr`.

In case of success, this method returns `true`. Otherwise, it returns `nil` and
a string describing the error.

If the `merge_stderr` option is specified in [spawn](#spawn), closing the
`stderr` direction will return `nil` and the error string `"merged to stdout"`.

Shutting down a direction when a light thread is waiting on it (such as during
reading or writing) will abort the light thread and return `true`.

Shutting down directions of an exited process will return `nil` and the error
string `"closed"`.

It is fine to shut down the same direction of the same stream multiple times;
no side effects are to be expected.

[Back to TOC](#table-of-contents)

write
-----
**syntax:** *nbytes, err = proc:write(data)*

**context:** *phases that support yielding*

Writes data to the current sub-process's stdin stream.

The `data` argument can be a string or a single level array-like Lua table with
string values.

This method is a synchronous and non-blocking operation that will not return
until *all* the data has been flushed to the sub-process's stdin buffer, or
an error occurs.

In case of success, it returns the total number of bytes that have been sent.
Otherwise, it returns `nil` and a string describing the error.

The timeout threshold of this `write` operation can be controlled by the
[set_timeouts](#set_timeouts) method. The default timeout threshold is 10
seconds.

When a timeout occurs, the data may be partially written into the sub-process's
stdin buffer and read by the sub-process.

Only one light thread is allowed to write to the sub-process at a time. If
another light thread tries to write to it, this method will return `nil` and
the error string `"pipe busy writing"`.

If the `write` operation is aborted by the [shutdown](#shutdown) method,
it will return `nil` and the error string `"aborted"`.

Writing to an exited sub-process will return `nil` and the error string
`"closed"`.

[Back to TOC](#table-of-contents)

stderr_read_all
---------------
**syntax:** *data, err, partial = proc:stderr_read_all()*

**context:** *phases that support yielding*

Reads all data from the current sub-process's stderr stream until it is closed.

This method is a synchronous and non-blocking operation, just like the
[write](#write) method.

The timeout threshold of this reading operation can be controlled by
[set_timeouts](#set_timeouts). The default timeout is 10 seconds.

In case of success, it returns the data received. Otherwise, it returns three
values: `nil`, a string describing the error, and, optionally, the partial data
received so far.

When `merge_stderr` is specified in [spawn](#spawn), calling `stderr_read_all`
will return `nil` and the error string `"merged to stdout"`.

Only one light thread is allowed to read from a sub-process's stderr or stdout
stream at a time. If another thread tries to read from the same stream, this
method will return `nil` and the error string `"pipe busy reading"`.

If the reading operation is aborted by the [shutdown](#shutdown) method,
it will return `nil` and the error string `"aborted"`.

Streams for stdout and stderr are separated, so at most two light threads may
be reading from a sub-process at a time (one for each stream).

The same way, a light thread may read from a stream while another light thread
is writing to the sub-process stdin stream.

Reading from an exited process's stream will return `nil` and the error string
`"closed"`.

[Back to TOC](#table-of-contents)

stdout_read_all
---------------
**syntax:** *data, err, partial = proc:stdout_read_all()*

**context:** *phases that support yielding*

Similar to the [stderr_read_all](#stderr_read_all) method, but reading from the
stdout stream of the sub-process.

[Back to TOC](#table-of-contents)

stderr_read_line
----------------
**syntax:** *data, err, partial = proc:stderr_read_line()*

**context:** *phases that support yielding*

Reads from stderr like [stderr_read_all](#stderr_read_all), but only reads a
single line of data.

When `merge_stderr` is specified in [spawn](#spawn), calling `stderr_read_line`
will return `nil` plus the error string `"merged to stdout"`.

When the data stream is truncated without a new-line character, it returns 3
values: `nil`, the error string `"closed"`, and the partial data received so
far.

The line should be terminated by a `Line Feed` (LF) character (ASCII 10),
optionally preceded by a `Carriage Return` (CR) character (ASCII 13). The CR
and LF characters are not included in the returned line data.

[Back to TOC](#table-of-contents)

stdout_read_line
----------------
**syntax:** *data, err, partial = proc:stdout_read_line()*

**context:** *phases that support yielding*

Similar to [stderr_read_line](#stderr_read_line), but reading from the
stdout stream of the sub-process.

[Back to TOC](#table-of-contents)

stderr_read_bytes
-----------------
**syntax:** *data, err, partial = proc:stderr_read_bytes(len)*

**context:** *phases that support yielding*

Reads from stderr like [stderr_read_all](#stderr_read_all), but only reads the
specified number of bytes.

If `merge_stderr` is specified in [spawn](#spawn), calling `stderr_read_bytes`
will return `nil` plus the error string `"merged to stdout"`.

If the data stream is truncated (fewer bytes of data available than requested),
this method returns 3 values: `nil`, the error string `"closed"`, and the
partial data string received so far.

[Back to TOC](#table-of-contents)

stdout_read_bytes
-----------------
**syntax:** *data, err, partial = proc:stdout_read_bytes(len)*

**context:** *phases that support yielding*

Similar to [stderr_read_bytes](#stderr_read_bytes), but reading from the
stdout stream of the sub-process.

[Back to TOC](#table-of-contents)

stderr_read_any
---------------
**syntax:** *data, err = proc:stderr_read_any(max)*

**context:** *phases that support yielding*

Reads from stderr like [stderr_read_all](#stderr_read_all), but returns
immediately when any amount of data is received.

At most `max` bytes are received.

If `merge_stderr` is specified in [spawn](#spawn), calling `stderr_read_any`
will return `nil` plus the error string `"merged to stdout"`.

If the received data is more than `max` bytes, this method will return with
exactly `max` bytes of data. The remaining data in the underlying receive
buffer can be fetched with a subsequent reading operation.

[Back to TOC](#table-of-contents)

stdout_read_any
---------------
**syntax:** *data, err = proc:stdout_read_any(max)*

**context:** *phases that support yielding*

Similar to [stderr_read_any](#stderr_read_any), but reading from the stdout
stream of the sub-process.

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
