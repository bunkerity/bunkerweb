"""`/support/config` and `/support/logs` (H16).

Both were `@login_required` only: a reader downloaded every setting -- `API_TOKEN`, the PRO
license key and every other `type: password` value included -- and every log file. They now need
the `write` permission (the same `list_permissions` gate every write route uses, no new role), and
the configuration export carries no secret value even for a user who may download it: the bundle
is meant to be attached to a support request.

Same loader idiom as `test_instances_write_permission.py`.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "support.py"

SETTINGS = {
    "SERVER_NAME": {"type": "text"},
    "API_TOKEN": {"type": "password"},
    "PRO_LICENSE_KEY": {"type": "password"},
    "AUTH_BASIC_PASSWORD": {"type": "password", "multiple": "auth-basic-credentials"},
    "LOG_LEVEL": {"type": "select"},
}
CONFIG = {
    "SERVER_NAME": {"value": "www.example.com", "method": "ui"},
    "API_TOKEN": {"value": "tok-secret", "method": "ui"},
    "PRO_LICENSE_KEY": {"value": "", "method": "default"},
    "LOG_LEVEL": {"value": "notice", "method": "default"},
    "www.example.com_AUTH_BASIC_PASSWORD_1": {"value": "basic-secret", "method": "ui"},
}


@pytest.fixture
def client():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.BW_CONFIG.get_plugins_settings.return_value = SETTINGS
    dependencies.BW_CONFIG.get_config.side_effect = lambda **kwargs: (
        {"SERVER_NAME": "www.example.com"} if not kwargs.get("methods") else json.loads(json.dumps(CONFIG))
    )
    dependencies.API_CLIENT.get_service.return_value = {"AUTH_BASIC_PASSWORD_1": {"value": "basic-secret"}, "USE_AUTH_BASIC": {"value": "yes"}}

    module_name = "app.routes._support_downloads_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, module_name: module}):
        spec.loader.exec_module(module)
    # N-H2-adjacent: the write-permission refusal now renders the designed 403 page
    # (app.models.biscuit.render_error_page -> unauthorized.html) instead of a bare text body.
    # Same stub idiom as test_mfa_pending_access.py -- the template/url_for machinery it needs is
    # irrelevant here, only the status code and that no secret leaks through it.
    module.render_error_page = lambda code, message=None: (message or "", code)

    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test
    for rule, view in (("/support/config", module.support_config), ("/support/logs", module.support_logs)):
        app.add_url_rule(rule, view_func=view.__wrapped__)
    app.module = module
    return app.test_client()


def _as(client, permissions):
    return patch.object(client.application.module, "current_user", SimpleNamespace(list_permissions=set(permissions)), create=True)


@pytest.mark.parametrize("path", ["/support/config", "/support/config?service=www.example.com", "/support/logs"])
def test_reader_cannot_download(client, path):
    with _as(client, ["read"]):
        response = client.get(path)
    assert response.status_code == 403


@pytest.mark.parametrize("path", ["/support/config", "/support/logs"])
def test_reader_refusal_uses_the_designed_error_page_not_a_bare_body(client, path):
    """A reader hitting these two routes directly (no disabled-button client-side gate in the
    way) used to get a bare ``"You do not have the write permission", 403`` text response instead
    of the same ``unauthorized.html`` page every other permission refusal renders. Proven by
    asserting the route calls through ``render_error_page`` rather than building its own tuple."""
    sentinel = ("rendered-unauthorized-page", 403)
    render_error_page = Mock(return_value=sentinel)
    with patch.object(client.application.module, "render_error_page", render_error_page), _as(client, ["read"]):
        response = client.get(path)

    render_error_page.assert_called_once_with(403, "You do not have the write permission")
    assert response.status_code == 403
    assert response.get_data(as_text=True) == "rendered-unauthorized-page"


@pytest.mark.parametrize("path", ["/support/config", "/support/logs"])
def test_the_refusal_detail_is_translated(client, path):
    """QA-UI-6 LOW: the 403 detail stayed English on a French page."""
    from app.i18n import init_i18n  # type: ignore

    client.application.root_path = str(ROUTE_PATH.parents[2])  # src/ui: where translations/ lives
    init_i18n(client.application)
    with client.session_transaction() as flask_session:
        flask_session["language"] = "fr"
    with _as(client, ["read"]):
        response = client.get(path)

    french = json.loads((ROUTE_PATH.parents[1] / "static" / "locales" / "fr.json").read_text(encoding="utf-8"))["flash"]["do_not_have_write_permission"]
    assert response.status_code == 403
    assert response.get_data(as_text=True) == french


def test_config_export_redacts_every_secret(client):
    with _as(client, ["read", "write"]):
        response = client.get("/support/config")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "tok-secret" not in body and "basic-secret" not in body
    exported = json.loads(body)
    assert exported["API_TOKEN"]["value"] == "[REDACTED]"
    assert exported["www.example.com_AUTH_BASIC_PASSWORD_1"]["value"] == "[REDACTED]"
    # An unset secret stays visibly unset, and a non-secret is untouched.
    assert exported["PRO_LICENSE_KEY"]["value"] == ""
    assert exported["LOG_LEVEL"]["value"] == "notice"


def test_service_export_redacts_every_secret(client):
    with _as(client, ["read", "write"]):
        response = client.get("/support/config?service=www.example.com")
    assert response.status_code == 200
    exported = json.loads(response.get_data(as_text=True))
    assert exported["AUTH_BASIC_PASSWORD_1"]["value"] == "[REDACTED]"
    assert exported["USE_AUTH_BASIC"]["value"] == "yes"
