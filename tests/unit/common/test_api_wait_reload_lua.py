"""`POST /reload` must keep making progress while it waits for the new workers.

`wait_reload` slept `math.min(RELOAD_POLL, deadline - ngx.now())`. `ngx.now()` is nginx's cached clock, and
the configuration test that runs just before does not refresh it, so near the deadline the remainder can be
a few hundred microseconds. The vendored `ngx.sleep` converts seconds to whole milliseconds by truncation
(`ngx_http_lua_sleep.c:44`), so that remainder became a zero-millisecond timer. A zero-delay timer is
already expired, nginx drains expired timers in a loop without refreshing the cached clock, and the
deadline test never became true: CI run 40848748952 logged 172,994 `ngx.sleep(0)` warnings on one request
while the reload held the swap lock for minutes.

Runs the shipped `wait_reload` body (spliced out of `src/bw/lua/bunkerweb/api.lua`, so a changed signature
fails the extraction instead of passing on a copy) through the `lua` binary. The stub of `ngx.sleep` keeps
the C truncation and the timer semantics: a zero-millisecond sleep does not advance the cached clock.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "api.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

SOURCE = API_LUA.read_text(encoding="utf-8")


def _required(pattern: str, what: str) -> str:
    body = re.search(pattern, SOURCE, re.M | re.S)
    assert body, f"{what} is gone from {API_LUA}"
    return body.group(0)


HARNESS = """
HTTP_OK = 200
HTTP_INTERNAL_SERVER_ERROR = 500
RELOAD_POLL = 0.1
logger = { log = function() end }

-- An epoch-sized cached clock: a double of this size has a resolution of about 2e-7 s, so a nominal
-- millisecond remainder is stored a hair under it.
local START = 1793267466.123
local cached = START
local sleeps, zero_sleeps = {}, 0
local ready, marker = false, "token"
local MAX_SLEEPS = 50

ngx = { WARN = 4 }
ngx.update_time = function() end
ngx.now = function() return cached end
ngx.sleep = function(seconds)
    -- ngx_http_lua_sleep.c:44 truncates to whole milliseconds. A zero-delay timer is already expired, so
    -- nginx runs it in the same pass and never refreshes the cached clock.
    local ms = math.floor(seconds * 1000)
    sleeps[#sleeps + 1] = ms
    if ms == 0 then
        zero_sleeps = zero_sleeps + 1
    else
        cached = cached + ms / 1000
    end
    if #sleeps > MAX_SLEEPS then
        error("spinning: " .. zero_sleeps .. " zero-millisecond sleeps without the clock moving")
    end
    AFTER_SLEEP(#sleeps)
end

internalstore = { get = function(_, key) if key == "misc_ready_token" and ready then return "ok" end end }
read_marker = function() return marker end

%s

%s
"""

TIMEOUT_NEAR_DEADLINE = """
-- The first sleep stands for the blocking configuration test: the cached clock then jumps to one
-- millisecond before the deadline, which is where the remainder-sized sleep truncates to zero.
AFTER_SLEEP = function(n)
    if n == 1 then cached = START + 10 - 0.001 end
end
local status, level, message, confirmed = wait_reload("token", 10)
print(table.concat({ status, level, tostring(confirmed), #sleeps, zero_sleeps }, "|"))
print(message)
"""

READY_AFTER_TWO_POLLS = """
AFTER_SLEEP = function(n)
    if n == 2 then ready = true end
end
local status, level, message, confirmed = wait_reload("token", 10)
print(table.concat({ status, level, tostring(confirmed), #sleeps, zero_sleeps }, "|"))
print(message)
"""

MARKER_DROPPED_WITHOUT_READINESS = """
AFTER_SLEEP = function(n)
    if n == 1 then marker = nil end
end
local status, level, message, confirmed = wait_reload("token", 10)
print(table.concat({ status, level, tostring(confirmed), #sleeps, zero_sleeps }, "|"))
print(message)
"""

NO_WAIT = """
AFTER_SLEEP = function() end
local status, level, message, confirmed = wait_reload("token", 0, "no time")
print(table.concat({ status, level, tostring(confirmed), #sleeps, zero_sleeps }, "|"))
print(message)
"""


def run(body: str):
    script = HARNESS % (_required(r"^local function wait_reload\(.*?^end$", "wait_reload()"), body)
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    summary, message = result.stdout.strip().split("\n", 1)
    return summary, message


class TestWaitReload:
    def test_a_sub_millisecond_remainder_does_not_become_a_zero_millisecond_sleep(self):
        """The regression: the loop spun on `ngx.sleep(0)` until the process was killed."""
        summary, message = run(TIMEOUT_NEAR_DEADLINE)
        status, level, confirmed, sleeps, zero_sleeps = summary.split("|")
        assert (status, level, confirmed) == ("200", "success", "false")
        assert zero_sleeps == "0", f"{zero_sleeps} zero-millisecond sleeps"
        assert int(sleeps) <= 3, f"{sleeps} sleeps to reach a deadline that was already due"
        assert message == "reload signalled but readiness is unconfirmed: timed out waiting for new workers"

    def test_readiness_published_while_polling_ends_the_wait_confirmed(self):
        summary, message = run(READY_AFTER_TWO_POLLS)
        assert summary == "200|success|true|2|0"
        assert message == "reload successful"

    def test_a_marker_removed_without_readiness_fails_the_reload(self):
        summary, message = run(MARKER_DROPPED_WITHOUT_READINESS)
        assert summary == "500|error|nil|1|0"
        assert message == "reload failed: initialization did not confirm readiness"

    def test_no_wait_budget_reports_why_without_sleeping(self):
        summary, message = run(NO_WAIT)
        assert summary == "200|success|false|0|0"
        assert message == "reload signalled but readiness is unconfirmed: no time"
