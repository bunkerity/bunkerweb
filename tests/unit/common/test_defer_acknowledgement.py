"""The job side of deferred acknowledgement: hand the flag to the push, do not clear it here."""

import sys
from datetime import datetime
from json import loads
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from jobs import defer_change_acknowledgement, drain_pending_acks


@pytest.fixture(autouse=True)
def _empty_queue():
    """The handoff is module state: a leftover from one test would arrive in the next."""
    drain_pending_acks()
    yield
    drain_pending_acks()


def test_the_watermark_survives_the_trip():
    """`clear_applied_changes` compares against `last_*_change`, so it must arrive intact.

    JSON cannot carry a datetime; the worker parses it back. Drop it and the compare-and-set
    silently degrades into an unconditional clear.
    """
    snapshot = {
        "certificates_changed": True,
        "last_certificates_change": datetime(2026, 8, 18, 8, 0, 0),
        "plugins_config_changed": {"geoip": None},  # not serializable, and not read for this key
    }

    assert defer_change_acknowledgement(("certificates",), snapshot, Mock()) == ""

    payload = loads(drain_pending_acks()[0])
    assert payload["keys"] == ["certificates"]
    assert payload["snapshot"]["certificates_changed"] is True
    assert payload["snapshot"]["last_certificates_change"] == "2026-08-18T08:00:00"


def test_deferring_never_reaches_for_the_broker():
    """The regression an end-to-end run caught: the job has no broker to reach for.

    The worker strips CELERY_BROKER_URL from every job environment, so a client built here fell
    back to redis://localhost and a split-container worker refused the connection — on every run,
    of every deferring job. The deferral reported that failure honestly and left the change
    pending, so nothing broke; the feature simply never once worked. Publishing moved to the
    worker, which still has the credential.
    """
    exploding = ModuleType("redis")
    exploding.Redis = Mock()
    exploding.Redis.from_url = Mock(side_effect=AssertionError("a job must not build a broker client"))

    with patch.dict(sys.modules, {"redis": exploding}):
        assert defer_change_acknowledgement(("certificates",), {"certificates_changed": True}, Mock()) == ""

    assert len(drain_pending_acks()) == 1
    exploding.Redis.from_url.assert_not_called()


def test_an_unserializable_watermark_is_refused_rather_than_dropped():
    """`plugins_config` breaks the shape every other key follows.

    `get_metadata` emits it as `plugins_config_changed = {plugin_id: last_config_change}` — the
    watermark IS the flag, and there is no `last_plugins_config_change` key at all. So a caller
    deferring that key hands over a dict, JSON keeps only the scalars, and dropping it would make
    `clear_applied_changes` match nothing, report success, and lose the flag forever. Refuse.
    """
    snapshot = {"plugins_config_changed": {"geoip": datetime(2026, 8, 18, 8, 0, 0)}}

    error = defer_change_acknowledgement(("plugins_config",), snapshot, Mock())

    assert "does not survive the broker" in error
    assert drain_pending_acks() == []


def test_a_drained_acknowledgement_is_not_handed_out_twice():
    defer_change_acknowledgement(("certificates",), {"certificates_changed": True}, Mock())

    assert len(drain_pending_acks()) == 1
    assert drain_pending_acks() == []
