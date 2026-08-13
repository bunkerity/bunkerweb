from datetime import datetime

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.models.totp import totp as TOTP
from app.models.webauthn import WebauthnCeremonyError, WebauthnDisabledError, webauthn as WEBAUTHN
from app.routes.utils import cors_required, flash, handle_error, verify_data_in_form
from app.utils import LOGGER, _sanitize_internal_next

totp = Blueprint("totp", __name__)

GENERIC_SECURITY_KEY_ERROR = "Couldn't verify your security key, please try again"


def _user_credentials() -> list:
    """The current user's registered credentials, empty when the API is unreachable."""
    try:
        return API_CLIENT.get_user_webauthn_credentials(current_user.get_id())
    except (ApiClientError, ApiUnavailableError) as e:
        LOGGER.error(f"Couldn't list the security keys: {e.message}")
        return []


def _mfa_next() -> str:
    try:
        return _sanitize_internal_next(request.values.get("next"), url_for("home.home_page"))
    except ValueError:
        return url_for("home.home_page")


@totp.route("/totp", methods=["GET", "POST"])
@login_required
def totp_page():
    has_credentials = bool(getattr(current_user, "webauthn_credentials_count", 0))

    if request.method == "POST":
        verify_data_in_form(data={"totp_token": None}, err_message="No token provided on /totp.", redirect_url="totp")

        if not TOTP.verify_totp(request.form["totp_token"], user=current_user):
            recovery_code = TOTP.verify_recovery_code(request.form["totp_token"], user=current_user)
            if not recovery_code:
                return handle_error("The token is invalid.", "totp")
            flash(f"You've used one of your recovery codes. You have {len(current_user.list_recovery_codes)} left.")
            try:
                API_CLIENT.use_recovery_code(current_user.get_id(), recovery_code)
            except (ApiClientError, ApiUnavailableError):
                return handle_error("An error occurred while using the recovery code.", "totp")

        session["mfa_validated"] = True
        try:
            safe_next = _sanitize_internal_next(request.form.get("next"), url_for("home.home_page"))
        except ValueError:
            safe_next = url_for("home.home_page")
        return redirect(url_for("loading", next=safe_next, message="Validating TOTP token."))

    # Nothing to prove (no second factor at all), or already proven
    if (not bool(current_user.totp_secret) and not has_credentials) or session.get("mfa_validated", False):
        return redirect(url_for("home.home_page"))

    return render_template(
        "totp.html",
        is_totp=bool(current_user.totp_secret),
        webauthn_enabled=WEBAUTHN.enabled and has_credentials,
    )


# ── Security key as a second factor ─────────────────────────────────
#
# For a user who already passed the password check. Unlike passwordless login this flow scopes the
# assertion to that user's own credentials and only prefers user verification, so an older
# non-discoverable FIDO2 key still works here even though it can't open a session on its own.


@totp.route("/totp/webauthn/options", methods=["POST"])
@login_required
@cors_required
def totp_webauthn_options():
    if session.get("mfa_validated", False):
        return jsonify({"message": "Already validated"}), 400

    credentials = _user_credentials()
    if not credentials:
        return jsonify({"message": "No security key registered"}), 404

    try:
        return current_app.response_class(WEBAUTHN.authentication_options(allow_credentials=credentials), mimetype="application/json")
    except WebauthnDisabledError:
        return jsonify({"message": "WebAuthn is not configured"}), 404


@totp.route("/totp/webauthn/verify", methods=["POST"])
@login_required
@cors_required
def totp_webauthn_verify():
    if session.get("mfa_validated", False):
        return jsonify({"message": "Already validated"}), 400

    if not WEBAUTHN.enabled:
        return jsonify({"message": "WebAuthn is not configured"}), 404

    credential = request.get_json(silent=True)
    if not isinstance(credential, dict):
        return jsonify({"message": GENERIC_SECURITY_KEY_ERROR}), 401

    username = current_user.get_id()

    try:
        credential_id = WEBAUTHN.credential_id_from_response(credential)

        # Scope the lookup to this user's own credentials: someone else's key must never satisfy
        # this user's second factor.
        stored = next((c for c in _user_credentials() if c["credential_id"] == credential_id), None)
        if not stored:
            raise WebauthnCeremonyError(f"Credential {credential_id} is not registered to {username}")

        new_sign_count = WEBAUTHN.verify_authentication(credential, stored, require_user_verification=False)
    except WebauthnCeremonyError as e:
        WEBAUTHN.log_failure(str(e))
        return jsonify({"message": GENERIC_SECURITY_KEY_ERROR}), 401

    session["mfa_validated"] = True

    try:
        API_CLIENT.update_user_webauthn_credential(username, credential_id, sign_count=new_sign_count, last_used=datetime.now().astimezone().isoformat())
    except (ApiClientError, ApiUnavailableError) as e:
        LOGGER.error(f"Couldn't update the security key usage: {e.message}")

    LOGGER.info(f"User {username} completed two-factor authentication with a security key")

    return jsonify({"redirect": url_for("loading", next=_mfa_next(), message="Validating security key.")})
