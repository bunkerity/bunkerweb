from datetime import datetime
from os import getenv

from bcrypt import checkpw
from flask import Blueprint, current_app, flash as flask_flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user

from app.dependencies import API_CLIENT
from app.api_client import ApiClientError, ApiUnavailableError
from app.routes.utils import cors_required
from app.utils import BISCUIT_PRIVATE_KEY_FILE, LOGGER, flash, _sanitize_internal_next
from app.models.biscuit import BiscuitTokenFactory, PrivateKey
from app.models.models import UiUsers
from app.models.webauthn import WebauthnCeremonyError, WebauthnDisabledError, webauthn as WEBAUTHN

login = Blueprint("login", __name__)

# Deliberately identical for every passkey failure: telling "unknown credential" apart from "bad
# signature" would leak whether an account exists.
GENERIC_PASSKEY_ERROR = "Couldn't sign you in with a passkey, please try again"


def _safe_next() -> str:
    """Resolve the post-login redirect target, fail-closed to home."""
    raw_next = request.args.get("next") or request.form.get("next") or ""
    # Support nested ?next= chaining
    if "?next=" in raw_next:
        raw_next = raw_next.split("?next=")[-1]

    try:
        return _sanitize_internal_next(raw_next, url_for("home.home_page"))
    except ValueError:
        return url_for("home.home_page")


def _establish_session(ui_user: UiUsers, user_data: dict, *, mfa_done: bool, remember_me: bool) -> bool:
    """Log the user in and build a fresh, fully-populated session.

    Shared by the password flow and the passwordless passkey flow so the session regeneration,
    session-id bookkeeping, remember-me handling and Biscuit token minting can't drift apart.

    `mfa_done` marks strong authentication as already complete: true for a passkey assertion, whose
    user verification happens inside the ceremony, false after a password, which may still owe a
    second factor.
    """
    # Regenerate the session to mitigate session fixation
    session.clear()  # Clear the current session
    current_app.session_interface.regenerate(session)  # Regenerate the session ID

    # log the user in
    session["creation_date"] = datetime.now().astimezone()
    session["ip"] = request.remote_addr
    session["user_agent"] = request.headers.get("User-Agent")
    session["mfa_validated"] = mfa_done
    session["flash_messages"] = []
    current_app.session_interface.regenerate(session)  # now non-empty -> sid actually rotates
    session.modified = True

    try:
        session["session_id"] = API_CLIENT.mark_user_login(ui_user.username, session["ip"], session["user_agent"])
    except (ApiClientError, ApiUnavailableError) as e:
        LOGGER.error(f"Couldn't mark the user login: {e.message}")

    if remember_me:
        session.permanent = True

    if not login_user(ui_user, remember=remember_me):
        return False

    # Generate and add Biscuit token to session
    try:
        if BISCUIT_PRIVATE_KEY_FILE.exists():
            private_key = PrivateKey(BISCUIT_PRIVATE_KEY_FILE.read_text().strip())
            token_factory = BiscuitTokenFactory(private_key)
            role = "super_admin" if user_data.get("admin") else (user_data.get("roles") or ["user"])[0]
            session["biscuit_token"] = token_factory.create_token_for_role(role, ui_user.username).to_base64()
        else:
            LOGGER.warning("BISCUIT_PRIVATE_KEY_PATH not configured, skipping Biscuit token generation")
    except Exception as e:
        LOGGER.error(f"Failed to create Biscuit token: {e}")

    return True


def _user_from_auth_data(user_data: dict) -> UiUsers:
    return UiUsers(
        username=user_data["username"],
        email=user_data.get("email"),
        password=user_data.get("password") or "",
        method=user_data.get("method", "manual"),
        admin=user_data.get("admin", False),
        theme=user_data.get("theme", "light"),
        language=user_data.get("language", "en"),
        totp_secret=user_data.get("totp_secret"),
    )


def _remember_me_requested() -> bool:
    always_remember = getenv("ALWAYS_REMEMBER", "no").lower() == "yes"
    if always_remember:
        LOGGER.info("ALWAYS_REMEMBER is set to yes, so the sessions will always be remembered")
        return True
    return request.form.get("remember-me") == "on"


