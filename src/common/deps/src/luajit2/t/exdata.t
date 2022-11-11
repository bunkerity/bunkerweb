# vim: set ss=4 ft= sw=4 et sts=4 ts=4:

use lib '.';
use t::TestLJ;

plan tests => 3 * blocks();

run_tests();

__DATA__

=== TEST 1: interpreted (sanity)
--- lua
jit.off()
local assert = assert
local exdata = require "thread.exdata"
local ffi = require "ffi"
local u64 = ffi.new("uintptr_t", 0xefdeaddeadbeefLL)
local ptr = ffi.cast("void *", u64)
local saved_q
for i = 1, 5 do
    exdata(u64)
    local q = exdata()
    if saved_q then
        assert(q == saved_q)
    end
    saved_q = q
end
print(tostring(ptr))
print(tostring(saved_q))
--- jv
--- out
cdata<void *>: 0xefdeaddeadbeef
cdata<void *>: 0xefdeaddeadbeef
--- err



=== TEST 2: newly created coroutines should inherit the exdata
--- lua
jit.off()
local exdata = require "thread.exdata"
local ffi = require "ffi"
local u64 = ffi.new("uintptr_t", 0xefdeadbeefLL)
local ptr = ffi.cast("void *", u64)
local ptr2 = ffi.cast("void *", u64 + 1)
local ptr3 = ffi.cast("void *", u64 - 2)
local saved_q
local function f()
    coroutine.yield(exdata())
    exdata(ptr2)
    coroutine.yield(exdata())
    coroutine.yield(exdata())
end

exdata(u64)

local co = coroutine.create(f)

local ok, data = coroutine.resume(co)
assert(ok)
print(tostring(data))

ok, data = coroutine.resume(co)
assert(ok)
print(tostring(data))

exdata(ptr3)

ok, data = coroutine.resume(co)
assert(ok)
print(tostring(data))

print(tostring(exdata()))
--- jv
--- out
cdata<void *>: 0xefdeadbeef
cdata<void *>: 0xefdeadbef0
cdata<void *>: 0xefdeadbef0
cdata<void *>: 0xefdeadbeed
--- err



=== TEST 3: JIT mode (reading)
--- lua
jit.opt.start("minstitch=100000", "hotloop=2")
local assert = assert
local exdata = require "thread.exdata"
local ffi = require "ffi"
local u64 = ffi.new("uintptr_t", 0xefdeaddeadbeefLL)
local ptr = ffi.cast("void *", u64)
local saved_q
exdata(u64)
for i = 1, 10 do
    local q = exdata()
    if saved_q then
        assert(q == saved_q)
    end
    saved_q = q
end
print(tostring(ptr))
print(tostring(saved_q))

--- jv
--- out
cdata<void *>: 0xefdeaddeadbeef
cdata<void *>: 0xefdeaddeadbeef
--- err
[TRACE   1 test.lua:9 loop]



=== TEST 4: JIT mode (writing)
--- lua
jit.opt.start("minstitch=100000", "hotloop=2")
local assert = assert
local exdata = require "thread.exdata"
local ffi = require "ffi"
local u64 = ffi.new("uintptr_t", 0xefdeaddeadbeefLL)
local ptr = ffi.cast("void *", u64)
local saved_q
for i = 1, 10 do
    exdata(u64)
    local q = exdata()
    if saved_q then
        assert(q == saved_q)
    end
    saved_q = q
end
print(tostring(ptr))
print(tostring(saved_q))

--- jv
--- out
cdata<void *>: 0xefdeaddeadbeef
cdata<void *>: 0xefdeaddeadbeef
--- err
[TRACE --- test.lua:8 -- trace too short at thread.exdata]



=== TEST 5: interpreted  - check the number of arguments
--- lua
jit.off()
local assert = assert
local select = select
local exdata = require "thread.exdata"
local ffi = require "ffi"
local u64 = ffi.new("uintptr_t", 0xefdeaddeadbeefLL)
local ptr = ffi.cast("void *", u64)

local function nargs(...)
    return select('#', ...)
end
print(nargs(exdata(ptr)))
print(nargs(exdata()))
--- jv
--- out
0
1
--- err



=== TEST 6: JIT mode  - check the number of arguments
--- lua
jit.opt.start("minstitch=100000", "hotloop=2")
local assert = assert
local select = select
local exdata = require "thread.exdata"
local ffi = require "ffi"
local u64 = ffi.new("uintptr_t", 0xefdeaddeadbeefLL)
local ptr = ffi.cast("void *", u64)

local function nargs(...)
    return select('#', ...)
end

local total = 0
for i = 1, 10 do
    total = total + nargs(exdata(ptr))
end

print("set: " .. total)

total = 0
for i = 1, 10 do
    total = total + nargs(exdata())
end

print("get: " .. total)
--- jv
--- out
set: 0
get: 10
--- err
[TRACE --- test.lua:14 -- trace too short at thread.exdata]
[TRACE   1 test.lua:21 loop]



=== TEST 7: interpreted (no ffi initialized)
--- lua
jit.off()
local assert = assert
local exdata = require "thread.exdata"
local saved_q
for i = 1, 5 do
    local q = exdata()
    if saved_q then
        assert(q == saved_q)
    end
    saved_q = q
end
print(tostring(saved_q))
--- jv
--- out
--- err
ffi module not loaded (yet)
--- exit: 1



=== TEST 8: default value (interpreted)
--- lua
jit.off()
local assert = assert
require "ffi"
local exdata = require "thread.exdata"
local saved_q
for i = 1, 5 do
    local q = exdata()
    if saved_q then
        assert(q == saved_q)
    end
    saved_q = q
end
print(saved_q == nil)
print(tostring(saved_q))
--- jv
--- out
true
cdata<void *>: NULL
--- err



=== TEST 9: default value (JIT)
--- lua
jit.opt.start("minstitch=100000", "hotloop=2")
jit.on()
local assert = assert
require "ffi"
local exdata = require "thread.exdata"
local saved_q
for i = 1, 5 do
    local q = exdata()
    if saved_q then
        assert(q == saved_q)
    end
    saved_q = q
end
print(saved_q == nil)
print(tostring(saved_q))
--- jv
--- out
true
cdata<void *>: NULL
--- err
[TRACE   1 test.lua:7 loop]
