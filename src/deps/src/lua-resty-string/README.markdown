Name
====

lua-resty-string - String utilities and common hash functions for ngx_lua and LuaJIT

Table of Contents
=================

* [Name](#name)
* [Status](#status)
* [Description](#description)
* [Synopsis](#synopsis)
* [Author](#author)
* [Copyright and License](#copyright-and-license)
* [See Also](#see-also)

Status
======

This library is considered experimental and still under active development.

The API is still in flux and may change without notice.

Description
===========

This library requires an nginx build with OpenSSL,
the [ngx_lua module](http://wiki.nginx.org/HttpLuaModule), and [LuaJIT 2.0](http://luajit.org/luajit.html).

Synopsis
========

```lua
    # nginx.conf:

    lua_package_path "/path/to/lua-resty-string/lib/?.lua;;";

    server {
        location = /test {
            content_by_lua_file conf/test.lua;
        }
    }

    -- conf/test.lua:

    local resty_sha1 = require "resty.sha1"

    local sha1 = resty_sha1:new()
    if not sha1 then
        ngx.say("failed to create the sha1 object")
        return
    end

    local ok = sha1:update("hello, ")
    if not ok then
        ngx.say("failed to add data")
        return
    end

    ok = sha1:update("world")
    if not ok then
        ngx.say("failed to add data")
        return
    end

    local digest = sha1:final()  -- binary digest

    local str = require "resty.string"
    ngx.say("sha1: ", str.to_hex(digest))
        -- output: "sha1: b7e23ec29af22b0b4e41da31e868d57226121c84"

    local resty_md5 = require "resty.md5"
    local md5 = resty_md5:new()
    if not md5 then
        ngx.say("failed to create md5 object")
        return
    end

    local ok = md5:update("hel")
    if not ok then
        ngx.say("failed to add data")
        return
    end

        -- md5:update() with an optional "len" parameter
    ok = md5:update("loxxx", 2)
    if not ok then
        ngx.say("failed to add data")
        return
    end

    local digest = md5:final()

    local str = require "resty.string"
    ngx.say("md5: ", str.to_hex(digest))
        -- yield "md5: 5d41402abc4b2a76b9719d911017c592"

    local resty_sha224 = require "resty.sha224"
    local str = require "resty.string"
    local sha224 = resty_sha224:new()
    ngx.say(sha224:update("hello"))
    local digest = sha224:final()
    ngx.say("sha224: ", str.to_hex(digest))

    local resty_sha256 = require "resty.sha256"
    local str = require "resty.string"
    local sha256 = resty_sha256:new()
    ngx.say(sha256:update("hello"))
    local digest = sha256:final()
    ngx.say("sha256: ", str.to_hex(digest))

    local resty_sha512 = require "resty.sha512"
    local str = require "resty.string"
    local sha512 = resty_sha512:new()
    ngx.say(sha512:update("hello"))
    local digest = sha512:final()
    ngx.say("sha512: ", str.to_hex(digest))

    local resty_sha384 = require "resty.sha384"
    local str = require "resty.string"
    local sha384 = resty_sha384:new()
    ngx.say(sha384:update("hel"))
    ngx.say(sha384:update("lo"))
    local digest = sha384:final()
    ngx.say("sha384: ", str.to_hex(digest))

    local resty_random = require "resty.random"
    local str = require "resty.string"
    local random = resty_random.bytes(16)
        -- generate 16 bytes of pseudo-random data
    ngx.say("pseudo-random: ", str.to_hex(random))

    local resty_random = require "resty.random"
    local str = require "resty.string"
    local strong_random = resty_random.bytes(16,true)
        -- attempt to generate 16 bytes of
        -- cryptographically strong random data
    while strong_random == nil do
        strong_random = resty_random.bytes(16,true)
    end
    ngx.say("random: ", str.to_hex(strong_random))

    local aes = require "resty.aes"
    local str = require "resty.string"
    local aes_128_cbc_md5 = aes:new("AKeyForAES")
        -- the default cipher is AES 128 CBC with 1 round of MD5
        -- for the key and a nil salt
    local encrypted = aes_128_cbc_md5:encrypt("Secret message!")
    ngx.say("AES 128 CBC (MD5) Encrypted HEX: ", str.to_hex(encrypted))
    ngx.say("AES 128 CBC (MD5) Decrypted: ", aes_128_cbc_md5:decrypt(encrypted))

    local aes = require "resty.aes"
    local str = require "resty.string"
    local aes_256_cbc_sha512x5 = aes:new("AKeyForAES-256-CBC",
        "MySalt!!", aes.cipher(256,"cbc"), aes.hash.sha512, 5)
        -- AES 256 CBC with 5 rounds of SHA-512 for the key
        -- and a salt of "MySalt!!"
        -- Note: salt can be either nil or exactly 8 characters long
    local encrypted = aes_256_cbc_sha512x5:encrypt("Really secret message!")
    ngx.say("AES 256 CBC (SHA-512, salted) Encrypted HEX: ", str.to_hex(encrypted))
    ngx.say("AES 256 CBC (SHA-512, salted) Decrypted: ",
        aes_256_cbc_sha512x5:decrypt(encrypted))

    local aes = require "resty.aes"
    local str = require "resty.string"
    local aes_128_cbc_with_iv = assert(aes:new("1234567890123456",
        nil, aes.cipher(128,"cbc"), {iv="1234567890123456"}))
        -- AES 128 CBC with IV and no SALT
    local encrypted = aes_128_cbc_with_iv:encrypt("Really secret message!")
    ngx.say("AES 128 CBC (WITH IV) Encrypted HEX: ", str.to_hex(encrypted))
    ngx.say("AES 128 CBC (WITH IV) Decrypted: ",
        aes_128_cbc_with_iv:decrypt(encrypted))

    local aes = require "resty.aes"
    local str = require "resty.string"
    local enable_padding = false
    local aes_256_cbc_with_padding = aes:new(
        key, nil, aes.cipher(256,"cbc"), {iv = string.sub(key, 1, 16)}, nil,
        nil, enable_padding)
        -- AES-256 CBC (custom keygen, user padding with block_size=32)
    local text = "hello"
    local block_size = 32
    local pad = block_size - #text % 32
    local text_paded = text .. string.rep(string.char(pad), pad)
    local encrypted = aes_256_cbc_with_padding:encrypt(text_paded)
    ngx.say("AES-256 CBC (custom keygen, user padding with block_size=32) HEX: ",
        str.to_hex(encrypted))
```

[Back to TOC](#table-of-contents)

Author
======

Yichun "agentzh" Zhang (章亦春) <agentzh@gmail.com>

[Back to TOC](#table-of-contents)

Copyright and License
=====================

This module is licensed under the BSD license.

Copyright (C) 2012-2018, by Yichun "agentzh" Zhang (章亦春) <agentzh@gmail.com>, OpenResty Inc.

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

[Back to TOC](#table-of-contents)

See Also
========
* the ngx_lua module: http://wiki.nginx.org/HttpLuaModule

[Back to TOC](#table-of-contents)