@login.route("/login", methods=["GET", "POST"])
def login_page():
    try:
        admin_user = API_CLIENT.get_admin_user(auth=True)
    except (ApiClientError, ApiUnavailableError):
        admin_user = None

    if not admin_user:
        return redirect(url_for("setup.setup_page"))
    elif current_user.is_authenticated:  # type: ignore
        return redirect(url_for("home.home_page"))

    fail = False
    if request.method == "POST" and "username" in request.form and "password" in request.form:
        LOGGER.warning(f"Login attempt from {request.remote_addr} with username \"{request.form['username']}\"")

        user_data = API_CLIENT.get_user_for_auth(request.form["username"])
        if (
            user_data
            and user_data["username"] == request.form["username"]
            and checkpw(request.form["password"].encode("utf-8"), user_data["password"].encode("utf-8"))
        ):
            ui_user = _user_from_auth_data(user_data)

            if not _establish_session(ui_user, user_data, mfa_done=False, remember_me=_remember_me_requested()):
                flask_flash("Couldn't log you in, please try again", "error")
                return render_template("login.html", error="Couldn't log you in, please try again")

            login_user_data = {
                "password": user_data["password"],
                "email": user_data.get("email"),
                "totp_secret": user_data.get("totp_secret"),
                "method": user_data.get("method", "manual"),
                "theme": request.form.get("theme", "light"),
                "language": request.form.get("language", "en"),
            }

            try:
                API_CLIENT.update_user(current_user.get_id(), **login_user_data)
            except (ApiClientError, ApiUnavailableError) as e:
                LOGGER.error(f"Couldn't update the user {current_user.get_id()}: {e.message}")

            LOGGER.info(f"User {ui_user.username} logged in successfully" + (" with remember me" if request.form.get("remember-me") == "on" else ""))

            if not user_data.get("totp_secret") and not user_data.get("webauthn_credentials_count"):
                flash(
                    f'Please enable two-factor authentication to secure your account <a href="{url_for("profile.profile_page", _anchor="security")}">here</a>',
                    "warning",
                )

            return redirect(url_for("loading", next=_safe_next()))
        else:
            flask_flash("Invalid username or password", "error")
            fail = True

    kwargs = {
        "is_totp": bool(current_user.totp_secret),
        "webauthn_enabled": WEBAUTHN.enabled,
    } | ({"error": "Invalid username or password"} if fail else {})

    return render_template("login.html", **kwargs), 401 if fail else 200


# ── Passwordless login ──────────────────────────────────────────────
#
# The options endpoint takes no username: the authenticator picks a discoverable credential on its
# own, so there is nothing here to enumerate accounts with.


@login.route("/login/webauthn/options", methods=["POST"])
@cors_required
def login_webauthn_options():
    if current_user.is_authenticated:  # type: ignore
        return jsonify({"message": "Already authenticated"}), 400

    try:
        return current_app.response_class(WEBAUTHN.authentication_options(), mimetype="application/json")
    except WebauthnDisabledError:
        return jsonify({"message": "WebAuthn is not configured"}), 404


@login.route("/login/webauthn/verify", methods=["POST"])
@cors_required
def login_webauthn_verify():
    if current_user.is_authenticated:  # type: ignore
        return jsonify({"message": "Already authenticated"}), 400

    if not WEBAUTHN.enabled:
        return jsonify({"message": "WebAuthn is not configured"}), 404

    credential = request.get_json(silent=True)
    if not isinstance(credential, dict):
        return jsonify({"message": GENERIC_PASSKEY_ERROR}), 401

    # The redirect target and remember-me flag ride along in the JSON body; read them before the
    # session is cleared below.
    remember_me = getenv("ALWAYS_REMEMBER", "no").lower() == "yes" or bool(credential.pop("remember_me", False))
    raw_next = credential.pop("next", "") or ""
    try:
        safe_next = _sanitize_internal_next(raw_next, url_for("home.home_page"))
    except ValueError:
        safe_next = url_for("home.home_page")

    LOGGER.warning(f"Passkey login attempt from {request.remote_addr}")

    try:
        credential_id = WEBAUTHN.credential_id_from_response(credential)

        stored = API_CLIENT.resolve_webauthn_credential(credential_id)
        if not stored:
            raise WebauthnCeremonyError(f"Unknown credential {credential_id}")

        # A discoverable credential reports the handle it was created with; it must match the one
        # stored for that credential, otherwise the assertion belongs to a different account.
        reported_handle = WEBAUTHN.user_handle_from_response(credential)
        if reported_handle and reported_handle != stored["user_handle"]:
            raise WebauthnCeremonyError("User handle mismatch")

        new_sign_count = WEBAUTHN.verify_authentication(credential, stored, require_user_verification=True)

        user_data = API_CLIENT.get_user_for_auth(stored["username"])
        if not user_data:
            raise WebauthnCeremonyError(f"Credential {credential_id} points at missing user {stored['username']}")
    except WebauthnCeremonyError as e:
        WEBAUTHN.log_failure(str(e))
        return jsonify({"message": GENERIC_PASSKEY_ERROR}), 401
    except (ApiClientError, ApiUnavailableError) as e:
        LOGGER.error(f"Couldn't verify the passkey: {e.message}")
        return jsonify({"message": GENERIC_PASSKEY_ERROR}), 401

    ui_user = _user_from_auth_data(user_data)

    # A verified assertion with user verification is a complete authentication on its own: the
    # authenticator checked the user locally, so no password and no TOTP prompt follow.
    if not _establish_session(ui_user, user_data, mfa_done=True, remember_me=remember_me):
        return jsonify({"message": GENERIC_PASSKEY_ERROR}), 401

    # Persisted only after the ceremony verified, never before.
    try:
        API_CLIENT.update_user_webauthn_credential(
            stored["username"], credential_id, sign_count=new_sign_count, last_used=datetime.now().astimezone().isoformat()
        )
    except (ApiClientError, ApiUnavailableError) as e:
        LOGGER.error(f"Couldn't update the passkey usage: {e.message}")

    LOGGER.info(f"User {ui_user.username} logged in successfully with a passkey")

    return jsonify({"redirect": url_for("loading", next=safe_next)})
