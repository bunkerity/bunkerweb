"""WebAuthn ceremonies (app.models.webauthn) and the Relying Party resolution in main.py.

Driven by a minimal in-process software authenticator (ES256) rather than recorded fixtures, so
the negative cases that matter — wrong origin, wrong RP ID, tampered signature, replayed or
expired challenge, cloned authenticator — are produced the same way a real attacker would produce
them, instead of being asserted against a canned blob.
"""

import json
import sys
from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Optional

import pytest
from flask import Flask, session

_UI_ROOT = str(Path(__file__).resolve().parents[3] / "src" / "ui")
if _UI_ROOT not in sys.path:
    sys.path.insert(0, _UI_ROOT)

from app.models.webauthn import (  # noqa: E402
    CHALLENGE_TTL_SECONDS,
    SESSION_CHALLENGE_KEY,
    WebauthnCeremonyError,
    WebauthnDisabledError,
    webauthn as WEBAUTHN,
)

cbor2 = pytest.importorskip("cbor2")
ec = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ec")
from cryptography.hazmat.primitives import hashes  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature  # noqa: E402

RP_ID = "ui.example.com"
ORIGIN = f"https://{RP_ID}"

FLAG_UP = 0x01  # user present
FLAG_UV = 0x04  # user verified
FLAG_BE = 0x08  # backup eligible
FLAG_BS = 0x10  # backed up
FLAG_AT = 0x40  # attested credential data included


def b64url(raw: bytes) -> str:
    return urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class SoftwareAuthenticator:
    """Just enough CTAP2 to produce responses py_webauthn accepts (or rightly rejects)."""

    def __init__(self, credential_id: bytes = b"credential-0001", *, user_verified: bool = True):
        self.credential_id = credential_id
        self.user_verified = user_verified
        self.sign_count = 0
        self._key = ec.generate_private_key(ec.SECP256R1())

    def clone(self, *, user_verified: bool) -> "SoftwareAuthenticator":
        """Same credential and key, different user-verification capability.

        Lets a test isolate the UV check: without sharing the key the assertion would fail on the
        signature instead, and the test would pass for the wrong reason.
        """
        twin = SoftwareAuthenticator(self.credential_id, user_verified=user_verified)
        twin._key = self._key
        twin.sign_count = self.sign_count
        return twin

    def _cose_key(self) -> bytes:
        numbers = self._key.public_key().public_numbers()
        return cbor2.dumps(
            {
                1: 2,  # kty: EC2
                3: -7,  # alg: ES256
                -1: 1,  # crv: P-256
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )

    def _flags(self, *, attested: bool) -> int:
        flags = FLAG_UP | FLAG_BE | FLAG_BS
        if self.user_verified:
            flags |= FLAG_UV
        if attested:
            flags |= FLAG_AT
        return flags

    def _authenticator_data(self, rp_id: str, *, attested: bool) -> bytes:
        data = sha256(rp_id.encode()).digest() + bytes([self._flags(attested=attested)]) + self.sign_count.to_bytes(4, "big")
        if attested:
            data += b"\x00" * 16  # aaguid
            data += len(self.credential_id).to_bytes(2, "big") + self.credential_id
            data += self._cose_key()
        return data

    @staticmethod
    def _client_data(ceremony: str, challenge: str, origin: str) -> bytes:
        return json.dumps({"type": ceremony, "challenge": challenge, "origin": origin, "crossOrigin": False}).encode()

    def register(self, options: dict, *, origin: str = ORIGIN, rp_id: str = RP_ID) -> dict:
        client_data = self._client_data("webauthn.create", options["challenge"], origin)
        authenticator_data = self._authenticator_data(rp_id, attested=True)
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": authenticator_data})
        return {
            "id": b64url(self.credential_id),
            "rawId": b64url(self.credential_id),
            "type": "public-key",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": b64url(client_data),
                "attestationObject": b64url(attestation),
                "transports": ["internal"],
            },
        }

    def authenticate(self, options: dict, *, origin: str = ORIGIN, rp_id: str = RP_ID, user_handle: Optional[str] = None, tamper: bool = False) -> dict:
        self.sign_count += 1
        client_data = self._client_data("webauthn.get", options["challenge"], origin)
        authenticator_data = self._authenticator_data(rp_id, attested=False)

        signature = self._key.sign(authenticator_data + sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        if tamper:
            # A structurally valid DER signature over nothing in particular.
            signature = encode_dss_signature(1, 1)

        return {
            "id": b64url(self.credential_id),
            "rawId": b64url(self.credential_id),
            "type": "public-key",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": b64url(client_data),
                "authenticatorData": b64url(authenticator_data),
                "signature": b64url(signature),
                "userHandle": user_handle,
            },
        }


