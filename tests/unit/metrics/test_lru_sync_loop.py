"""The timer's LRU sync loop: walk direction, and what a miss must not write.

Two defects in one loop, fixed together because the first one manufactures the second.

**Direction.** ``lru:get_keys()`` returns the keys hottest-first, and ``lru:get()`` promotes what it
reads (``src/deps/src/lua-resty-lrucache/lib/resty/lrucache.lua:195-196`` -- ``queue_remove`` then
``queue_insert_head``). Walking that snapshot forward therefore reverses the entire queue on every
timer cycle, and the next insertion evicts the *hottest* key instead of the coldest. Measured on the
real library, five keys, one insertion after the walk::

    forward   before=k5,k4,k3,k2,k1   after=k1,k2,k3,k4,k5   evicted=k5   <- the hottest
    backward  before=k5,k4,k3,k2,k1   after=k5,k4,k3,k2,k1   evicted=k1   <- correct

**Misses.** ``get_keys()`` is a snapshot and every ``redis_call`` in the loop body yields, so a
concurrent ``log()`` can evict a key before the loop reaches it. ``lru:get()`` then returns nil,
``type(nil) ~= "table"`` sends it down the scalar branch, and ``tostring(nil)`` writes the literal
string ``"nil"`` into Redis as that counter's value.

The two compound: the forward walk leaves every *unvisited* key at the cold end of the queue, which
is precisely the set eligible for eviction during the yields. Fixing the direction makes the miss
rare; it does not make it impossible, so the guard is not optional.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
METRICS_LUA = ROOT / "src" / "common" / "core" / "metrics" / "metrics.lua"

LUA = shutil.which("luajit") or shutil.which("lua")
LUA_LRUCACHE = LUA is not None and subprocess.run([LUA, "-e", 'assert(require "resty.lrucache")'], capture_output=True, text=True).returncode == 0
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")
needs_lua_lrucache = pytest.mark.skipif(not LUA_LRUCACHE, reason="no stand-alone resty.lrucache on PATH")

# RULE 15. `resty.lrucache` needs LuaJIT's `ffi`, so on a plain-lua host the behavioural half of the
# coldest-first fix skipped and the file reported "4 passed, 2 skipped" -- which reads as success in
# any summary line while the fix itself was never executed. A skip is not a pass.
#
# So the property runs against TWO backends. The stub below implements the part of resty's contract
# the fix depends on, and nothing else: get_keys() hands keys back HOTTEST-FIRST, get() PROMOTES what
# it reads, and an insert past capacity evicts the tail. Those three facts are the entire reason a
# forward walk reverses the queue. It is not a substitute for resty -- the resty-backed case still
# runs wherever LuaJIT exists and is the fidelity check -- but it means no host runs zero behavioural
# cases. The stub is deliberately dumb: O(n) list surgery, no ffi, no eviction callbacks.
LRUCACHE_STUB = """
local lrucache = {}
lrucache.__index = lrucache
function lrucache.new(cap)
  return setmetatable({ cap = cap, order = {}, vals = {} }, lrucache)
end
local function detach(self, key)
  for i, k in ipairs(self.order) do
    if k == key then table.remove(self.order, i) return true end
  end
  return false
end
function lrucache:set(key, value)
  detach(self, key)
  table.insert(self.order, 1, key)
  self.vals[key] = value
  while #self.order > self.cap do
    local cold = table.remove(self.order)          -- the tail is the coldest
    self.vals[cold] = nil
  end
end
function lrucache:get(key)
  local value = self.vals[key]
  if value ~= nil and detach(self, key) then
    table.insert(self.order, 1, key)               -- reading PROMOTES
  end
  return value
end
function lrucache:get_keys()
  local out = {}
  for i, k in ipairs(self.order) do out[i] = k end -- hottest first
  return out
end
"""

# Reproduces the loop head, so the property is tested rather than the spelling.
WALK_PROPERTY = """
ngx = { now = function() return os.time() end, null = {} }
%s
local backwards = arg[1] == "backward"
local c = assert(lrucache.new(5))
for i = 1, 5 do c:set("k" .. i, i) end
local keys = c:get_keys()
if backwards then
  for i = #keys, 1, -1 do c:get(keys[i]) end
else
  for i = 1, #keys do c:get(keys[i]) end
