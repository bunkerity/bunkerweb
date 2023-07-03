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
local exdata2 = require "thread.exdata2"
local ffi = require "ffi"
local u64 = ffi.new("uintptr_t", 0xefdeaddeadbeefLL)
local ptr = ffi.cast("void *", u64)
local saved_q
for i = 1, 5 do
    exdata2(u64)
    local q = exdata2()
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



=== TEST 2: interpreted (using both exdata and exdata2)
--- lua
jit.off()
local assert = assert
local exdata = require "thread.exdata"
local exdata2 = require "thread.exdata2"
assert(exdata ~= exdata2)
local ffi = require "ffi"
local u64 = ffi.new("uintptr_t", 0xefdeaddeadbeefLL)
local u64_2 = ffi.new("uintptr_t", 0xefdeaddeddbeffLL)
local ptr = ffi.cast("void *", u64)
local saved_q
exdata(u64)
exdata2(u64_2)
print(tostring(exdata()))
print(tostring(exdata2()))
--- jv
--- out
cdata<void *>: 0xefdeaddeadbeef
cdata<void *>: 0xefdeaddeddbeff
--- err



=== TEST 3: newly created coroutines should inherit the exdata2
--- lua
jit.off()
local exdata2 = require "thread.exdata2"
local ffi = require "ffi"
local u64 = ffi.new("uintptr_t", 0xefdeadbeefLL)
local ptr = ffi.cast("void *", u64)
local ptr2 = ffi.cast("void *", u64 + 1)
local ptr3 = ffi.cast("void *", u64 - 2)
local saved_q
local function f()
    coroutine.yield(exdata2())
    exdata2(ptr2)
    coroutine.yield(exdata2())
    coroutine.yield(exdata2())
end

exdata2(u64)

local co = coroutine.create(f)

local ok, data = coroutine.resume(co)
assert(ok)
print(tostring(data))

ok, data = coroutine.resume(co)
assert(ok)
print(tostring(data))

exdata2(ptr3)

ok, data = coroutine.resume(co)
assert(ok)
print(tostring(data))

print(tostring(exdata2()))
--- jv
--- out
cdata<void *>: 0xefdeadbeef
cdata<void *>: 0xefdeadbef0
cdata<void *>: 0xefdeadbef0
cdata<void *>: 0xefdeadbeed
--- err



=== TEST 4: JIT mode (reading)
--- lua
jit.opt.start("minstitch=100000", "hotloop=2")
local assert = assert
local exdata2 = require "thread.exdata2"
local ffi = require "ffi"
local u64 = ffi.new("uintptr_t", 0xefdeaddeadbeefLL)
local ptr = ffi.cast("void *", u64)
local saved_q
exdata2(u64)
for i = 1, 10 do
    local q = exdata2()
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



=== TEST 5: JIT mode (writing)
--- lua
jit.opt.start("minstitch=100000", "hotloop=2")
local assert = assert
local exdata2 = require "thread.exdata2"
local ffi = require "ffi"
local u64 = ffi.new("uintptr_t", 0xefdeaddeadbeefLL)
local ptr = ffi.cast("void *", u64)
local saved_q
for i = 1, 10 do
    exdata2(u64)
    local q = exdata2()
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
[TRACE --- test.lua:8 -- trace too short at thread.exdata2]



=== TEST 6: interpreted  - check the number of arguments
--- lua
jit.off()
local assert = assert
local select = select
local exdata2 = require "thread.exdata2"
local ffi = require "ffi"
local u64 = ffi.new("uintptr_t", 0xefdeaddeadbeefLL)
local ptr = ffi.cast("void *", u64)

local function nargs(...)
    return select('#', ...)
end
print(nargs(exdata2(ptr)))
print(nargs(exdata2()))
--- jv
--- out
0
1
--- err



=== TEST 7: JIT mode  - check the number of arguments
--- lua
jit.opt.start("minstitch=100000", "hotloop=2")
local assert = assert
local select = select
local exdata = require "thread.exdata"
local exdata2 = require "thread.exdata2"
local ffi = require "ffi"
local u64 = ffi.new("uintptr_t", 0xefdeaddeadbeefLL)
local ptr = ffi.cast("void *", u64)

local function nargs(...)
    return select('#', ...)
end

local total = 0
for i = 1, 10 do
    total = total + nargs(exdata2(ptr))
end

print("set: " .. total)

total = 0
for i = 1, 10 do
    total = total + nargs(exdata2())
end

print("get: " .. total)
print(tostring(exdata()))
print(tostring(exdata2()))
--- jv
--- out
set: 0
get: 10
cdata<void *>: NULL
cdata<void *>: 0xefdeaddeadbeef
--- err
[TRACE --- test.lua:15 -- trace too short at thread.exdata2]
[TRACE   1 test.lua:22 loop]



=== TEST 8: interpreted (no ffi initialized)
--- lua
jit.off()
local assert = assert
local exdata2 = require "thread.exdata2"
local saved_q
for i = 1, 5 do
    local q = exdata2()
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



=== TEST 9: default value (interpreted)
--- lua
jit.off()
local assert = assert
require "ffi"
local exdata2 = require "thread.exdata2"
local saved_q
for i = 1, 5 do
    local q = exdata2()
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



=== TEST 10: default value (JIT)
--- lua
jit.opt.start("minstitch=100000", "hotloop=2")
jit.on()
local assert = assert
require "ffi"
local exdata2 = require "thread.exdata2"
local saved_q
for i = 1, 5 do
    local q = exdata2()
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
