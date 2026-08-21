"""Zero means "no expiry" to the shared dict and "already expired" to lrucache.

`datastore:set(key, value, exptime, worker=true)` writes the per-worker LRU. The two backing stores
read `exptime = 0` in opposite ways: `ngx.shared.DICT:safe_set` treats it as *never expires*, while
`resty.lrucache:set` treats it as a TTL that has already elapsed. Passing it through therefore makes
the very next `get()` a miss -- silently, with the value having been "stored" successfully.

This exists because `47e1ec72a` normalised only the negative case (`exptime < 0`) and `a3e3eeb98`
had to come back for the zero. RULE 14a: the moment that fix went in is the moment its test should
have, and the round-3 port applied both hunks four hours apart.

TWO TIERS, AND THE REASON THEY ARE SPLIT
----------------------------------------
`resty.lrucache` is a LuaJIT library -- `lib/resty/lrucache.lua:4` is `require "ffi"`. This host has
PUC Lua 5.4.8 and no LuaJIT, so the real library cannot be loaded here at all. Skipping the whole
file on that basis would be wrong: it would discard coverage of the fix, which is a branch in
`datastore.lua` and has nothing to do with ffi.

    tier 1  ffi-free.  A faithful stub of `resty.lrucache` records what ttl `datastore:set` passed
            it. This is where the FIX is tested, and it is the tier that catches the `<= 0` -> `< 0`
            mutant. Runs on any host with a lua interpreter.
    tier 2  needs ffi. Loads the REAL library and proves a zero ttl really does expire -- the
            PREMISE the stub models. Skipped here; see the RULE 15 note below.

A stub can only be trusted while it still matches the thing it stands in for, so
`test_the_stub_still_models_the_vendored_lrucache` pins the three source lines it was derived from.
That test is pure Python and never skips, which is what keeps tier 1 honest while tier 2 is dark.

RULE 15 -- THE HOLE THIS FILE CANNOT CLOSE
------------------------------------------
A skipped test is not a passing test and CI cannot tell them apart, so
`test_not_every_behavioural_case_is_skipped_on_this_host` FAILS rather than skips if the ffi-free
tier is unrunnable too. It cannot manufacture a LuaJIT host, though: tier 2 stays dark until one
exists. That is a real gap in this release's verification story and it is written up for the closing
chantier -- no host we run tests on can execute `resty.lrucache`, so every fix whose *consequence*
lives inside that library is verified by model rather than by execution.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "datastore.lua"
LRUCACHE_SRC = ROOT / "src" / "deps" / "src" / "lua-resty-lrucache" / "lib" / "resty" / "lrucache.lua"

HAS_LUA = shutil.which("lua") is not None
HAS_FFI = HAS_LUA and subprocess.run(["lua", "-e", "require 'ffi'"], capture_output=True).returncode == 0

needs_lua = pytest.mark.skipif(not HAS_LUA, reason="no lua interpreter on this host")
needs_ffi = pytest.mark.skipif(not HAS_FFI, reason="resty.lrucache is a LuaJIT library; this host has no ffi")

# The stub is a transcription of lua-resty-lrucache, not an approximation of it. Each line carries
# the vendored line it came from, and test_the_stub_still_models_the_vendored_lrucache pins them.
LRU_STUB = """
package.preload["resty.lrucache"] = function()
    local M = {}
    M.__index = M
    function M.new(size)
        return setmetatable({ slots = {}, size = size }, M)
    end
    function M:set(key, value, ttl)
        -- lrucache.lua:266  node.expire = ngx_now() + ttl   /  :268  node.expire = -1
        RECORDED_TTL = ttl == nil and "nil" or tostring(ttl)
        self.slots[key] = { value = value, expire = ttl and ngx.now() + ttl or -1 }
    end
    function M:get(key)
        local node = self.slots[key]
        if not node then
            return nil
        end
        -- lrucache.lua:198  if node.expire >= 0 and node.expire < ngx_now() then -> stale
        if node.expire >= 0 and node.expire < ngx.now() then
            return nil, node.value
        end
        return node.value
    end
    return M
end
"""

HARNESS = """
package.path = "@DEPS@/lua-resty-lrucache/lib/?.lua;@ROOT@/src/bw/lua/?.lua;" .. package.path
-- logger.lua reaches for OpenResty's error log; stub it rather than pull in OpenResty.
package.preload["ngx.errlog"] = function() return { raw_log = function() end } end
NOW = 1000
ngx = {
    ERR = 1, WARN = 2, INFO = 3,
    config = { subsystem = "http" },
    shared = { datastore = {}, datastore_stream = {} },
    log = function() end,
    now = function() return NOW end,
}
@STUB@
local datastore = dofile("@MODULE@")
local store = datastore:new()

