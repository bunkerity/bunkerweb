"""An instance's lock waits and its callers' read budgets are one contract, in two languages.

`POST /confs` queues `PUSH_LOCK_WAIT` for the swap key and `POST /reload` queues
`SWAP_WAIT_TIMEOUT`; whichever loses answers 503, and `ApiCaller`'s `BUSY_ATTEMPTS` retry
(`test_api_caller_busy_retry.py`) is what keeps that from being reported as a failed push.

That retry keys on the **503**. A refusal written after the caller stopped listening never arrives
as one: `requests` raises `ReadTimeout`, `API.request` reports `status=None`, the retry does not
fire, `_trigger_reload` reports the reload as failed and `push-configs.py` restores a failover
snapshot over a fleet that was merely busy applying the previous change. So the server-side wait has
to end well inside the client-side read budget, and nothing pinned that until this module: the
reload waited exactly as long as its callers were willing to read (30 s against `(5, 30)`), which is
no margin at all -- the sleep loop and the log line put the answer past the deadline every time.

`RELOAD_CALLERS` is the set of callers that DECLARE a budget. A caller that passes no timeout
inherits `ApiCaller.send_to_apis`' own 10 s default, which is exactly the instance-side wait and
therefore no margin at all -- that is what the two certbot jobs did until they were given a budget
of their own. Source scanning cannot see whether a declared constant is still passed at the call
site either, so this module pins the budgets, not their use.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "api.lua"
RELOAD_CALLERS = (
    "src/worker/tasks.py",
    "src/api/app/routers/instances.py",
    "src/ui/app/models/instance.py",
    "src/common/core/jobs/jobs/push-configs.py",
    # These two used to pass no timeout at all and inherit `send_to_apis`' 10 s default, which is
    # exactly the instance-side wait: margin zero, and the 503 arrives as a status-less timeout the
    # busy retry cannot see. They declare their own budget since DEV-2b6.
    "src/common/core/letsencrypt/jobs/certbot-new.py",
    "src/common/core/letsencrypt/jobs/certbot-renew.py",
)
# What the wait still has to spend after its last tick: the ERR log line, the response, and the
# 100 ms sleep granularity of the queue loop. Ten seconds is slack, not a measurement -- the point is
# that the margin exists and cannot silently go to zero again.
BUSY_ANSWER_MARGIN = 10


def _lua_seconds(name: str) -> int:
    found = re.search(rf"^local {name} = (\d+)$", API_LUA.read_text(encoding="utf-8"), re.M)
    assert found, f"{name} is gone from {API_LUA}"
    return int(found.group(1))


@pytest.mark.parametrize("caller", RELOAD_CALLERS)
def test_the_reload_wait_leaves_its_503_time_to_arrive(caller):
    """POST /reload must refuse while its caller is still listening, or its 503 is unreachable."""
    source = (ROOT / caller).read_text(encoding="utf-8")
    declared = re.search(r"^RELOAD_TIMEOUT = \(\d+, (\d+)\)$", source, re.M)
    assert declared, f"{caller} no longer declares RELOAD_TIMEOUT as a (connect, read) literal"
    read_budget = int(declared.group(1))
    # Declaring it is not using it: drop the argument and the caller silently falls back to
    # send_to_apis' own 10 s default, which is the defect this module exists to catch.
    assert "timeout=RELOAD_TIMEOUT" in source, f"{caller} declares a reload budget it no longer passes"
    wait = _lua_seconds("SWAP_WAIT_TIMEOUT")

    assert wait < read_budget, f"{caller} stops reading after {read_budget}s, so a {wait}s wait can never deliver its 503"
    assert read_budget - wait >= BUSY_ANSWER_MARGIN, (
        f"{caller} leaves only {read_budget - wait}s for the refusal to be logged and written; "
        f"a busy instance would be reported as a failed reload instead of retried"
    )


def test_a_push_never_queues_longer_than_the_reload_it_must_not_overlap():
    """The push wait is the same ceiling for the same reason, and neither may quietly outgrow it."""
    assert _lua_seconds("PUSH_LOCK_WAIT") <= _lua_seconds("SWAP_WAIT_TIMEOUT")
