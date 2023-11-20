# vim:ft=

use lib '.';
use t::TestLJ;

plan tests => 3 * blocks();

run_tests();

__DATA__

=== TEST 1: empty tables - interpreted
--- lua
jit.off()
local new_tab = require "table.new"
local isempty = require "table.isempty"
local list = {
  {},
  new_tab(5, 6),
  { nil },
  { dogs = nil },
}
for i, t in ipairs(list) do
    assert(isempty(t))
end
print("ok")

--- jv
--- out
ok
--- err



=== TEST 2: empty tables - JIT
--- lua
jit.on()
require "jit.opt".start("hotloop=3")
local new_tab = require "table.new"
local isempty = require "table.isempty"
local list = {
  {},
  new_tab(5, 6),
  { nil },
  { dogs = nil },
}
for i, t in ipairs(list) do
    for i = 1, 10 do
        assert(isempty(t))
    end
end
print("ok")

--- jv
--- out
ok
--- err
[TRACE   1 test.lua:12 loop]
[TRACE   2 test.lua:11 -> 1]



=== TEST 3: non-empty tables - interpreted
--- lua
jit.off()
local new_tab = require "table.new"
local isempty = require "table.isempty"
local list = {
  { 3.1 },
  { "a", "b" },
  { nil, false },
  { dogs = 3 },
  { dogs = 3, cats = 4 },
  { dogs = 3, 5 },
}
for i, t in ipairs(list) do
    assert(not isempty(t))
end
print("ok")

--- jv
--- out
ok
--- err



=== TEST 4: non-empty tables - JIT
--- lua
jit.on()
require "jit.opt".start("hotloop=3")
local new_tab = require "table.new"
local isempty = require "table.isempty"
local list = {
  { 3.1 },
  { "a", "b" },
  { nil, false },
  { dogs = 3 },
  { dogs = 3, cats = 4 },
  { dogs = 3, 5 },
}
for i, t in ipairs(list) do
    for i = 1, 10 do
        assert(not isempty(t))
    end
end
print("ok")

--- jv
--- out
ok
--- err
[TRACE   1 test.lua:14 loop]
[TRACE   2 test.lua:13 -> 1]
