"""M19 residual: the MFA reminder flashed at login spoke the previous language.

A language picked on the login page itself lives in `session["language"]` until the login saves it.
`_establish_session` clears the session and logs in the user object built from the stored record,
so the reminder, translated in that same request, resolved its locale from the user's *stored*
language (`app/i18n.resolve_locale`, step 2) instead of the one just picked. The logged-in user
object must carry the pick before anything is translated.

Loader and fixtures are `test_login_language.py`'s (H11, the same code path).
"""

from types import SimpleNamespace
from unittest.mock import patch

from flask import session

from test_login_language import app, login_module  # noqa: F401 -- pytest fixtures


def _login_recording_the_reminder_language(app, login, *, session_language, stored_language):  # noqa: F811
    login.API_CLIENT.get_admin_user.return_value = {"username": "admin"}
    login.API_CLIENT.get_user_for_auth.return_value = {
        "username": "admin",
        "password": "$2b$12$stubstubstubstubstubstubstubstubstubstubstubstubstubs",
        "email": None,
        "method": "manual",
        "admin": True,
        "theme": "light",
        "language": stored_language,
        "totp_secret": None,  # no second factor: the reminder path
        "webauthn_credentials_count": 0,
    }
    if "profile.profile_page" not in app.view_functions:
        app.add_url_rule("/profile", endpoint="profile.profile_page", view_func=lambda: "")  # the reminder links there
    logged_in = {}
    languages_seen = []

    def fake_establish_session(ui_user, user_data, *, mfa_done, remember_me):
        # The real one clears the session and calls login_user(ui_user): from here on
        # resolve_locale reads this object's `language`.
        session.clear()
        logged_in["user"] = ui_user
        return True

    def recording_translated(key, **variables):
        languages_seen.append(logged_in["user"].language)
        return None

    with app.test_request_context("/login", method="POST", data={"username": "admin", "password": "whatever"}):
        if session_language is not None:
            session["language"] = session_language
        with patch.object(login, "current_user", SimpleNamespace(is_authenticated=False, totp_secret=None, get_id=lambda: "admin")), patch.object(
            login, "_establish_session", side_effect=fake_establish_session
        ), patch.object(login, "checkpw", return_value=True), patch.object(login, "dismissed_notices", return_value={}), patch.object(
            login, "translated", side_effect=recording_translated
        ):
            login.login_page()

    login.API_CLIENT.update_user.reset_mock()
    assert languages_seen, "the MFA reminder was not built at all"
    return set(languages_seen)


def test_the_reminder_speaks_the_language_picked_on_the_login_page(app, login_module):  # noqa: F811
    assert _login_recording_the_reminder_language(app, login_module, session_language="de", stored_language="fr") == {"de"}


def test_without_a_pick_the_reminder_speaks_the_stored_language(app, login_module):  # noqa: F811
    assert _login_recording_the_reminder_language(app, login_module, session_language=None, stored_language="fr") == {"fr"}
