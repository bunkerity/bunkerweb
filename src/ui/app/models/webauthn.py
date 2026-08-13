"""WebAuthn / FIDO2 ceremonies for the web UI.

All cryptography (CBOR decoding, COSE keys, signature and attestation verification) is delegated to
py_webauthn. This module only owns the BunkerWeb-specific glue: resolving the Relying Party
identity, keeping challenges single-use and short-lived, and translating between the library's
byte-oriented API and the base64url strings the database stores.

BunkerWeb never sees a private key, a PIN or a biometric: the authenticator keeps those and only
returns a signature over a challenge we issued.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Union

from flask import current_app, session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, generate_challenge, generate_user_handle
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.utils import LOGGER

# A ceremony is a two-step exchange (options, then response). Five minutes is long enough for a
# user to find their security key and short enough that a leaked challenge is worthless.
CHALLENGE_TTL_SECONDS = 300
SESSION_CHALLENGE_KEY = "webauthn_challenge"

# Ceremony kinds. The kind is stored alongside the challenge and checked on the way back, so a
# registration challenge can never be replayed into an authentication (or the other way round).
KIND_REGISTRATION = "registration"
KIND_AUTHENTICATION = "authentication"


class WebauthnDisabledError(Exception):
    """Raised when a ceremony is attempted while no Relying Party identity is configured."""


class WebauthnCeremonyError(Exception):
    """Any failed ceremony. The message is for the log, never for the user."""


class Webauthn:
    # ── Relying Party identity ──────────────────────────────────────────

    @property
    def rp_id(self) -> Optional[str]:
        return current_app.config.get("WEBAUTHN_RP_ID")

    @property
    def rp_name(self) -> str:
        return current_app.config.get("WEBAUTHN_RP_NAME", "BunkerWeb UI")

    @property
    def origins(self) -> List[str]:
        return current_app.config.get("WEBAUTHN_ORIGINS") or []

    @property
    def enabled(self) -> bool:
        """WebAuthn is only offered when the RP identity is known.

        Fails closed on purpose: guessing the RP ID from the request would bind credentials to
        whatever Host header happened to arrive, and a wrong RP ID silently bricks every passkey.
        """
        return bool(self.rp_id and self.origins)

    def _require_enabled(self) -> str:
        if not self.enabled:
            raise WebauthnDisabledError("WebAuthn is not configured")
        return self.rp_id  # type: ignore[return-value]

    # ── Challenges ──────────────────────────────────────────────────────

    def _stash_challenge(self, kind: str) -> bytes:
        challenge = generate_challenge()
        session[SESSION_CHALLENGE_KEY] = {
            "kind": kind,
            "value": bytes_to_base64url(challenge),
            "expires": (datetime.now().astimezone() + timedelta(seconds=CHALLENGE_TTL_SECONDS)).isoformat(),
        }
        return challenge

    def _pop_challenge(self, kind: str) -> bytes:
        """Consume the pending challenge. Single use: it is removed whether or not it validates."""
        stashed = session.pop(SESSION_CHALLENGE_KEY, None)
        if not stashed:
            raise WebauthnCeremonyError("No pending WebAuthn challenge")
        if stashed.get("kind") != kind:
            raise WebauthnCeremonyError(f"WebAuthn challenge kind mismatch (expected {kind}, got {stashed.get('kind')})")
        try:
            expires = datetime.fromisoformat(stashed["expires"])
        except (KeyError, TypeError, ValueError):
            raise WebauthnCeremonyError("Malformed WebAuthn challenge")
        if datetime.now().astimezone() > expires:
            raise WebauthnCeremonyError("Expired WebAuthn challenge")
        return base64url_to_bytes(stashed["value"])

    # ── Registration ────────────────────────────────────────────────────

    def registration_options(self, username: str, existing_credentials: List[dict]) -> Tuple[str, str]:
        """Build creation options for a new passkey.

        Returns (options JSON, user handle). Every credential of a user shares one handle, so a
        second passkey is recognized by the authenticator as the same account instead of piling up
        a duplicate entry.
        """
        rp_id = self._require_enabled()

        user_handle = next((c["user_handle"] for c in existing_credentials if c.get("user_handle")), None) or bytes_to_base64url(generate_user_handle())

        options = generate_registration_options(
            rp_id=rp_id,
            rp_name=self.rp_name,
            user_name=username,
            user_id=base64url_to_bytes(user_handle),
            user_display_name=username,
            challenge=self._stash_challenge(KIND_REGISTRATION),
            authenticator_selection=AuthenticatorSelectionCriteria(
                # Discoverable + user-verifying is what makes the credential able to replace both
                # the password and the TOTP prompt on its own.
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c["credential_id"])) for c in existing_credentials],
        )
        return options_to_json(options), user_handle

    def verify_registration(self, credential: Union[str, dict]) -> dict:
        """Verify a registration response and return the row to persist."""
        rp_id = self._require_enabled()
        challenge = self._pop_challenge(KIND_REGISTRATION)

        try:
            verified = verify_registration_response(
                credential=credential,
                expected_challenge=challenge,
                expected_rp_id=rp_id,
                expected_origin=self.origins,
                require_user_verification=True,
            )
        except (InvalidRegistrationResponse, ValueError) as e:
            raise WebauthnCeremonyError(f"Invalid registration response: {e}")

        return {
            "credential_id": bytes_to_base64url(verified.credential_id),
            "public_key": bytes_to_base64url(verified.credential_public_key),
            "sign_count": verified.sign_count,
            "device_type": verified.credential_device_type.value if verified.credential_device_type else None,
            "backed_up": bool(verified.credential_backed_up),
        }

    # ── Authentication ──────────────────────────────────────────────────

    def authentication_options(self, allow_credentials: Optional[List[dict]] = None) -> str:
        """Build assertion options.

        Without `allow_credentials` this is the passwordless flow: no username is sent, the
        authenticator picks a discoverable credential, and user verification is mandatory because
        that assertion alone opens a full session. It also means the endpoint cannot be used to
        enumerate accounts.

        With `allow_credentials` this is the second-factor flow for a user who already passed the
        password check; user verification is only preferred, so an older non-discoverable security
        key still works.
        """
        rp_id = self._require_enabled()

        options = generate_authentication_options(
            rp_id=rp_id,
            challenge=self._stash_challenge(KIND_AUTHENTICATION),
            allow_credentials=(
                [PublicKeyCredentialDescriptor(id=base64url_to_bytes(c["credential_id"])) for c in allow_credentials] if allow_credentials else None
            ),
            user_verification=UserVerificationRequirement.PREFERRED if allow_credentials else UserVerificationRequirement.REQUIRED,
        )
        return options_to_json(options)

    def verify_authentication(self, credential: Union[str, dict], stored_credential: dict, *, require_user_verification: bool) -> int:
        """Verify an assertion against a stored credential and return the new signature counter.

        py_webauthn rejects a counter that fails to advance when either side is non-zero, which is
        the cloned-authenticator signal. Authenticators that always report 0 are unaffected.
        """
        rp_id = self._require_enabled()
        challenge = self._pop_challenge(KIND_AUTHENTICATION)

        try:
            verified = verify_authentication_response(
                credential=credential,
                expected_challenge=challenge,
                expected_rp_id=rp_id,
                expected_origin=self.origins,
                credential_public_key=base64url_to_bytes(stored_credential["public_key"]),
                credential_current_sign_count=stored_credential.get("sign_count", 0),
                require_user_verification=require_user_verification,
            )
        except (InvalidAuthenticationResponse, ValueError) as e:
            raise WebauthnCeremonyError(f"Invalid authentication response: {e}")

        return verified.new_sign_count

    # ── Misc ────────────────────────────────────────────────────────────

    @staticmethod
    def credential_id_from_response(credential: dict) -> str:
        """Pull the credential ID out of a raw browser response."""
        credential_id = credential.get("rawId") or credential.get("id")
        if not credential_id:
            raise WebauthnCeremonyError("Response carries no credential ID")
        return credential_id

    @staticmethod
    def user_handle_from_response(credential: dict) -> Optional[str]:
        """Pull the user handle a discoverable credential reports, if it reports one."""
        return (credential.get("response") or {}).get("userHandle") or None

    @staticmethod
    def log_failure(message: str) -> None:
        """Ceremony failures are logged in full and reported to the user as a single generic error.

        Distinguishing "unknown credential" from "bad signature" in the response would leak whether
        an account exists.
        """
        LOGGER.warning(f"WebAuthn ceremony failed: {message}")


webauthn = Webauthn()

__all__ = ("webauthn", "WebauthnCeremonyError", "WebauthnDisabledError")
