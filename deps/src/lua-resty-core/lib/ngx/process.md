Name
====

`ngx.process` - manage the nginx processes for OpenResty/ngx_lua.

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
* [Functions](#functions)
    * [type](#type)
    * [enable_privileged_agent](#enable_privileged_agent)
    * [signal_graceful_exit](#signal_graceful_exit)
    * [get_master_pid](#get_master_pid)
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

Enables privileged agent process, gets process type, and then gets the master process PID:

```nginx
# http config
init_by_lua_block {
    local process = require "ngx.process"

    -- enables privileged agent process
    local ok, err = process.enable_privileged_agent()
    if not ok then
        ngx.log(ngx.ERR, "enables privileged agent failed error:", err)
    end

    -- output process type
    ngx.log(ngx.INFO, "process type: ", process.type())
}

init_worker_by_lua_block {
    local process = require "ngx.process"
    ngx.log(ngx.INFO, "process type: ", process.type())
}

server {
    # ...
    location = /t {
        content_by_lua_block {
            local process = require "ngx.process"
            ngx.say("process type: ", process.type())
            ngx.say("master process pid: ", process.get_master_pid() or "-")
        }
    }
}

```

The example config above produces an output to `error.log` when
server starts:

```
[lua] init_by_lua:11: process type: master
[lua] init_worker_by_lua:3: process type: privileged agent
[lua] init_worker_by_lua:3: process type: worker
```

The example location above produces the following response body:

```
process type: worker
master process pid: 8261
```

[Back to TOC](#table-of-contents)

Functions
=========

type
----
**syntax:** *type_name = process_module.type()*

**context:** *any*

Returns the type of the current Nginx process. Depending on the calling context
and current process, the type can be one of:

* `master`: returned when this function is called from within the master
  process
* `worker`: returned when this function is called from within a worker process
* `single`: returned when Nginx is running in the single process mode
* `signaller`: returned when Nginx is running as a signaller process
* `privileged agent`: returned when this funtion is called from within a
  privileged agent process

For example:

```lua
local process = require "ngx.process"
ngx.say("process type:", process.type())   -- RESPONSE: worker
```

[Back to TOC](#table-of-contents)

enable_privileged_agent
-----------------------
**syntax:** *ok, err = process_module.enable_privileged_agent()*

**context:** *init_by_lua&#42;*

Enables the privileged agent process in Nginx.

The privileged agent process does not listen on any virtual server ports like those worker processes.
And it uses the same system account as the nginx master process, which is usually a privileged account
like `root`.

The `init_worker_by_lua*` directive handler still runs in the privileged agent process. And one can
use the [type](#type) function provided by this module to check if the current process is a privileged
agent.

In case of failures, returns `nil` and a string describing the error.

[Back to TOC](#table-of-contents)

signal_graceful_exit
--------------------
**syntax:** *process_module.signal_graceful_exit()*

**context:** *any*

Signals the *current* nginx (worker) process to quit gracefully, i.e., after all the timers have expired (in time or expired prematurely).

Note that this API function simply sets the nginx global C variable `ngx_quit` to signal the nginx event
loop directly. No UNIX signals or IPC are involved here.

WARNING: the official NGINX core does not perform the graceful exiting procedure when the [master_process](http://nginx.org/r/master_process)
directive is turned `off`. The OpenResty's NGINX core has a
[custom patch](https://github.com/openresty/openresty/blob/master/patches/nginx-1.11.2-single_process_graceful_exit.patch)
applied, which fixes this issue.

[Back to TOC](#table-of-contents)

get_master_pid
--------------
**syntax:** *pid = process_module.get_master_pid()*

**context:** *any*

Returns a number value for the nginx master process's process ID (or PID).

This function requires NGINX 1.13.8+ cores to work properly. Otherwise it returns `nil`.

This feature first appeared in lua-resty-core v0.1.14.

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

