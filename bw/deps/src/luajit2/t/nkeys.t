# vim: set ss=4 ft= sw=4 et sts=4 ts=4:

use lib '.';
use t::TestLJ;

plan tests => 3 * blocks();

run_tests();

__DATA__

=== TEST 1: hash table, interpreted
--- lua
jit.off()
local new_tab = require "table.new"
local assert = assert
local nkeys = require "table.nkeys"
print(nkeys(new_tab(0, 4)))
print(nkeys({}))
print(nkeys({ cats = 4 }))
print(nkeys({ dogs = 3, cats = 4 }))
print(nkeys({ dogs = nil, cats = 4 }))
--- jv
--- out
0
0
1
2
1
--- err



=== TEST 2: hash table, JIT
--- lua
jit.on()
jit.opt.start("minstitch=100000", "hotloop=2")

local new_tab = require "table.new"
local assert = assert
local nkeys = require "table.nkeys"

local list = {
  new_tab(0, 4),
  {},
  { cats = 4 },
  { dogs = 3, cats = 4 },
  { dogs = nil, cats = 4 },
}

for i, t in ipairs(list) do
  local total = 0
  for i = 1, 10 do
    total = total + nkeys(t)
  end
  print(total)
end
--- jv
--- out
0
0
10
20
10
--- err
[TRACE   1 test.lua:18 loop]
[TRACE   2 test.lua:16 -> 1]



=== TEST 3: pure arrays, interpreted
--- lua
jit.off()
local new_tab = require "table.new"
local assert = assert
local nkeys = require "table.nkeys"
print(nkeys(new_tab(5, 0)))
print(nkeys({}))
print(nkeys({ "cats" }))
print(nkeys({ "dogs", 3, "cats", 4 }))
print(nkeys({ "dogs", nil, "cats", 4 }))
--- jv
--- out
0
0
1
4
3
--- err



=== TEST 4: pure array, JIT
--- lua
jit.on()
jit.opt.start("minstitch=100000", "hotloop=2")

local new_tab = require "table.new"
local assert = assert
local nkeys = require "table.nkeys"

local list = {
  new_tab(0, 4),
  {},
  { 3 },
  { "cats", 4 },
  { "dogs", 3, "cats", 4 },
  { "dogs", nil, "cats", 4 },
}

for i, t in ipairs(list) do
  local total = 0
  for i = 1, 10 do
    total = total + nkeys(t)
  end
  print(total)
end
--- jv
--- out
0
0
10
20
40
30
--- err
[TRACE   1 test.lua:19 loop]
[TRACE   2 test.lua:17 -> 1]



=== TEST 5: mixing array and hash table, interpreted
--- lua
jit.off()
local new_tab = require "table.new"
local assert = assert
local nkeys = require "table.nkeys"
print(nkeys({ cats = 4, 5, 6 }))
print(nkeys({ nil, "foo", dogs = 3, cats = 4 }))
--- jv
--- out
3
3
--- err



=== TEST 6: mixing array & hash, JIT
--- lua
jit.on()
jit.opt.start("minstitch=100000", "hotloop=2")

local new_tab = require "table.new"
local assert = assert
local nkeys = require "table.nkeys"

local list = {
  { cats = 4, 5, 6 },
  { nil, "foo", dogs = 3, cats = 4 },
}

for i, t in ipairs(list) do
  local total = 0
  for i = 1, 10 do
    total = total + nkeys(t)
  end
  print(total)
end
--- jv
--- out
30
30
--- err
[TRACE   1 test.lua:15 loop]
[TRACE   2 test.lua:13 -> 1]
