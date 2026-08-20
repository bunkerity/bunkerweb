from flask import Blueprint, redirect, request, session, url_for
from flask_login import current_user, logout_user

from app.utils import LOGGER, LOGIN_NOTICES, revoke_sessions

logout = Blueprint("logout", __name__)


@logout.route("/logout")
def logout_page():
    # A caller that has something left to tell the user passes ?reason=; it is forwarded to the
    # login page, which looks it up in LOGIN_NOTICES and renders a fixed translated banner. It has
    # to travel in the URL because session.clear() below destroys both flash stores -- a message
    # flashed before a logout is never rendered. Only known reasons are forwarded, so nothing
    # caller-supplied reaches the next page.
    reason = request.args.get("reason", "")
    login_url = url_for("login.login_page", **({"reason": reason} if reason in LOGIN_NOTICES else {}))

    try:
        if current_user.is_authenticated:
            # Track the revoked session ID to prevent token reuse (recorded in the session
            # backend, which expires the entry itself — see app.utils.revoke_sessions).
            if "session_id" in session:
                LOGGER.info(f"Revoking session ID {session['session_id']} for user {current_user.username}")
                err = revoke_sessions([session["session_id"]])
                if err:
                    LOGGER.error(f"Couldn't revoke the session: {err}")

            # Log the logout event
            LOGGER.info(f"User {current_user.username} logged out")

        # Clear session and logout user
        session.clear()
        logout_user()

        # Add security headers to prevent cached credentials
        response = redirect(login_url)
        response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage", "executionContexts"'
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except BaseException as e:
        LOGGER.error(f"Error during logout: {e}")
        session.clear()
        logout_user()
        return redirect(login_url)
