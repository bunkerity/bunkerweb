# vim: set ss=4 ft= sw=4 et sts=4 ts=4:

use lib '.';
use t::TestLJ;

plan tests => 3 * blocks();

run_tests();

__DATA__

=== TEST 1: interpreted (sanity)
--- lua
jit.off()

function print_array(a)
  local out = a[1]
  for i=2,#a do
    out = out.." "..tostring(a[i])
  end
  print(out)
end

jit.prngstate({32})
print_array(jit.prngstate({56,1,7}))
print_array(jit.prngstate({423,432,432,423,56,867,35,5347}))
print_array(jit.prngstate())
print_array(jit.prngstate({423,432,432,423,56,867,35,5347,452}))
--- out
32 0 0 0 0 0 0 0
56 1 7 0 0 0 0 0
423 432 432 423 56 867 35 5347
--- jv
--- err
bad argument #1 to 'prngstate' (PRNG state must be an array with up to 8 integers or an integer)
--- exit: 1



=== TEST 2: JIT (set)
--- lua
jit.opt.start("minstitch=100000", "hotloop=2")

for i = 1, 50 do
  jit.prngstate({i})
end
print('ok')
--- out
ok
--- jv
--- err eval
qr/trace too short at jit\.prngstate/



=== TEST 3: PRNG state can be an integer
--- lua
function print_array(a)
  local out = a[1]
  for i=2,#a do
    out = out.." "..tostring(a[i])
  end
  print(out)
end

jit.prngstate(0)
print_array(jit.prngstate(30))
print_array(jit.prngstate(32))
print_array(jit.prngstate(4294967296)) -- 2 ** 32
--- out
0 0 0 0 0 0 0 0
30 0 0 0 0 0 0 0
--- jv
--- err
bad argument #1 to 'prngstate' (PRNG state must be an array with up to 8 integers or an integer)
--- exit: 1
