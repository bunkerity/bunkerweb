from flask import Blueprint, redirect, session, url_for
from flask_login import current_user, logout_user

from app.utils import LOGGER, revoke_sessions

logout = Blueprint("logout", __name__)


@logout.route("/logout")
def logout_page():
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
        response = redirect(url_for("login.login_page"))
        response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage", "executionContexts"'
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except BaseException as e:
        LOGGER.error(f"Error during logout: {e}")
        session.clear()
        logout_user()
        return redirect(url_for("login.login_page"))
