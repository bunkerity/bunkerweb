Name
====

lua-resty-env - Lua cache for calls to `os.getenv`.


Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Description](#description)
* [Synopsis](#synopsis)
* [Methods](#methods)
    * [get](#get)
    * [set](#set)
    * [value](#value)
    * [enabled](#enabled)
    * [reset](#reset)
* [Installation](#installation)
* [TODO](#todo)
* [Community](#community)
* [Bugs and Patches](#bugs-and-patches)
* [Author](#author)
* [Copyright and License](#copyright-and-license)
* [See Also](#see-also)

Status
======

This library is considered production ready.

Description
===========

This Lua library is a cache for calls to `os.getenv`.

This library acts as a mediator between other libraries and the environment variables.
Variables can not only be get but also set.

Synopsis
========

```lua

env SOME_VARIABLE;

http {
    server {
        location /test {
            content_by_lua_block {
                local resty_env = require 'resty.env'

                ngx.say("SOME_VARIABLE: ", resty_env.get('SOME_VARIABLE'))
            }
        }
    }
```

[Back to TOC](#table-of-contents)

Methods
=======

All the methods are expected to be called on the module without self.

[Back to TOC](#table-of-contents)

get
---
`syntax: val = env.get(name)`

Returns environment value from the cache or uses `os.getenv` to get it.

[Back to TOC](#table-of-contents)

set
-------
`syntax: prev = env.set(name, value)`

Sets the the `value` to the cache and returns the previous value in the cache.

[Back to TOC](#table-of-contents)

list
-------
`syntax: table = env.list()`

Returns a table with all environment variables. Names are keys and values are values.

[Back to TOC](#table-of-contents)

enabled
----------
`syntax: ok = env.enabled(name)`

Returns true if the environment variable has truthy value (`1`, `true`), false (`0`, `false`) or `nil`.

[Back to TOC](#table-of-contents)

reset
------------
`syntax: env = env.reset()`

Resets the internal cache.

[Back to TOC](#table-of-contents)

Installation
============

If you are using the OpenResty bundle (http://openresty.org ), then
you can use [opm](https://github.com/openresty/opm#synopsis) to install this package.

```shell
opm get 3scale/lua-resty-env
```

[Back to TOC](#table-of-contents)

Bugs and Patches
================

Please report bugs or submit patches by

1. creating a ticket on the [GitHub Issue Tracker](http://github.com/3scale/lua-resty-env/issues),

[Back to TOC](#table-of-contents)

Author
======

Michal "mikz" Cichra <mcichra@redhat.com>, Red Hat Inc.

[Back to TOC](#table-of-contents)

Copyright and License
=====================

This module is licensed under the Apache License Version 2.0.

Copyright (C) 2016-2017, Red Hat Inc.

All rights reserved.

See [LICENSE](LICENSE) for the full license.

[Back to TOC](#table-of-contents)

See Also
========
* the APIcast API Gateway: https://github.com/3scale/apicast/#readme

[Back to TOC](#table-of-contents)
