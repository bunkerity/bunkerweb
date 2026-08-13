"""End-to-end HTTP flow for the passkey routes, driven through a real Flask test client.

Complements test_webauthn.py, which exercises the ceremonies directly. What is proved here is
the wiring the ceremony tests can't see: blueprints registered, `@cors_required` enforced, the
challenge surviving from the options request to the verify request in the server-side session,
the session flags the 2FA gate reads, and the fact that a failure never tells the caller whether
an account exists.

The route modules are loaded with `app.dependencies` stubbed, the pattern established by
test_home_dashboard.py.
"""

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask, session
from flask_login import AnonymousUserMixin, LoginManager, UserMixin, login_user

from test_webauthn import RP_ID, ORIGIN, SoftwareAuthenticator, b64url  # noqa: E402

UI_ROOT = Path(__file__).resolve().parents[3] / "src" / "ui"
DT = datetime(2024, 1, 1, tzinfo=timezone.utc)

AJAX = {"X-Requested-With": "XMLHttpRequest"}


class _User(UserMixin):
    """Minimal stand-in for UiUsers — only what the passkey routes actually read."""

    def __init__(self, username="alice", *, totp_secret=None, credentials=0, password_ok=True):
        self.username = username
        self.totp_secret = totp_secret
        self.webauthn_credentials_count = credentials
        self.list_recovery_codes = []
        self._password_ok = password_ok

    def get_id(self):
        return self.username

    def check_password(self, password):
        return self._password_ok and password == "correct-horse"


def _load(module_file, api_client):
    """Load one route module with its dependencies stubbed out."""
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = api_client
    dependencies.DATA = {}
    dependencies.BW_CONFIG = None
    dependencies.BW_INSTANCES_UTILS = None

    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode_image = ModuleType("qrcode.image")
    qrcode_pil = ModuleType("qrcode.image.pil")
    qrcode_pil.PilImage = Mock()

    # app.models.totp is stubbed wholesale rather than imported: it needs passlib (absent from
    # the pared-down unit venv) and, at import time, reads the TOTP encryption keys off disk and
    # calls stop(1) when they are missing. None of the passkey routes touch TOTP verification.
    totp_module = ModuleType("app.models.totp")
    totp_module.totp = Mock()

    # Two more transitive imports absent from the pared-down unit venv and untouched by the
    # passkey paths: user_agents (profile's session list) and biscuit_auth (login's RBAC token,
    # which login.py already degrades gracefully when the private key file is missing).
    user_agents = ModuleType("user_agents")
    user_agents.parse = Mock()
    biscuit_module = ModuleType("app.models.biscuit")
    biscuit_module.BiscuitTokenFactory = Mock()
    biscuit_module.PrivateKey = Mock()

    module_name = f"app.routes._{module_file}_webauthn_test"
    spec = importlib.util.spec_from_file_location(module_name, UI_ROOT / "app" / "routes" / f"{module_file}.py")
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "app.dependencies": dependencies,
        "app.models.totp": totp_module,
        "app.models.biscuit": biscuit_module,
        "user_agents": user_agents,
        "qrcode": qrcode,
        "qrcode.main": qrcode_main,
        "qrcode.image": qrcode_image,
        "qrcode.image.pil": qrcode_pil,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


@pytest.fixture
def api():
    client = Mock()
    client.readonly = False
    return client


class _AnonymousUser(AnonymousUserMixin):
    """Mirrors app.models.models.AnonymousUser — the real app wires this into Flask-Login."""

    totp_secret = None
    webauthn_credentials_count = 0