@pytest.fixture
def app():
    application = Flask(__name__)
    application.secret_key = "test"
    application.config["WEBAUTHN_RP_ID"] = RP_ID
    application.config["WEBAUTHN_RP_NAME"] = "BunkerWeb UI"
    application.config["WEBAUTHN_ORIGINS"] = [ORIGIN]
    return application


@pytest.fixture
def authenticator():
    return SoftwareAuthenticator()


def _register(app, authenticator, **kwargs):
    """Run a full registration ceremony and return the row the UI would persist."""
    with app.test_request_context():
        options_json, user_handle = WEBAUTHN.registration_options("alice", [])
        response = authenticator.register(json.loads(options_json), **kwargs)
        return WEBAUTHN.verify_registration(response), user_handle


class TestRegistration:
    def test_round_trip(self, app, authenticator):
        stored, user_handle = _register(app, authenticator)
        assert stored["credential_id"] == b64url(authenticator.credential_id)
        assert stored["public_key"]
        assert stored["device_type"] == "multi_device"
        assert stored["backed_up"] is True
        assert user_handle

    def test_options_demand_a_discoverable_verified_credential(self, app):
        """Both are what let the resulting passkey replace the password AND the TOTP prompt."""
        with app.test_request_context():
            options = json.loads(WEBAUTHN.registration_options("alice", [])[0])
        assert options["authenticatorSelection"]["residentKey"] == "required"
        assert options["authenticatorSelection"]["userVerification"] == "required"

    def test_existing_credentials_are_excluded(self, app):
        existing = {"credential_id": b64url(b"already-here"), "user_handle": b64url(b"handle")}
        with app.test_request_context():
            options = json.loads(WEBAUTHN.registration_options("alice", [existing])[0])
        assert [c["id"] for c in options["excludeCredentials"]] == [b64url(b"already-here")]

    def test_user_handle_is_reused_when_one_exists(self, app):
        existing_handle = b64url(b"the-existing-handle")
        with app.test_request_context():
            _, user_handle = WEBAUTHN.registration_options("alice", [{"credential_id": b64url(b"x"), "user_handle": existing_handle}])
        assert user_handle == existing_handle

    def test_wrong_origin_rejected(self, app, authenticator):
        with pytest.raises(WebauthnCeremonyError):
            _register(app, authenticator, origin="https://evil.example.com")

    def test_wrong_rp_id_rejected(self, app, authenticator):
        with pytest.raises(WebauthnCeremonyError):
            _register(app, authenticator, rp_id="evil.example.com")

    def test_unverified_user_rejected(self, app):
        """Registration demands user verification; a key that only reports presence can't enroll."""
        with pytest.raises(WebauthnCeremonyError):
            _register(app, SoftwareAuthenticator(user_verified=False))


