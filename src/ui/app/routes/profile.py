from contextlib import suppress
from datetime import datetime
from typing import Dict, Generator, Tuple, Union
from flask import Blueprint, Response, current_app, jsonify, redirect, render_template, request, stream_with_context, url_for, session
from flask_login import current_user, login_required
from user_agents import parse

from app.models.totp import totp as TOTP
from app.models.webauthn import WebauthnCeremonyError, WebauthnDisabledError, webauthn as WEBAUTHN

from app.dependencies import API_CLIENT
from app.api_client import ApiClientError, ApiUnavailableError
from app.utils import LOGGER, MAX_PASSWORD_BYTES, USER_PASSWORD_RX, flash, gen_password_hash, password_exceeds_bcrypt_limit, revoke_sessions

from app.routes.utils import cors_required, handle_error, verify_data_in_form

profile = Blueprint("profile", __name__)

# The enrolment secret is a *candidate*: minted for the QR code, promoted to the user's real secret
# only once they prove they scanned it. Two properties have to hold at once, and the original code
# held neither.
#
# **It must survive re-rendering the page.** `/profile` used to mint a new secret on every GET, so
# any second render — a second tab, a refresh, a reload the product issues itself — silently
# replaced the secret behind the QR the user was already looking at. The code from their
# authenticator app was then checked against a secret that had never been displayed, and enrolment
# could not be completed at all. Minting only when there is no candidate makes the flow immune to
# any number of concurrent loads, which is the property that matters; "it works once the extra
# render is gone" is not the same thing and would break again the next time something re-rendered.
#
# **It must not be supplied by the client.** The enrolment form posts `secret_token`, and verifying
# against *that* would be the small fix — and would let anyone who can get a user to submit a
# crafted form enrol a secret of the attacker's choosing, which is an account takeover dressed as a
# convenience. The candidate is only ever read back out of the server-side session, keyed to the
# user it was minted for so a session that outlives a user change cannot hand the next one a
# foreign secret.


def _stored_totp_candidate() -> str:
    """The enrolment secret currently in flight for this user, or `""` when there is none."""
    if session.get("tmp_totp_user") != current_user.get_id():
        return ""
    return session.get("tmp_totp_secret", "")


def _issue_totp_candidate() -> str:
    """The secret to put behind the QR code — the one already in flight, or a fresh one."""
    secret = _stored_totp_candidate()
    if not secret:
        secret = TOTP.generate_totp_secret()
        session["tmp_totp_secret"] = secret
        session["tmp_totp_user"] = current_user.get_id()
    return secret


def _discard_totp_candidate() -> str:
    """Consume the candidate so the next enrolment starts from a fresh secret."""
    secret = _stored_totp_candidate()
    session.pop("tmp_totp_secret", None)
    session.pop("tmp_totp_user", None)
    return secret


def _list_credentials() -> list:
    """The current user's registered WebAuthn credentials, empty when the API is unreachable."""
    if not WEBAUTHN.enabled:
        return []
    try:
        return API_CLIENT.get_user_webauthn_credentials(current_user.get_id())
    except (ApiClientError, ApiUnavailableError) as e:
        LOGGER.error(f"Couldn't list the passkeys: {e.message}")
        return []


def get_last_sessions(page: int, per_page: int) -> Tuple[Generator[Dict[str, Union[str, bool]], None, None], int]:
    db_sessions = API_CLIENT.get_user_sessions(current_user.username, session.get("session_id"))
    total_sessions = len(db_sessions)
    if "session_id" not in session:
        total_sessions += 1

    if total_sessions <= per_page:
        per_page = total_sessions
        page = 1
    elif total_sessions <= (page - 1) * per_page:
        page = total_sessions // per_page

    def session_generator(page: int, per_page: int):
        additional_sessions = []
        if page == 1 and "session_id" not in session and per_page > 1:
            per_page -= 1
            additional_sessions.append(session)

        for db_session in additional_sessions + db_sessions[(page - 1) * per_page : page * per_page]:  # noqa: E203
            # Support both DB session dicts and the current Flask session object which may miss some keys
            ua_raw = db_session.get("user_agent", "") if isinstance(db_session, dict) else str(db_session.get("user_agent", ""))
            ua_data = parse(ua_raw or "")

            def _fmt_dt(dt_val):
                with suppress(Exception):
                    if isinstance(dt_val, str):
                        dt_val = datetime.fromisoformat(dt_val)
                    if isinstance(dt_val, datetime):
                        return dt_val.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
                return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

            creation_dt = db_session.get("creation_date") if isinstance(db_session, dict) else None
            last_activity_dt = db_session.get("last_activity") if isinstance(db_session, dict) else None

            yield {
                "current": (
                    db_session.get("id") == session.get("session_id") if isinstance(db_session, dict) and "session_id" in session else "id" not in db_session
                ),
                "browser": ua_data.get_browser(),
                "os": ua_data.get_os(),
                "device": ua_data.get_device(),
                "ip": (db_session.get("ip") if isinstance(db_session, dict) else session.get("ip", "-")) or "-",
                "creation_date": _fmt_dt(creation_dt),
                "last_activity": (
                    _fmt_dt(last_activity_dt)
                    if isinstance(db_session, dict) and "id" in db_session
                    else datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
                ),
            }

    return session_generator(page, per_page), total_sessions


