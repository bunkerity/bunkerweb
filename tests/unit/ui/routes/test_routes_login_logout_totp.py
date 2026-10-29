"""Signing in, signing out and the second factor."""

from unittest.mock import MagicMock

import pytest

from _ui_routes_helpers import FakeUser


def _flashed(h, client):
    return [message for message, _category in h.flashes(client)]


@pytest.fixture
def login(h, tmp_path, monkeypatch):
    module = h.routes.login
    monkeypatch.setattr(module, "BISCUIT_PRIVATE_KEY_FILE", tmp_path / "missing.key")
    user = FakeUser("alice", language="en")
    h.db.get_ui_user.side_effect = lambda username=None: (user if username in (None, "alice") else None)
    h.db.mark_ui_user_login.return_value = 41
    h.db.update_ui_user.return_value = ""
    h.users["alice"] = user
    h.login_user = user
    return module


FORM = {"username": "alice", "password": "Correct-Horse1!"}


def _next(response):
    return response.headers["Location"]


def test_login_page_without_any_user_redirects_to_setup(h, login):
    h.db.get_ui_user.side_effect = None
    h.db.get_ui_user.return_value = None

    response = h.client(None).get("/login")

    assert response.status_code == 302 and response.headers["Location"].endswith("/setup")


def test_setup_redirect_carries_only_a_known_reason(h, login):
    h.db.get_ui_user.side_effect = None
    h.db.get_ui_user.return_value = None

    known = h.client(None).get("/login?reason=session_expired")
    unknown = h.client(None).get("/login?reason=%3Cscript%3E")

    assert known.headers["Location"].endswith("/setup?reason=session_expired")
    assert unknown.headers["Location"].endswith("/setup")


def test_login_page_renders_for_an_anonymous_visitor(h, login):
    response = h.client(None).get("/login?reason=session_expired")

    assert response.status_code == 200
    template, context = h.renders[-1]
    assert template == "login.html" and context["is_totp"] is False
    assert "Your session ended" in context["notice"]


def test_login_page_never_echoes_an_unknown_reason(h, login):
    h.client(None).get("/login?reason=<b>pwned</b>")

    assert "notice" not in h.renders[-1][1]


def test_an_authenticated_visitor_is_sent_home(h, login):
    response = h.client("alice").get("/login")

    assert response.status_code == 302 and response.headers["Location"].endswith("/home")


def test_a_successful_login_rotates_the_session_and_stores_the_login(h, login):
    client = h.client(None)

    response = client.post("/login", data=FORM | {"theme": "dark", "language": "fr"})

    assert response.status_code == 302 and "/loading?next=/home" in _next(response)
    with client.session_transaction() as sess:
        assert sess["session_id"] == 41 and sess["totp_validated"] is False and sess["_user_id"] == "alice"
        assert sess.permanent is False
    update = h.db.update_ui_user.call_args.kwargs
    assert update["theme"] == "dark" and update["language"] == "fr" and update["old_username"] == "alice"
    assert any("enable two-factor authentication" in message for message in _flashed(h, client))


def test_login_ignores_an_invalid_theme(h, login):
    h.client(None).post("/login", data=FORM | {"theme": "neon"})

    assert h.db.update_ui_user.call_args.kwargs["theme"] == "light"


@pytest.mark.parametrize("form", [{"username": "alice", "password": "wrong"}, {"username": "ghost", "password": "Correct-Horse1!"}])
def test_a_failed_login_is_a_401_that_does_not_say_which_part_was_wrong(h, login, form):
    client = h.client(None)

    response = client.post("/login", data=form)

    assert response.status_code == 401
    assert h.renders[-1][1]["error"] == "Invalid username or password"
    h.db.mark_ui_user_login.assert_not_called()
    with client.session_transaction() as sess:
        assert "_user_id" not in sess


def test_a_post_without_credentials_just_shows_the_form(h, login):
    response = h.client(None).post("/login", data={"username": "alice"})

    assert response.status_code == 200
    h.db.mark_ui_user_login.assert_not_called()


def test_remember_me_makes_the_session_permanent(h, login):
    client = h.client(None)

    client.post("/login", data=FORM | {"remember-me": "on"})

    with client.session_transaction() as sess:
        assert sess.permanent is True


def test_always_remember_environment_forces_it(h, login, monkeypatch):
    monkeypatch.setenv("ALWAYS_REMEMBER", "yes")
    client = h.client(None)

    client.post("/login", data=FORM)

    with client.session_transaction() as sess:
        assert sess.permanent is True


def test_a_login_mark_failure_still_logs_the_user_in_without_a_session_id(h, login):
    h.db.mark_ui_user_login.return_value = "database locked"
    client = h.client(None)

    response = client.post("/login", data=FORM)

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert "session_id" not in sess


@pytest.mark.parametrize(
    "target, expected",
    [
        ("/services", "/loading?next=/services"),
        ("https://evil.example/", "/loading?next=/home"),
        ("//evil.example/x", "/loading?next=/home"),
        ("/loading?next=/bans", "/loading?next=/bans"),
    ],
)
def test_login_redirects_only_to_internal_targets(h, login, target, expected):
    response = h.client(None).post("/login", data=FORM, query_string={"next": target})

    assert _next(response) == expected


