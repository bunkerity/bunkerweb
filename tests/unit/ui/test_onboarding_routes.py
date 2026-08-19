"""`/onboarding/state` — signal fan-out, the ack_hint allow-list and the read-only path.

Route module is loaded with `app.dependencies` stubbed (it reads container-only paths at
import time), following the pattern in ``test_bans_stats.py``.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from app.models.onboarding import CATALOG

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "onboarding.py"


@pytest.fixture(scope="module")
def route_module():
    client, data = Mock(), {}
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.DATA = data
    # `app.routes.utils` pulls more of the dependency module than this blueprint does.
    dependencies.BW_CONFIG = Mock()
    dependencies.BW_INSTANCES_UTILS = Mock()
    dependencies.LOGGER = Mock()
    # `app.routes.utils` imports qrcode at module level; it is not in the unit-test venv.
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    module_name = "app.routes._onboarding_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client, data


@pytest.fixture
def app_ctx(route_module, monkeypatch):
    module, client, data = route_module
    client.reset_mock(return_value=True, side_effect=True)
    data.clear()

    app = Flask(__name__)
    app.secret_key = "test"
    # Register every endpoint the catalog links to so `url_for` can build them.
    for endpoint in {step.endpoint for step in CATALOG}:
        app.add_url_rule(f"/_{endpoint}", endpoint=endpoint, view_func=lambda: "")

    client.get_metadata.return_value = {}
    client.get_instances.return_value = []
    client.get_services.return_value = []
    client.get_certificates.return_value = {"total": 0}
    client.get_metrics_requests.return_value = {"total": 0}
    client.get_workflows.return_value = {"total": 0}
    client.get_user_preferences.return_value = {}
    client.update_user_preferences.return_value = {"status": "success"}

    monkeypatch.setattr(module, "current_user", SimpleNamespace(admin=True, list_permissions=["read", "write"], totp_secret=None, get_id=lambda: "alice"))
    return module, client, data, app


def _get(module, app):
    with app.test_request_context("/onboarding/state"):
        return module.onboarding_state.__wrapped__.__wrapped__().get_json()


def _patch(module, app, body):
    with app.test_request_context("/onboarding/state", method="PATCH", json=body):
        response = module.update_onboarding_state.__wrapped__.__wrapped__()
        if isinstance(response, tuple):
            return response[0].get_json(), response[1]
        return response.get_json(), 200


# --------------------------------------------------------------------------------------
# GET
# --------------------------------------------------------------------------------------
def test_state_reports_a_fresh_admin_with_nothing_done(app_ctx):
    module, _, _, app = app_ctx

    payload = _get(module, app)

    assert payload["track"] == "admin"
    assert payload["done"] == 0
    assert payload["total"] > 0
    assert payload["completed"] is False
    assert payload["dismissed"] is False
    assert {step["id"] for step in payload["steps"]} >= {"install", "service", "https", "first_block", "mfa"}


def test_every_step_carries_a_resolved_target(app_ctx):
    module, _, _, app = app_ctx

    for step in _get(module, app)["steps"]:
        assert step["target"].startswith("/_"), step


def test_one_failing_signal_leaves_its_step_pending_instead_of_erroring(app_ctx):
    """An unreachable certificates endpoint must not hide the other steps."""
    module, client, _, app = app_ctx
    client.get_certificates.side_effect = RuntimeError("boom")
    client.get_services.return_value = [{"SERVER_NAME": "app1.example.com"}]

    payload = _get(module, app)

    by_id = {step["id"]: step for step in payload["steps"]}
    assert by_id["https"]["done"] is False
    assert by_id["service"]["done"] is True


def test_an_unbuildable_target_drops_the_step_rather_than_linking_nowhere(app_ctx):
    """The workflows blueprint can be pulled out from under us by the plugin machinery."""
    module, _, _, app = app_ctx
    app.url_map._rules_by_endpoint.pop("workflows.workflows_page", None)
    for rule in [rule for rule in app.url_map.iter_rules() if rule.endpoint == "workflows.workflows_page"]:
        app.url_map._rules.remove(rule)

    assert "workflow" not in {step["id"] for step in _get(module, app)["steps"]}


def test_a_corrupt_stored_blob_does_not_break_the_page(app_ctx):
    module, client, _, app = app_ctx
    client.get_user_preferences.return_value = {"acked_hints": "not-a-list"}

    assert _get(module, app)["acked_hints"] == []


# --------------------------------------------------------------------------------------
# PATCH
# --------------------------------------------------------------------------------------
def test_dismissing_stamps_the_blob_for_the_current_user_only(app_ctx):
    module, client, _, app = app_ctx

    payload, status = _patch(module, app, {"dismissed": True})

    assert status == 200 and payload["saved"] is True
    username, key, blob = client.update_user_preferences.call_args.args
    assert username == "alice"  # never read from the request body
    assert key == "onboarding"
    assert blob["dismissed_at"]


def test_an_unknown_hint_is_rejected(app_ctx):
    """The blob is compared against catalog ids later; an unchecked value lets a crafted
    request grow it without bound."""
    module, client, _, app = app_ctx

    payload, status = _patch(module, app, {"ack_hint": "../../etc/passwd"})

    assert status == 400
    client.update_user_preferences.assert_not_called()


def test_a_known_hint_is_stored_once(app_ctx):
    module, client, _, app = app_ctx
    client.get_user_preferences.return_value = {"acked_hints": ["home"]}

    payload, _status = _patch(module, app, {"ack_hint": "reports"})
    assert payload["state"]["acked_hints"] == ["home", "reports"]

    client.update_user_preferences.reset_mock()
    payload, _status = _patch(module, app, {"ack_hint": "home"})
    assert payload["saved"] is False
    client.update_user_preferences.assert_not_called()


def test_a_read_only_database_is_told_about_rather_than_faked(app_ctx):
    module, client, data, app = app_ctx
    data["READONLY_MODE"] = True

    payload, status = _patch(module, app, {"dismissed": True})

    assert status == 200
    assert payload["saved"] is False
    client.update_user_preferences.assert_not_called()


def test_a_failed_save_is_reported_as_a_failure(app_ctx):
    module, client, _, app = app_ctx
    from app.api_client import ApiClientError

    client.update_user_preferences.side_effect = ApiClientError("nope")

    _payload, status = _patch(module, app, {"opened": True})

    assert status == 502