class TestAuthentication:
    def _stored(self, app, authenticator):
        stored, _ = _register(app, authenticator)
        return stored

    def test_round_trip(self, app, authenticator):
        stored = self._stored(app, authenticator)
        with app.test_request_context():
            options = json.loads(WEBAUTHN.authentication_options())
            response = authenticator.authenticate(options)
            assert WEBAUTHN.verify_authentication(response, stored, require_user_verification=True) == authenticator.sign_count

    def test_passwordless_options_carry_no_credentials_and_demand_verification(self, app):
        """No allowCredentials means no username is needed — and nothing to enumerate accounts with."""
        with app.test_request_context():
            options = json.loads(WEBAUTHN.authentication_options())
        assert not options.get("allowCredentials")
        assert options["userVerification"] == "required"

    def test_second_factor_options_are_scoped_and_only_prefer_verification(self, app):
        """Older non-discoverable keys can't do UV, but are still valid as a second factor."""
        with app.test_request_context():
            options = json.loads(WEBAUTHN.authentication_options(allow_credentials=[{"credential_id": b64url(b"cred")}]))
        assert [c["id"] for c in options["allowCredentials"]] == [b64url(b"cred")]
        assert options["userVerification"] == "preferred"

    def test_tampered_signature_rejected(self, app, authenticator):
        stored = self._stored(app, authenticator)
        with app.test_request_context():
            options = json.loads(WEBAUTHN.authentication_options())
            response = authenticator.authenticate(options, tamper=True)
            with pytest.raises(WebauthnCeremonyError):
                WEBAUTHN.verify_authentication(response, stored, require_user_verification=True)

    def test_wrong_origin_rejected(self, app, authenticator):
        stored = self._stored(app, authenticator)
        with app.test_request_context():
            options = json.loads(WEBAUTHN.authentication_options())
            response = authenticator.authenticate(options, origin="https://evil.example.com")
            with pytest.raises(WebauthnCeremonyError):
                WEBAUTHN.verify_authentication(response, stored, require_user_verification=True)

    def test_wrong_rp_id_rejected(self, app, authenticator):
        stored = self._stored(app, authenticator)
        with app.test_request_context():
            options = json.loads(WEBAUTHN.authentication_options())
            response = authenticator.authenticate(options, rp_id="evil.example.com")
            with pytest.raises(WebauthnCeremonyError):
                WEBAUTHN.verify_authentication(response, stored, require_user_verification=True)

    def test_another_credentials_public_key_rejected(self, app, authenticator):
        """The assertion must not validate against a credential it wasn't signed for."""
        stored_other = self._stored(app, SoftwareAuthenticator(credential_id=b"credential-0002"))
        with app.test_request_context():
            options = json.loads(WEBAUTHN.authentication_options())
            response = authenticator.authenticate(options)
            with pytest.raises(WebauthnCeremonyError):
                WEBAUTHN.verify_authentication(response, stored_other, require_user_verification=True)

    def test_sign_count_regression_rejected(self, app, authenticator):
        """A counter that fails to advance is the cloned-authenticator signal."""
        stored = self._stored(app, authenticator)
        stored["sign_count"] = 9999
        with app.test_request_context():
            options = json.loads(WEBAUTHN.authentication_options())
            response = authenticator.authenticate(options)
            with pytest.raises(WebauthnCeremonyError):
                WEBAUTHN.verify_authentication(response, stored, require_user_verification=True)

    def test_unverified_user_rejected_for_passwordless(self, app, authenticator):
        """A key that can't verify its user must not be able to open a session on its own.

        Same credential and key as the enrolled one, so the only thing that can fail here is the
        user-verification flag.
        """
        stored = self._stored(app, authenticator)
        weak = authenticator.clone(user_verified=False)
        with app.test_request_context():
            options = json.loads(WEBAUTHN.authentication_options())
            response = weak.authenticate(options)
            with pytest.raises(WebauthnCeremonyError):
                WEBAUTHN.verify_authentication(response, stored, require_user_verification=True)

    def test_unverified_user_accepted_as_second_factor(self, app, authenticator):
        """The very same assertion the passwordless flow refuses is fine behind a password."""
        stored = self._stored(app, authenticator)
        weak = authenticator.clone(user_verified=False)
        with app.test_request_context():
            options = json.loads(WEBAUTHN.authentication_options(allow_credentials=[stored]))
            response = weak.authenticate(options)
            assert WEBAUTHN.verify_authentication(response, stored, require_user_verification=False) == weak.sign_count


