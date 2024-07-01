Name
====

Nginx Development Kit (NDK)

Table of Contents
=================

* [Name](#name)
* [Synopsis](#synopsis)
* [Status](#status)
* [Features](#features)
* [Design](#design)
    * [modular](#modular)
    * [auto-generated & easily extensible](#auto-generated--easily-extensible)
* [Usage for users](#usage-for-users)
    * [Building as a dynamic module](#building-as-a-dynamic-module)
* [Usage for developers](#usage-for-developers)
    * [Warning: using NDK_ALL](#warning-using-ndk_all)
* [Modules using NDK](#modules-using-ndk)
* [TODO](#todo)
* [License](#license)
* [Contributing / Feedback](#contributing--feedback)
* [Authors](#authors)
* [Special Thanks](#special-thanks)

Synopsis
========

The NDK is an Nginx module that is designed to extend the core functionality of the
excellent Nginx webserver in a way that can be used as a basis of other Nginx modules.

It has functions and macros to deal with generic tasks that don't currently have
generic code as part of the core distribution.  The NDK itself adds few features
that are seen from a user's point of view - it's just designed to help reduce the
code that Nginx module developers need to write.

Nginx module developers wishing to use any of the features in the NDK should specify
that the NDK is a dependency of their module, and that users will need to compile
it as well when they compile their own modules.  They will also need to declare in
their own modules which features of the NDK they wish to use (explained below).

If you are not an Nginx module developer, then the only useful part of this project
will be the 'usage for users' section below.

[Back to TOC](#table-of-contents)

Status
======

The NDK is now considered to be stable. It is already being used in quite a few third
party modules (see list below).

[Back to TOC](#table-of-contents)

Features
========

* additional conf_set functions for regexes, complex/script values, paths...
* macros to simplify tasks like checking for NULL values when doing ngx_array_push
* patches to the main source code
* ngx_auto_lib_core generic external library handler is included (see separate readme)

[Back to TOC](#table-of-contents)

Design
======

modular
-------

The kit itself is designed in a modular way, so that only the required code is compiled.
It's possible to add just a single NDK module, a few or all of them.

[Back to TOC](#table-of-contents)

auto-generated & easily extensible
----------------------------------

Many of the macros available in the NDK are auto-generated from simple configuration
files.  This makes creating similar macros for your own code very simple - it's usually
just the case of adding an extra line to a config file and re-running the build script.

[Back to TOC](#table-of-contents)

Usage for users
===============

If another Nginx module you wish to use specifies that the NDK is a dependency, you
will need to do the following :

1. download the source (https://github.com/simpl/ngx_devel_kit)
2. unpack the source (tar -xzf $name)
3. compile Nginx with the following extra option `--add-module=/path/to/ngx_devel_kit`.

e.g.

```bash
./configure --add-module=/path/to/ngx_devel_kit \
            --add-module=/path/to/another/module
```

[Back to TOC](#table-of-contents)

Building as a dynamic module
----------------------------

Starting from NGINX 1.9.11, you can also compile this module as a dynamic module, by using the `--add-dynamic-module=PATH` option instead of `--add-module=PATH` on the
`./configure` command line above. And then you can explicitly load the module in your `nginx.conf` via the [load_module](http://nginx.org/en/docs/ngx_core_module.html#load_module)
directive, for example,

```nginx
load_module /path/to/modules/ndk_http_module.so;
load_module /path/to/another/module.so;
```

[Back to TOC](#table-of-contents)

Usage for developers
====================

To use the NDK in your own module, you need to add the following:

1. add this line to your module

```C
#include    <ndk.h>
```

Note: since the NDK includes the following lines

```C
#include    <ngx_config.h>
#include    <ngx_core.h>
#include    <ngx_http.h>
```

you can replace these with the single include above.
2. add the following line in the config file for your module:

```bash
have=NDK_[module_name]  . auto/have
```

for each NDK module that you wish to use (you need to include auto/have multiple
times if you wish to use multiple NDK modules.

Note: the old method of setting

```config
CFLAGS="$CFLAGS -DNDK_[module_name]"
```

is now deprecated. It will still work, but results in unnecessary lines being
displayed when compiling Nginx.

[Back to TOC](#table-of-contents)

Warning: Using NDK_ALL
----------------------

You can also set `NDK_ALL` to include all the NDK modules.  This is primarily as
a convenience in the early stages of development of another module. However,

DO NOT LEAVE `NDK_ALL` IN YOUR CONFIG FILE WHEN PUBLISHING

Although the NDK is fairly small now, it could in time become a large repository
of code that would, if using NDK_ALL, result in considerably more code being compiled
than is necessary.

[Back to TOC](#table-of-contents)

Modules using NDK
=================

The following 3rd-party modules make use of NDK.

* [ngx_http_lua_module](https://github.com/openresty/lua-nginx-module#readme)
* [ngx_http_set_misc_module](https://github.com/openresty/set-misc-nginx-module#readme)
* [ngx_http_encrypted_session_module](https://github.com/openresty/encrypted-session-nginx-module#readme)
* [ngx_http_form_input_module](https://github.com/calio/form-input-nginx-module#readme)
* [ngx_http_iconv_module](https://github.com/calio/iconv-nginx-module#readme)
* [ngx_http_array_var_module](https://github.com/openresty/array-var-nginx-module#readme)

If you would like to add your module to this list, please let us know.

[Back to TOC](#table-of-contents)

TODO
====

* documentation for modules that don't already have it
* additional phase-handler functions
* generically testing for needing to add a handler
* remove dependency of set_var on OpenSSL being compiled in
* for backward compatability, add the ndk_macros

[Back to TOC](#table-of-contents)

License
=======

Copyright (c) 2010-2018, Marcus Clyne

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are
permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of
conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of
conditions and the following disclaimer in the documentation and/or other materials
provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors may be used
to endorse or promote products derived from this software without specific prior
written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS
OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE
GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

[Back to TOC](#table-of-contents)

Contributing / Feedback
=======================

If you are an Nginx module developer, and have developed some functions that are
generic in nature (or would be easily adapted to be so), then please send them to
me at the address below, and I'll addmclyne to the kit.

[Back to TOC](#table-of-contents)

Author
======

[Marcus Clyne](https://github.com/mclyne)

[Back to TOC](#table-of-contents)


Special Thanks
==============

A special thanks goes to [Yichun Zhang](https://github.com/agentzh) for helping to maintain
this module.

[Back to TOC](#table-of-contents)
