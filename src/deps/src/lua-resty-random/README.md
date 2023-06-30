lua-resty-random
================

**lua-resty-random** is a random library for OpenResty.

This library works only in OpenResty (or Nginx with Lua module) that has OpenSSL support.

## Hello World with lua-resty-random

```lua
local random = require "resty.random"
-- Get two random bytes
local bytes = random.bytes(2)
-- Get two random bytes hexadecimal encoded
local hxbts = random.bytes(2, 'hex')
-- Get random number
local numbr = random.number(1, 10)
-- Get random token (by default uses A-Z, a-z, and 0-9 chars)
local token = random.token(10)
```

## About The Internals

For random bytes `lua-resty-random` uses OpenSSL `RAND_bytes` that is included in OpenResty (or Nginx) when compiled with OpenSSL. For random numbers the library uses Lua's `math.random`, and `math.randomseed`. You should note that on LuaJIT environment, LuaJIT uses a Tausworthe PRNG with period 2^223 to implement `math.random` and `math.randomseed`. Hexadecimal dumps are implemented using `ngx_hex_dump`.

## Lua API
#### string random.bytes(len, format)

Returns `len` number of random bytes using OpenSSL `RAND_bytes`. You may optionally pass `"hex"` as format argument if you want random bytes hexadecimal encoded.

##### Example

```lua
local random = require "resty.random"
print(random.bytes(10))
print(random.bytes(10, "hex")
```

#### number random.number(min, max, reseed)

Returns random number between `min` and `max` (including `min` and `max`). You may optionally pass `true` as reseed argument if you want to reseend random number generator (normally not needed, and random number generator is seeded once when you do `require "resty.random"`.

##### Example

```lua
local random = require "resty.random"
print(random.number(1, 10))
print(random.number(1, 10, true))
```

#### string random.token(len, chars, sep)

Returns random token consisting of chars (by default it uses A-Z, a-z, and 0-9 as chars). You may also pass a string as a separator with `sep` argument.

##### Example

```lua
local random = require "resty.random"
print(random.token(10))
print(random.token(10, "ABCD"))
print(random.token(10, { "A", "B", "C", "D" }))
print(random.token(10, { "Ford", "Audi", "Mustang", "A6" }, " "))
```

## License

`lua-resty-random` uses two clause BSD license.

```
Copyright (c) 2013, Aapo Talvensaari
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this
  list of conditions and the following disclaimer in the documentation and/or
  other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