@profile.route("/profile", methods=["GET"])
@login_required
def profile_page():
    totp_qr_image = ""
    if not bool(current_user.totp_secret):
        totp_qr_image = TOTP.generate_qrcode(current_user.get_id(), _issue_totp_candidate())

    last_sessions, total_sessions = get_last_sessions(1, 3)

    return render_template(
        "profile.html",
        is_totp=bool(current_user.totp_secret),
        totp_qr_image=totp_qr_image,
        totp_recovery_codes=session.pop("decrypted_recovery_codes", current_user.list_recovery_codes),
        is_recovery_refreshed=session.pop("totp_refreshed", False),
        totp_secret=TOTP.get_totp_pretty_key(_stored_totp_candidate()),
        last_sessions=last_sessions,
        total_sessions=total_sessions,
        webauthn_enabled=WEBAUTHN.enabled,
        webauthn_credentials=_list_credentials(),
    )


@profile.route("/profile/sessions", methods=["GET"])
@login_required
@cors_required
def get_sessions():
    page = request.args.get("page", 1, type=int)

    if page < 1:
        return Response("Invalid page number", status=400)

    session_generator = get_last_sessions(page, 3)[0]

    def generate_stream():
        yield "["
        first = True
        for session_data in session_generator:
            if not first:
                yield ","
            first = False
            yield jsonify(session_data).get_data(as_text=True)
        yield "]"

    return Response(stream_with_context(generate_stream()), content_type="application/json")


@profile.route("/profile/totp-refresh", methods=["POST"])
@login_required
def totp_refresh():
    if API_CLIENT.readonly:
        return handle_error("Database is in read-only mode", "profile")

    if not bool(current_user.totp_secret):
        return handle_error("Two-factor authentication is not enabled.", "profile")

    verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/totp-refresh.", redirect_url="profile")

    if not current_user.check_password(request.form["password"]):
        return handle_error("The current password is incorrect.", "profile")

    totp_recovery_codes = TOTP.generate_recovery_codes()

    try:
        API_CLIENT.refresh_recovery_codes(current_user.get_id(), totp_recovery_codes)
    except (ApiClientError, ApiUnavailableError) as e:
        return handle_error(f"Couldn't refresh the recovery codes: {e.message}", "profile")

    session["totp_refreshed"] = True
    session["decrypted_recovery_codes"] = totp_recovery_codes

    flash("The recovery codes have been successfully refreshed. The old ones are no longer valid.")
    return redirect(url_for("profile.profile_page") + "#security")


@profile.route("/profile/totp-disable", methods=["POST"])
@login_required
def totp_disable():
    if API_CLIENT.readonly:
        return handle_error("Database is in read-only mode", "profile")

    if not bool(current_user.totp_secret):
        return handle_error("Two-factor authentication is not enabled.", "profile")

    verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/totp-disable.", redirect_url="profile")

    if not current_user.check_password(request.form["password"]):
        return handle_error("The current password is incorrect.", "profile")

    verify_data_in_form(data={"totp_token": None}, err_message="Missing totp token parameter on /profile/totp-enable.", redirect_url="profile")

    # No candidate is in flight here — TOTP is already enabled — so this checks the *enrolled*
    # secret. Passing None says that outright; the old `session.get("tmp_totp_secret", "")` reached
    # the same place only because `verify_totp` falls back to the user's secret on an empty one.
    if not TOTP.verify_totp(request.form["totp_token"], totp_secret=None, user=current_user) and not TOTP.verify_recovery_code(
        request.form["totp_token"], user=current_user
    ):
        return handle_error("The totp token is invalid.", "profile")

    try:
        API_CLIENT.update_user(
            current_user.get_id(),
            totp_secret=None,
            theme=current_user.theme,
            method=current_user.method,
            language=current_user.language,
        )
    except (ApiClientError, ApiUnavailableError) as e:
        return handle_error(f"Couldn't disable the two-factor authentication: {e.message}", "profile")

    session["mfa_validated"] = False

    flash("The two-factor authentication has been successfully disabled.")
    return redirect(url_for("profile.profile_page") + "#security")