def _make_app(module, blueprint_name, user=None):
    app = Flask(__name__)
    app.secret_key = "test"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["WEBAUTHN_RP_ID"] = RP_ID
    app.config["WEBAUTHN_RP_NAME"] = "BunkerWeb UI"
    app.config["WEBAUTHN_ORIGINS"] = [ORIGIN]
    # Session-ID rotation comes from Flask-Session in the real app; the default cookie interface
    # has no regenerate(). A no-op stands in for it — the rotation itself is not what these
    # tests cover, and the password login path has always relied on the same call.
    app.session_interface.regenerate = lambda _session: None
    app.register_blueprint(getattr(module, blueprint_name))

    login_manager = LoginManager()
    login_manager.anonymous_user = _AnonymousUser
    login_manager.init_app(app)
    login_manager.user_loader(lambda _username: user)

    # Endpoints the routes redirect to but that live in other blueprints. Skip any the
    # blueprint under test already provides, or Flask refuses the duplicate.
    for rule, endpoint in (
        ("/loading", "loading"),
        ("/home", "home.home_page"),
        ("/setup", "setup.setup_page"),
        ("/logout", "logout.logout_page"),
        ("/profile", "profile.profile_page"),
        ("/totp", "totp.totp_page"),
    ):
        if endpoint not in app.view_functions:
            app.add_url_rule(rule, endpoint, lambda: endpoint)

    if user is not None:
        # Sign the fixture user in so @login_required routes are reachable.
        @app.route("/_sign_in")
        def _sign_in():
            login_user(user)
            return "ok"

    return app


def _stored_credential(authenticator, verified, *, username="alice", user_handle=None):
    return {
        "username": username,
        "credential_id": verified["credential_id"],
        "user_handle": user_handle or b64url(b"the-user-handle"),
        "public_key": verified["public_key"],
        "sign_count": verified["sign_count"],
        "transports": ["internal"],
        "device_type": verified["device_type"],
        "backed_up": verified["backed_up"],
        "name": "Phone",
        "creation_date": DT.isoformat(),
        "last_used": None,
    }


def _enroll(profile_module, api, client, authenticator):
    """Drive the real enrollment flow and return the credential row the UI sent to the API."""
    api.get_user_webauthn_credentials.return_value = []
    options = client.post("/profile/webauthn/register/options", json={"password": "correct-horse"}, headers=AJAX)
    assert options.status_code == 200

    credential = authenticator.register(json.loads(options.data))
    verify = client.post("/profile/webauthn/register/verify", json={"credential": credential, "name": "Phone"}, headers=AJAX)
    assert verify.status_code == 200, verify.data

    sent = api.create_user_webauthn_credential.call_args.kwargs
    return sent


# ── Enrollment ──────────────────────────────────────────────────────


class TestProfileEnrollment:
    @pytest.fixture
    def setup(self, api):
        module = _load("profile", api)
        user = _User(credentials=0)
        app = _make_app(module, "profile", user)
        client = app.test_client()
        client.get("/_sign_in")
        return module, api, client, user

    def test_full_enrollment_persists_a_credential(self, setup):
        module, api, client, _user = setup
        sent = _enroll(module, api, client, SoftwareAuthenticator())

        assert sent["name"] == "Phone"
        assert sent["user_handle"]
        assert sent["public_key"]
        assert sent["transports"] == ["internal"]
        assert api.create_user_webauthn_credential.call_args.args == ("alice",)

    def test_enrollment_marks_strong_auth_complete(self, setup):
        """Enrolling from an authenticated session proves the same thing a second factor would."""
        module, api, client, _user = setup
        with client:
            _enroll(module, api, client, SoftwareAuthenticator())
            assert session["mfa_validated"] is True

    def test_wrong_password_is_refused_before_any_ceremony(self, setup):
        _module, api, client, _user = setup
        api.get_user_webauthn_credentials.return_value = []

        response = client.post("/profile/webauthn/register/options", json={"password": "wrong"}, headers=AJAX)

        assert response.status_code == 403
        api.create_user_webauthn_credential.assert_not_called()

    def test_missing_password_is_refused(self, setup):
        _module, _api, client, _user = setup
        assert client.post("/profile/webauthn/register/options", json={}, headers=AJAX).status_code == 403

    def test_verify_without_a_pending_registration_is_refused(self, setup):
        """The user handle is held server-side; without it there is nothing to attach a key to."""
        _module, _api, client, _user = setup
        response = client.post("/profile/webauthn/register/verify", json={"credential": {}, "name": "x"}, headers=AJAX)
        assert response.status_code == 400

    def test_readonly_database_blocks_enrollment(self, setup):
        _module, api, client, _user = setup
        api.readonly = True
        assert client.post("/profile/webauthn/register/options", json={"password": "correct-horse"}, headers=AJAX).status_code == 403

    def test_non_ajax_request_is_refused(self, setup):
        """@cors_required — a cross-site form post must not be able to drive a ceremony."""
        _module, _api, client, _user = setup
        assert client.post("/profile/webauthn/register/options", json={"password": "correct-horse"}).status_code == 403

    def test_delete_requires_the_password(self, setup):
        _module, api, client, _user = setup

        refused = client.post("/profile/webauthn/delete", data={"credential_id": "cred-1", "password": "wrong"})
        assert refused.status_code in (302, 303)
        api.delete_user_webauthn_credential.assert_not_called()

        client.post("/profile/webauthn/delete", data={"credential_id": "cred-1", "password": "correct-horse"})
        assert api.delete_user_webauthn_credential.call_args.args == ("alice", "cred-1")

    def test_rename(self, setup):
        _module, api, client, _user = setup
        client.post("/profile/webauthn/rename", data={"credential_id": "cred-1", "name": "Laptop"})
        assert api.update_user_webauthn_credential.call_args.kwargs["name"] == "Laptop"

    def test_rename_rejects_an_empty_name(self, setup):
        _module, api, client, _user = setup
        client.post("/profile/webauthn/rename", data={"credential_id": "cred-1", "name": "   "})
        api.update_user_webauthn_credential.assert_not_called()


