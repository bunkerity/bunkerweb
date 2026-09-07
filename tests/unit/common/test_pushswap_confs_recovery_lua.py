"""The recovery path of ``POST /confs`` must always release the swap key, raise or not.

Lane PS-1 (wave 14), DEV-2b5 residuals 8 and 2, both at their real call site.

**Residual 8.** ``pushswap.clear()`` was the one post-lock call into that module left bare, while
``pushswap.swap()`` twelve lines above it is wrapped in ``pcall`` for exactly this reason. It runs
on the last-resort restore -- reached only when a swap failed AND its ordered undo could not put
the tree back -- so the destination is already half applied when it runs. A Lua error there unwinds
past ``fail()``, the key is never deleted, and every push and reload on the instance answers 503
until the 900 s TTL expires: fifteen minutes of an instance that cannot be repaired by the thing
that repairs instances, on top of a configuration tree that is neither the old one nor the new one.

**Residual 2.** ``.bw-rescue.<epoch>`` directories were created and never reaped, and ``api.lua``
opens every push with ``cp -R <destination>/. <backup>/``, so each one is copied into every later
backup. The sweep belongs to the SUCCESS path only: on a failure a rescue may be the only surviving
copy of an entry, and the push that just failed is the one that may have created it.

The whole shipped handler runs here -- spliced out of ``api.lua`` by name -- against stubs for the
upload, the filesystem and ``pushswap``. Splicing rather than restating is the point: a handler that
stops calling ``pcall``, stops releasing, or starts sweeping on the failure path fails this module.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "api.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")


def _spliced(pattern: str, what: str) -> str:
    body = re.search(pattern, API_LUA.read_text(encoding="utf-8"), re.M | re.S)
    assert body, f"{what} is gone from {API_LUA} or changed shape"
    return body.group(0)


def _primitives() -> str:
    return "\n".join(
        (
            "local swap_lock_seq = 0",
            _spliced(r"^local function new_swap_token\(\).*?^end$", "new_swap_token()"),
            _spliced(r"^local function take_swap_lock\(wait\).*?^end$", "take_swap_lock()"),
            _spliced(r"^local function release_swap_lock\(token\).*?^end$", "release_swap_lock()"),
        )
    )


def _confs_handler() -> str:
    return _spliced(r'^api\.global\.POST\["\^/confs\$"\] = function\(self\).*?^end$', "the POST /confs handler")


HARNESS = """
local key_value = nil
local released, swept = 0, 0
local clear_calls, log_lines, reaped_path = 0, {}, nil

-- Knobs. Each names the exact failure the case is about.
local zone_full        = %s  -- safe_add refuses with "no memory": the zone, not another swap
local swap_fails       = %s  -- pushswap.swap() reports a failure
local rollback_stuck   = %s  -- ... whose ordered undo could NOT put the tree back: the restore runs
local clear_raises     = %s  -- pushswap.clear() throws instead of returning false
local clear_returns_ok = %s  -- ... or returns cleanly, so the cp -R decides
local restore_fails    = %s  -- the cp -R from the backup fails