def test_login_adds_a_biscuit_token_when_the_key_exists(h, login, tmp_path):
    key_file = tmp_path / "biscuit.key"
    key_file.write_text("deadbeef\n")
    login.BISCUIT_PRIVATE_KEY_FILE = key_file
    login.PrivateKey = MagicMock()
    login.BiscuitTokenFactory = MagicMock()
    login.BiscuitTokenFactory.return_value.create_token_for_role.return_value.to_base64.return_value = "tok"
    h.login_user.admin = True
    client = h.client(None)

    client.post("/login", data=FORM)

    login.PrivateKey.assert_called_once_with("deadbeef")
    login.BiscuitTokenFactory.return_value.create_token_for_role.assert_called_once_with("super_admin", "alice")
    with client.session_transaction() as sess:
        assert sess["biscuit_token"] == "tok"


def test_a_biscuit_failure_does_not_prevent_the_login(h, login, tmp_path):
    key_file = tmp_path / "biscuit.key"
    key_file.write_text("x")
    login.BISCUIT_PRIVATE_KEY_FILE = key_file
    login.PrivateKey = MagicMock(side_effect=ValueError("bad key"))
    client = h.client(None)

    response = client.post("/login", data=FORM)

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert "biscuit_token" not in sess


# --------------------------------------------------------------------------------------
# logout
# --------------------------------------------------------------------------------------
def test_logout_revokes_the_session_clears_the_site_data_and_redirects(h):
    h.routes.logout.revoke_sessions = MagicMock(return_value="")
    client = h.client("alice")
    with client.session_transaction() as sess:
        sess["session_id"] = "sid-9"

    response = client.get("/logout")

    h.routes.logout.revoke_sessions.assert_called_once_with(["sid-9"])
    assert response.status_code == 302 and response.headers["Location"].endswith("/login")
    assert "storage" in response.headers["Clear-Site-Data"]
    assert "no-store" in response.headers["Cache-Control"]
    with client.session_transaction() as sess:
        assert "_user_id" not in sess and "session_id" not in sess


def test_logout_still_signs_out_when_revocation_fails(h):
    h.routes.logout.revoke_sessions = MagicMock(return_value="no backend")
    client = h.client("alice")
    with client.session_transaction() as sess:
        sess["session_id"] = "sid-9"

    response = client.get("/logout")

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert "_user_id" not in sess


def test_logout_as_a_visitor_is_harmless(h):
    h.routes.logout.revoke_sessions = MagicMock()

    response = h.client(None).get("/logout")

    assert response.status_code == 302
    h.routes.logout.revoke_sessions.assert_not_called()


# --------------------------------------------------------------------------------------
# totp
# --------------------------------------------------------------------------------------
def test_totp_page_is_skipped_for_a_user_without_two_factor(h):
    response = h.client("alice").get("/totp")

    assert response.headers["Location"].endswith("/home")


def test_totp_page_is_skipped_once_validated(h):
    client = h.client("alice", totp_secret="S")
    with client.session_transaction() as sess:
        sess["totp_validated"] = True

    assert client.get("/totp").headers["Location"].endswith("/home")


def test_totp_page_asks_for_the_token(h):
    assert h.client("alice", totp_secret="S").get("/totp").status_code == 200
    assert h.renders[-1][0] == "totp.html"


def test_a_valid_token_validates_the_session(h):
    h.totp.verify_totp.return_value = True
    client = h.client("alice", totp_secret="S")

    response = client.post("/totp", data={"totp_token": "123456", "next": "/services"})

    assert "/loading?next=/services" in response.headers["Location"]
    with client.session_transaction() as sess:
        assert sess["totp_validated"] is True


def test_an_invalid_token_is_refused_and_not_validated(h):
    h.totp.verify_totp.return_value = False
    h.totp.verify_recovery_code.return_value = None
    client = h.client("alice", totp_secret="S")

    response = client.post("/totp", data={"totp_token": "000000"})

    assert response.headers["Location"].endswith("/totp")
    assert "The token is invalid." in _flashed(h, client)
    with client.session_transaction() as sess:
        assert not sess.get("totp_validated")


def test_a_recovery_code_is_consumed(h):
    h.totp.verify_totp.return_value = False
    h.totp.verify_recovery_code.return_value = "hash"
    h.db.use_ui_user_recovery_code.return_value = ""
    client = h.client("alice", totp_secret="S", list_recovery_codes=["a", "b"])

    client.post("/totp", data={"totp_token": "recovery"})

    h.db.use_ui_user_recovery_code.assert_called_once_with("alice", "hash")
    assert any("You have 2 left" in message for message in _flashed(h, client))


def test_a_recovery_code_that_cannot_be_consumed_is_refused(h):
    h.totp.verify_totp.return_value = False
    h.totp.verify_recovery_code.return_value = "hash"
    h.db.use_ui_user_recovery_code.return_value = "error"
    client = h.client("alice", totp_secret="S")

    response = client.post("/totp", data={"totp_token": "recovery"})

    assert response.headers["Location"].endswith("/totp")
    with client.session_transaction() as sess:
        assert not sess.get("totp_validated")


def test_a_read_only_database_keeps_the_recovery_code_valid(h):
    h.totp.verify_totp.return_value = False
    h.totp.verify_recovery_code.return_value = "hash"
    h.db.use_ui_user_recovery_code.return_value = "readonly"
    h.db.readonly = True
    client = h.client("alice", totp_secret="S")

    client.post("/totp", data={"totp_token": "recovery"})

    assert "The database is read-only, the recovery code you used stays valid." in _flashed(h, client)
    with client.session_transaction() as sess:
        assert sess["totp_validated"] is True


def test_totp_redirect_target_is_sanitized(h):
    h.totp.verify_totp.return_value = True

    response = h.client("alice", totp_secret="S").post("/totp", data={"totp_token": "1", "next": "https://evil.example"})

    assert "next=/home" in response.headers["Location"]
