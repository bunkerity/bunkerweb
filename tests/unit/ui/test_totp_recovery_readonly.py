"""A recovery code must be spent, unless the database itself cannot spend anything.

`/totp` accepts a recovery code as the second factor and then asks the API to consume it. The
refusal has three shapes and only one of them may leave the code valid:

* the API answers **409** — the database is read-only. Refusing here would lock every 2FA user out
  of a read-only deployment, so the code is accepted and stays valid, with a warning saying so.
* the API is unreachable or answers 5xx (`ApiUnavailableError`). That is **not** a read-only
  database, and treating it as one hands every captured recovery code a window that lasts as long
  as the outage — recovery codes have no counter and no expiry, so such a code stays valid forever.
* any other 4xx: refused.

The trap this pins is that the UI cannot use `API_CLIENT.readonly` to make the distinction:
`BaseApiClient.readonly` answers **True whenever its own probe fails**, so an outage reads exactly
like a read-only database. The verdict has to come from the failed call itself.

Route module loaded with its container-only dependencies stubbed, following `test_totp_enrolment.py`.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "totp.py"


class ApiClientError(Exception):
    """Stands in for `app.api_client.ApiClientError` — a 4xx, carrying its status."""

    def __init__(self, message="boom", status_code=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ApiUnavailableError(Exception):
    """Stands in for `app.api_client.ApiUnavailableError` — unreachable, or a 5xx."""

    def __init__(self, message="API unavailable"):
        super().__init__(message)
        self.message = message


def _stub(name, **attributes):
    module = ModuleType(name)
    module.__path__ = []
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


class _ForbiddenReadonly:
    """`API_CLIENT.readonly` is a defect on this path: reading it fails the test loudly."""

    def __get__(self, instance, owner=None):
        raise AssertionError("the recovery-code path must not consult the client's readonly probe")


class FakeApiClient:
    readonly = _ForbiddenReadonly()

    def __init__(self):
        self.raises = None
        self.calls = []

    def use_recovery_code(self, username, code):
        self.calls.append((username, code))
        if self.raises:
            raise self.raises
        return {"status": "success"}


@pytest.fixture(scope="module")
def route_module():
    client = FakeApiClient()
    stubs = {
        "app.api_client": _stub("app.api_client", ApiClientError=ApiClientError, ApiUnavailableError=ApiUnavailableError),
        "app.dependencies": _stub("app.dependencies", API_CLIENT=client, DATA={}, BW_CONFIG=Mock(), BW_INSTANCES_UTILS=Mock(), LOGGER=Mock()),
        "app.models.totp": _stub("app.models.totp", totp=Mock()),
        # `app.routes.utils` draws QR codes and parses user agents at import time; neither package
        # is in the unit-test venv and neither is reached here.
        "user_agents": _stub("user_agents", parse=Mock()),
        "qrcode": _stub("qrcode", make=Mock()),
        "qrcode.main": _stub("qrcode.main", QRCode=Mock()),
        "qrcode.image": _stub("qrcode.image"),
        "qrcode.image.pil": _stub("qrcode.image.pil", PilImage=Mock()),
        "app.models.webauthn": _stub(
            "app.models.webauthn",
            webauthn=Mock(),
            WebauthnCeremonyError=type("WebauthnCeremonyError", (Exception,), {}),
            WebauthnDisabledError=type("WebauthnDisabledError", (Exception,), {}),
        ),
    }
    module_name = "app.routes._totp_recovery_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {**stubs, module_name: module}):
        spec.loader.exec_module(module)
        yield module, client


@pytest.fixture
def totp_route(route_module, monkeypatch):
    module, client = route_module
    client.raises = None
    client.calls.clear()

    flashed, errors, logger = [], [], Mock()
    monkeypatch.setattr(module, "API_CLIENT", client)
    monkeypatch.setattr(module, "LOGGER", logger)
    monkeypatch.setattr(module, "flash", lambda message, *args, **kwargs: flashed.append((message, args)))
    monkeypatch.setattr(module, "handle_error", lambda message, *args, **kwargs: errors.append(message) or "ERROR")
    monkeypatch.setattr(module, "verify_data_in_form", lambda **kwargs: None)
    monkeypatch.setattr(module, "redirect", lambda target: "REDIRECT")
    monkeypatch.setattr(module, "url_for", lambda endpoint, **kwargs: f"/{endpoint}")
    monkeypatch.setattr(module, "session", {})
    monkeypatch.setattr(
        module,
        "current_user",
        SimpleNamespace(get_id=lambda: "alice", totp_secret="SECRET", list_recovery_codes=["r1", "r2"], webauthn_credentials_count=0),
    )
    # The TOTP code is wrong, the recovery code is right: the branch under test.
    monkeypatch.setattr(
        module,
        "TOTP",
        SimpleNamespace(verify_totp=lambda token, **kwargs: False, verify_recovery_code=lambda token, user=None: "hashed-r1"),
    )

    app = Flask(__name__)
    app.secret_key = "test"

    def post():
        with app.test_request_context("/totp", method="POST", data={"totp_token": "123456"}):
            return module.totp_page.__wrapped__()

    return SimpleNamespace(post=post, client=client, flashed=flashed, errors=errors, logger=logger, session=module.session)


def test_a_valid_recovery_code_is_consumed_and_the_login_proceeds(totp_route):
    assert totp_route.post() == "REDIRECT"
    assert totp_route.client.calls == [("alice", "hashed-r1")]
    assert totp_route.errors == []
    assert "recovery codes" in totp_route.flashed[0][0]


def test_a_read_only_database_lets_the_code_through_and_says_it_stays_valid(totp_route):
    """409 is the database refusing every write. Refusing the login instead would lock out every
    2FA user for as long as the deployment is read-only."""
    totp_route.client.raises = ApiClientError("read-only", status_code=409)

    assert totp_route.post() == "REDIRECT"
    assert totp_route.errors == []
    assert totp_route.logger.warning.called
    assert "stays valid" in totp_route.flashed[0][0]


def test_an_unreachable_api_refuses_instead_of_leaving_the_code_valid(totp_route):
    """The hole this test exists for: an outage must not be read as a read-only database.

    A recovery code has no counter and no expiry, so accepting one unconsumed here leaves it usable
    forever — strictly worse than the TOTP equivalent."""
    totp_route.client.raises = ApiUnavailableError("api down")

    assert totp_route.post() == "ERROR"
    assert totp_route.errors == ["An error occurred while using the recovery code."]
    assert totp_route.logger.warning.called is False


def test_any_other_4xx_refuses_too(totp_route):
    totp_route.client.raises = ApiClientError("bad request", status_code=400)

    assert totp_route.post() == "ERROR"
    assert totp_route.errors == ["An error occurred while using the recovery code."]


def test_a_wrong_code_never_reaches_the_api(totp_route, monkeypatch):
    module = sys.modules["app.routes._totp_recovery_test"]
    monkeypatch.setattr(module, "TOTP", SimpleNamespace(verify_totp=lambda token, **kwargs: False, verify_recovery_code=lambda token, user=None: None))

    assert totp_route.post() == "ERROR"
    assert totp_route.errors == ["The token is invalid."]
    assert totp_route.client.calls == []