ngx = {
    now = function() return 1000 end,
    worker = { pid = function() return 4242 end },
    sleep = function() end,
    var = { connection = 7 },
}
shared = {
    internalstore = {
        safe_add = function(_, _, value, _)
            if zone_full then return false, "no memory" end
            if key_value ~= nil then return false, "exists" end
            key_value = value
            return true
        end,
    },
}
internalstore = {
    get = function() return key_value end,
    delete = function() key_value = nil released = released + 1 end,
}
logger = { log = function(_, level, line) log_lines[#log_lines + 1] = tostring(level) .. ":" .. tostring(line) end }
ERR, NOTICE, HTTP_OK, HTTP_INTERNAL_SERVER_ERROR, HTTP_BAD_REQUEST, HTTP_SERVICE_UNAVAILABLE = 1, 5, 200, 500, 400, 503
SWAP_LOCK_KEY, SWAP_LOCK_TTL, PUSH_LOCK_WAIT = "api_swap_in_progress", 900, 10
NEEDS_CONFIG_PATH = "/var/tmp/bunkerweb_needs_config"

-- Filesystem. Nothing real is touched: the handler's own shell-outs are the unit under test only
-- insofar as their RESULT steers it.
execute = function(cmd)
    if restore_fails and cmd:find("cp -R /var/tmp/bunkerweb/backup_", 1, true) then return 1 end
    return 0
end
open = function() return { write = function() end, flush = function() end, close = function() end } end
remove = function() return true end

pushswap = {
    RESERVED_PREFIX = ".bw-",
    -- Only the log line reads it here. Its VALUE is pinned against the shipped module by
    -- test_pushswap_reap_lua.py::test_the_window_is_a_week -- asserting it against this stub too
    -- would only prove the stub agrees with itself.
    RESCUE_MAX_AGE = 604800,
    swap = function()
        if swap_fails then return false, "cannot place a.conf: simulated ENOSPC", rollback_stuck end
        return true
    end,
    clear = function()
        clear_calls = clear_calls + 1
        if clear_raises then error("clear exploded") end
        if clear_returns_ok then return true end
        return false, "cannot remove a.conf"
    end,
    reap_rescues = function(path) swept = swept + 1 reaped_path = path return 2 end,
}

-- One-shot multipart body: a single chunk then eof.
local chunks = { { "body", "tarball" }, { "eof" } }
upload = {
    new = function()
        return {
            set_timeout = function() end,
            read = function()
                local chunk = table.remove(chunks, 1)
                return chunk[1], chunk[2]
            end,
        }
    end,
}

%s

api = { global = { POST = {} } }
local self = {
    ctx = { bw = { uri = "/confs" } },
    response = function(_, status, level, message) return { status, level, message } end,
}

%s

local out = api.global.POST["^/confs$"](self)
print(string.format("%%d|%%s|%%d|%%d|%%d|%%s|%%s|%%s", out[1], out[3], released, swept, clear_calls,
    tostring(key_value), tostring(reaped_path), table.concat(log_lines, " ~~ ")))
"""


def run_push(
    *,
    zone_full: bool = False,
    swap_fails: bool = False,
    rollback_stuck: bool = False,
    clear_raises: bool = False,
    clear_returns_ok: bool = True,
    restore_fails: bool = False,
):
    script = HARNESS % (
        str(zone_full).lower(),
        str(swap_fails).lower(),
        str(rollback_stuck).lower(),
        str(clear_raises).lower(),
        str(clear_returns_ok).lower(),
        str(restore_fails).lower(),
        _primitives(),
        _confs_handler(),
    )
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    status, message, released, swept, clear_calls, key_value, reaped_path, logs = result.stdout.strip().split("|", 7)
    return {
        "status": int(status),
        "message": message,
        "released": int(released),
        "swept": int(swept),
        "clear_calls": int(clear_calls),
        "key_value": None if key_value == "nil" else key_value,
        "reaped_path": None if reaped_path == "nil" else reaped_path,
        "logs": logs,
    }


class TestTheHappyPath:
    """The floor. Without it every assertion below could be passing on a handler that never ran."""

    def test_a_clean_push_answers_200_and_releases_the_key(self):
        out = run_push()

        assert out["status"] == 200
        assert (out["released"], out["key_value"]) == (1, None)
        assert out["clear_calls"] == 0, "the restore path must not run when the swap succeeded"


class TestTheRescueSweep:
    """DEV-2b5 residual 2."""

    def test_a_clean_push_reaps_the_stale_rescues(self):
        assert run_push()["swept"] == 1

    def test_removing_a_rescue_is_not_silent(self):
        """The module's own comment calls a rescue the only copy left anywhere. Deleting one without
        a log line leaves an operator looking for a directory an error message sent them to."""
        out = run_push()

        assert "5:removed 2 rescue directories" in out["logs"], "the removal must be a NOTICE, not a nil level"

    def test_the_sweep_is_pointed_at_the_destination(self):
        """Counting calls is blind to WHICH tree is swept, and the wrong one is a silent no-op: a
        successful `pushswap.swap` ends by removing the staging directory, so a sweep aimed there
        reaps nothing, ever, while every call-counting assertion above stays green."""
        assert run_push()["reaped_path"] == "/etc/nginx", "the sweep is aimed at a tree that is not the destination"

    def test_the_sweep_runs_before_the_key_is_released(self):
        """Criticos REQUIRED 1. The next push opens with `cp -R <destination>/. <backup>/`, which
        descends into every `.bw-rescue.*`. Reaping after the release lets that copy walk into a
        directory being deleted, `cp` exits non-zero on the vanished entry, and the backup guard
        turns it into `cannot create the pre-swap backup, refusing to push` -- a 500 on a healthy
        instance, which `push-configs.py` answers with a failover restore over a fleet that is fine.
        """
        body = _confs_handler()
        sweep = body.index("pcall(pushswap.reap_rescues, destination)")
        release = body.index("\n\trelease_swap_lock(token)")

        assert sweep < release, "the rescue sweep runs unlocked, where a concurrent push's backup copy can race it"

    def test_a_failed_swap_never_reaps(self):
        """A rescue may be the only surviving copy of an entry, and the push that just failed is the
        one that may have created it. Sweeping here would delete the recovery it exists to be."""
        out = run_push(swap_fails=True)

        assert out["status"] == 500
        assert out["swept"] == 0, "the sweep ran on a failure path, where a rescue is the last copy"

    def test_an_incomplete_rollback_never_reaps(self):
        out = run_push(swap_fails=True, rollback_stuck=True)

        assert out["status"] == 500
        assert out["swept"] == 0


class TestASaturatedZoneIsAnsweredAsItself:
    """DEV-2b5 residual 10, at the call site rather than in the primitive.

    `TestASaturatedZoneIsNotABusySwap` in `test_api_swap_lock_lua.py` splices `take_swap_lock` on
    its own and pins the REASON it returns; deleting the whole `lock_err == "memory"` branch from
    this handler left that green, and the branch is the entire operator-facing half of the residual
    -- the distinct message and the ERR line are what stop an operator hunting a swap that does not
    exist. Same class of gap as DEV-2b6's Criticos round 2 REQUIRED 3.
    """

    def test_a_full_zone_is_answered_with_its_own_message(self):
        out = run_push(zone_full=True)

        assert out["status"] == 503, "the caller must still be told to retry"
        assert "cannot take the swap lock: no memory" in out["message"], "a full zone is reported as a swap that will never end"

    def test_a_full_zone_is_logged_at_err_with_the_reason_the_dict_gave(self):
        out = run_push(zone_full=True)

        assert "1:the internalstore zone cannot hold the swap lock" in out["logs"], "the brief mandates ERROR"
        assert "no memory" in out["logs"], "the dict's own reason is what makes this diagnosable"

    def test_a_full_zone_touches_nothing(self):
        """It never had the lock, so it must not release one, and it must not sweep."""
        assert (run_push(zone_full=True)["released"], run_push(zone_full=True)["swept"]) == (0, 0)


class TestClearIsWrappedLikeSwap:
    """DEV-2b5 residual 8. The defect is a leaked key, so that is what every case here measures."""

    def test_a_raising_clear_still_releases_the_swap_key(self):
        out = run_push(swap_fails=True, rollback_stuck=True, clear_raises=True)

        assert out["clear_calls"] == 1, "the case did not reach pushswap.clear() at all"
        assert out["released"] == 1, "a raise inside clear() leaked the swap key for the whole 900 s TTL"
        assert out["key_value"] is None, "the key is still held: every push and reload answers 503 until it expires"

    def test_a_raising_clear_is_answered_500_and_named_in_the_response(self):
        """An operator reading the 500 body must not have to correlate it with an ERR line to learn
        that the restore is what failed, and why."""
        out = run_push(swap_fails=True, rollback_stuck=True, clear_raises=True)

        assert out["status"] == 500
        assert "the restore failed too" in out["message"]
        assert "clear exploded" in out["message"], "the raise reaches the caller as a reason, not as a bare 500"

    def test_a_raising_clear_is_logged_at_err_with_where_the_originals_are(self):
        out = run_push(swap_fails=True, rollback_stuck=True, clear_raises=True)

        assert "1:restore from backup FAILED" in out["logs"]
        assert "simulated ENOSPC" in out["logs"], "the swap error names where the originals were kept"

    def test_a_clear_that_merely_returns_false_is_unchanged(self):
        """The pre-existing contract: `false, err` was already handled, and wrapping must not turn
        an orderly refusal into a raise or vice versa."""
        out = run_push(swap_fails=True, rollback_stuck=True, clear_returns_ok=False)

        assert out["status"] == 500
        assert out["released"] == 1
        assert "cannot remove a.conf" in out["message"]

    def test_a_clean_clear_whose_copy_fails_still_releases(self):
        out = run_push(swap_fails=True, rollback_stuck=True, restore_fails=True)

        assert out["status"] == 500
        assert out["released"] == 1
        assert "copy failed" in out["message"]

    def test_a_successful_restore_answers_500_and_releases(self):
        """The push still failed -- the caller must not read a restored tree as an applied one."""
        out = run_push(swap_fails=True, rollback_stuck=True)

        assert out["status"] == 500
        assert "restored from backup" in out["message"]
        assert (out["released"], out["swept"]) == (1, 0)


def test_the_clear_call_is_wrapped_in_pcall():
    """A source guard on top of the behavioural cases above, because the behavioural ones can be
    satisfied by an `if` that happens to catch the one error this harness injects, while the defect
    is about EVERY raise `pushswap.clear` can produce."""
    body = _confs_handler()

    assert "pcall(pushswap.clear, destination)" in body, "pushswap.clear() is called bare again"
    assert "pushswap.clear(destination)" not in body.replace(
        "pcall(pushswap.clear, destination)", ""
    ), "a bare pushswap.clear() call is back alongside the wrapped one"