@profile.route("/profile/totp-enable", methods=["POST"])
@login_required
def totp_enable():
    if API_CLIENT.readonly:
        return handle_error("Database is in read-only mode", "profile")

    if bool(current_user.totp_secret):
        return handle_error("Two-factor authentication is already enabled.", "profile")

    verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/totp-enable.", redirect_url="profile")
    verify_data_in_form(data={"totp_token": None}, err_message="Missing totp token parameter on /profile/totp-enable.", redirect_url="profile")

    if not current_user.check_password(request.form["password"]):
        return handle_error("The current password is incorrect.", "profile")

    candidate = _stored_totp_candidate()
    if not candidate:
        # Nothing in flight: the session was cleared, or this POST never had a matching render.
        # Saying so beats falling through to `verify_totp`, which would treat an empty secret as
        # "check the enrolled one" and look up a secret that does not exist yet.
        return handle_error("The two-factor enrolment expired. Reload the page and scan the new QR code.", "profile")

    if not TOTP.verify_totp(request.form["totp_token"], totp_secret=candidate, user=current_user) and not TOTP.verify_recovery_code(
        request.form["totp_token"], user=current_user
    ):
        return handle_error("The totp token is invalid.", "profile")

    totp_recovery_codes = TOTP.generate_recovery_codes()
    totp_secret = _discard_totp_candidate()

    try:
        API_CLIENT.update_user(
            current_user.get_id(),
            totp_secret=totp_secret,
            theme=current_user.theme,
            totp_recovery_codes=totp_recovery_codes,
            method=current_user.method,
            language=current_user.language,
        )
    except (ApiClientError, ApiUnavailableError) as e:
        return handle_error(f"Couldn't enable the two-factor authentication: {e.message}", "profile")

    session["mfa_validated"] = True
    session["totp_refreshed"] = True
    session["decrypted_recovery_codes"] = totp_recovery_codes

    flash("The two-factor authentication has been successfully enabled.")
    return redirect(url_for("profile.profile_page") + "#security")


