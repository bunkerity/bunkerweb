from flask import Blueprint, redirect, request, session, url_for
from flask_login import current_user, logout_user

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.i18n import locale_code
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

    # Resolved while the request is still whatever it was (an authenticated user's saved
    # language, or an anonymous pre-login pick) and carried to /login the same way `reason` is:
    # in the URL, not the session. `session["language"] = ...` below would not survive the trip
    # -- this response's own `Clear-Site-Data: "cookies"` header (a deliberate wipe, for stale
    # credentials) discards any cookie this response sets before the browser ever follows the
    # redirect, session included. Without this the next /login render falls straight to
    # `Accept-Language`/English even when the page the user just saw was fr (QA-UI-5 item 7).
    # `resolve_locale()` (app/i18n.py) never returns anything outside `SUPPORTED_LANGUAGE_CODES`,
    # so unlike `reason` above this needs no whitelist of its own -- `login_page` is the boundary
    # that actually receives untrusted input off this URL, and it re-validates there.
    login_url = url_for(
        "login.login_page",
        lang=locale_code(),
        **({"reason": reason} if reason in LOGIN_NOTICES else {}),
    )

    try:
        if current_user.is_authenticated:
            # Track the revoked session ID to prevent token reuse (recorded in the session
            # backend, which expires the entry itself — see app.utils.revoke_sessions).
            if "session_id" in session:
                LOGGER.info(f"Revoking session ID {session['session_id']} for user {current_user.username}")
                err = revoke_sessions([session["session_id"]])
                if err:
                    LOGGER.error(f"Couldn't revoke the session: {err}")
                # Its row is what the profile's Sessions list shows; a logged-out session is not
                # one (N-M2). The revocation above is what ends it, so a failure here only leaves
                # a stale row, not a reason to fail the logout.
                try:
                    API_CLIENT.delete_user_session(current_user.username, session["session_id"])
                except (ApiClientError, ApiUnavailableError) as e:
                    LOGGER.error(f"Couldn't close the session row: {e.message}")

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
