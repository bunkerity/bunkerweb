"""FastAPI /users WebAuthn credential endpoints, plus the TOTP-clearing contract.

There is no live TestClient in tests/unit/api; the router module is loaded with its imports
stubbed and its handler functions are called directly against a Mock db (see
test_api_web_cache.py for the canonical shape of this loader).
"""

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
DT = datetime(2024, 1, 1, tzinfo=timezone.utc)


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = patch = delete = put = get


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


_DB = Mock()


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_users": ModuleType("bw_users"),
        "bw_users.routers": ModuleType("bw_users.routers"),
        "bw_users.auth": ModuleType("bw_users.auth"),
        "bw_users.auth.guard": ModuleType("bw_users.auth.guard"),
        "bw_users.utils": ModuleType("bw_users.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_users"].__path__ = []
    names["bw_users.routers"].__path__ = []
    names["bw_users.auth"].__path__ = []
    names["bw_users.auth.guard"].guard = object()
    names["bw_users.utils"].get_db = lambda: _DB

    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "users.py"
        spec = importlib.util.spec_from_file_location("bw_users.routers.users", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture(autouse=True)
def db():
    _DB.reset_mock(return_value=True, side_effect=True)
    return _DB


def _credential(**overrides):
    credential = {
        "username": "alice",
        "credential_id": "cred-1",
        "user_handle": "HANDLE",
        "public_key": "PUBKEY",
        "sign_count": 3,
        "transports": ["internal"],
        "device_type": "multi_device",
        "backed_up": True,
        "name": "Phone",
        "creation_date": DT,
        "last_used": None,
    }
    credential.update(overrides)
    return credential


class TestList:
    def test_returns_serialized_credentials(self, db):
        db.get_ui_user_webauthn_credentials.return_value = [_credential()]

        response = ROUTER.get_user_webauthn_credentials("alice")

        assert response.status_code == 200
        credential = response.content["credentials"][0]
        assert credential["credential_id"] == "cred-1"
        # datetimes must be JSON-safe on the way out
        assert credential["creation_date"] == DT.isoformat()
        assert credential["last_used"] is None

    def test_empty(self, db):
        db.get_ui_user_webauthn_credentials.return_value = []
        assert ROUTER.get_user_webauthn_credentials("alice").content["credentials"] == []


class TestCreate:
    @staticmethod
    def _request(**overrides):
        payload = {"credential_id": "cred-1", "user_handle": "HANDLE", "public_key": "PUBKEY", "name": "Phone"}
        payload.update(overrides)
        return ROUTER.CreateWebauthnCredentialRequest(**payload)

    def test_created(self, db):
        db.create_ui_user_webauthn_credential.return_value = ""

        response = ROUTER.create_user_webauthn_credential("alice", self._request(transports=["usb"], sign_count=1))

        assert response.status_code == 201
        assert db.create_ui_user_webauthn_credential.call_args.args == ("alice",)
        assert db.create_ui_user_webauthn_credential.call_args.kwargs["transports"] == ["usb"]

    def test_duplicate_is_a_conflict(self, db):
        db.create_ui_user_webauthn_credential.return_value = "This credential already exists"
        assert ROUTER.create_user_webauthn_credential("alice", self._request()).status_code == 409

    def test_unknown_user_is_a_404(self, db):
        db.create_ui_user_webauthn_credential.return_value = "User ghost doesn't exist"
        assert ROUTER.create_user_webauthn_credential("ghost", self._request()).status_code == 404

    def test_readonly_is_a_conflict(self, db):
        db.create_ui_user_webauthn_credential.return_value = "The database is read-only, the changes will not be saved"
        assert ROUTER.create_user_webauthn_credential("alice", self._request()).status_code == 409


class TestResolve:
    def test_returns_the_owner(self, db):
        db.get_ui_user_webauthn_credential.return_value = _credential()
        response = ROUTER.resolve_webauthn_credential("cred-1")
        assert response.status_code == 200
        assert response.content["credential"]["username"] == "alice"

    def test_unknown_credential_is_a_404(self, db):
        db.get_ui_user_webauthn_credential.return_value = None
        assert ROUTER.resolve_webauthn_credential("nope").status_code == 404


class TestUpdate:
    def test_updates_sign_count(self, db):
        db.get_ui_user_webauthn_credential.return_value = _credential()
        db.update_ui_user_webauthn_credential.return_value = ""

        request = ROUTER.UpdateWebauthnCredentialRequest(sign_count=9, last_used=DT)
        response = ROUTER.update_user_webauthn_credential("alice", "cred-1", request)

        assert response.status_code == 200
        assert db.update_ui_user_webauthn_credential.call_args.kwargs["sign_count"] == 9

    def test_another_users_credential_is_a_404(self, db):
        """The path username must own the credential; otherwise this would be a cross-account write."""
        db.get_ui_user_webauthn_credential.return_value = _credential(username="bob")

        response = ROUTER.update_user_webauthn_credential("alice", "cred-1", ROUTER.UpdateWebauthnCredentialRequest(name="Mine now"))

        assert response.status_code == 404
        db.update_ui_user_webauthn_credential.assert_not_called()

    def test_unknown_credential_is_a_404(self, db):
        db.get_ui_user_webauthn_credential.return_value = None
        assert ROUTER.update_user_webauthn_credential("alice", "nope", ROUTER.UpdateWebauthnCredentialRequest(name="x")).status_code == 404


class TestDelete:
    def test_deleted(self, db):
        db.delete_ui_user_webauthn_credential.return_value = ""
        response = ROUTER.delete_user_webauthn_credential("alice", "cred-1")
        assert response.status_code == 200
        assert db.delete_ui_user_webauthn_credential.call_args.args == ("alice", "cred-1")

    def test_missing_is_a_404(self, db):
        db.delete_ui_user_webauthn_credential.return_value = "Credential not found"
        assert ROUTER.delete_user_webauthn_credential("alice", "nope").status_code == 404


class TestTotpSecretClearing:
    """Regression: an explicit null must clear the secret, an absent field must not.

    Before the fix, `totp_secret=None` was read as "not provided", so disabling 2FA left the
    secret in place and the UI bounced the user back to /totp forever.
    """

    @staticmethod
    def _stored_user():
        return {"password": b"hash", "totp_secret": "STORED", "theme": "light", "email": "a@b.c", "method": "manual", "language": "en"}

    def test_explicit_null_clears_the_secret(self, db):
        db.get_ui_user.return_value = self._stored_user()
        db.update_ui_user.return_value = ""

        request = ROUTER.UpdateUserRequest.model_validate({"totp_secret": None, "theme": "light"})
        ROUTER.update_user("alice", request)

        assert db.update_ui_user.call_args.kwargs["totp_secret"] is None

    def test_absent_field_keeps_the_secret(self, db):
        db.get_ui_user.return_value = self._stored_user()
        db.update_ui_user.return_value = ""

        request = ROUTER.UpdateUserRequest.model_validate({"theme": "dark"})
        ROUTER.update_user("alice", request)

        assert db.update_ui_user.call_args.kwargs["totp_secret"] == "STORED"

    def test_new_secret_is_written(self, db):
        db.get_ui_user.return_value = self._stored_user()
        db.update_ui_user.return_value = ""

        request = ROUTER.UpdateUserRequest.model_validate({"totp_secret": "NEW"})
        ROUTER.update_user("alice", request)

        assert db.update_ui_user.call_args.kwargs["totp_secret"] == "NEW"
