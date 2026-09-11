"""A job-triggered reload must not land in the middle of a configuration push.

`push-configs` renders with `gen/main.py --output /etc/nginx`, and `gen/main.py` EMPTIES its output
directory before rendering into it. On All-in-one and the Linux package that directory is the
running instance's live configuration, so for the length of a render the instance has no
`variables.env` on disk. Nothing coordinated that window with this function: a job exiting 1 asks
for a fleet reload with no knowledge of a push in flight.

CI run 34576775876 (All-in-one `upgrade`) lost the race inside one second:

    [GENERATOR]  [437] Removing old files ...            <- push-configs wiping /etc/nginx
    [GENERATOR]  [437] Rendering templates ...
    [API.CALLER] [436] Successfully sent .../reload?test=no
    [GENERATOR]  [437] Generator successfully executed !

`init_by_lua` read a tree with no `variables.env`, and because the variables live in a per-Lua-VM
LRU (`datastore.lua:39`) the new cycle came up with an empty internalstore. Every control-plane
request was then refused 444 -- including the `POST /confs` that would have repaired it. The
instance answered `ping` for five more minutes and never accepted a configuration again.

The instance side is already guarded: `POST /confs` and `POST /reload` both take the swap lock in
`api.lua`. The render is the one unguarded window, and it is guarded here instead -- the push holds
`bw:push_configs_inflight` for its whole run and ends with its own `_trigger_reload`, so the reload
this job wants is already coming. What the push cannot promise is that it carried THIS job's files:
it may already have pushed `/cache` before the job wrote them. So the debt is recorded rather than
dropped, and the next run carries it -- the same machinery the no-instance branch uses.
"""

from test_delivery_guarantees import BROKER, LOGGER, TASKS
from test_reload_broadcast import _LockRedis, _apis, _with_redis

PUSH_LOCK = "bw:push_configs_inflight"


def test_a_reload_is_held_while_a_configuration_push_is_in_flight():
    """The regression this file exists for: reloading onto a half-rendered /etc/nginx."""
    client = _LockRedis({PUSH_LOCK: "some-celery-task-id"})
    apis = _apis()
    with _with_redis(client):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)

    apis.send_files.assert_not_called()
    apis.send_to_apis.assert_not_called()
    # The push owns the reload; this job must not have taken the reload lock on the way out.
    assert TASKS.RELOAD_LOCK_KEY not in client.keys


def test_the_held_reload_leaves_the_debt_behind():
    """Holding is only safe if nothing is dropped.

    The push ships the whole cache tree, but it may already have pushed `/cache` before this job
    wrote its files -- the lease covers the reload too. Recording the debt means the next run that
    reaches `_reload_is_owed` carries them; dropping it would be the silent job-output loss the
    debounce was rewritten to close.
    """
    client = _LockRedis({PUSH_LOCK: "some-celery-task-id"})
    with _with_redis(client):
        TASKS._request_reload_debounced(_apis(), BROKER, LOGGER)

    assert client.keys.get(TASKS.RELOAD_OWED_KEY), "the held reload dropped this job's material"
    # A fresh debt must not inherit an older backoff, same rule as the no-instance branch.
    assert TASKS.RELOAD_OWED_ATTEMPTS_KEY not in client.keys


def test_the_dirty_flag_is_not_raised_with_nobody_to_claim_it():
    """`bw:reload_dirty` is only ever read by the holder of the reload lock.

    Raised on a path that then returns without taking the lock, it just expires, and the material
    it stood for is dropped. The durable `bw:reload_owed` marker is the right one here.
    """
    client = _LockRedis({PUSH_LOCK: "some-celery-task-id"})
    with _with_redis(client):
        TASKS._request_reload_debounced(_apis(), BROKER, LOGGER)

    assert TASKS.RELOAD_DIRTY_KEY not in client.keys


def test_no_push_in_flight_still_pushes_and_reloads():
    """The gate must be exactly as narrow as the window: no lease, no change."""
    client = _LockRedis()
    apis = _apis()
    with _with_redis(client):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)

    apis.send_files.assert_called_once_with("/var/cache/bunkerweb", "/cache", timeout=(5, 30))
    apis.send_to_apis.assert_called_once_with("POST", "/reload?test=yes", timeout=(5, 30))


def test_a_broker_that_cannot_answer_does_not_hold_the_reload():
    """Fails OPEN, deliberately, and the opposite way round from `_reload_is_owed`.

    A broker we cannot read is not evidence of a push in flight. Holding on a read error would
    turn a Redis hiccup into "no instance ever gets reloaded again", which is a far worse failure
    than the narrow race this gate closes -- and the instance side still refuses a reload that
    overlaps a swap.
    """

    class _Blind(_LockRedis):
        def exists(self, key):
            if key == PUSH_LOCK:
                raise RuntimeError("broker is down")
            return super().exists(key)

    client = _Blind()
    apis = _apis()
    with _with_redis(client):
        TASKS._request_reload_debounced(apis, BROKER, LOGGER)

    apis.send_files.assert_called_once()


def test_the_lease_key_matches_the_one_push_configs_takes():
    """Two literals in two files. A rename on either side silently disarms the gate."""
    from pathlib import Path

    job = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "jobs" / "jobs" / "push-configs.py"
    assert f'LOCK_KEY = "{TASKS.PUSH_CONFIGS_LOCK_KEY}"' in job.read_text(encoding="utf-8")
