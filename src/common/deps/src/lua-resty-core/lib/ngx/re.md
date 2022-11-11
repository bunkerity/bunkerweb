Name
====

ngx.re - Lua API for convenience utilities for `ngx.re`.

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
* [Description](#description)
* [Methods](#methods)
    * [split](#split)
    * [opt](#opt)
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

```lua
local ngx_re = require "ngx.re"

-- split
local res, err = ngx_re.split("a,b,c,d", ",")
--> res is now {"a", "b", "c", "d"}

-- opt
ngx_re.opt("jit_stack_size", 128 * 1024)
--> the PCRE jit stack can now handle more complex regular expressions
```

[Back to TOC](#table-of-contents)

Description
===========

This Lua module provides a Lua API which implements convenience utilities for
the `ngx.re` API.

[Back to TOC](#table-of-contents)

Methods
=======

All the methods of this module are static (or module-level). That is, you do
not need an object (or instance) to call these methods.

[Back to TOC](#table-of-contents)

split
-----
**syntax:** *res, err = ngx_re.split(subject, regex, options?, ctx?, max?, res?)*

Splits the `subject` string using the Perl compatible regular expression
`regex` with the optional `options`.

This function returns a Lua (array) table (with integer keys) containing the
split values.

In case of error, `nil` will be returned as well as a string describing the
error.

When `regex` contains a sub-match capturing group, and when such a match is
found, the first submatch capture will be inserted in between each split
value, like so:

```lua
local ngx_re = require "ngx.re"

local res, err = ngx_re.split("a,b,c,d", "(,)")
-- res is now {"a", ",", "b", ",", "c", ",", "d"}
```

When `regex` is empty string `""`, the `subject` will be split into chars,
like so:

```lua
local ngx_re = require "ngx.re"

local res, err = ngx_re.split("abcd", "")
-- res is now {"a", "b", "c", "d"}
```

The optional `ctx` table argument can be a Lua table holding an optional `pos`
field. When the `pos` field in the `ctx` table argument is specified,
`ngx_re.split` will start splitting the `subject` from that index:

```lua
local ngx_re = require "ngx.re"

local res, err = ngx_re.split("a,b,c,d", ",", nil, {pos = 5})
-- res is now {"c", "d"}
```

The optional `max` argument is a number that when specified, will prevent
`ngx_re.split` from adding more than `max` matches to the `res` array:

```lua
local ngx_re = require "ngx.re"

local res, err = ngx_re.split("a,b,c,d", ",", nil, nil, 3)
-- res is now {"a", "b", "c,d"}
```

Specifying `max <= 0` disables this behavior, meaning that the number of
results won't be limited.

The optional 6th argument `res` can be a table that `ngx_re.split` will re-use
to hold the results instead of creating a new one, which can improve
performance in hot code paths. It is used like so:

```lua
local ngx_re = require "ngx.re"

local my_table = {"hello world"}

local res, err = ngx_re.split("a,b,c,d", ",", nil, nil, nil, my_table)
-- res/my_table is now {"a", "b", "c", "d"}
```

When provided with a `res` table, `ngx_re.split` won't clear the table
for performance reasons, but will rather insert a trailing `nil` value
when the split is completed:

```lua
local ngx_re = require "ngx.re"

local my_table = {"W", "X", "Y", "Z"}

local res, err = ngx_re.split("a,b", ",", nil, nil, nil, my_table)
-- res/my_table is now {"a", "b", nil, "Z"}
```

When the trailing `nil` is not enough for your purpose, you should
clear the table yourself before feeding it into the `split` function.

[Back to TOC](#table-of-contents)

opt
-----
**syntax:** *ngx_re.opt(option, value)*

Allows changing of regex settings. Currently, it can only change the
`jit_stack_size` of the PCRE engine, like so:

```nginx

 init_by_lua_block { require "ngx.re".opt("jit_stack_size", 200 * 1024) }

 server {
     location /re {
         content_by_lua_block {
             -- full regex and string are taken from https://github.com/JuliaLang/julia/issues/8278
             local very_long_string = [[71.163.72.113 - - [30/Jul/2014:16:40:55 -0700] ...]]
             local very_complicated_regex = [[([\d\.]+) ([\w.-]+) ([\w.-]+) (\[.+\]) ...]]
             local from, to, err = ngx.re.find(very_long_string, very_complicated_regex, "jo")

             -- with the regular jit_stack_size, we would get the error 'pcre_exec() failed: -27'
             -- instead, we get a match
             ngx.print(from .. "-" .. to) -- prints '1-1563'
         }
     }
 }
```

The `jit_stack_size` cannot be set to a value lower than PCRE's default of 32K.

This method requires the PCRE library enabled in Nginx.

This feature was first introduced in the `v0.1.12` release.

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

Author
======

Thibault Charbonnier - ([@thibaultcha](https://github.com/thibaultcha))

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

See Also
========
* the [lua-resty-core](https://github.com/openresty/lua-resty-core) library.
* the ngx_lua module: https://github.com/openresty/lua-nginx-module
* OpenResty: https://openresty.org

[Back to TOC](#table-of-contents)
