"""`/whats-new/state` and the silent-stamp rule behind the recap modal.

The rule is the whole feature: **a user with no stored version is stamped and shown nothing.**
Without it, the day this ships every existing account is met with a modal containing 90
releases. It is asserted from both directions here, because a green suite would otherwise be
perfectly happy with the version that dumps the entire history.

Route module is loaded with `app.dependencies` stubbed, same pattern as
``test_onboarding_routes.py``.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from app.models.changelog import Release

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "whats_new.py"


@pytest.fixture(scope="module")
def route_module():
    client, data = Mock(), {}
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.DATA = data
    dependencies.BW_CONFIG = Mock()
    dependencies.BW_INSTANCES_UTILS = Mock()
    dependencies.LOGGER = Mock()
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    module_name = "app.routes._whats_new_test"
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

    client.get_metadata.return_value = {"version": "1.7.0"}
    client.get_user_preferences.return_value = {}
    client.update_user_preferences.return_value = {"status": "success"}

    monkeypatch.setattr(module, "current_user", SimpleNamespace(get_id=lambda: "alice"))
    # A short, known history: the real file is covered by test_changelog.py.
    monkeypatch.setattr(module, "load", lambda: tuple(Release(version=v, date="", entries=()) for v in ("v1.7.0", "v1.6.14", "v1.6.13")))
    return module, client, data, app


def _patch(module, app, body=None):
    with app.test_request_context("/whats-new/state", method="PATCH", json=body or {}):
        response = module.update_whats_new_state.__wrapped__.__wrapped__()
        if isinstance(response, tuple):
            return response[0].get_json(), response[1]
        return response.get_json(), 200


# --------------------------------------------------------------------------------------
# The silent-stamp rule
# --------------------------------------------------------------------------------------
def test_a_user_with_no_stored_version_is_stamped_and_shown_nothing(app_ctx):
    """Shipping day: an existing account must not be handed the whole history."""
    module, client, _, app = app_ctx

    with app.test_request_context("/"):
        releases, stored = module.pending_releases("alice", "1.7.0")

    assert releases == ()
    assert stored == ""
    client.update_user_preferences.assert_called_once_with("alice", module.PREFERENCE_KEY, {"last_seen_version": "1.7.0"})


def test_a_stored_older_version_gets_exactly_the_interval(app_ctx):
    module, client, _, app = app_ctx
    client.get_user_preferences.return_value = {"last_seen_version": "1.6.13"}

    with app.test_request_context("/"):
        releases, stored = module.pending_releases("alice", "1.7.0")

    assert [release.version for release in releases] == ["v1.7.0", "v1.6.14"]
    assert stored == "1.6.13"
    client.update_user_preferences.assert_not_called(), "reading the recap is not what stamps it"


def test_a_caught_up_user_sees_nothing(app_ctx):
    module, client, _, app = app_ctx
    client.get_user_preferences.return_value = {"last_seen_version": "1.7.0"}

    with app.test_request_context("/"):
        releases, _ = module.pending_releases("alice", "1.7.0")

    assert releases == ()


def test_a_downgrade_shows_nothing(app_ctx):
    module, client, _, app = app_ctx
    client.get_user_preferences.return_value = {"last_seen_version": "1.7.0"}

    with app.test_request_context("/"):
        releases, _ = module.pending_releases("alice", "1.6.14")

    assert releases == ()


def test_a_read_only_database_is_not_written_to_on_the_silent_stamp(app_ctx):
    module, client, data, app = app_ctx
    data["READONLY_MODE"] = True

    with app.test_request_context("/"):
        releases, _ = module.pending_releases("alice", "1.7.0")

    assert releases == ()
    client.update_user_preferences.assert_not_called()


def test_an_unreachable_api_shows_nothing_rather_than_everything(app_ctx):
    """`get_user_preferences` failing must not read as "this user has seen nothing"."""
    module, client, _, app = app_ctx
    client.get_user_preferences.side_effect = RuntimeError("boom")

    with app.test_request_context("/"):
        try:
            releases, _ = module.pending_releases("alice", "1.7.0")
        except RuntimeError:
            pytest.fail("a failing preferences call must not take the page down with it")

    assert releases == ()


# --------------------------------------------------------------------------------------
# The stamp
# --------------------------------------------------------------------------------------
def test_closing_the_modal_stamps_the_running_version(app_ctx):
    module, client, _, app = app_ctx

    payload, status = _patch(module, app, {"version": "1.7.0"})

    assert status == 200
    assert payload["saved"] is True
    client.update_user_preferences.assert_called_once_with("alice", module.PREFERENCE_KEY, {"last_seen_version": "1.7.0"})


def test_the_version_is_taken_from_the_api_when_the_body_omits_it(app_ctx):
    module, client, _, app = app_ctx

    payload, status = _patch(module, app)

    assert status == 200
    assert payload["version"] == "1.7.0"


def test_a_read_only_database_says_so_instead_of_pretending(app_ctx):
    module, client, data, app = app_ctx
    data["READONLY_MODE"] = True

    payload, status = _patch(module, app, {"version": "1.7.0"})

    assert status == 200
    assert payload["saved"] is False
    client.update_user_preferences.assert_not_called()


def test_a_failed_write_is_reported_as_a_failure(app_ctx):
    module, client, _, app = app_ctx
    client.update_user_preferences.side_effect = RuntimeError("boom")

    payload, status = _patch(module, app, {"version": "1.7.0"})

    assert status == 502
    assert payload["status"] == "error"


def test_an_unknown_running_version_is_never_stamped(app_ctx):
    """Stamping "" would mark the user caught up with a version that does not exist, and the
    recap would then be skipped for good."""
    module, client, _, app = app_ctx
    client.get_metadata.return_value = {}

    payload, status = _patch(module, app)

    assert status == 503
    client.update_user_preferences.assert_not_called()
