# vim: set ss=4 ft= sw=4 et sts=4 ts=4:

use lib '.';
use t::TestLJ;

plan tests => 3 * blocks();

run_tests();

__DATA__

=== TEST 1: pairs() loop jit
--- jv
--- lua
jit.opt.start("minstitch=1", "hotloop=2")
local tb = {}
for i = 1, 100 do
  local s = "a" .. i
  tb[s] = i
end
local total = 0
for k, v in pairs(tb) do
  total = total + tb[k]
end
print("total = " .. total)
--- out
total = 5050
--- err
[TRACE   1 test.lua:3 loop]
[TRACE   2 test.lua:8 loop]
[TRACE   3 (2/1) test.lua:8 stitch print]



=== TEST 2: explicit next() in loops
--- jv
--- lua
jit.opt.start("minstitch=1", "hotloop=2")
local tb = {}
for i = 1, 100 do
  local s = "a" .. i
  tb[s] = i
end
local function f(tb, k)
  if not next(tb) then
    return nil
  end
  -- print("k = " .. k)
  return k, tb["a" .. k]
end
local total = 0
for i = 1, 100 do
  local k, v = f(tb, i)
  if not v then
    break
  end
  total = total + v
end
print("total = " .. total)
--- out
total = 5050
--- err
[TRACE   1 test.lua:3 loop]
[TRACE   2 test.lua:15 loop]



=== TEST 3: custom lua iterator
--- jv
--- lua
jit.opt.start("minstitch=1", "hotloop=2")
local tb = {}
for i = 1, 100 do
  local s = "a" .. i
  tb[s] = i
end
local iter
function iter2(tb, k)
    if k >= 100 then
        return nil
    end
    return k + 1, tb["a" .. (k + 1)]
end

function iter(tb, k)
    -- print("tb = " .. tostring(tb))
    -- print("key = " .. tostring(k))
    if k == nil then
        return iter2, tb, 0
    end
    error("bad")
end
local total = 0
for k, v in iter(tb) do
    if not v then
        print("value is nil for key " .. tostring(k))
    end
    total = total + v
end
print("total = " .. total)
--- out
total = 5050
--- err
[TRACE   1 test.lua:3 loop]
[TRACE   2 test.lua:24 loop]
