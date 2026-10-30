"""The /profile blueprint: account edits, two-factor management and session wiping."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

STRONG = "N3w-Passw0rd!"
CURRENT = "Correct-Horse1!"


@pytest.fixture
def profile(h, monkeypatch):
    module = h.routes.profile
    monkeypatch.setattr(module, "revoke_sessions", MagicMock(return_value=""))
    h.db.update_ui_user.return_value = ""
    h.db.get_ui_user_sessions.return_value = []
    h.totp.generate_totp_secret.return_value = "SECRET"
    h.totp.generate_qrcode.return_value = "qr"
    h.totp.get_totp_pretty_key.side_effect = lambda key: f"pretty:{key}"
    h.totp.generate_recovery_codes.return_value = ["c1", "c2"]
    return module


def _flashed(h, client):
    return [message for message, _category in h.flashes(client)]


# --------------------------------------------------------------------------------------
# page and session listing
# --------------------------------------------------------------------------------------
def test_profile_page_offers_a_totp_secret_to_a_user_without_two_factor(h, profile):
    client = h.client("alice")

    client.get("/profile")

    template, context = h.renders[-1]
    assert template == "profile.html" and context["is_totp"] is False
    assert context["totp_qr_image"] == "qr" and context["totp_secret"] == "pretty:SECRET"
    with client.session_transaction() as sess:
        assert sess["tmp_totp_secret"] == "SECRET"


def test_profile_page_does_not_generate_a_secret_when_two_factor_is_on(h, profile):
    h.client("alice", totp_secret="S", list_recovery_codes=["r1"]).get("/profile")

    context = h.renders[-1][1]
    assert context["is_totp"] is True and context["totp_qr_image"] == "" and context["totp_recovery_codes"] == ["r1"]
    h.totp.generate_totp_secret.assert_not_called()


def test_profile_page_shows_the_recovery_codes_stashed_by_a_refresh_exactly_once(h, profile):
    client = h.client("alice", totp_secret="S")
    with client.session_transaction() as sess:
        sess["decrypted_recovery_codes"] = ["fresh"]
        sess["totp_refreshed"] = True

    client.get("/profile")
    client.get("/profile")

    first, second = h.renders[-2][1], h.renders[-1][1]
    assert first["totp_recovery_codes"] == ["fresh"] and first["is_recovery_refreshed"] is True
    assert second["totp_recovery_codes"] == [] and second["is_recovery_refreshed"] is False


def test_profile_page_summarizes_the_last_sessions(h, profile):
    now = datetime.now().astimezone()
    h.db.get_ui_user_sessions.return_value = [
        {"id": i, "user_agent": f"ua{i}", "ip": f"10.0.0.{i}", "creation_date": now, "last_activity": now} for i in range(1, 6)
    ]
    client = h.client("alice")
    with client.session_transaction() as sess:
        sess["session_id"] = 1

    client.get("/profile")

    context = h.renders[-1][1]
    sessions = list(context["last_sessions"])
    assert context["total_sessions"] == 5 and len(sessions) == 3
    assert sessions[0]["current"] is True and sessions[1]["current"] is False
    assert sessions[0]["ip"] == "10.0.0.1" and sessions[0]["browser"] == "browser(ua1)"


def test_sessions_endpoint_streams_a_json_page(h, profile):
    now = datetime.now().astimezone()
    h.db.get_ui_user_sessions.return_value = [{"id": i, "user_agent": "ua", "ip": "1.1.1.1", "creation_date": now, "last_activity": now} for i in range(1, 8)]
    client = h.client("alice")
    with client.session_transaction() as sess:
        sess["session_id"] = 99

    response = client.get("/profile/sessions?page=2", headers={"Sec-Fetch-Mode": "cors"})

    assert response.mimetype == "application/json"
    assert len(response.get_json()) == 3


def test_sessions_endpoint_rejects_a_bad_page_and_a_non_ajax_call(h, profile):
    client = h.client("alice")

    assert client.get("/profile/sessions?page=0", headers={"Sec-Fetch-Mode": "cors"}).status_code == 400
    assert client.get("/profile/sessions").status_code == 403


# --------------------------------------------------------------------------------------
# edit
# --------------------------------------------------------------------------------------
def test_edit_username_and_email_updates_the_user(h, profile):
    client = h.client("alice", email="old@example.com")

    response = client.post("/profile/edit", data={"username": "bob", "email": "new@example.com", "password": CURRENT})

    kwargs = h.db.update_ui_user.call_args.kwargs
    assert (kwargs["username"], kwargs["email"], kwargs["old_username"]) == ("bob", "new@example.com", "alice")
    assert response.headers["Location"].endswith("/profile")
    assert "The profile has been successfully updated." in _flashed(h, client)


@pytest.mark.parametrize(
    "form, message",
    [
        ({"username": "alice", "email": "", "password": "wrong"}, "The current password is incorrect."),
        ({"username": "x" * 257, "email": "", "password": CURRENT}, "The username is too long. It must be less than 256 characters."),
        ({"username": "alice", "email": "e" * 257, "password": CURRENT}, "The email is too long. It must be less than 256 characters."),
        ({"username": "alice", "email": "", "password": CURRENT}, "The username and email are the same as the current ones."),
    ],
)
def test_edit_identity_refusals(h, profile, form, message):
    client = h.client("alice")

    client.post("/profile/edit", data=form)

    h.db.update_ui_user.assert_not_called()
    assert message in _flashed(h, client)


@pytest.mark.parametrize(
    "form, message",
    [
        ({"new_password": STRONG, "new_password_confirm": STRONG, "password": "wrong"}, "The current password is incorrect."),
        ({"new_password": STRONG, "new_password_confirm": "other", "password": CURRENT}, "The passwords do not match the confirm password."),
        ({"new_password": "weak", "new_password_confirm": "weak", "password": CURRENT}, "The new password is not strong enough."),
        ({"new_password": "Aa1!" + "x" * 80, "new_password_confirm": "Aa1!" + "x" * 80, "password": CURRENT}, "The new password is too long."),
        ({"new_password": CURRENT, "new_password_confirm": CURRENT, "password": CURRENT}, "The new password is the same as the current one."),
    ],
)
def test_password_change_refusals(h, profile, form, message):
    client = h.client("alice")

    client.post("/profile/edit", data=form)

    h.db.update_ui_user.assert_not_called()
    assert any(message in flashed for flashed in _flashed(h, client))


def test_a_password_change_revokes_every_other_session_and_signs_out(h, profile):
    h.db.get_ui_user_sessions.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]
    client = h.client("alice")
    with client.session_transaction() as sess:
        sess["session_id"] = 2

    response = client.post("/profile/edit", data={"new_password": STRONG, "new_password_confirm": STRONG, "password": CURRENT})

    profile.revoke_sessions.assert_called_once_with([1, 3])
    h.db.delete_ui_user_old_sessions.assert_called_once_with("alice", keep_session_id=2)
    assert response.headers["Location"].endswith("/logout")
    stored = h.db.update_ui_user.call_args.kwargs["password"]
    assert stored != STRONG.encode() and stored.startswith(b"$2")


def test_theme_edit_accepts_only_known_themes(h, profile):
    client = h.client("alice")

    client.post("/profile/edit", data={"theme": "dark"})
    assert h.db.update_ui_user.call_args.kwargs["theme"] == "dark"

    h.db.update_ui_user.reset_mock()
    client.post("/profile/edit", data={"theme": "neon"})
    h.db.update_ui_user.assert_not_called()
    assert "The theme is invalid." in _flashed(h, client)


def test_edit_without_fields_is_refused(h, profile):
    client = h.client("alice")

    client.post("/profile/edit", data={"unrelated": "1"})

    assert "No fields were updated." in _flashed(h, client)


def test_edit_reports_a_database_error(h, profile):
    h.db.update_ui_user.return_value = "locked"
    client = h.client("alice")

    client.post("/profile/edit", data={"theme": "dark"})

    assert "Couldn't update the alice user in the database: locked" in _flashed(h, client)


# --------------------------------------------------------------------------------------
# two-factor
# --------------------------------------------------------------------------------------
def test_totp_enable_stores_the_secret_and_stashes_fresh_recovery_codes(h, profile):
    h.totp.match_totp.return_value = SimpleNamespace(counter=12)
    h.db.enable_ui_user_totp.return_value = ""
    client = h.client("alice")
    with client.session_transaction() as sess:
        sess["tmp_totp_secret"] = "SECRET"

    response = client.post("/profile/totp-enable", data={"password": CURRENT, "totp_token": "123456"})

    h.totp.match_totp.assert_called_once_with("123456", "SECRET")
    h.db.enable_ui_user_totp.assert_called_once_with("alice", "SECRET", 12, ["c1", "c2"])
    assert response.headers["Location"].endswith("/profile#security")
    with client.session_transaction() as sess:
        assert sess["totp_validated"] is True and sess["decrypted_recovery_codes"] == ["c1", "c2"] and "tmp_totp_secret" not in sess


@pytest.mark.parametrize(
    "user, form, message",
    [
        ({"totp_secret": "S"}, {"password": CURRENT, "totp_token": "1"}, "Two-factor authentication is already enabled."),
        ({}, {"password": "wrong", "totp_token": "1"}, "The current password is incorrect."),
    ],
)
def test_totp_enable_refusals(h, profile, user, form, message):
    client = h.client("alice", **user)

    client.post("/profile/totp-enable", data=form)

    h.db.enable_ui_user_totp.assert_not_called()
    assert message in _flashed(h, client)


def test_totp_enable_rejects_a_token_that_does_not_match(h, profile):
    h.totp.match_totp.return_value = None
    client = h.client("alice")

    client.post("/profile/totp-enable", data={"password": CURRENT, "totp_token": "000000"})

    h.db.enable_ui_user_totp.assert_not_called()
    assert "The totp token is invalid." in _flashed(h, client)


def test_totp_enable_reports_a_database_error(h, profile):
    h.totp.match_totp.return_value = SimpleNamespace(counter=1)
    h.db.enable_ui_user_totp.return_value = "locked"
    client = h.client("alice")

    client.post("/profile/totp-enable", data={"password": CURRENT, "totp_token": "1"})

    assert "Couldn't enable the two-factor authentication in the database: locked" in _flashed(h, client)


def test_totp_disable_clears_the_secret(h, profile):
    h.totp.verify_totp.return_value = True
    client = h.client("alice", totp_secret="S")

    response = client.post("/profile/totp-disable", data={"password": CURRENT, "totp_token": "123456"})

    args = h.db.update_ui_user.call_args.args
    assert args[0] == "alice" and args[2] is None
    assert response.headers["Location"].endswith("/profile#security")
    with client.session_transaction() as sess:
        assert sess["totp_validated"] is False


@pytest.mark.parametrize(
    "user, form, verify, message",
    [
        ({}, {"password": CURRENT, "totp_token": "1"}, True, "Two-factor authentication is not enabled."),
        ({"totp_secret": "S"}, {"password": "wrong", "totp_token": "1"}, True, "The current password is incorrect."),
        ({"totp_secret": "S"}, {"password": CURRENT, "totp_token": "1"}, False, "The totp token is invalid."),
    ],
)
def test_totp_disable_refusals(h, profile, user, form, verify, message):
    h.totp.verify_totp.return_value = verify
    h.totp.verify_recovery_code.return_value = None
    client = h.client("alice", **user)

    client.post("/profile/totp-disable", data=form)

    h.db.update_ui_user.assert_not_called()
    assert message in _flashed(h, client)


def test_totp_refresh_replaces_the_recovery_codes(h, profile):
    h.db.refresh_ui_user_recovery_codes.return_value = ""
    client = h.client("alice", totp_secret="S")

    response = client.post("/profile/totp-refresh", data={"password": CURRENT})

    h.db.refresh_ui_user_recovery_codes.assert_called_once_with("alice", ["c1", "c2"])
    assert response.headers["Location"].endswith("/profile#security")
    with client.session_transaction() as sess:
        assert sess["decrypted_recovery_codes"] == ["c1", "c2"] and sess["totp_refreshed"] is True


@pytest.mark.parametrize(
    "user, form, db_error, message",
    [
        ({}, {"password": CURRENT}, "", "Two-factor authentication is not enabled."),
        ({"totp_secret": "S"}, {"password": "wrong"}, "", "The current password is incorrect."),
        ({"totp_secret": "S"}, {"password": CURRENT}, "locked", "Couldn't refresh the recovery codes in the database: locked"),
    ],
)
def test_totp_refresh_refusals(h, profile, user, form, db_error, message):
    h.db.refresh_ui_user_recovery_codes.return_value = db_error
    client = h.client("alice", **user)

    client.post("/profile/totp-refresh", data=form)

    assert message in _flashed(h, client)
    with client.session_transaction() as sess:
        assert "decrypted_recovery_codes" not in sess


# --------------------------------------------------------------------------------------
# wipe other sessions
# --------------------------------------------------------------------------------------
def test_wipe_other_sessions_keeps_only_the_current_one(h, profile):
    h.db.get_ui_user_sessions.return_value = [{"id": 1}, {"id": 2}]
    h.db.delete_ui_user_old_sessions.return_value = ""
    client = h.client("alice")
    with client.session_transaction() as sess:
        sess["session_id"] = 1

    response = client.post("/profile/wipe-other-sessions", data={"password": CURRENT})

    profile.revoke_sessions.assert_called_once_with([2])
    h.db.delete_ui_user_old_sessions.assert_called_once_with("alice", keep_session_id=1)
    assert response.headers["Location"].endswith("/profile#sessions")


@pytest.mark.parametrize(
    "revoke, delete, message",
    [
        ("", "", "The current password is incorrect."),
        ("no backend", "", "Couldn't revoke the other sessions: no backend"),
        ("", "locked", "Couldn't wipe the other sessions in the database: locked"),
    ],
)
def test_wipe_other_sessions_refusals(h, profile, revoke, delete, message):
    profile.revoke_sessions.return_value = revoke
    h.db.delete_ui_user_old_sessions.return_value = delete
    client = h.client("alice")

    client.post("/profile/wipe-other-sessions", data={"password": "wrong" if message.startswith("The current") else CURRENT})

    assert message in _flashed(h, client)
    if message.startswith("The current"):
        h.db.delete_ui_user_old_sessions.assert_not_called()


@pytest.mark.parametrize("path", ["/profile/edit", "/profile/totp-enable", "/profile/totp-disable", "/profile/totp-refresh", "/profile/wipe-other-sessions"])
def test_every_profile_write_is_refused_in_read_only_mode(h, profile, path):
    h.db.readonly = True
    client = h.client("alice", totp_secret="S")

    client.post(path, data={"password": CURRENT, "totp_token": "1", "theme": "dark"})

    h.db.update_ui_user.assert_not_called()
    h.db.enable_ui_user_totp.assert_not_called()
    h.db.refresh_ui_user_recovery_codes.assert_not_called()
    h.db.delete_ui_user_old_sessions.assert_not_called()
    assert "Database is in read-only mode" in _flashed(h, client)
