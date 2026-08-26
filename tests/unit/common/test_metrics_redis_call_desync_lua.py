"""`metrics:redis_call` must reconnect once when the reply stream desyncs, not fail the cycle.

`clusterstore:call` contains a desync and condemns the socket (`healthy = false`), but the two
shapes it reports name no socket condition:

* `unknown prefix: "..."` -- lua-resty-redis read a byte where a RESP type marker belongs;
* `redis client raised : ...` -- reading that same stream reached `string.byte` with a non-string.

`is_connection_error` matches neither, so `redis_call` used to hand the error straight back and
keep the poisoned client for the rest of the timer cycle. In the buffered-report replay
(`sync_request_buffer`) that means the batch stays unsynced and every remaining call in the
cycle reads off the same desynced stream. One reconnect, one retry, then fail loud -- a desync
that survives a fresh connection is not a stale socket.

The function under test and the three classifiers are spliced out of the shipped sources, so
narrowing or deleting either fails the extraction rather than passing on a private copy.

Runs through the ``lua`` binary; `redis_call` touches no OpenResty API of its own.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
METRICS = ROOT / "src" / "common" / "core" / "metrics" / "metrics.lua"
UTILS = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"
CLUSTERSTORE = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "clusterstore.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


def real_predicate(name: str) -> str:
    body = re.search(rf"^utils\.{name} = (function\(err\).*?^end)$", UTILS.read_text(encoding="utf-8"), re.M | re.S)
    assert body, f"utils.{name} is gone from {UTILS}"
    return body.group(1)


def contained_raise_prefix() -> str:
    """Return the literal `clusterstore:call` prepends to a contained raise, source-exact.

    Hardcoding it would let a reword of clusterstore.lua:269 stop production reconnecting on a
    raise while both suites stayed green -- the predicate matches on this exact substring.
    """
    prefix = re.search(r'return nil, "([^"]*?)" \.\. tostring\(res\)', CLUSTERSTORE.read_text(encoding="utf-8"))
    assert prefix, f"the contained-raise error is no longer built in {CLUSTERSTORE}"
    return prefix.group(1)


def real_redis_call() -> str:
    body = re.search(r"^function metrics:redis_call\(method, \.\.\.\)$.*?^end$", METRICS.read_text(encoding="utf-8"), re.M | re.S)
    assert body, f"metrics:redis_call is gone from {METRICS}"
    return body.group(0)


# `redis_call` reads three file-locals and one log level; everything else it touches is `self`.
PRELUDE = """
local ERR = 1
local is_connection_error = %s
local is_protocol_error = %s
local is_oom_error = %s
local metrics = {}

%s