# ── Passwordless login ──────────────────────────────────────────────


class TestPasswordlessLogin:
    @pytest.fixture
    def setup(self, api):
        api.get_admin_user.return_value = {"username": "alice"}
        module = _load("login", api)
        app = _make_app(module, "login", _User())
        return module, api, app.test_client()

    def _assertion(self, client, authenticator, stored, **kwargs):
        options = client.post("/login/webauthn/options", json={}, headers=AJAX)
        assert options.status_code == 200
        assertion = authenticator.authenticate(json.loads(options.data), user_handle=stored["user_handle"], **kwargs)
        return assertion

    def _prepare(self, api):
        """Enroll a credential out-of-band and wire the API mock to serve it."""
        authenticator = SoftwareAuthenticator()
        enrol_module = _load("profile", api)
        enrol_app = _make_app(enrol_module, "profile", _User())
        enrol_client = enrol_app.test_client()
        enrol_client.get("/_sign_in")
        sent = _enroll(enrol_module, api, enrol_client, authenticator)

        stored = _stored_credential(authenticator, sent, user_handle=sent["user_handle"])
        api.resolve_webauthn_credential.return_value = stored
        api.get_user_for_auth.return_value = {
            "username": "alice",
            "password": "$2b$13$abcdefghijklmnopqrstuv",
            "admin": True,
            "roles": ["admin"],
            "theme": "light",
            "language": "en",
            "totp_secret": None,
        }
        api.mark_user_login.return_value = 1
        return authenticator, stored

    def test_login_opens_a_session_with_no_username_and_no_password(self, setup):
        _module, api, client = setup
        authenticator, stored = self._prepare(api)

        with client:
            assertion = self._assertion(client, authenticator, stored)
            response = client.post("/login/webauthn/verify", json=assertion, headers=AJAX)

            assert response.status_code == 200
            assert "/loading" in response.get_json()["redirect"]
            # A verified assertion IS the strong authentication: no TOTP prompt follows.
            assert session["mfa_validated"] is True
            assert session["session_id"] == 1

    def test_options_request_carries_no_identifier(self, setup):
        """Nothing in the request or the response can be used to probe for accounts."""
        _module, _api, client = setup
        options = json.loads(client.post("/login/webauthn/options", json={}, headers=AJAX).data)
        assert not options.get("allowCredentials")
        assert options["userVerification"] == "required"

    def test_sign_count_is_persisted_only_after_a_successful_ceremony(self, setup):
        _module, api, client = setup
        authenticator, stored = self._prepare(api)

        assertion = self._assertion(client, authenticator, stored)
        client.post("/login/webauthn/verify", json=assertion, headers=AJAX)

        assert api.update_user_webauthn_credential.call_args.kwargs["sign_count"] == authenticator.sign_count

    def test_unknown_credential_is_a_generic_401(self, setup):
        module, api, client = setup
        authenticator, stored = self._prepare(api)
        assertion = self._assertion(client, authenticator, stored)
        api.resolve_webauthn_credential.return_value = None

        response = client.post("/login/webauthn/verify", json=assertion, headers=AJAX)

        assert response.status_code == 401
        assert response.get_json()["message"] == module.GENERIC_PASSKEY_ERROR

    def test_tampered_signature_is_the_same_generic_401(self, setup):
        """Byte-identical to the unknown-credential response — nothing leaks either way."""
        module, api, client = setup
        authenticator, stored = self._prepare(api)

        assertion = self._assertion(client, authenticator, stored, tamper=True)
        response = client.post("/login/webauthn/verify", json=assertion, headers=AJAX)

        assert response.status_code == 401
        assert response.get_json()["message"] == module.GENERIC_PASSKEY_ERROR

    def test_user_handle_mismatch_rejected(self, setup):
        _module, api, client = setup
        authenticator, stored = self._prepare(api)

        options = client.post("/login/webauthn/options", json={}, headers=AJAX)
        assertion = authenticator.authenticate(json.loads(options.data), user_handle=b64url(b"someone-else-entirely"))

        response = client.post("/login/webauthn/verify", json=assertion, headers=AJAX)
        assert response.status_code == 401

    def test_replayed_assertion_rejected(self, setup):
        """The challenge is consumed on first use, so a captured assertion is worthless."""
        _module, api, client = setup
        authenticator, stored = self._prepare(api)

        with client:
            assertion = self._assertion(client, authenticator, stored)
            assert client.post("/login/webauthn/verify", json=assertion, headers=AJAX).status_code == 200
            assert client.post("/login/webauthn/verify", json=assertion, headers=AJAX).status_code == 400

    def test_next_is_sanitised(self, setup):
        """An attacker-supplied redirect must not leave the UI."""
        _module, api, client = setup
        authenticator, stored = self._prepare(api)

        assertion = self._assertion(client, authenticator, stored)
        assertion["next"] = "https://evil.example.com/"
        response = client.post("/login/webauthn/verify", json=assertion, headers=AJAX)

        assert "evil.example.com" not in response.get_json()["redirect"]

    def test_non_ajax_request_is_refused(self, setup):
        _module, _api, client = setup
        assert client.post("/login/webauthn/options", json={}).status_code == 403

    def test_login_page_advertises_passkeys_when_configured(self, setup):
        """The template only renders the passkey button when the server says it is available."""
        module, _api, client = setup
        captured = {}

        def fake_render_template(template_name, **context):
            captured["template"] = template_name
            captured.update(context)
            return "rendered"

        module.render_template = fake_render_template
        assert client.get("/login").status_code == 200
        assert captured["template"] == "login.html"
        assert captured["webauthn_enabled"] is True


