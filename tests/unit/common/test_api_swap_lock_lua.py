"""Two pushes to one instance must never run their rename sequences at the same time.

Port of dev ``32a2985ab``'s serialization half, onto this tree's own primitive. ``POST /confs``
used to STAMP the swap lock (``internalstore:set``) rather than take it: the key only ever made
``POST /reload`` wait, and nothing excluded one push from another. A scheduler retrying a push
while the first attempt is still running -- which ``ApiCaller``'s 503 retry makes routine -- or a
second scheduler and the UI reaching the same instance, ran two ``pushswap.swap`` sequences over
one destination and left it neither the old tree nor the new one.

``take_swap_lock`` is an atomic ``safe_add`` on the shared dict, deliberately not a get-then-set:
two workers that both find the key free would both proceed, which is the race being closed. It is
the shipped function that runs here -- spliced out of ``api.lua`` by name, so narrowing or deleting
it fails this module rather than passing on a copy.

``POST /reload`` is held to the same contract, and for a reason Criticos found rather than the lane:
it used to POLL the key and then proceed WITHOUT taking it. That was survivable only while a second
push barged in with ``set`` and kept the key continuously present. Once pushes queue on the same key
at the same 100 ms cadence, a reload polling a just-released key wins the race often enough to make
the overlap systematic -- so the reload handler takes the key too, and releases it on every exit
including a Lua error inside the body.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "api.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")


def _take_swap_lock_source() -> str:
    body = re.search(r"^local function take_swap_lock\(wait\).*?^end$", API_LUA.read_text(encoding="utf-8"), re.M | re.S)
    assert body, f"take_swap_lock() is gone from {API_LUA}"
    return body.group(0)


HARNESS = """
local now = 1000
local sleeps = 0
local held = %s          -- true when another swap already holds the key
local release_after = %s -- release it after this many sleeps, -1 = never
local adds = 0

ngx = {
    now = function() return now end,
    sleep = function(d)
        now = now + d
        sleeps = sleeps + 1
        if release_after >= 0 and sleeps >= release_after then held = false end
    end,
}
shared = {
    internalstore = {
        safe_add = function(_, _, _, _)
            adds = adds + 1
            if held then return false, "exists" end
            held = true
            return true
        end,
    },
}
SWAP_LOCK_KEY = "api_swap_in_progress"
SWAP_LOCK_TTL = 120

%s

local ok = take_swap_lock(%s)
print(string.format("%%s|%%d|%%d|%%.1f", tostring(ok), adds, sleeps, now - 1000))
"""


def run(*, held: bool, release_after: int = -1, wait: float = 10):
    script = HARNESS % (str(held).lower(), release_after, _take_swap_lock_source(), wait)
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    ok, adds, sleeps, elapsed = result.stdout.strip().split("|")
    return ok == "true", int(adds), int(sleeps), float(elapsed)


def test_a_free_lock_is_taken_at_once():
    ok, adds, sleeps, elapsed = run(held=False)

    assert ok is True
    assert (adds, sleeps, elapsed) == (1, 0, 0.0), "an idle instance must not pay for the lock"


def test_a_held_lock_is_queued_behind_not_stamped_over():
    ok, adds, sleeps, elapsed = run(held=True, wait=10)

    assert ok is False, "the loser answers 503; it must never proceed into the swap"
    assert adds > 1, "it has to keep trying, not give up on the first refusal"
    assert elapsed >= 10, f"it gave up after {elapsed}s of a 10s budget"


def test_a_lock_released_while_queuing_is_then_taken():
    ok, _, sleeps, elapsed = run(held=True, release_after=5, wait=10)

    assert ok is True
    assert sleeps == 5
    assert elapsed < 10, "it must not keep waiting once the other swap is done"


def test_the_wait_is_bounded_so_a_push_is_never_left_hanging():
    """The scheduler's own budget is what a longer wait would blow through."""
    ok, _, _, elapsed = run(held=True, wait=1)

    assert ok is False
    assert elapsed < 2, f"a 1s budget waited {elapsed}s"


RELOAD_HARNESS = """
local released, taken, body_saw_key, responses = 0, 0, nil, {}
local key_held = %s   -- true when another swap already holds it

local now = 1000
ngx = {
    now = function() return now end,
    sleep = function(d) now = now + d end,
    req = { get_uri_args = function() return {} end },
}
shared = {
    internalstore = {
        safe_add = function()
            if key_held then return false, "exists" end
            key_held = true
            taken = taken + 1
            return true
        end,
    },
}
internalstore = {
    delete = function()
        key_held = false
        released = released + 1
    end,
}
logger = { log = function() end }
ERR, HTTP_OK, HTTP_INTERNAL_SERVER_ERROR, HTTP_SERVICE_UNAVAILABLE = 1, 200, 500, 503
SWAP_LOCK_KEY, SWAP_LOCK_TTL, SWAP_WAIT_TIMEOUT = "api_swap_in_progress", 900, %s

%s

-- The body under test is the WRAPPER: reload_locked is faked so the assertion is about what the
-- wrapper holds while the body runs, not about reloading nginx.
reload_locked = function()
    body_saw_key = key_held
    %s
    return HTTP_OK, "success", "reload successful"
end

api = { global = { POST = {} } }
local self = { response = function(_, status, level, message) return { status, level, message } end }

%s

local out = api.global.POST["^/reload"](self)
print(string.format("%%d|%%d|%%s|%%d|%%s|%%s", taken, released, tostring(body_saw_key), out[1], out[2], out[3]))
"""