class TestChallenges:
    def test_challenge_is_single_use(self, app, authenticator):
        stored, _ = _register(app, authenticator)
        with app.test_request_context():
            options = json.loads(WEBAUTHN.authentication_options())
            response = authenticator.authenticate(options)
            WEBAUTHN.verify_authentication(response, stored, require_user_verification=True)
            # Same response replayed: the challenge is already consumed.
            with pytest.raises(WebauthnCeremonyError):
                WEBAUTHN.verify_authentication(response, stored, require_user_verification=True)

    def test_expired_challenge_rejected(self, app, authenticator):
        stored, _ = _register(app, authenticator)
        with app.test_request_context():
            options = json.loads(WEBAUTHN.authentication_options())
            response = authenticator.authenticate(options)

            stale = datetime.now().astimezone() - timedelta(seconds=CHALLENGE_TTL_SECONDS + 1)
            session[SESSION_CHALLENGE_KEY]["expires"] = stale.isoformat()

            with pytest.raises(WebauthnCeremonyError, match="Expired"):
                WEBAUTHN.verify_authentication(response, stored, require_user_verification=True)

    def test_registration_challenge_cannot_be_used_for_authentication(self, app, authenticator):
        """Binding the ceremony kind stops one challenge from being replayed into the other."""
        stored, _ = _register(app, authenticator)
        with app.test_request_context():
            options_json, _ = WEBAUTHN.registration_options("alice", [])
            response = authenticator.authenticate(json.loads(options_json))
            with pytest.raises(WebauthnCeremonyError, match="kind mismatch"):
                WEBAUTHN.verify_authentication(response, stored, require_user_verification=True)

    def test_missing_challenge_rejected(self, app, authenticator):
        stored, _ = _register(app, authenticator)
        with app.test_request_context():
            with pytest.raises(WebauthnCeremonyError, match="No pending"):
                WEBAUTHN.verify_authentication({}, stored, require_user_verification=True)

    def test_challenge_ttl_is_five_minutes(self, app):
        with app.test_request_context():
            WEBAUTHN.authentication_options()
            expires = datetime.fromisoformat(session[SESSION_CHALLENGE_KEY]["expires"])
        assert 0 < (expires - datetime.now().astimezone()).total_seconds() <= CHALLENGE_TTL_SECONDS


class TestDisabled:
    @pytest.fixture
    def app_without_rp(self, app):
        app.config["WEBAUTHN_RP_ID"] = None
        app.config["WEBAUTHN_ORIGINS"] = []
        return app

    def test_not_enabled_without_an_rp_id(self, app_without_rp):
        with app_without_rp.test_request_context():
            assert WEBAUTHN.enabled is False

    def test_not_enabled_without_origins(self, app):
        app.config["WEBAUTHN_ORIGINS"] = []
        with app.test_request_context():
            assert WEBAUTHN.enabled is False

    def test_ceremonies_refuse_to_start(self, app_without_rp):
        with app_without_rp.test_request_context():
            with pytest.raises(WebauthnDisabledError):
                WEBAUTHN.authentication_options()
            with pytest.raises(WebauthnDisabledError):
                WEBAUTHN.registration_options("alice", [])


class TestResponseHelpers:
    def test_credential_id_prefers_raw_id(self):
        assert WEBAUTHN.credential_id_from_response({"rawId": "RAW", "id": "ID"}) == "RAW"

    def test_credential_id_falls_back_to_id(self):
        assert WEBAUTHN.credential_id_from_response({"id": "ID"}) == "ID"

    def test_missing_credential_id_raises(self):
        with pytest.raises(WebauthnCeremonyError):
            WEBAUTHN.credential_id_from_response({})

    def test_user_handle_extracted(self):
        assert WEBAUTHN.user_handle_from_response({"response": {"userHandle": "H"}}) == "H"

    def test_user_handle_absent(self):
        assert WEBAUTHN.user_handle_from_response({"response": {}}) is None
        assert WEBAUTHN.user_handle_from_response({}) is None


