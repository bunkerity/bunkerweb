"""Unit tests for ``InstancesUtils`` ban/unban propagation semantics.

Covers the "no instance matched the ``status == 'up'`` propagation filter" gap
found by a live e2e where the only instance was stuck in ``failover``: a ban or
unban that reaches zero instances must report failure, not silent success.

Also pins the ``Instance.status`` Literal now enumerating ``failover`` and the
rule that ``failover`` instances are excluded from propagation (only ``up`` is
healthy). ``src/ui`` is on ``sys.path`` via ``tests/unit/ui/conftest.py``;
``src/common/{utils,api,db}`` via the root conftest.
"""

from types import SimpleNamespace
from typing import get_args
from unittest.mock import Mock

from app.models.instance import Instance, InstancesUtils


def _fake_instance(name, ban_result="ok", unban_result="ok"):
    """Instance stand-in exposing only what ``InstancesUtils`` calls: ``name``
    plus ``ban``/``unban`` returning the per-instance status string (a
    ``Can't ban``/``Can't unban`` prefix marks failure)."""
    return SimpleNamespace(
        name=name,
        ban=lambda *a, **k: ban_result,
        unban=lambda *a, **k: unban_result,
    )


def _utils_with_instances(instances_data):
    api_client = Mock()
    api_client.get_instances.return_value = instances_data
    return InstancesUtils(api_client=api_client)


# --- Literal / rule ---------------------------------------------------------


def test_instance_status_literal_includes_failover():
    assert "failover" in get_args(Instance.__annotations__["status"])


# --- ban: zero-match must fail ---------------------------------------------


def test_ban_no_instances_reports_failure():
    resp = _utils_with_instances([]).ban("1.2.3.4", 3600, "ui", "", "global")
    assert resp  # truthy -> caller flashes an error
    assert isinstance(resp, str) and "1.2.3.4" in resp


def test_ban_failover_only_reports_failure():
    # A failover instance is not 'up', so status='up' filtering yields zero
    # targets -> the ban reached nothing and must report failure.
    resp = _utils_with_instances([{"status": "failover"}]).ban("1.2.3.4", 3600, "ui", "", "global")
    assert resp
    assert isinstance(resp, str) and "1.2.3.4" in resp


def test_unban_no_instances_reports_failure():
    resp = _utils_with_instances([]).unban("1.2.3.4")
    assert resp
    assert isinstance(resp, str) and "1.2.3.4" in resp


# --- ban/unban: success path unchanged -------------------------------------


def test_ban_success_returns_empty_string():
    utils = _utils_with_instances([])
    resp = utils.ban("1.2.3.4", 3600, "ui", "", "global", instances=[_fake_instance("bw1"), _fake_instance("bw2")])
    assert resp == ""


def test_ban_partial_failure_returns_failed_names():
    utils = _utils_with_instances([])
    resp = utils.ban(
        "1.2.3.4",
        3600,
        "ui",
        "",
        "global",
        instances=[_fake_instance("ok"), _fake_instance("bad", ban_result="Can't ban 1.2.3.4 on instance bad")],
    )
    assert resp == ["bad"]


def test_unban_success_returns_empty_string():
    utils = _utils_with_instances([])
    resp = utils.unban("1.2.3.4", instances=[_fake_instance("bw1")])
    assert resp == ""


def test_unban_partial_failure_returns_failed_names():
    utils = _utils_with_instances([])
    resp = utils.unban(
        "1.2.3.4",
        instances=[_fake_instance("ok"), _fake_instance("bad", unban_result="Can't unban 1.2.3.4 on instance bad")],
    )
    assert resp == ["bad"]
