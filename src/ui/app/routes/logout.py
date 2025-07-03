from flask import Blueprint, redirect, session, url_for
from flask_login import current_user, logout_user

from app.dependencies import DATA
from app.utils import LOGGER

logout = Blueprint("logout", __name__)


@logout.route("/logout")
def logout_page():
    try:
        if current_user.is_authenticated:
            DATA.load_from_file()

            # Track the revoked session ID to prevent token reuse
            if "session_id" in session:
                LOGGER.info(f"Revoking session ID {session['session_id']} for user {current_user.username}")
                if "REVOKED_SESSIONS" not in DATA:
                    DATA["REVOKED_SESSIONS"] = []
                if session["session_id"] not in DATA["REVOKED_SESSIONS"]:
                    DATA["REVOKED_SESSIONS"].append(session["session_id"])
                    # Save changes to the DATA file
                    DATA.write_to_file()

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
