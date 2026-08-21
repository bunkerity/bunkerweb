"""The debounce loop `DockerController` and `SwarmController` used to hold two copies of.

The two bodies were near byte-identical -- 96 lines differing only in the word they logged, the
stream they read and the filter they applied -- so a fix landing in one silently left the other
behind. They now both call `Controller._run_event_loop`. What has to hold is behavioural: a burst
of events must produce ONE apply, not one per event, and the stream's error path must not swallow
a shutdown signal.

No test here is skipped and none needs a daemon: the event stream is a generator.
"""

import importlib.util
import sys
from pathlib import Path
from threading import Lock
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load_controller():
    """Import `Controller` with `Config` and `logger` stubbed -- neither is on `.venv-unit`."""
    config_mod = ModuleType("Config")

    class Config:
        def __init__(self, *args, **kwargs):
            self._supported_config_types = []

    config_mod.Config = Config
    logger_mod = ModuleType("logger")
    logger_mod.getLogger = lambda *a, **k: Mock()

    with patch.dict(sys.modules, {"Config": config_mod, "logger": logger_mod}):
        path = ROOT / "src" / "autoconf" / "controllers" / "Controller.py"
        spec = importlib.util.spec_from_file_location("bw_autoconf_controller_base", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


BASE = _load_controller()
Controller = BASE.Controller


class _Stop(BaseException):
    """Not an Exception on purpose: the loop's stream handler is `except Exception`, so this
    escapes it and ends the loop. Under the bare `except:` it replaces, it would be swallowed."""


class _Bail(BaseException):
    """Raised from the stubbed 10-second retry sleep.

    Needed so a mutant that widens the stream handler back to `except:`/`BaseException` FAILS
    rather than HANGS: it would swallow `_Stop`, set `error`, and spin the outer `while True`
    forever, ten seconds at a time. `_Bail` comes out of the `finally`, which propagates past any
    except clause, so the mutant lands as a red test in milliseconds. RULE 12 wants a red, not a
    timeout -- a hanging suite is not a failing suite.
    """


def _no_retry_sleep(seconds):
    """Stand-in for the loop's module-level `sleep`. The debounce sleeps are real (the tests time
    them); only the 10-second error-retry sleep is turned into a bail-out."""
    from time import sleep as _real_sleep

    if seconds >= 10:
        raise _Bail(f"the loop reached its error-retry sleep({seconds})")
    _real_sleep(seconds)


@pytest.fixture(autouse=True)
def _bail_instead_of_retrying():
    """Patched once for the whole module, never per call.

    `patch.object` on a module attribute is not thread-safe, and one test drives the loop from two
    threads: each thread captured the *other's* stand-in as its "original" and restored that on
    exit, so the real `sleep` came back mid-test and a mutant span for ten seconds a turn instead
    of failing. One patch, no nesting, no race.
    """
    with patch.object(BASE, "sleep", _no_retry_sleep):
        yield


def _controller(*, update_needed=True):
    """A controller without __init__: __init__ reads the environment, which RULE 17 says must not
    be the thing supplying the answer here. Every field the loop touches is set explicitly."""
    controller = object.__new__(Controller)
    controller._logger = Mock()
    controller._first_start = False
    controller._pending_apply = False
    controller._last_event_time = 0.0
    controller._debounce_delay = 0.05  # the real 2 s only makes the test slow
    controller._instances = []
    controller._services = []
    controller._configs = {}
    controller._loaded = True
    controller._api = Mock()
    controller._api.expect_errors.return_value.__enter__ = Mock()
    controller._api.expect_errors.return_value.__exit__ = Mock(return_value=False)
    controller.have_to_wait = Mock(return_value=False)
    controller._update_settings = Mock()
    controller.get_instances = Mock(return_value=[])
    controller.get_services = Mock(return_value=[])
    controller.get_configs = Mock(return_value={})
    controller.update_needed = Mock(return_value=update_needed)
    controller.apply_config = Mock(return_value=True)
    controller._set_autoconf_loaded = Mock()
    return controller


def _run(controller, events, *, process_event=None, calls=None):
    """Drive the loop once. The factory raises _Stop after yielding, which ends the loop."""

    def factory():
        if calls is not None:
            calls.append(1)
        yield from events
        raise _Stop

    with pytest.raises(_Stop):
        controller._run_event_loop(
            events=factory,
            process_event=process_event or (lambda event: True),
            label="Test",
            lock=Lock(),
        )


def test_the_apply_waits_for_the_debounce_window_to_go_quiet():
    """The delay is the loop's own contract: an event does not deploy until the stream has been
    silent for `_debounce_delay`. Mutant: drop the `while (time() - _last_event_time) < delay`
    wait -- the apply then lands immediately and the elapsed assertion goes red."""
    from time import monotonic

    controller = _controller()
    controller._debounce_delay = 0.3

    started = monotonic()
    _run(controller, [{"n": 1}])
    elapsed = monotonic() - started

    assert controller.apply_config.call_count == 1
    assert elapsed >= 0.3, f"deployed after {elapsed:.3f}s, before the {controller._debounce_delay}s window closed"


def test_two_concurrent_event_streams_collapse_into_one_apply():
    """This is where the batching actually happens, and it is the shape SwarmController runs:
    two threads (`service` and `config`) over one controller, one lock and one `_last_event_time`.
    A second stream's event lands inside the first's debounce window, pushes the timer out, and
    the first thread finds the window re-opened and yields its apply instead of doubling it.

    Mutant: drop the second `(time() - _last_event_time) < _debounce_delay` re-check after the
    lock is re-acquired. Note what that mutant does and does not do -- `_pending_apply` alone
    already collapses the two threads to ONE apply, so a call-count assertion does not see it.
    What it changes is WHEN: without the re-check the first thread deploys as soon as its own
    window closes, while the second stream is still delivering, instead of waiting for the whole
    burst to go quiet. So this test asserts the deploy timestamp, not just the count.
    """
    from threading import Barrier, Thread
    from time import monotonic

    controller = _controller()
    controller._debounce_delay = 0.4
    deployed_at = []
    controller.apply_config = Mock(side_effect=lambda *a, **k: (deployed_at.append(monotonic()), True)[1])
    lock = Lock()
    both_ready = Barrier(2)

    def stream(delay):
        def factory():
            both_ready.wait(timeout=5)
            sleep_until(delay)
            yield {"stream": delay}
            raise _Stop

        try:
            controller._run_event_loop(events=factory, process_event=lambda event: True, label="Test", lock=lock)
        except _Stop:
            pass

    def sleep_until(delay):
        from time import sleep as _sleep

        if delay:
            _sleep(delay)

    LAST_EVENT_OFFSET = 0.2
    threads = [Thread(target=stream, args=(offset,)) for offset in (0.0, LAST_EVENT_OFFSET)]
    started = monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive(), "an event-loop thread did not finish"

    assert controller.apply_config.call_count == 1, f"{controller.apply_config.call_count} applies for two events inside one debounce window"

    # The burst's LAST event is at +0.2; the window must close from THERE, not from the first.
    quiet_at = started + LAST_EVENT_OFFSET + controller._debounce_delay
    early_by = quiet_at - deployed_at[0]
    assert deployed_at[0] >= quiet_at, f"deployed {early_by:.3f}s before the burst went quiet: the first stream applied while the second was still delivering"


def test_an_event_arriving_while_the_loop_blocks_on_the_lock_defers_the_deploy():
    """The exact race the post-lock re-check exists for, made deterministic.

    The debounce wait loop reads the SHARED `_last_event_time`, so a concurrent stream bumping it
    *during* the wait is already absorbed there -- which is why removing the re-check does not
    change the outcome of the two-thread test above. The only instant the re-check alone covers is
    between that wait loop's last condition check and `lock.acquire()` returning: an event landing
    while this thread is blocked on the lock must push the deploy to the next pass, not ship a view
    of the cluster that is already one event stale.

    So the LOCK is the hook -- there is no other code in that gap. Mutant: remove the re-check.
    """
    from time import time as wall_clock

    controller = _controller()
    controller._debounce_delay = 0.2
    acquisitions = []

    class LockThatTakesAnEvent:
        """Wraps a real lock -- `_thread.lock` cannot be subclassed -- and simulates another
        stream delivering an event while this one was blocked on the acquire."""

        def __init__(self):
            self._lock = Lock()

        def acquire(self, *args, **kwargs):
            got = self._lock.acquire(*args, **kwargs)
            acquisitions.append(1)
            if len(acquisitions) == 2:  # the post-debounce re-acquire
                controller._last_event_time = wall_clock()
            return got

        def release(self):
            self._lock.release()

    with pytest.raises(_Stop):
        controller._run_event_loop(
            events=_one_event_then_stop,
            process_event=lambda event: True,
            label="Test",
            lock=LockThatTakesAnEvent(),
        )

    assert len(acquisitions) >= 2, "the loop never re-acquired the lock -- the race was not reproduced"
    assert controller.apply_config.call_count == 0, "deployed a view of the cluster that was already one event stale"
    assert controller._pending_apply is True, "the deferred event must stay pending for the next pass"


def _one_event_then_stop():
    yield {"n": 1}
    raise _Stop


def test_a_following_event_that_changes_nothing_does_not_redeploy():
    """The single-stream case. A lazy event stream delivers one event at a time, so successive
    events each get their own debounce window -- what stops them each deploying to the fleet is
    `update_needed`, not the timer. `docker compose up` of one labelled service emits several
    events; only the first must reach `apply_config`.

    Worth stating plainly because the log line says "Batched ... event(s)" and reads as if the
    timer did it. Mutant: drop the `update_needed` short-circuit.
    """
    controller = _controller()
    controller.update_needed = Mock(side_effect=[True, False, False])

    _run(controller, [{"n": 1}, {"n": 2}, {"n": 3}])

    assert controller.apply_config.call_count == 1, f"{controller.apply_config.call_count} deploys for one real state change"


def test_an_event_the_filter_rejects_never_reaches_apply():
    """RULE 19 floor: the loop must apply for accepted events and not for rejected ones, so the
    test above cannot pass by the loop simply never applying."""
    controller = _controller()

    _run(controller, [{"n": 1}, {"n": 2}], process_event=lambda event: False)

    assert controller.apply_config.call_count == 0
    assert controller._pending_apply is False


def test_nothing_is_deployed_when_the_cluster_state_did_not_actually_change():
    """`update_needed` False means the burst was noise; the loop must not push to the fleet."""
    controller = _controller(update_needed=False)

    _run(controller, [{"n": 1}])

    assert controller.apply_config.call_count == 0


def test_the_stream_error_path_does_not_swallow_a_shutdown_signal():
    """The bare `except:` this replaces caught KeyboardInterrupt and SystemExit, so the controller
    kept looping through a shutdown. Mutant: `except Exception` -> `except:` (or `BaseException`).

    Asserted without relying on a timeout: under the mutant `_Stop` is caught, `error` is set and
    the `finally` logs the retry warning. That warning is the fingerprint of the swallow.
    """
    controller = _controller()
    calls = []

    _run(controller, [], calls=calls)

    assert calls == [1], f"the stream was re-opened {len(calls)} times -- the signal was swallowed"
    warnings = [str(call) for call in controller._logger.warning.call_args_list]
    assert not any("retrying in 10 seconds" in warning for warning in warnings), f"the shutdown signal was caught as a stream error: {warnings}"


def test_a_real_stream_error_is_still_caught_and_retried():
    """RULE 19: the typed except must still absorb what it is there for. A daemon that drops the
    event stream has to be retried, not to kill the controller."""
    controller = _controller()
    attempts = []

    def factory():
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionError("daemon went away")
        raise _Stop

    # This one test opts out of the module-wide bail-out -- it asserts the retry path *does* run --
    # but the stand-in stays BOUNDED. An unbounded no-op sleep let a mutant that swallows `_Stop`
    # spin here forever, which is a hung suite rather than a failing one.
    retries = []

    def bounded_sleep(_seconds):
        retries.append(1)
        if len(retries) > 2:
            raise _Bail("the loop kept retrying: the stream handler swallowed the stop signal")

    with patch.object(BASE, "sleep", bounded_sleep), pytest.raises(_Stop):
        controller._run_event_loop(events=factory, process_event=lambda event: True, label="Test", lock=Lock())

    assert len(attempts) == 2, "a dropped stream must be re-opened"
    assert any("retrying in 10 seconds" in str(call) for call in controller._logger.warning.call_args_list)


def test_both_controllers_route_through_the_shared_loop():
    """A guard against the copies coming back. Not a presence marker on its own -- the behavioural
    assertions above are what prove the loop works; this proves both callers use *that* loop."""
    docker_source = (ROOT / "src" / "autoconf" / "controllers" / "DockerController.py").read_text()
    swarm_source = (ROOT / "src" / "autoconf" / "controllers" / "SwarmController.py").read_text()

    for name, source in (("DockerController", docker_source), ("SwarmController", swarm_source)):
        assert "_run_event_loop(" in source, f"{name} no longer calls the shared loop"
        assert "Batched" not in source, f"{name} grew its own copy of the debounce loop again"
