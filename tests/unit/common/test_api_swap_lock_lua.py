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

**Lane PS-1 (wave 14)** closes two residuals DEV-2b5 disclosed on that primitive, and both change
its contract, which is why every harness below moved with them:

* residual 9 -- every release was ownership-blind. ``take_swap_lock`` now returns a TOKEN naming
  the acquisition, and ``release_swap_lock(token)`` deletes the key only while it is still that
  token's. Without it, a holder whose TTL expired mid-swap deleted its SUCCESSOR's fresh key and
  put two workers into one destination believing they each held it.
* residual 10 -- ``safe_add`` refuses both for "another swap holds it" and for "the zone is full",
  and both were reported as a swap in progress. The second never ends on its own, so an operator
  was sent hunting a swap that does not exist. It is now a distinct reason, a distinct message and
  an ERR line.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "api.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")


def _lua_function_source(name: str, signature: str = r"\(.*?\)") -> str:
    """Splice one shipped `local function` out of api.lua, so a copy can never drift from it."""
    body = re.search(rf"^local function {name}{signature}.*?^end$", API_LUA.read_text(encoding="utf-8"), re.M | re.S)
    assert body, f"{name}() is gone from {API_LUA}"
    return body.group(0)


def _lua_local(declaration: str) -> str:
    """Splice a module-level `local` the primitives close over. Spliced rather than restated so a
    rename fails this module instead of leaving the harness feeding the function a nil global."""
    source = API_LUA.read_text(encoding="utf-8")
    assert f"\n{declaration}\n" in source, f"`{declaration}` is gone from {API_LUA}"
    return declaration


def _lock_primitives() -> str:
    """The three functions the lock is made of. PS-1 split the acquisition into a token minter, so
    splicing `take_swap_lock` alone would leave the harness calling a global that does not exist --
    which is a loud failure, not a silent pass, and is why they are spliced together."""
    return "\n".join(
        (
            _lua_local("local swap_lock_seq = 0"),
            _lua_function_source("new_swap_token"),
            _lua_function_source("take_swap_lock", r"\(wait\)"),
            _lua_function_source("release_swap_lock", r"\(token\)"),
        )
    )


HARNESS = """
local now = 1000
local sleeps = 0
local held = %s          -- true when another swap already holds the key
local release_after = %s -- release it after this many sleeps, -1 = never
local no_memory = %s     -- the zone is saturated: safe_add refuses for a reason that is not "exists"
local adds = 0
local stored = nil

ngx = {
    now = function() return now end,
    worker = { pid = function() return 4242 end },
    sleep = function(d)
        now = now + d
        sleeps = sleeps + 1
        if release_after >= 0 and sleeps >= release_after then held = false end
    end,
}
shared = {
    internalstore = {
        safe_add = function(_, _, value, _)
            adds = adds + 1
            -- A full zone refuses with "no memory", never with "exists": safe_add will not evict an
            -- unexpired entry to make room. Reporting it as contention is residual 10's defect.
            if no_memory then return false, "no memory" end
            if held then return false, "exists" end
            held = true
            stored = value
            return true
        end,
    },
}
internalstore = {
    get = function() return stored end,
    delete = function() stored, held = nil, false end,
}
logger = { log = function() end }
ERR = 1
SWAP_LOCK_KEY = "api_swap_in_progress"
SWAP_LOCK_TTL = 120

%s

local token, reason = take_swap_lock(%s)
print(string.format("%%s|%%s|%%d|%%d|%%.1f|%%s", tostring(token), tostring(reason), adds, sleeps, now - 1000, tostring(stored)))
"""


def run(*, held: bool, release_after: int = -1, wait: float = 10, no_memory: bool = False):
    script = HARNESS % (str(held).lower(), release_after, str(no_memory).lower(), _lock_primitives(), wait)
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    token, reason, adds, sleeps, elapsed, stored = result.stdout.strip().split("|")
    return {
        "ok": token != "nil",
        "token": None if token == "nil" else token,
        "reason": None if reason == "nil" else reason,
        "adds": int(adds),
        "sleeps": int(sleeps),
        "elapsed": float(elapsed),
        "stored": None if stored == "nil" else stored,
    }