@profile.route("/profile/edit", methods=["POST"])
@login_required
def edit_profile():
    if API_CLIENT.readonly:
        return handle_error("Database is in read-only mode", "profile")

    user_data = {
        "username": current_user.get_id(),
        "email": current_user.email,
        "totp_secret": current_user.totp_secret,
        "method": current_user.method,
        "theme": current_user.theme,
        "language": current_user.language,
    }

    if "username" in request.form:
        verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/edit.", redirect_url="profile")

        if not current_user.check_password(request.form["password"]):
            return handle_error("The current password is incorrect.", "profile")

        verify_data_in_form(data={"email": None}, err_message="Missing email parameter on /profile/edit.", redirect_url="profile")

        if request.form["email"] and request.form["email"] != current_user.email:
            if len(request.form["email"]) > 256:
                return handle_error("The email is too long. It must be less than 256 characters.", "profile")
            user_data["email"] = request.form["email"] or None

        if request.form["username"] and request.form["username"] != current_user.get_id():
            if len(request.form["username"]) > 256:
                return handle_error("The username is too long. It must be less than 256 characters.", "profile")
            user_data["username"] = request.form["username"]

        if request.form["email"] == (current_user.email or "") and request.form["username"] == current_user.get_id():
            return handle_error("The username and email are the same as the current ones.", "profile")
    elif "new_password" in request.form:
        verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/edit.", redirect_url="profile")

        if not current_user.check_password(request.form["password"]):
            return handle_error("The current password is incorrect.", "profile")

        verify_data_in_form(
            data={"new_password_confirm": None},
            err_message="Missing new password confirm parameter on /profile/edit.",
            redirect_url="profile",
        )

        if request.form["new_password"] != request.form["new_password_confirm"]:
            return handle_error("The passwords do not match the confirm password.", "profile")
        elif not USER_PASSWORD_RX.match(request.form["new_password"]):
            return handle_error(
                "The new password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-).",
                "profile",
            )
        elif password_exceeds_bcrypt_limit(request.form["new_password"]):
            LOGGER.warning(
                f"Rejected password change for user {current_user.get_id()}: new password is "
                f"{len(request.form['new_password'].encode('utf-8'))} bytes, over bcrypt's {MAX_PASSWORD_BYTES}-byte limit."
            )
            return handle_error(
                f"The new password is too long. It must not exceed {MAX_PASSWORD_BYTES} bytes (bcrypt's hard limit); "
                "accented or emoji characters count as several bytes each.",
                "profile",
            )
        elif current_user.check_password(request.form["new_password"]):
            return handle_error("The new password is the same as the current one.", "profile")

        user_data["password"] = gen_password_hash(request.form["new_password"])
    elif "theme" in request.form:
        if request.form["theme"] not in ("dark", "light"):
            return handle_error("The theme is invalid.", "profile")

        user_data["theme"] = request.form["theme"]
    else:
        return handle_error("No fields were updated.", "profile")

    try:
        api_data = {k: (v.decode("utf-8") if isinstance(v, bytes) else v) for k, v in user_data.items()}
        API_CLIENT.update_user(api_data.pop("username"), **api_data, old_username=current_user.get_id())
    except (ApiClientError, ApiUnavailableError) as e:
        return handle_error(f"Couldn't update the {current_user.get_id()} user: {e.message}", "profile")

    flash("The profile has been successfully updated.")

    if "new_password" in request.form:
        # A password change has to take the user's other sessions with it. Without this, someone who
        # changed their password *because* they believed it had leaked kept every session an attacker
        # already held -- live for up to SESSION_ABSOLUTE_HOURS -- behind a success message that said
        # nothing had survived.
        try:
            other_ids = [
                db_session["id"] for db_session in API_CLIENT.get_user_sessions(current_user.username) if db_session["id"] != session.get("session_id")
            ]
            err = revoke_sessions(other_ids)
        except (ApiClientError, ApiUnavailableError) as e:
            err = e.message

        if err:
            # Deliberate divergence from dev 9603eeb84, which logs and continues. Keep both halves:
            #  * the log line reaches an operator who is not watching, while the only person who can
            #    act -- log out everywhere, rotate again, call support -- is the user, and they would
            #    otherwise be looking at an unqualified success message;
            #  * the redirect goes to /profile rather than /logout because logout.py calls
            #    session.clear(), which destroys Flask's _flashes *and* our own
            #    session["flash_messages"] -- a warning flashed on the way out is never rendered
            #    (measured: .cache/results-2026-08-20/flash-survives-logout.py). /profile is also
            #    where "Wipe other sessions" is, i.e. the action this warning asks for.
            # The password change itself stands either way; it already succeeded above.
            LOGGER.error(f"Couldn't revoke the other sessions after the password change: {err}")
            flash(
                "Your password was changed, but your other sessions could not be revoked. "
                'Use "Wipe other sessions" below and check the list of active sessions.',
                "error",
            )
            # Returning here also means the session rows are deliberately NOT deleted. It is the
            # revocation that stops a session, not the row: deleting the rows now would remove the
            # list the user needs in order to act, while ending exactly nothing. Not an omission.
            return redirect(url_for("profile.profile_page") + "#sessions")

        try:
            API_CLIENT.delete_user_sessions(current_user.username, keep_session_id=session.get("session_id"))
        except (ApiClientError, ApiUnavailableError) as e:
            # They are revoked already, so what is left stale is the session *list*, not a usable
            # session. Worth a log line, not worth stranding the user after a successful change.
            LOGGER.error(f"Couldn't delete the other session rows after the password change: {e.message}")

        return redirect(url_for("logout.logout_page"))

    return redirect(url_for("profile.profile_page"))


@profile.route("/profile/wipe-other-sessions", methods=["POST"])
@login_required
def wipe_old_sessions():
    if API_CLIENT.readonly:
        return handle_error("Database is in read-only mode", "profile")

    verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/wipe-other-sessions.", redirect_url="profile")

    if not current_user.check_password(request.form["password"]):
        return handle_error("The current password is incorrect.", "profile")

    try:
        other_ids = [db_session["id"] for db_session in API_CLIENT.get_user_sessions(current_user.username) if db_session["id"] != session.get("session_id")]
        # Revoke before deleting: the ids come from the rows we are about to remove, and a failure
        # here must abort rather than leave sessions deleted server-side but still presentable.
        err = revoke_sessions(other_ids)
        if err:
            return handle_error(f"Couldn't revoke the other sessions: {err}", "profile")
        API_CLIENT.delete_user_sessions(current_user.username, keep_session_id=session.get("session_id"))
    except (ApiClientError, ApiUnavailableError) as e:
        return handle_error(f"Couldn't wipe the other sessions: {e.message}", "profile")

    flash("The other sessions have been successfully wiped.")
    return redirect(url_for("profile.profile_page") + "#sessions")


