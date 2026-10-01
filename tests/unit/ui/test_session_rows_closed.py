"""N-M2: a session that ended must leave the Sessions list.

`GET /users/admin/sessions` listed 33 rows on the dev stack, sessions ended by logout among them:
logout recorded `revoked:<id>` in the session store and never touched the `bw_ui_user_sessions`
row. "Wipe other sessions" and a password change already delete the rows they revoke; logout now
closes its own, and the profile list drops rows whose session has expired on its own (idle past
the session lifetime), which no request ever closes.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import session
from flask_login import UserMixin, login_user

from app.api_client import ApiClientError, ApiUnavailableError
from test_webauthn_routes import _load, _make_app

LIFETIME = timedelta(hours=12)


class _User(UserMixin):
    username = "alice"
    totp_secret = None
    webauthn_credentials_count = 0

    def get_id(self):
        return self.username


@pytest.fixture
def api():
    client = Mock()
    client.readonly = False
    return client


def _logout(api):
    module = _load("logout", api)
    app = _make_app(module, "logout", user=_User())
    app.add_url_rule("/login", endpoint="login.login_page", view_func=lambda: "")
    with app.test_request_context("/logout"):
        login_user(_User())
        session["session_id"] = 7
        with patch.object(module, "revoke_sessions", return_value=""):
            response = module.logout_page()
        assert "session_id" not in session
    return response


def test_logout_closes_its_own_row(api):
    response = _logout(api)

    api.delete_user_session.assert_called_once_with("alice", 7)
    assert response.status_code == 302


def test_logout_still_logs_out_when_the_row_cannot_be_closed(api):
    """The revocation already ended the session; a stale row is not worth a failed logout."""
    api.delete_user_session.side_effect = ApiClientError("boom", 500)

    response = _logout(api)

    assert response.status_code == 302
    assert response.location.startswith("/login")


def test_the_ui_client_deletes_one_session_row():
    from app.api_client import ApiClient

    client = ApiClient.__new__(ApiClient)
    with patch.object(ApiClient, "_delete", return_value={"status": "success"}) as delete:
        client.delete_user_session("alice", 7)

    delete.assert_called_once_with("/users/alice/sessions/7")


# ------------------------------------------------------------------------------ profile list


def _row(session_id, idle):
    moment = (datetime.now().astimezone() - idle).isoformat()
    return {"id": session_id, "ip": f"10.0.0.{session_id}", "user_agent": "", "creation_date": moment, "last_activity": moment}


def _listed(api, rows, current_id=1):
    module = _load("profile", api)
    api.get_user_sessions.return_value = rows
    app = _make_app(module, "profile")
    app.config["PERMANENT_SESSION_LIFETIME"] = LIFETIME
    with app.test_request_context("/profile"):
        session["session_id"] = current_id
        with patch.object(module, "current_user", SimpleNamespace(username="alice")):
            generator, total = module.get_last_sessions(1, 50)
            return [int(entry["ip"].rsplit(".", 1)[1]) for entry in generator], total


def test_the_profile_lists_only_live_sessions(api):
    listed, total = _listed(api, [_row(1, timedelta(minutes=1)), _row(2, timedelta(hours=1)), _row(3, LIFETIME + timedelta(minutes=5))])

    assert listed == [1, 2], "a session idle past the lifetime has expired and must not be listed"
    assert total == 2


def test_the_current_session_is_always_listed(api):
    listed, _ = _listed(api, [_row(1, LIFETIME + timedelta(hours=1))], current_id=1)

    assert listed == [1]


# ------------------------------------------------------------------ absolute-lifetime logout


def _expire(api):
    """Run main.py's `_enforce_session_lifetime` on a session past SESSION_ABSOLUTE_HOURS."""
    from flask import Flask

    from test_session_plumbing import MAIN, _shipped

    app = Flask("bw_ui_absolute_lifetime_test")
    app.secret_key = "test"
    app.config["SESSION_ABSOLUTE_SECONDS"] = 3600
    user = SimpleNamespace(is_authenticated=True, get_id=lambda: "alice", username="alice")
    namespace = _shipped(
        MAIN,
        ("_enforce_session_lifetime",),
        {
            "app": app,
            "current_user": user,
            "session": session,
            "datetime": datetime,
            "logout_user": Mock(),
            "LOGGER": Mock(),
            "_delete_session_store_entry": Mock(),
            "_rotate_session_id": Mock(),
            "API_CLIENT": api,
            "ApiClientError": ApiClientError,
            "ApiUnavailableError": ApiUnavailableError,
        },
    )
    with app.test_request_context("/home"):
        session["creation_date"] = datetime.now().astimezone() - timedelta(hours=2)
        session["session_id"] = 7
        return namespace["_enforce_session_lifetime"]()


def test_the_absolute_lifetime_logout_closes_its_row(api):
    assert _expire(api) is True

    api.delete_user_session.assert_called_once_with("alice", 7)


def test_the_absolute_lifetime_logout_survives_a_row_it_cannot_close(api):
    api.delete_user_session.side_effect = ApiUnavailableError("down")

    assert _expire(api) is True