def _handler_source() -> str:
    source = API_LUA.read_text(encoding="utf-8")
    body = re.search(r'^api\.global\.POST\["\^/reload"\] = function\(self\).*?^end$', source, re.M | re.S)
    assert body, "the /reload handler is gone or changed shape"
    return body.group(0)


def _lua_constant(name: str) -> int:
    """Read a shipped constant instead of copying it: a harness carrying a stale 30 s wait would
    keep passing after the value moved, which is the whole point of splicing the real function."""
    found = re.search(rf"^local {name} = (\d+)$", API_LUA.read_text(encoding="utf-8"), re.M)
    assert found, f"{name} is gone from {API_LUA}"
    return int(found.group(1))


def run_reload(*, key_held: bool = False, body_raises: bool = False, refused: bool = False):
    harness = RELOAD_HARNESS
    if refused:
        # DEV-2b6 (Criticos round 2 REQUIRED 2): the fake body hands back a verdict the wrapper is
        # supposed to forward untouched.
        harness = harness.replace(
            'return HTTP_OK, "success", "reload successful"',
            'return HTTP_INTERNAL_SERVER_ERROR, "error", "reload refused by nginx: duplicate location"',
        )
        assert "refused by nginx" in harness, "the fake reload body changed shape"
    script = harness % (
        str(key_held).lower(),
        _lua_constant("SWAP_WAIT_TIMEOUT"),
        _take_swap_lock_source(),
        'error("boom")' if body_raises else "",
        _handler_source(),
    )
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    taken, released, body_saw_key, status, level, message = result.stdout.strip().split("|", 5)
    return int(taken), int(released), body_saw_key == "true", int(status), level, message


class TestReloadHoldsTheKey:
    def test_the_reload_holds_the_key_while_it_runs(self):
        taken, released, body_saw_key, status, _, _ = run_reload()

        assert taken == 1, "polling the key and proceeding unlocked is what let a queued push barge in"
        assert body_saw_key is True, "the key must be HELD across nginx -t and the SIGHUP, not merely observed free"
        assert released == 1
        assert status == 200

    def test_the_key_is_released_even_when_the_reload_raises(self):
        """A leaked key now costs 15 minutes of 503 on every push and reload of this instance."""
        taken, released, _, status, _, message = run_reload(body_raises=True)

        assert (taken, released) == (1, 1)
        assert status == 500
        assert "reload failed" in message

    def test_a_swap_in_progress_still_answers_503(self):
        taken, released, body_saw_key, status, _, _ = run_reload(key_held=True)

        assert (taken, released) == (0, 0)
        assert body_saw_key is None or body_saw_key is False
        assert status == 503

    def test_a_verdict_the_body_refused_reaches_the_caller_unchanged(self):
        """DEV-2b6 (Criticos round 2 REQUIRED 2). The wrapper forwards the body's triple, untested.

        Splitting the handler moved the refusal out of a `self:response(HTTP_INTERNAL_SERVER_ERROR,
        ...)` literal -- where `test_api_reload_verdict_lua.py`'s source guard pinned it -- into a
        return value that one line of the wrapper turns back into a response. That guard followed
        the body into `reload_locked`, where the status is only data, so a wrapper answering 200 for
        every verdict passed the whole suite. `push-configs.py` reads that status to decide whether
        the fleet adopted the configuration: answering 200 for a refused reload tells it a config
        NGINX rejected is live.
        """
        taken, released, _, status, level, message = run_reload(refused=True)

        assert status == 500, "a reload NGINX refused must not be answered 200 by the lock wrapper"
        assert level == "error", "the whole triple is forwarded, not just the status"
        assert "refused by nginx" in message, "the body's own message must reach the caller"
        assert (taken, released) == (1, 1), "a refused reload still holds and releases the key"


def _confs_handler_source() -> str:
    body = re.search(r'^api\.global\.POST\["\^/confs\$"\] = function\(self\).*?^end$', API_LUA.read_text(encoding="utf-8"), re.M | re.S)
    assert body, "the POST /confs handler is gone or changed shape"
    return body.group(0)


def test_the_push_takes_the_key_and_releases_it_on_every_exit():
    """DEV-2b6 (Criticos round 2 REQUIRED 3). This row's headline change had no test at its call site.

    Everything above splices `take_swap_lock` in isolation, so reverting `POST /confs` to the
    `internalstore:set` stamp it used to do -- the exact bug this row exists to fix, two pushes
    running two rename sequences over one destination -- left the suite green. A source guard is the
    honest instrument here: the handler reads the request body and shells out to `pushswap`, so what
    is worth pinning is that it takes the key rather than stamping it, and releases it on both exits
    (the `fail()` path and the success path).
    """
    body = _confs_handler_source()

    assert "take_swap_lock(PUSH_LOCK_WAIT)" in body, "POST /confs stamps the swap key again instead of taking it"
    assert "internalstore:set(SWAP_LOCK_KEY" not in body, "stamping overwrites the key another push is holding"
    assert body.count("internalstore:delete(SWAP_LOCK_KEY)") == 2, "the key is released in fail() and on the success path"
    # Counting occurrences is blind to WHERE the success release sits: moving it six lines down into
    # the `if self.ctx.bw.uri == "/confs"` branch keeps the count at 2 and leaks the key for the full
    # 900 s TTL on every /cache, /data, /plugins and /custom_configs push -- i.e. on every worker
    # cache push, after which the instance answers 503 to everything for 15 minutes. `fail()`'s copy
    # is indented one level deeper, so anchoring on a single tab isolates the top-level one.
    assert body.count("\n\tinternalstore:delete(SWAP_LOCK_KEY)") == 1, "the success release must be at handler top level, not inside a branch"
