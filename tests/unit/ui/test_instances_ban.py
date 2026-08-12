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

from typing import get_args

from app.models.instance import Instance


def test_instance_status_literal_includes_failover():
    # A failover instance runs a broken/degraded config (its last-known-good restore failed too),
    # so it is a status of its own and never counted as healthy.
    assert "failover" in get_args(Instance.__annotations__["status"])