# ── Passkeys and security keys ──────────────────────────────────────
#
# Enrollment is gated on the current password, the same inline re-authentication every other
# sensitive action on this page uses.


@profile.route("/profile/webauthn/register/options", methods=["POST"])
@login_required
@cors_required
def webauthn_register_options():
    if API_CLIENT.readonly:
        return jsonify({"message": "Database is in read-only mode"}), 403

    password = (request.get_json(silent=True) or {}).get("password", "")
    if not current_user.check_password(password):
        return jsonify({"message": "The current password is incorrect."}), 403

    try:
        options, user_handle = WEBAUTHN.registration_options(current_user.get_id(), _list_credentials())
    except WebauthnDisabledError:
        return jsonify({"message": "WebAuthn is not configured"}), 404

    # Kept server-side: the handle must be the one we issued, not one the browser echoes back.
    session["webauthn_pending_handle"] = user_handle

    return current_app.response_class(options, mimetype="application/json")


@profile.route("/profile/webauthn/register/verify", methods=["POST"])
@login_required
@cors_required
def webauthn_register_verify():
    if API_CLIENT.readonly:
        return jsonify({"message": "Database is in read-only mode"}), 403

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("credential"), dict):
        return jsonify({"message": "Malformed registration response"}), 400

    user_handle = session.pop("webauthn_pending_handle", None)
    if not user_handle:
        return jsonify({"message": "No pending registration"}), 400

    name = (payload.get("name") or "").strip()[:256] or "Passkey"

    try:
        verified = WEBAUTHN.verify_registration(payload["credential"])
    except WebauthnDisabledError:
        return jsonify({"message": "WebAuthn is not configured"}), 404
    except WebauthnCeremonyError as e:
        WEBAUTHN.log_failure(str(e))
        return jsonify({"message": "Couldn't register this passkey, please try again"}), 400

    transports = (payload["credential"].get("response") or {}).get("transports") or None

    try:
        API_CLIENT.create_user_webauthn_credential(current_user.get_id(), user_handle=user_handle, name=name, transports=transports, **verified)
    except (ApiClientError, ApiUnavailableError) as e:
        LOGGER.error(f"Couldn't save the passkey: {e.message}")
        return jsonify({"message": f"Couldn't save this passkey: {e.message}"}), 400

    # Enrolling from an authenticated session proves the same thing the second factor would.
    session["mfa_validated"] = True

    LOGGER.info(f"User {current_user.get_id()} registered a new passkey ({name})")
    flash("The passkey has been successfully registered.")
    return jsonify({"redirect": url_for("profile.profile_page") + "#security"})


@profile.route("/profile/webauthn/rename", methods=["POST"])
@login_required
def webauthn_rename():
    if API_CLIENT.readonly:
        return handle_error("Database is in read-only mode", "profile")

    verify_data_in_form(data={"credential_id": None, "name": None}, err_message="Missing parameters on /profile/webauthn/rename.", redirect_url="profile")

    name = request.form["name"].strip()[:256]
    if not name:
        return handle_error("The passkey name cannot be empty.", "profile")

    try:
        API_CLIENT.update_user_webauthn_credential(current_user.get_id(), request.form["credential_id"], name=name)
    except (ApiClientError, ApiUnavailableError) as e:
        return handle_error(f"Couldn't rename the passkey: {e.message}", "profile")

    flash("The passkey has been successfully renamed.")
    return redirect(url_for("profile.profile_page") + "#security")


@profile.route("/profile/webauthn/delete", methods=["POST"])
@login_required
def webauthn_delete():
    if API_CLIENT.readonly:
        return handle_error("Database is in read-only mode", "profile")

    verify_data_in_form(data={"credential_id": None, "password": None}, err_message="Missing parameters on /profile/webauthn/delete.", redirect_url="profile")

    if not current_user.check_password(request.form["password"]):
        return handle_error("The current password is incorrect.", "profile")

    try:
        API_CLIENT.delete_user_webauthn_credential(current_user.get_id(), request.form["credential_id"])
    except (ApiClientError, ApiUnavailableError) as e:
        return handle_error(f"Couldn't delete the passkey: {e.message}", "profile")

    flash("The passkey has been successfully deleted.")
    return redirect(url_for("profile.profile_page") + "#security")
