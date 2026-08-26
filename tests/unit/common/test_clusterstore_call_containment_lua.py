"""A misbehaving Redis reply must not escape `clusterstore:call` nor poison the keepalive pool.

`utils.is_connection_error` documents the invariant: a socket that is dead or mid-command
"must never go back to the keepalive pool for the next borrower to desync on", and callers
enforce it by flipping `healthy` off so `close()` hard-closes instead of `set_keepalive`.
Two shapes slipped through it:

* **a raise.** lua-resty-redis reads a reply off a desynced stream and reaches `string.byte`
  with a non-string. In run 32834226362 that killed `reversescan:access()` outright
  (`resty/redis.lua:255: bad argument #1 to 'byte' (string expected, got boolean)`), and the
  request was served unscanned — while `healthy` stayed true, so the poisoned socket was
  offered back to the pool. The log records what happened next, on the same request:
  `set_keepalive failed: socket busy reading` then `error while closing redis_client`.
* **a protocol desync.** lua-resty-redis reports it as `unknown prefix: "..."`, which matches
  none of is_connection_error's substrings, so that socket was recycled too.

A redis call is I/O: it reports failures, it does not abort its caller's phase.

Runs through the ``lua`` binary with OpenResty stubbed.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "clusterstore.lua"
LUA_DIR = ROOT / "src" / "bw" / "lua"
UTILS = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")


def real_predicate(name: str) -> str:
    """Return the shipped `utils.<name>` function expression, source-exact.

    Splicing the real body in is what keeps this file honest: delete or narrow the classifier
    in utils.lua and the extraction fails here rather than the assertions passing on a copy.
    """
    body = re.search(rf"^utils\.{name} = (function\(err\).*?^end)$", UTILS.read_text(encoding="utf-8"), re.M | re.S)
    assert body, f"utils.{name} is gone from {UTILS}"
    return body.group(1)


HARNESS = """
package.path = "%s/?.lua;" .. package.path

ngx = { ERR = 1, WARN = 4, INFO = 7 }

package.loaded["bunkerweb.logger"] = {
    new = function(_, _) return { log = function() end } end,
}
package.loaded["resty.redis.connector"] = { new = function() return {}, nil end }
-- The real predicates, spliced out of utils.lua rather than restated here: a copy would let
-- this file keep passing while the shipped classifier was weakened or deleted outright.
package.loaded["bunkerweb.utils"] = {
    get_variable = function() return "", nil end,
    is_cosocket_available = function() return false end,
    is_connection_error = %s,
    is_protocol_error = %s,
}

local clusterstore = dofile("%s")

-- `call` only reads self.redis_client and writes self.healthy, so the object is built
-- directly: initialize() would drag in the whole settings read for nothing.
local function new_store(method)
    local store = clusterstore:allocate()
    store.healthy = true
    store.redis_client = { eval = method }
    return store
end

-- 1. A raise is contained: it is reported, not propagated, and the socket is condemned.
local store = new_store(function() error("resty/redis.lua:255: bad argument #1 to 'byte' (string expected, got boolean)") end)
local ok, res, err = pcall(store.call, store, "eval", "return 1")
assert(ok, "a raising redis client must not propagate out of call(): " .. tostring(res))
assert(res == nil, "a raise must report nil, got " .. tostring(res))
assert(err and err:find("redis client raised", 1, true), "unexpected error: " .. tostring(err))
assert(store.healthy == false, "a raise must condemn the socket so close() does not keepalive it")

-- 2. A protocol desync is condemned too, even though it names no socket condition.
store = new_store(function() return nil, 'unknown prefix: "t"' end)
res, err = store:call("eval", "return 1")
assert(res == nil and err == 'unknown prefix: "t"', "the error must pass through unchanged")
assert(store.healthy == false, "a desynced stream must never go back to the keepalive pool")

-- 3. The pre-existing connection-error classification is unchanged.
store = new_store(function() return nil, "connection reset by peer" end)
store:call("eval", "return 1")
assert(store.healthy == false, "a connection error must still condemn the socket")

-- 4. A Redis-level error (RESP '-') is not a socket problem: the connection stays reusable.
store = new_store(function() return false, "ERR wrong number of arguments" end)
res, err = store:call("eval", "return 1")
assert(res == false and err == "ERR wrong number of arguments", "the RESP error must pass through")
assert(store.healthy == true, "a RESP error must not condemn a perfectly good socket")

-- 5. Success is untouched.
store = new_store(function() return "pong", nil end)
res, err = store:call("eval", "return 1")
assert(res == "pong" and err == nil, "a successful call must pass its value through")
assert(store.healthy == true, "a successful call must leave the socket healthy")

-- 6. No client at all still reports rather than raises.
store = clusterstore:allocate()
res, err = store:call("eval", "return 1")
assert(res == false and err == "client is not instantiated", "unexpected: " .. tostring(res) .. " / " .. tostring(err))

print("OK")
"""


def test_a_raise_or_desync_is_contained_and_condemns_the_socket():
    result = subprocess.run(
        ["lua", "-e", HARNESS % (LUA_DIR.as_posix(), real_predicate("is_connection_error"), real_predicate("is_protocol_error"), MODULE.as_posix())],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