end
c:set("new", 0)
local survivors = {}
for _, k in ipairs(c:get_keys()) do survivors[k] = true end
for i = 1, 5 do if not survivors["k" .. i] then print("k" .. i) end end
"""


def source() -> str:
    return METRICS_LUA.read_text(encoding="utf-8")


def test_the_sync_loop_walks_the_snapshot_backwards():
    """A forward walk over get_keys() is the defect; the snapshot local is part of the fix."""
    body = source()
    assert re.search(r"^\tlocal lru_keys = lru:get_keys\(\)$", body, re.M), "the snapshot must be taken once, into a local"
    assert re.search(r"^\tfor idx = #lru_keys, 1, -1 do$", body, re.M), "the sync loop must walk the snapshot backwards -- see the module docstring"
    assert not re.search(r"^\tfor _, key in ipairs\(lru:get_keys\(\)\) do$", body, re.M), "the forward walk is back"


def test_a_missing_lru_value_is_never_written_out():
    body = source()
    assert re.search(r"^\t\tif value ~= nil then$", body, re.M), 'without this guard tostring(nil) writes the string "nil" into Redis'
    # The guard is worthless if it does not actually enclose the write.
    guard = body.index("\t\tif value ~= nil then")
    write = body.index('redis_call("set", redis_key, tostring(value))')
    assert guard < write, "the nil guard no longer encloses the scalar write"


def test_the_shed_path_honours_the_configured_retry_count():
    """`METRICS_MEMORY_MAX_RETRIES` is a documented setting; the re-write after shedding is the same
    write and must not silently fall back to the library default."""
    body = source()
    assert body.count('set_with_retries(key .. "_" .. wid, encode(live), nil, max_retries)') == 1, "the shed re-write must pass max_retries"
    assert re.search(r'local max_retries = tonumber\(self\.variables\["METRICS_MEMORY_MAX_RETRIES"\]\) or 5', body), "max_retries must be resolved once"


def test_a_full_datastore_sheds_half_before_dropping_everything():
    body = source()
    assert re.search(r"while not ok and err == \"no memory\" do", body), "no shedding loop: a full datastore still drops the whole key history"
    assert "table_remove(live, 1)" in body, "shedding must drop the OLDEST entries"
    assert "datastore_shed_" in body and "datastore_purge_" in body, "both outcomes must be throttled-logged and distinguishable"
    assert not re.search(
        r'self\.logger:log\(INFO, "not enough memory in the metrics datastore', body
    ), "the purge is a WARN, not an INFO an operator scrolls past"


BACKENDS = [
    pytest.param('local lrucache = require "resty.lrucache"', id="resty", marks=needs_lua_lrucache),
    pytest.param(LRUCACHE_STUB, id="contract-stub"),
]
# RULE 15 floor: >= 1, because the stub case is unconditional. `==` would fight a host that HAS
# LuaJIT and legitimately runs both. What this catches is the two backends collapsing to zero
# runnable cases, which is what "4 passed, 2 skipped" looked like before the stub existed.
BEHAVIOURAL_BACKEND_FLOOR = 1


def test_at_least_one_walk_backend_actually_runs():
    """RULE 15: a skipped behavioural case and a passing one are the same line in a CI summary.

    `resty.lrucache` needs LuaJIT's `ffi`; this host has plain lua 5.4, so the resty case skips and
    the coldest-first fix went entirely unexecuted while the file reported success. This asserts the
    behavioural half is not inert -- not that any particular backend is present.
    """
    runnable = [b for b in BACKENDS if not any(m.name == "skipif" and m.args[0] for m in b.marks)]

    assert len(runnable) >= BEHAVIOURAL_BACKEND_FLOOR, (
        "every walk-direction backend is skipped: the coldest-first fix has NO behavioural coverage "
        "on this host. Install LuaJIT, or fix the contract stub -- do not bank the green."
    )


@needs_lua
@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize(("direction", "evicted"), [("forward", "k5"), ("backward", "k1")])
def test_the_walk_direction_decides_which_key_dies(tmp_path, direction, evicted, backend):
    """The property itself -- k5 is the hottest key, k1 the coldest. A forward walk promotes every
    key it reads, reversing the queue, so the next insert evicts the HOTTEST key instead of the
    coldest. That is the whole defect, and it is invisible to a source-level assertion."""
    script = tmp_path / "walk.lua"
    script.write_text(WALK_PROPERTY % backend, encoding="utf-8")
    result = subprocess.run([LUA, str(script), direction], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == [evicted], f"{direction} walk evicted {result.stdout.split()} instead of {evicted}"
