"""Unit tests for ``Instance`` ban-related status semantics.

``InstancesUtils.ban``/``.unban`` used to live here and push straight to the instances whose
``status == "up"``; the tests below pinned the "zero targets must report failure" rule found by a
live e2e. Both methods are gone since bans became durable — the UI calls the API, which writes the
row before fanning out, and the convergence job reconciles whatever instance was unreachable at the
time. That makes the zero-target case a non-event rather than a silent success, so those tests went
with the code.

What remains worth pinning is the ``failover`` status itself: it is not ``up``, and nothing that
distributes state may treat it as healthy. ``src/ui`` is on ``sys.path`` via
``tests/unit/ui/conftest.py``; ``src/common/{utils,api,db}`` via the root conftest.
"""

from datetime import datetime
from typing import get_args
from unittest.mock import Mock

from app.models.instance import Instance


def test_instance_status_literal_includes_failover():
    # A failover instance runs a broken/degraded config (its last-known-good restore failed too),
    # so it is a status of its own and never counted as healthy.
    assert "failover" in get_args(Instance.__annotations__["status"])


def test_reload_allows_time_for_nginx_confirmation(monkeypatch):
    monkeypatch.delenv("DISABLE_CONFIGURATION_TESTING", raising=False)
    api_caller = Mock()
    api_caller.send_to_apis.return_value = (True, None)
    timestamp = datetime(2026, 8, 27)
    instance = Instance("bw-1", "bw-1", "ui", "up", "static", timestamp, timestamp, api_caller)

    assert instance.reload() == "Instance bw-1 has been reloaded."
    api_caller.send_to_apis.assert_called_once_with("POST", "/reload?test=yes", timeout=(5, 30))