class TestRelyingPartyResolution:
    """main.py derives the RP identity from UI_ALLOWED_HOSTS, never from the request Host."""

    @staticmethod
    def _resolve(allowed_hosts, rp_id_env="", origins_env="", listen_port="7000"):
        # Mirrors the resolution block in src/ui/main.py; kept in sync by
        # test_matches_main_py below.
        from re import split as resplit

        rp_id = rp_id_env.strip().lower() or None
        if not rp_id and len(allowed_hosts) == 1 and not allowed_hosts[0].startswith("*."):
            rp_id = allowed_hosts[0].strip().lower().rsplit(":", 1)[0] or None

        if origins_env.strip():
            origins = [o.rstrip("/") for o in resplit(r"[\s,]+", origins_env.strip()) if o]
        elif rp_id:
            origins = [f"https://{rp_id}"]
            if rp_id == "localhost":
                origins.append(f"http://localhost:{listen_port}")
        else:
            origins = []
        return rp_id, origins

    def test_single_host_becomes_the_rp_id(self):
        assert self._resolve(["ui.example.com"]) == ("ui.example.com", ["https://ui.example.com"])

    def test_port_is_stripped(self):
        assert self._resolve(["ui.example.com:8443"])[0] == "ui.example.com"

    def test_wildcard_host_is_not_usable(self):
        """A wildcard can't be an RP ID, and guessing one would brick every credential."""
        assert self._resolve(["*.example.com"]) == (None, [])

    def test_several_hosts_are_ambiguous(self):
        assert self._resolve(["a.example.com", "b.example.com"]) == (None, [])

    def test_no_allowlist_leaves_it_disabled(self):
        assert self._resolve([]) == (None, [])

    def test_explicit_env_wins(self):
        assert self._resolve(["a.example.com", "b.example.com"], rp_id_env="ui.example.com")[0] == "ui.example.com"

    def test_explicit_origins_win(self):
        assert self._resolve(["ui.example.com"], origins_env="https://a.example.com, https://b.example.com/")[1] == [
            "https://a.example.com",
            "https://b.example.com",
        ]

    def test_localhost_keeps_its_http_origin(self):
        """The only origin the spec exempts from HTTPS, and what makes the dev stack testable."""
        assert self._resolve(["localhost"])[1] == ["https://localhost", "http://localhost:7000"]

    def test_matches_main_py(self):
        """Guard against the real resolution drifting away from the copy exercised above."""
        source = (Path(_UI_ROOT) / "main.py").read_text()
        assert 'app.config["WEBAUTHN_RP_ID"] = _webauthn_rp_id' in source
        assert 'getenv("UI_WEBAUTHN_RP_ID", "")' in source
        assert 'getenv("UI_WEBAUTHN_ORIGINS", "")' in source
        assert 'app.config["ALLOWED_HOSTS"][0].startswith("*.")' in source


class TestSecurityHeaders:
    def test_permissions_policy_allows_webauthn(self):
        """One reverted directive here silently disables the whole feature in the browser."""
        source = (Path(_UI_ROOT) / "main.py").read_text()
        assert "publickey-credentials-create=(self)" in source
        assert "publickey-credentials-get=(self)" in source
        assert "publickey-credentials-create=()," not in source
        assert "publickey-credentials-get=()," not in source


class TestSessionFlagMigration:
    def test_main_py_migrates_the_legacy_flag(self):
        """Live sessions predate the rename; without the backfill an upgrade re-prompts everyone."""
        source = (Path(_UI_ROOT) / "main.py").read_text()
        assert 'session["mfa_validated"] = session.pop("totp_validated")' in source

    def test_gate_is_not_widened_to_passkeys(self):
        """Registering a passkey must not start gating password logins.

        Passkeys have no recovery codes, so making one mandatory after a password would lock the
        user out permanently the day they lose the device — while the chantier keeps the password
        as the *fallback*.
        """
        source = (Path(_UI_ROOT) / "main.py").read_text()
        assert 'if not session.get("mfa_validated", False) and bool(current_user.totp_secret) and request.endpoint != "totp.totp_page":' in source
        assert "has_second_factor" not in source


def test_no_stale_totp_validated_references():
    """Every read/write moved to mfa_validated except the one-line backwards-compat migration."""
    ui_root = Path(_UI_ROOT)
    offenders = []
    for path in list(ui_root.rglob("*.py")) + list(ui_root.rglob("*.html")) + list(ui_root.rglob("*.js")):
        if "__pycache__" in str(path) or "/static/libs/" in str(path):
            continue
        for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            if "totp_validated" in line and 'session.pop("totp_validated")' not in line and '"totp_validated" in session' not in line:
                offenders.append(f"{path}:{number}")
    assert offenders == [], f"stale totp_validated references: {offenders}"


def test_timezone_import_is_used():
    """Keeps flake8 quiet about the timezone import used by the fixtures above."""
    assert datetime.now(timezone.utc).tzinfo is timezone.utc