class TestPasswordlessDisabled:
    def test_routes_are_404_without_a_relying_party(self, api):
        api.get_admin_user.return_value = {"username": "alice"}
        module = _load("login", api)
        app = _make_app(module, "login", _User())
        app.config["WEBAUTHN_RP_ID"] = None
        app.config["WEBAUTHN_ORIGINS"] = []
        client = app.test_client()

        assert client.post("/login/webauthn/options", json={}, headers=AJAX).status_code == 404
        assert client.post("/login/webauthn/verify", json={}, headers=AJAX).status_code == 404


# ── Security key as a second factor ─────────────────────────────────


class TestSecurityKeySecondFactor:
    @pytest.fixture
    def setup(self, api):
        module = _load("totp", api)
        user = _User(totp_secret="SECRET", credentials=1)
        app = _make_app(module, "totp", user)
        client = app.test_client()
        client.get("/_sign_in")
        return module, api, client

    def _prepare(self, api):
        authenticator = SoftwareAuthenticator()
        enrol_module = _load("profile", api)
        enrol_app = _make_app(enrol_module, "profile", _User())
        enrol_client = enrol_app.test_client()
        enrol_client.get("/_sign_in")
        sent = _enroll(enrol_module, api, enrol_client, authenticator)

        stored = _stored_credential(authenticator, sent, user_handle=sent["user_handle"])
        api.get_user_webauthn_credentials.return_value = [stored]
        return authenticator, stored

    def test_security_key_completes_two_factor(self, setup):
        _module, api, client = setup
        authenticator, _stored = self._prepare(api)

        with client:
            options = client.post("/totp/webauthn/options", json={}, headers=AJAX)
            assert options.status_code == 200
            assertion = authenticator.authenticate(json.loads(options.data))

            response = client.post("/totp/webauthn/verify", json=assertion, headers=AJAX)

            assert response.status_code == 200
            assert session["mfa_validated"] is True

    def test_options_are_scoped_to_the_users_own_credentials(self, setup):
        _module, api, client = setup
        _authenticator, stored = self._prepare(api)

        options = json.loads(client.post("/totp/webauthn/options", json={}, headers=AJAX).data)

        assert [c["id"] for c in options["allowCredentials"]] == [stored["credential_id"]]
        # Preferred, not required: an older non-discoverable key has to remain usable here.
        assert options["userVerification"] == "preferred"

    def test_someone_elses_credential_is_refused(self, setup):
        """The assertion must be checked against this user's credentials, not any credential."""
        _module, api, client = setup
        authenticator, _stored = self._prepare(api)

        options = client.post("/totp/webauthn/options", json={}, headers=AJAX)
        assertion = authenticator.authenticate(json.loads(options.data))
        api.get_user_webauthn_credentials.return_value = []  # not registered to this user

        response = client.post("/totp/webauthn/verify", json=assertion, headers=AJAX)
        assert response.status_code == 401

    def test_no_registered_key_is_a_404(self, setup):
        _module, api, client = setup
        api.get_user_webauthn_credentials.return_value = []
        assert client.post("/totp/webauthn/options", json={}, headers=AJAX).status_code == 404

    def test_already_validated_session_is_refused(self, setup):
        _module, api, client = setup
        self._prepare(api)
        with client:
            with client.session_transaction() as flask_session:
                flask_session["mfa_validated"] = True
            assert client.post("/totp/webauthn/options", json={}, headers=AJAX).status_code == 400

    def test_non_ajax_request_is_refused(self, setup):
        _module, api, client = setup
        self._prepare(api)
        assert client.post("/totp/webauthn/options", json={}).status_code == 403


class TestTotpPageForPasskeyOnlyUser:
    """A user whose only second factor is a security key must not loop between /totp and home."""

    def test_page_renders_instead_of_redirecting(self, api):
        module = _load("totp", api)
        user = _User(totp_secret=None, credentials=1)
        app = _make_app(module, "totp", user)
        client = app.test_client()
        client.get("/_sign_in")

        captured = {}

        def fake_render_template(template_name, **context):
            captured["template"] = template_name
            captured.update(context)
            return "rendered"

        module.render_template = fake_render_template
        response = client.get("/totp")

        assert response.status_code == 200
        assert captured["template"] == "totp.html"
        assert captured["is_totp"] is False
        assert captured["webauthn_enabled"] is True

    def test_user_without_any_second_factor_is_sent_home(self, api):
        module = _load("totp", api)
        app = _make_app(module, "totp", _User(totp_secret=None, credentials=0))
        client = app.test_client()
        client.get("/_sign_in")

        response = client.get("/totp")
        assert response.status_code in (302, 303)
        assert "/home" in response.headers["Location"]
