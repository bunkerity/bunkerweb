"""`/profile/edit`: emptying the e-mail field clears the stored address (QA-UI M16).

The route only took the field into account when it was non-empty, so a cleared field kept the old
address and still flashed "The profile has been successfully updated.". The users API skips a
`None` field on PATCH, so the clear is sent as "".

Loader: `test_totp_enrolment.py`'s (every container-only import stubbed).
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "profile.py"


def _stub(name, **attributes):
    module = ModuleType(name)
    module.__path__ = []
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


@pytest.fixture(scope="module")
def route_module():
    client = Mock()
    stubs = {
        "app.dependencies": _stub("app.dependencies", API_CLIENT=client, DATA={}, BW_CONFIG=Mock(), BW_INSTANCES_UTILS=Mock(), LOGGER=Mock()),
        "user_agents": _stub("user_agents", parse=Mock()),
        "qrcode": _stub("qrcode", make=Mock()),
        "qrcode.main": _stub("qrcode.main", QRCode=Mock()),
        "qrcode.image": _stub("qrcode.image"),
        "qrcode.image.pil": _stub("qrcode.image.pil", PilImage=Mock()),
        "app.models.totp": _stub("app.models.totp", totp=Mock()),
        "app.models.webauthn": _stub(
            "app.models.webauthn",
            webauthn=Mock(),
            WebauthnCeremonyError=type("WebauthnCeremonyError", (Exception,), {}),
            WebauthnDisabledError=type("WebauthnDisabledError", (Exception,), {}),
        ),
    }
    module_name = "app.routes._profile_email_clear_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {**stubs, module_name: module}):
        spec.loader.exec_module(module)
        yield module, client


@pytest.fixture
def edit(route_module, monkeypatch):
    module, client = route_module
    client.reset_mock(return_value=True, side_effect=True)
    client.readonly = False
    flashed = []
    monkeypatch.setattr(module, "flash", lambda message, category="success", *args, **kwargs: flashed.append((message, category)))
    monkeypatch.setattr(
        module,
        "current_user",
        SimpleNamespace(
            username="alice",
            get_id=lambda: "alice",
            email="alice@example.com",
            totp_secret=None,
            method="ui",
            theme="light",
            language="en",
            check_password=lambda password: password == "right",
        ),
    )
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.profile)

    def _edit(email):
        form = {"username": "alice", "email": email, "password": "right"}
        with app.test_request_context("/profile/edit", method="POST", data=form):
            module.edit_profile.__wrapped__()
        return client, flashed

    return _edit


def test_an_emptied_email_is_sent_as_a_clear(edit):
    client, flashed = edit("")

    assert client.update_user.called, f"nothing was saved: {flashed}"
    assert client.update_user.call_args.kwargs["email"] == ""
    assert ("The profile has been successfully updated.", "success") in flashed


def test_a_new_email_is_still_saved(edit):
    client, _ = edit("new@example.com")
    assert client.update_user.call_args.kwargs["email"] == "new@example.com"


def test_an_unchanged_profile_is_still_refused(edit):
    client, _ = edit("alice@example.com")
    assert not client.update_user.called