@BODY@
"""


def _run(body, *, stub=True):
    script = (
        HARNESS.replace("@DEPS@", str(ROOT / "src" / "deps" / "src"))
        .replace("@ROOT@", str(ROOT))
        .replace("@MODULE@", str(MODULE))
        .replace("@STUB@", LRU_STUB if stub else "")
        .replace("@BODY@", body)
    )
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


# --------------------------------------------------------------------------- tier 1: the fix
# RULE 13: a floor, not an exact count -- widening this list is collaboration, not regression.
NO_EXPIRY_SPELLINGS = ["0", "-1", "nil"]
MINIMUM_NO_EXPIRY_SPELLINGS = 3


@needs_lua
@pytest.mark.parametrize("exptime", NO_EXPIRY_SPELLINGS)
def test_a_non_positive_exptime_is_normalised_before_it_reaches_the_lru(exptime):
    """The fix itself: datastore:set must hand lrucache `nil`, not the caller's spelling of zero.

    The mutant this catches is `exptime <= 0` weakened back to `exptime < 0` -- zero then reaches
    lrucache verbatim, as a ttl that elapsed the instant it was written."""
    out = _run(
        f"""
        store:set("k", "v", {exptime}, true)
        print(tostring(RECORDED_TTL))
        """
    )
    assert out == "nil", f"datastore passed ttl={out!r} to lrucache for exptime={exptime}; only nil means no expiry there"


@needs_lua
@pytest.mark.parametrize("exptime", NO_EXPIRY_SPELLINGS)
def test_a_value_written_with_no_expiry_survives_the_passage_of_time(exptime):
    """The consequence, not just the argument: advance the clock past any ttl and re-read.

    With the fix reverted, `exptime = 0` yields `expire = ngx.now()`, and one tick later
    `expire < ngx.now()` holds -- so this is the case that goes red on the mutant."""
    out = _run(
        f"""
        store:set("k", "v", {exptime}, true)
        NOW = NOW + 3600
        print(tostring(store:get("k", true)))
        """
    )
    assert out == "v", f"exptime={exptime} expired despite meaning no-expiry: {out!r}"


@needs_lua
def test_a_positive_exptime_is_still_honoured():
    """Anti-vacuity: the normalisation must not turn every write into a permanent one."""
    fresh = _run(
        """
        store:set("k", "v", 60, true)
        print(tostring(store:get("k", true)))
        """
    )
    assert fresh == "v", "a live value must read back"

    stale = _run(
        """
        store:set("k", "v", 60, true)
        NOW = NOW + 61
        print(tostring(store:get("k", true)))
        """
    )
    assert stale == "nil", "a 60s ttl must still expire after 61s -- the normalisation swallowed it"


# --------------------------------------------------- the stub's licence to stand in for the library
def test_the_stub_still_models_the_vendored_lrucache():
    """The three lines LRU_STUB was transcribed from. If the vendored library moves, this fails and
    the stub gets re-derived rather than silently modelling a contract that no longer exists."""
    source = LRUCACHE_SRC.read_text(encoding="utf-8")
    for line in (
        r"node\.expire = ngx_now\(\) \+ ttl",
        r"node\.expire = -1",
        r"if node\.expire >= 0 and node\.expire < ngx_now\(\) then",
    ):
        assert re.search(line, source), f"lrucache no longer contains {line!r}; re-derive LRU_STUB"


# ------------------------------------------------------------------ tier 2: the premise (needs ffi)
@needs_ffi
def test_the_real_lrucache_treats_a_zero_ttl_as_already_expired():
    """Why the normalisation has to exist at all. Runs against the real library, not the stub."""
    out = _run(
        """
        local lrucache = require "resty.lrucache"
        local c = lrucache.new(10)
        c:set("k", "v", 0)
        NOW = NOW + 1
        print(tostring(c:get("k")))
        """,
        stub=False,
    )
    assert out == "nil", "a zero ttl did not expire -- the premise of this whole file is wrong"


# ------------------------------------------------------------------------------ RULE 15 anti-skip
def test_not_every_behavioural_case_is_skipped_on_this_host():
    """A skipped test is not a passing test, and `0 failed` looks identical either way.

    This one never skips. If the ffi-free tier is unrunnable too, the file is contributing nothing
    and says so in red. It cannot vouch for tier 2 -- see the RULE 15 note in the module docstring."""
    assert len(NO_EXPIRY_SPELLINGS) >= MINIMUM_NO_EXPIRY_SPELLINGS, "the parametrised list emptied; a vacuous parametrize reports success over zero cases"
    assert HAS_LUA, "no lua interpreter: every behavioural case in this file skipped, and the datastore exptime fix has zero coverage on this host"
