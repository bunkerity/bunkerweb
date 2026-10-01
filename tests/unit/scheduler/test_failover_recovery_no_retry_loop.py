"""An instance push-configs marked ``failover`` must not be re-pushed forever with the same configuration.

push-configs marks the instances ``failover`` when a reload is refused and the previous configuration cannot be
restored. The healthcheck then sees them answer, flips them to ``up`` and, on that ``failover`` -> ``up`` edge,
dispatched push-configs again: same broken configuration, same refusal, same marking, every 30 s until someone
removed the config (smoke Q8, item 1b). The retry is only worth it when something changed since the last attempt.
"""

import pytest

# the scheduler import sandbox and the fake client/scheduler live with the healthcheck loading tests
from test_healthcheck_loading import NO_PENDING_CHANGES, PENDING_CHANGES, harness, scheduler_import, scheduler_main  # noqa: F401

FAILOVER = [{"hostname": "bw", "status": "failover"}]
UP = {"bw": "up"}


@pytest.fixture(autouse=True)
def _fresh(scheduler_main):  # noqa: F811
    scheduler_main.FAILED_PUSH_FINGERPRINT = None
    scheduler_main.PENDING_REDISPATCH_PASSES = 0


def _pass(scheduler_main):  # noqa: F811
    scheduler_main.HEALTHCHECK_EVENT.clear()
    scheduler_main.healthcheck_job()


def test_a_recovered_failover_instance_is_re_pushed_once(harness, scheduler_main):  # noqa: F811
    _api, scheduler = harness(FAILOVER, UP, metadata=PENDING_CHANGES)

    _pass(scheduler_main)

    assert scheduler.dispatched == ["push-configs"]


def test_the_same_configuration_is_not_re_pushed_after_it_failed(harness, scheduler_main):  # noqa: F811
    api, scheduler = harness(FAILOVER, UP, metadata=PENDING_CHANGES)

    _pass(scheduler_main)
    # push-configs failed again and marked the instance failover once more
    api._instances = [{"hostname": "bw", "status": "failover"}]
    _pass(scheduler_main)

    assert scheduler.dispatched == ["push-configs"]


def test_a_changed_configuration_is_pushed_again(harness, scheduler_main):  # noqa: F811
    api, scheduler = harness(FAILOVER, UP, metadata=PENDING_CHANGES)

    _pass(scheduler_main)
    api._instances = [{"hostname": "bw", "status": "failover"}]
    api._metadata = PENDING_CHANGES | {"last_custom_configs_change": "2026-09-30T13:20:00"}
    _pass(scheduler_main)

    assert scheduler.dispatched == ["push-configs", "push-configs"]


def test_recovery_from_down_is_never_skipped(harness, scheduler_main):  # noqa: F811
    scheduler_main.FAILED_PUSH_FINGERPRINT = scheduler_main.push_fingerprint(PENDING_CHANGES)
    _api, scheduler = harness([{"hostname": "bw", "status": "down"}], UP, metadata=PENDING_CHANGES)

    _pass(scheduler_main)

    assert scheduler.dispatched == ["push-configs"]


def test_the_hold_survives_the_instance_staying_up(harness, scheduler_main):  # noqa: F811
    """After the failover -> up edge the instance stays `up` while the rejected config stays pending: the
    pending-changes fallback (including its every-20th-pass slow retry) must not re-push it either."""
    api, scheduler = harness(FAILOVER, UP, metadata=PENDING_CHANGES)

    _pass(scheduler_main)
    api._instances = [{"hostname": "bw", "status": "up"}]
    for _ in range(25):
        _pass(scheduler_main)

    assert scheduler.dispatched == ["push-configs"]


def test_a_change_after_the_hold_releases_it(harness, scheduler_main):  # noqa: F811
    api, scheduler = harness(FAILOVER, UP, metadata=PENDING_CHANGES)

    _pass(scheduler_main)
    api._instances = [{"hostname": "bw", "status": "up"}]
    for _ in range(3):
        _pass(scheduler_main)
    api._metadata = PENDING_CHANGES | {"last_custom_configs_change": "2026-09-30T13:20:00"}
    _pass(scheduler_main)

    assert scheduler.dispatched == ["push-configs", "push-configs"]


def test_an_applied_config_clears_the_hold(harness, scheduler_main):  # noqa: F811
    api, scheduler = harness(FAILOVER, UP, metadata=PENDING_CHANGES)

    _pass(scheduler_main)
    api._instances = [{"hostname": "bw", "status": "up"}]
    api._metadata = NO_PENDING_CHANGES
    _pass(scheduler_main)
    assert scheduler_main.FAILED_PUSH_FINGERPRINT is None


def test_the_apply_rearm_skips_the_held_configuration(scheduler_main):  # noqa: F811
    """The 300 s APPLY_RETRY_INTERVAL re-arm cleared the baseline for the very configuration a failover rejected
    and re-dispatched it (Criticos Q8 follow-up): past 300 s of simulated time with the hold active it must stay quiet."""
    from datetime import datetime, timedelta

    scheduler_main.FAILED_PUSH_FINGERPRINT = scheduler_main.push_fingerprint(PENDING_CHANGES)
    start = datetime(2026, 9, 30, 12, 0, 0)
    for seconds in range(0, 1201, 30):
        assert not scheduler_main.apply_rearm_due(PENDING_CHANGES, start, start + timedelta(seconds=seconds))


def test_the_apply_rearm_still_fires_without_a_hold_and_when_a_change_releases_it(scheduler_main):  # noqa: F811
    from datetime import datetime, timedelta

    start = datetime(2026, 9, 30, 12, 0, 0)
    later = start + timedelta(seconds=scheduler_main.APPLY_RETRY_INTERVAL + 1)
    assert not scheduler_main.apply_rearm_due(PENDING_CHANGES, start, start + timedelta(seconds=10))  # too early

    assert scheduler_main.apply_rearm_due(PENDING_CHANGES, start, later)  # no hold: the old behaviour

    scheduler_main.FAILED_PUSH_FINGERPRINT = scheduler_main.push_fingerprint(PENDING_CHANGES)
    assert not scheduler_main.apply_rearm_due(PENDING_CHANGES, start, later)  # held
    released = PENDING_CHANGES | {"last_custom_configs_change": "2026-09-30T13:20:00"}  # a real change moves the watermark
    assert scheduler_main.apply_rearm_due(released, start, later)
    assert not scheduler_main.apply_rearm_due(NO_PENDING_CHANGES, start, later)  # nothing pending
