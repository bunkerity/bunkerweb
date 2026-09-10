"""A Redis wipe used to freeze the reports window at zero forever.

Port of dev 27a8aa150. Redis can lose the ``requests`` list wholesale — a burst past
``maxmemory`` evicts it as one key, an operator ``DEL`` or a restart with no persistence does
the same. Every report already pushed stays latched ``synced`` in the worker's buffer, so
nothing ever refilled the list: the UI showed an empty window while every instance still held
a full one.

``reclaim_wiped_requests`` unlatches the buffer when, and only when, the list is *empty* —
the one trigger that needs no LRANGE scan and can never duplicate a report.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
METRICS_LUA = ROOT / "src" / "common" / "core" / "metrics" / "metrics.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


def _source() -> str:
    return METRICS_LUA.read_text(encoding="utf-8")


def _extract(name: str) -> str:
    match = re.search(rf"^local function {name}\(.*?^end$", _source(), re.S | re.M)
    assert match, f"{name} not found in metrics.lua — did it get renamed?"
    return match.group(0)


def _ceiling() -> int:
    """The give-up ceiling, read from the shipped source so the test cannot drift from it."""
    match = re.search(r"^local MAX_RECLAIM_ATTEMPTS = (\d+)$", _source(), re.M)
    assert match, "MAX_RECLAIM_ATTEMPTS is gone from metrics.lua"
    return int(match.group(1))


def _run(body: str, *, llen, cap='"10k"') -> subprocess.CompletedProcess:
    prelude = """
    local WARN = 4
    local match = string.match
    local MAX_RECLAIM_ATTEMPTS = %d
    local reclaim_attempts = 0
    local logs = {}
    local llen_calls = 0
    local self = {
        variables = { METRICS_MAX_BLOCKED_REQUESTS_REDIS = %s },
        redis_call = function(_, method, key)
            if method == "llen" and key == "requests" then
                llen_calls = llen_calls + 1
                return %s
            end
            error("unexpected redis_call " .. tostring(method))
        end,
        log_throttled = function(_, _, id, msg) table.insert(logs, id .. "|" .. msg) end,
    }
    """ % (_ceiling(), cap, llen)
    source = prelude + _extract("parse_count") + "\n" + _extract("reclaim_wiped_requests") + "\n" + body
    return subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)


BUFFER = """
    local requests = {
        { id = "a", synced = true },
        { id = "b", synced = true },
        { id = "c", synced = false },
    }
"""


def _unlatched(stdout: str) -> int:
    return int(stdout.strip().splitlines()[0])


@needs_lua
def test_an_empty_list_unlatches_every_synced_report():
    """The defect in one assertion: an empty list must put the buffered reports back in play."""
    result = _run(
        BUFFER + """
        reclaim_wiped_requests(self, requests)
        local unlatched = 0
        for _, r in ipairs(requests) do
            if not r.synced then unlatched = unlatched + 1 end
        end
        print(unlatched)
        print(#logs > 0 and logs[1] or "no-log")
    """,
        llen="0",
    )
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    lines = result.stdout.strip().splitlines()
    assert _unlatched(result.stdout) == 3, "both synced rows plus the already-unsynced one"
    assert lines[1].startswith("requests_reclaim|"), lines[1]
    assert "re-syncing 2 buffered reports" in lines[1]


@needs_lua
def test_a_live_list_is_left_alone():
    """A list that still holds reports must never be refilled: that would duplicate every row."""
    result = _run(
        BUFFER + """
        reclaim_wiped_requests(self, requests)
        local unlatched = 0
        for _, r in ipairs(requests) do
            if not r.synced then unlatched = unlatched + 1 end
        end
        print(unlatched)
        print(#logs)
    """,
        llen="42",
    )
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert _unlatched(result.stdout) == 1, "only the row that was already unsynced"
    assert result.stdout.strip().splitlines()[1] == "0", "a live list is not worth a log line"


@needs_lua
def test_a_cap_of_zero_never_even_asks_redis():
    """Cap 0 means the operator wants no report in Redis; the trim deletes the list every
    cycle, so refilling it here would fight that forever."""
    result = _run(
        BUFFER + """
        reclaim_wiped_requests(self, requests)
        local unlatched = 0
        for _, r in ipairs(requests) do
            if not r.synced then unlatched = unlatched + 1 end
        end
        print(unlatched)
        print(llen_calls)
    """,
        llen="0",
        cap='"0"',
    )
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert _unlatched(result.stdout) == 1
    assert result.stdout.strip().splitlines()[1] == "0", "cap 0 must short-circuit before the LLEN"


@needs_lua
def test_an_unparsable_cap_still_recovers_the_reports():
    """An unreadable cap leaves reports being pushed, so it must not disable their recovery."""
    result = _run(
        BUFFER + """
        reclaim_wiped_requests(self, requests)
        local unlatched = 0
        for _, r in ipairs(requests) do
            if not r.synced then unlatched = unlatched + 1 end
        end
        print(unlatched)
    """,
        llen="0",
        cap='"not-a-number"',
    )
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert _unlatched(result.stdout) == 3


@needs_lua
def test_an_unreadable_llen_proves_nothing():
    """`redis_call` answers `false` with an error string when the cycle's breaker is open.
    `tonumber(false)` is nil, which is neither empty nor alive: change nothing."""
    result = _run(
        BUFFER + """
        reclaim_wiped_requests(self, requests)
        local unlatched = 0
        for _, r in ipairs(requests) do
            if not r.synced then unlatched = unlatched + 1 end
        end
        print(unlatched)
        print(#logs)
    """,
        llen="false",
    )
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert _unlatched(result.stdout) == 1
    assert result.stdout.strip().splitlines()[1] == "0"


@needs_lua
def test_a_redis_that_keeps_losing_the_list_stops_being_refilled():
    """Eviction raises no error, so the OOM breaker never trips on it. Without a ceiling the
    refill becomes a permanent push storm."""
    ceiling = _ceiling()
    result = _run(
        """
        local cycles = %d
        local reclaimed_cycles = 0
        for _ = 1, cycles do
            local requests = { { id = "a", synced = true } }
            reclaim_wiped_requests(self, requests)
            if not requests[1].synced then reclaimed_cycles = reclaimed_cycles + 1 end
        end
        print(reclaimed_cycles)
        print(logs[#logs])
    """ % (ceiling + 3),
        llen="0",
    )
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    lines = result.stdout.strip().splitlines()
    assert int(lines[0]) == ceiling, f"the refill must stop after {ceiling} consecutive wipes"
    assert lines[1].startswith("requests_reclaim_giveup|"), lines[1]


@needs_lua
def test_one_surviving_cycle_clears_the_ceiling():
    """A list seen alive means the wipe was transient, so the budget has to come back."""
    ceiling = _ceiling()
    result = _run(
        """
        local llen_value = 0
        self.redis_call = function(_, method, key)
            if method == "llen" and key == "requests" then return llen_value end
            error("unexpected redis_call " .. tostring(method))
        end
        local reclaimed_cycles = 0
        for cycle = 1, %d do
            -- One healthy cycle in the middle, right at the ceiling.
            llen_value = (cycle == %d) and 7 or 0
            local requests = { { id = "a", synced = true } }
            reclaim_wiped_requests(self, requests)
            if not requests[1].synced then reclaimed_cycles = reclaimed_cycles + 1 end
        end
        print(reclaimed_cycles)
    """ % (ceiling * 2 + 1, ceiling + 1),
        llen="0",
    )
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    # `ceiling` wipes, one live cycle that resets the counter, then `ceiling` more.
    assert int(result.stdout.strip().splitlines()[0]) == ceiling * 2
