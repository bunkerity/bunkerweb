from contextlib import suppress
from datetime import datetime
from typing import Dict, Generator, Tuple, Union
from flask import Blueprint, Response, jsonify, redirect, render_template, request, stream_with_context, url_for, session
from flask_login import current_user, login_required
from user_agents import parse

from app.models.totp import totp as TOTP

from app.dependencies import DATA, DB
from app.utils import USER_PASSWORD_RX, flash, gen_password_hash

from app.routes.utils import cors_required, handle_error, verify_data_in_form

profile = Blueprint("profile", __name__)


def get_last_sessions(page: int, per_page: int) -> Tuple[Generator[Dict[str, Union[str, bool]], None, None], int]:
    db_sessions = DB.get_ui_user_sessions(current_user.username, session.get("session_id"))
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
        session["tmp_totp_secret"] = TOTP.generate_totp_secret()
        totp_qr_image = TOTP.generate_qrcode(current_user.get_id(), session["tmp_totp_secret"])

    last_sessions, total_sessions = get_last_sessions(1, 3)

    return render_template(
        "profile.html",
        is_totp=bool(current_user.totp_secret),
        totp_qr_image=totp_qr_image,
        totp_recovery_codes=session.pop("decrypted_recovery_codes", current_user.list_recovery_codes),
        is_recovery_refreshed=session.pop("totp_refreshed", False),
        totp_secret=TOTP.get_totp_pretty_key(session.get("tmp_totp_secret", "")),
        last_sessions=last_sessions,
        total_sessions=total_sessions,
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
    if DB.readonly:
        return handle_error("Database is in read-only mode", "profile")

    if not bool(current_user.totp_secret):
        return handle_error("Two-factor authentication is not enabled.", "profile")

    verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/totp-refresh.", redirect_url="profile")

    if not current_user.check_password(request.form["password"]):
        return handle_error("The current password is incorrect.", "profile")

    totp_recovery_codes = TOTP.generate_recovery_codes()

    ret = DB.refresh_ui_user_recovery_codes(current_user.get_id(), totp_recovery_codes)
    if ret:
        return handle_error(f"Couldn't refresh the recovery codes in the database: {ret}", "profile")

    session["totp_refreshed"] = True
    session["decrypted_recovery_codes"] = totp_recovery_codes

    flash("The recovery codes have been successfully refreshed. The old ones are no longer valid.")
    return redirect(url_for("profile.profile_page") + "#security")


@profile.route("/profile/totp-disable", methods=["POST"])
@login_required
def totp_disable():
    if DB.readonly:
        return handle_error("Database is in read-only mode", "profile")

    if not bool(current_user.totp_secret):
        return handle_error("Two-factor authentication is not enabled.", "profile")

    verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/totp-disable.", redirect_url="profile")

    if not current_user.check_password(request.form["password"]):
        return handle_error("The current password is incorrect.", "profile")

    verify_data_in_form(data={"totp_token": None}, err_message="Missing totp token parameter on /profile/totp-enable.", redirect_url="profile")

    if not TOTP.verify_totp(request.form["totp_token"], totp_secret=session.get("tmp_totp_secret", ""), user=current_user) and not TOTP.verify_recovery_code(
        request.form["totp_token"], user=current_user
    ):
        return handle_error("The totp token is invalid.", "profile")

    ret = DB.update_ui_user(
        current_user.get_id(), current_user.password.encode("utf-8"), None, theme=current_user.theme, method=current_user.method, language=current_user.language
    )
    if ret:
        return handle_error(f"Couldn't disable the two-factor authentication in the database: {ret}", "profile")

    session["totp_validated"] = False

    flash("The two-factor authentication has been successfully disabled.")
    return redirect(url_for("profile.profile_page") + "#security")


@profile.route("/profile/totp-enable", methods=["POST"])
@login_required
def totp_enable():
    if DB.readonly:
        return handle_error("Database is in read-only mode", "profile")

    if bool(current_user.totp_secret):
        return handle_error("Two-factor authentication is already enabled.", "profile")

    verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/totp-enable.", redirect_url="profile")
    verify_data_in_form(data={"totp_token": None}, err_message="Missing totp token parameter on /profile/totp-enable.", redirect_url="profile")

    if not current_user.check_password(request.form["password"]):
        return handle_error("The current password is incorrect.", "profile")

    if not TOTP.verify_totp(request.form["totp_token"], totp_secret=session.get("tmp_totp_secret", ""), user=current_user) and not TOTP.verify_recovery_code(
        request.form["totp_token"], user=current_user
    ):
        return handle_error("The totp token is invalid.", "profile")

    totp_recovery_codes = TOTP.generate_recovery_codes()
    totp_secret = session.pop("tmp_totp_secret", "")

    ret = DB.update_ui_user(
        current_user.get_id(),
        current_user.password.encode("utf-8"),
        totp_secret,
        theme=current_user.theme,
        totp_recovery_codes=totp_recovery_codes,
        method=current_user.method,
        language=current_user.language,
    )
    if ret:
        return handle_error(f"Couldn't enable the two-factor authentication in the database: {ret}", "profile")

    session["totp_validated"] = True
    session["totp_refreshed"] = True
    session["decrypted_recovery_codes"] = totp_recovery_codes

    flash("The two-factor authentication has been successfully enabled.")
    return redirect(url_for("profile.profile_page") + "#security")


@profile.route("/profile/edit", methods=["POST"])
@login_required
def edit_profile():
    if DB.readonly:
        return handle_error("Database is in read-only mode", "profile")

    user_data = {
        "username": current_user.get_id(),
        "password": current_user.password.encode("utf-8"),
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
        elif current_user.check_password(request.form["new_password"]):
            return handle_error("The new password is the same as the current one.", "profile")

        user_data["password"] = gen_password_hash(request.form["new_password"])
    elif "theme" in request.form:
        if request.form["theme"] not in ("dark", "light"):
            return handle_error("The theme is invalid.", "profile")

        user_data["theme"] = request.form["theme"]
    else:
        return handle_error("No fields were updated.", "profile")

    ret = DB.update_ui_user(**user_data, old_username=current_user.get_id())
    if ret:
        return handle_error(f"Couldn't update the {current_user.get_id()} user in the database: {ret}", "profile")

    flash("The profile has been successfully updated.")

    if "new_password" in request.form:
        return redirect(url_for("logout.logout_page"))

    return redirect(url_for("profile.profile_page"))


@profile.route("/profile/wipe-other-sessions", methods=["POST"])
@login_required
def wipe_old_sessions():
    if DB.readonly:
        return handle_error("Database is in read-only mode", "profile")

    verify_data_in_form(data={"password": None}, err_message="Missing current password parameter on /profile/wipe-other-sessions.", redirect_url="profile")

    if not current_user.check_password(request.form["password"]):
        return handle_error("The current password is incorrect.", "profile")

    DATA["REVOKED_SESSIONS"] = [
        db_session["id"] for db_session in DB.get_ui_user_sessions(current_user.username) if db_session["id"] != session.get("session_id")
    ]

    ret = DB.delete_ui_user_old_sessions(current_user.username)
    if ret:
        return handle_error(f"Couldn't wipe the other sessions in the database: {ret}", "profile")

    flash("The other sessions have been successfully wiped.")
    return redirect(url_for("profile.profile_page") + "#sessions")