def test_a_free_lock_is_taken_at_once():
    out = run(held=False)

    assert out["ok"] is True
    assert (out["adds"], out["sleeps"], out["elapsed"]) == (1, 0, 0.0), "an idle instance must not pay for the lock"


def test_a_held_lock_is_queued_behind_not_stamped_over():
    out = run(held=True, wait=10)

    assert out["ok"] is False, "the loser answers 503; it must never proceed into the swap"
    assert out["reason"] == "held", "a busy key is contention, not a broken zone"
    assert out["adds"] > 1, "it has to keep trying, not give up on the first refusal"
    assert out["elapsed"] >= 10, f"it gave up after {out['elapsed']}s of a 10s budget"


def test_a_lock_released_while_queuing_is_then_taken():
    out = run(held=True, release_after=5, wait=10)

    assert out["ok"] is True
    assert out["sleeps"] == 5
    assert out["elapsed"] < 10, "it must not keep waiting once the other swap is done"


def test_the_wait_is_bounded_so_a_push_is_never_left_hanging():
    """The scheduler's own budget is what a longer wait would blow through."""
    out = run(held=True, wait=1)

    assert out["ok"] is False
    assert out["elapsed"] < 2, f"a 1s budget waited {out['elapsed']}s"


class TestTheAcquisitionIsIdentified:
    """PS-1, residual 9. The stored value used to be `tostring(ngx.now())`, written and never read."""

    def test_the_key_carries_the_token_that_was_returned(self):
        out = run(held=False)

        assert out["stored"] == out["token"], "a release cannot check ownership against a value nobody stored"

    def test_two_acquisitions_in_one_clock_tick_get_different_tokens(self):
        """`ngx.now()` is the cached request time: two acquisitions inside one tick read it equal, so
        a token built from the clock alone would make a stale holder's release look legitimate."""
        script = (
            "ngx = { now = function() return 1000 end, worker = { pid = function() return 4242 end } }\n%s\n%s\nprint(new_swap_token() .. '|' .. new_swap_token())"
            % (
                _lua_local("local swap_lock_seq = 0"),
                _lua_function_source("new_swap_token"),
            )
        )
        result = subprocess.run(["lua", "-e", script], capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        first, second = result.stdout.strip().split("|")

        assert first != second, "two acquisitions inside one clock tick minted the same token"


class TestASaturatedZoneIsNotABusySwap:
    """PS-1, residual 10. `safe_add` will not evict an unexpired entry, so a full zone refuses
    forever -- and reporting it as "a swap is in progress" sends an operator after a swap that does
    not exist and that nothing will ever finish."""

    def test_a_full_zone_is_reported_as_the_zone_and_not_as_contention(self):
        out = run(held=False, no_memory=True, wait=10)

        assert out["ok"] is False
        assert out["reason"] == "memory", "a full zone read as contention is the defect"

    def test_a_full_zone_is_not_waited_out(self):
        """Waiting is for a swap that will end. Nothing frees this key by finishing."""
        out = run(held=False, no_memory=True, wait=10)

        assert out["adds"] == 1, "it retried a refusal that no amount of waiting can change"
        assert out["elapsed"] == 0.0, f"it burned {out['elapsed']}s of a caller's budget on a full zone"


RELOAD_HARNESS = """
local released, taken, body_saw_key = 0, 0, nil
local key_value = %s   -- non-nil when another swap already holds it
local zone_full = %s   -- safe_add refuses with "no memory": the zone, not another swap
local log_lines = {}

local now = 1000
ngx = {
    now = function() return now end,
    worker = { pid = function() return 4242 end },
    sleep = function(d) now = now + d end,
    req = { get_uri_args = function() return {} end },
}
shared = {
    internalstore = {
        safe_add = function(_, _, value, _)
            if zone_full then return false, "no memory" end
            if key_value ~= nil then return false, "exists" end
            key_value = value
            taken = taken + 1
            return true
        end,
    },
}
internalstore = {
    get = function() return key_value end,
    delete = function()
        key_value = nil
        released = released + 1
    end,
}
logger = { log = function(_, level, line) log_lines[#log_lines + 1] = tostring(level) .. ":" .. tostring(line) end }
ERR, HTTP_OK, HTTP_INTERNAL_SERVER_ERROR, HTTP_SERVICE_UNAVAILABLE = 1, 200, 500, 503
SWAP_LOCK_KEY, SWAP_LOCK_TTL, SWAP_WAIT_TIMEOUT = "api_swap_in_progress", 900, %s

%s

-- The body under test is the WRAPPER: reload_locked is faked so the assertion is about what the
-- wrapper holds while the body runs, not about reloading nginx.
reload_locked = function()
    body_saw_key = key_value ~= nil
    %s
    return HTTP_OK, "success", "reload successful"
end

api = { global = { POST = {} } }
local self = { response = function(_, status, level, message) return { status, level, message } end }

%s

local out = api.global.POST["^/reload"](self)
print(string.format("%%d|%%d|%%s|%%d|%%s|%%s|%%s|%%s", taken, released, tostring(body_saw_key), out[1], out[2], out[3], tostring(key_value), table.concat(log_lines, " ~~ ")))
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


def run_reload(*, key_held: bool = False, zone_full: bool = False, body_raises: bool = False, refused: bool = False, body: str = ""):
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
        '"someone-else"' if key_held else "nil",
        str(zone_full).lower(),
        _lua_constant("SWAP_WAIT_TIMEOUT"),
        _lock_primitives(),
        'error("boom")' if body_raises else body,
        _handler_source(),
    )
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    taken, released, body_saw_key, status, level, message, key_value, logs = result.stdout.strip().split("|", 7)
    return {
        "taken": int(taken),
        "released": int(released),
        "body_saw_key": body_saw_key == "true" if body_saw_key != "nil" else None,
        "status": int(status),
        "level": level,
        "message": message,
        "key_value": None if key_value == "nil" else key_value,
        "logs": logs,
    }


class TestReloadHoldsTheKey:
    def test_the_reload_holds_the_key_while_it_runs(self):
        out = run_reload()

        assert out["taken"] == 1, "polling the key and proceeding unlocked is what let a queued push barge in"
        assert out["body_saw_key"] is True, "the key must be HELD across nginx -t and the SIGHUP, not merely observed free"
        assert out["released"] == 1
        assert out["status"] == 200

    def test_the_key_is_released_even_when_the_reload_raises(self):
        """A leaked key now costs 15 minutes of 503 on every push and reload of this instance."""
        out = run_reload(body_raises=True)

        assert (out["taken"], out["released"]) == (1, 1)
        assert out["status"] == 500
        assert "reload failed" in out["message"]

    def test_a_swap_in_progress_still_answers_503(self):
        out = run_reload(key_held=True)

        assert (out["taken"], out["released"]) == (0, 0)
        assert out["body_saw_key"] is None or out["body_saw_key"] is False
        assert out["status"] == 503

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
        out = run_reload(refused=True)

        assert out["status"] == 500, "a reload NGINX refused must not be answered 200 by the lock wrapper"
        assert out["level"] == "error", "the whole triple is forwarded, not just the status"
        assert "refused by nginx" in out["message"], "the body's own message must reach the caller"
        assert (out["taken"], out["released"]) == (1, 1), "a refused reload still holds and releases the key"

    def test_a_full_zone_is_answered_with_its_own_message_and_an_err_line(self):
        """PS-1, residual 10, at the call site. `TestASaturatedZoneIsNotABusySwap` above splices
        `take_swap_lock` alone and pins the REASON it hands back; deleting this handler's whole
        `lock_err == "memory"` branch left that green, and the branch IS the residual -- the reason
        exists only to be turned into a message an operator can act on."""
        out = run_reload(zone_full=True)

        assert out["status"] == 503, "the caller must still be told to retry"
        assert "cannot take the swap lock: no memory" in out["message"], "a full zone reported as a swap in progress is the defect"
        assert "1:the internalstore zone cannot hold the swap lock" in out["logs"], "the brief mandates ERROR"
        assert "no memory" in out["logs"], "the dict's own reason is what makes this diagnosable"
        assert (out["taken"], out["released"]) == (0, 0), "it never held the key, so it must not release one"

    def test_a_key_that_simply_expired_is_not_deleted_blind(self):
        """Criticos round 2, concern 3. A miss means our TTL already expired and nobody has taken
        the key since. Deleting an absent key is a no-op, so that delete can only ever do harm: a
        successor's `safe_add` landing between the read and it would be dropped -- the exact outcome
        this function exists to prevent, in the one half of the race that IS closable without a
        second key. The reload itself still succeeded, so the caller still gets its 200.
        """
        out = run_reload(body="key_value = nil")

        assert out["taken"] == 1
        assert out["released"] == 0, "it issued a delete against a key it no longer owned"
        assert out["status"] == 200
        assert "1:the swap lock expired while this request held it : nothing to release" in out["logs"]
        assert (
            "another swap has taken it since" not in out["logs"]
        ), "the two branches share a prefix: matching it cannot tell 'nobody holds it' from 'someone else does'"

    def test_a_key_that_expired_mid_reload_is_not_taken_from_its_new_owner(self):
        """PS-1, residual 9, at the real call site.

        The 900 s TTL is the backstop for a worker killed mid-swap, so it CAN expire under a live
        holder -- `nginx -t` on a CRS-heavy tree plus `confirm_reload` is exactly the kind of body
        that reaches it. When it does, a successor's `safe_add` succeeds and the successor starts
        renaming; the blind `internalstore:delete(SWAP_LOCK_KEY)` this replaces then deleted the
        SUCCESSOR's key on the way out, putting a third worker into the same destination while the
        second was still swapping. That is the concurrent-swap window the key exists to close,
        re-opened by the thing that closes it.
        """
        out = run_reload(body='key_value = nil; key_value = "the-successor"')

        assert out["taken"] == 1
        assert out["released"] == 0, "it deleted a key another swap is holding"
        assert out["key_value"] == "the-successor", "the successor's lock must survive our release"
        assert out["status"] == 200, "losing the key is not the caller's problem: the reload itself succeeded"


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

    PS-1 moved the release behind `release_swap_lock(token)`; a bare `internalstore:delete` anywhere
    in the handler is the ownership-blind release coming back.
    """
    body = _confs_handler_source()

    assert "take_swap_lock(PUSH_LOCK_WAIT)" in body, "POST /confs stamps the swap key again instead of taking it"
    assert "internalstore:set(SWAP_LOCK_KEY" not in body, "stamping overwrites the key another push is holding"
    assert "internalstore:delete(SWAP_LOCK_KEY)" not in body, "an ownership-blind release is back in the push handler"
    assert body.count("release_swap_lock(token)") == 2, "the key is released in fail() and on the success path"
    # Counting occurrences is blind to WHERE the success release sits: moving it six lines down into
    # the `if self.ctx.bw.uri == "/confs"` branch keeps the count at 2 and leaks the key for the full
    # 900 s TTL on every /cache, /data, /plugins and /custom_configs push -- i.e. on every worker
    # cache push, after which the instance answers 503 to everything for 15 minutes. `fail()`'s copy
    # is indented one level deeper, so anchoring on a single tab isolates the top-level one.
    assert body.count("\n\trelease_swap_lock(token)") == 1, "the success release must be at handler top level, not inside a branch"
