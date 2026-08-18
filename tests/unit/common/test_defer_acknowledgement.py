"""The job side of deferred acknowledgement: hand the flag to the push, do not clear it here."""

import sys
from datetime import datetime
from json import loads
from types import ModuleType
from unittest.mock import Mock, patch

from jobs import RELOAD_ACK_PENDING_KEY, defer_change_acknowledgement


def _redis_stub(client):
    module = ModuleType("redis")
    module.Redis = Mock()
    module.Redis.from_url = Mock(return_value=client)
    return patch.dict(sys.modules, {"redis": module})


def test_the_watermark_survives_the_trip():
    """`clear_applied_changes` compares against `last_*_change`, so it must arrive intact.

    JSON cannot carry a datetime; the worker parses it back. Drop it and the compare-and-set
    silently degrades into an unconditional clear.
    """
    client = Mock()
    snapshot = {
        "certificates_changed": True,
        "last_certificates_change": datetime(2026, 8, 18, 8, 0, 0),
        "plugins_config_changed": {"geoip": None},  # not serializable, and not read for this key
    }

    with _redis_stub(client):
        assert defer_change_acknowledgement(("certificates",), snapshot, Mock()) == ""

    key, raw = client.sadd.call_args[0]
    assert key == RELOAD_ACK_PENDING_KEY
    payload = loads(raw)
    assert payload["keys"] == ["certificates"]
    assert payload["snapshot"]["certificates_changed"] is True
    assert payload["snapshot"]["last_certificates_change"] == "2026-08-18T08:00:00"


def test_a_broker_failure_is_reported_not_swallowed():
    """The caller leaves the change pending on error — it must be able to tell."""
    client = Mock()
    client.sadd.side_effect = OSError("broker unreachable")

    with _redis_stub(client):
        error = defer_change_acknowledgement(("certificates",), {"certificates_changed": True}, Mock())

    assert "broker unreachable" in error