-- A clusterstore whose calls are scripted one per invocation, counting the reconnect cycle.
local function new_store(replies, connect_ok)
    local calls, closes, connects = {}, 0, 0
    local store = {
        call = function(_, method, ...)
            calls[#calls + 1] = method
            local reply = replies[#calls] or { nil, "no scripted reply left" }
            return reply[1], reply[2]
        end,
        close = function() closes = closes + 1 return true end,
        connect = function()
            connects = connects + 1
            if connect_ok == false then return false, "connection refused" end
            return true, "success", 0
        end,
    }
    local self = { clusterstore = store, logged = {} }
    self.log_throttled = function(_, _, key, message) self.logged[key] = message end
    self.redis_call = metrics.redis_call
    self.counts = function() return #calls, closes, connects end
    return self
end

local function check(label, condition, detail)
    if not condition then
        error(label .. " : " .. tostring(detail), 2)
    end
end
"""


def run(scenario: str) -> subprocess.CompletedProcess:
    chunk = (
        PRELUDE
        % (
            real_predicate("is_connection_error"),
            real_predicate("is_protocol_error"),
            real_predicate("is_oom_error"),
            real_redis_call(),
        )
        + scenario
    )
    return subprocess.run([LUA, "-e", chunk], capture_output=True, text=True)


DESYNCS = [
    pytest.param('unknown prefix: "t"', id="wire-desync"),
    # What `clusterstore:call` actually hands back, prefix spliced out of the producer, with the
    # raise that provoked it in run 32834226362 appended as the tostring(res) tail.
    pytest.param(contained_raise_prefix() + "resty/redis.lua:255: bad argument #1 to 'byte'", id="contained-raise"),
]


@pytest.mark.parametrize("desync", DESYNCS)
def test_a_desync_reconnects_once_and_retries(desync):
    """Both desync shapes get the connection-error treatment: close, reconnect, retry once."""
    result = run("""
local self = new_store({ { nil, %s }, { "replayed", nil } })
local res, err = self:redis_call("eval", "return 1")
check("the retry's value must be returned", res == "replayed", res)
check("a successful retry must report no error", err == nil, err)
check("the cycle must stay open after a recovered desync", self.redis_ok ~= false, self.redis_ok)
local calls, closes, connects = self.counts()
check("exactly one retry", calls == 2, calls)
check("the poisoned socket must be closed before reconnecting", closes == 1, closes)
check("exactly one reconnect", connects == 1, connects)
""" % _quote(desync))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("desync", DESYNCS)
def test_a_desync_that_survives_the_reconnect_fails_loud(desync):
    """Bounded: the retry is not a loop. A second desync trips the breaker for the cycle."""
    result = run("""
local self = new_store({ { nil, %s }, { nil, %s } })
local res = self:redis_call("eval", "return 1")
check("a surviving desync must not report success", not res, res)
check("the breaker must trip so the rest of the cycle short-circuits", self.redis_ok == false, self.redis_ok)
local calls, _, connects = self.counts()
check("exactly two attempts, never a third", calls == 2, calls)
check("exactly one reconnect, never a second", connects == 1, connects)
""" % (_quote(desync), _quote(desync)))
    assert result.returncode == 0, result.stderr


def test_a_desync_whose_reconnect_fails_reports_the_original_error():
    result = run("""
local self = new_store({ { nil, 'unknown prefix: "t"' } }, false)
local res, err = self:redis_call("eval", "return 1")
check("a failed reconnect must not report success", res == false, res)
check("the caller must see the desync, not the reconnect failure", err == 'unknown prefix: "t"', err)
check("the breaker must trip", self.redis_ok == false, self.redis_ok)
check("the operator must be told the reconnect failed", self.logged["redis_reconnect"] ~= nil, self.logged)
local calls = self.counts()
check("no retry is possible without a connection", calls == 1, calls)
""")
    assert result.returncode == 0, result.stderr


def test_oom_and_resp_errors_are_left_alone():
    """The reconnect must stay scoped to a dead or desynced stream: neither of these is one."""
    result = run("""
local self = new_store({ { false, "OOM command not allowed when used memory > 'maxmemory'" } })
self:redis_call("set", "k", "v")
check("OOM must trip the breaker", self.redis_ok == false, self.redis_ok)
local calls, closes, connects = self.counts()
check("OOM must not reconnect: the connection is healthy", connects == 0, connects)
check("OOM must not close the connection", closes == 0, closes)
check("OOM must not retry", calls == 1, calls)

local resp = new_store({ { false, "ERR wrong number of arguments" } })
local res, err = resp:redis_call("eval", "return 1")
check("a RESP error must pass through", res == false and err == "ERR wrong number of arguments", err)
check("a RESP error must not trip the breaker", resp.redis_ok ~= false, resp.redis_ok)
local rcalls, rcloses, rconnects = resp.counts()
check("a RESP error must not reconnect", rconnects == 0 and rcloses == 0, rconnects)
check("a RESP error must not retry", rcalls == 1, rcalls)
""")
    assert result.returncode == 0, result.stderr


def test_the_breaker_short_circuits_without_touching_redis():
    result = run("""
local self = new_store({ { "never reached", nil } })
self.redis_ok = false
local res, err = self:redis_call("eval", "return 1")
check("a tripped breaker must report failure", res == false, res)
check("a tripped breaker must say why", err == "Redis unavailable for this cycle", err)
local calls = self.counts()
check("a tripped breaker must not call Redis at all", calls == 0, calls)
""")
    assert result.returncode == 0, result.stderr


def _quote(value: str) -> str:
    """Lua long-bracket literal: the desync strings carry both quote kinds and a `#`."""
    return "[==[" + value + "]==]"
