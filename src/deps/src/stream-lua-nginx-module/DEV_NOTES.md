**DO NOT EDIT THIS REPO DIRECTLY, CODE ARE AUTOMATICALLY GENERATED FROM TEMPLATES**

# Install

There are some quirks when compiling the refactored stream module.

You will need NGINX 1.13.x for it to work as we targeted the refactor toward
that version only. The [1.13.x branch](https://github.com/openresty/openresty/tree/1.13.x)
of OpenResty should serve this well.

You need to turn off FFI when compiling (for the time being) as not all FFI functions got
their respective guard.

Here is what I use for compiling:

```shell
./configure --prefix=/home/datong/openresty-stream-build \
            --with-stream --with-stream_ssl_module
            --add-module=/home/datong/orinc/stream-lua-nginx-module
            -j4 --with-cc-opt='-DNGX_LUA_NO_FFI_API' --with-debug
```

# Status
The project can run simple "Hello, World" without any problem or Valgrind warnings.

I have also tested timer and variable support and they appears to work as well.

The only feature that has not been ported is the cosocket API due to it's
complexity. This does makes the module somewhat useless as input from user can not be read by
Lua programs right now. I will spend some time to sort this out shortly.

I will spend some time debugging and get the test suite running next.
