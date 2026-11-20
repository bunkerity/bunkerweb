"""Failed logins are throttled per client IP and per username, in the database, through the real routes.

The login and TOTP blueprints run on the route harness, but ``DB`` is a real ``UIDatabase`` on SQLite, so
the count really lives in ``bw_ui_login_failures`` and survives from one request (one worker) to the next.
"""

from datetime import datetime, timedelta, timezone

import pytest
from bcrypt import gensalt, hashpw

from app.models.reverse_proxied import ReverseProxied

PASSWORD = "Correct-Horse1!"
WRONG = {"username": "alice", "password": "wrong"}
RIGHT = {"username": "alice", "password": PASSWORD}


@pytest.fixture
def real(h, ui_db, tmp_path, monkeypatch):
    """The login and TOTP routes over a real database holding ``alice`` (no second factor)."""
    monkeypatch.setattr(h.routes.login, "BISCUIT_PRIVATE_KEY_FILE", tmp_path / "missing.key")
    monkeypatch.setattr(h.routes.login, "DB", ui_db)
    monkeypatch.setattr(h.routes.totp, "DB", ui_db)
    for name in ("LOGIN_THROTTLE", "LOGIN_MAX_ATTEMPTS", "LOGIN_WINDOW_MINUTES", "LOGIN_LOCKOUT_MINUTES"):
        monkeypatch.delenv(name, raising=False)
    assert ui_db.create_ui_user("alice", hashpw(PASSWORD.encode(), gensalt(rounds=4)), [], admin=True) == ""
    h.users["alice"] = ui_db.get_ui_user(username="alice")
    h.totp.verify_totp.return_value = False
    h.totp.verify_recovery_code.return_value = None
    return ui_db


def _client(h, ip="203.0.113.1"):
    client = h.app.test_client()
    client.environ_base["REMOTE_ADDR"] = ip
    return client


def _post(h, form, ip="203.0.113.1"):
    return _client(h, ip).post("/login", data=form)


def _failures(ui_db):
    from model import UserLoginFailures

    with ui_db._db_session() as session:
        return [(row.username, row.ip) for row in session.query(UserLoginFailures).order_by(UserLoginFailures.id).all()]


def _age(ui_db, minutes):
    from model import UserLoginFailures

    with ui_db._db_session() as session:
        for row in session.query(UserLoginFailures).all():
            stored = row.failure_date if row.failure_date.tzinfo else row.failure_date.replace(tzinfo=timezone.utc)
            row.failure_date = stored - timedelta(minutes=minutes)
        session.commit()


def _seed(ui_db, *minutes_ago, username="alice", ip="203.0.113.1"):
    from model import UserLoginFailures

    now = datetime.now(timezone.utc)
    with ui_db._db_session() as session:
        for minutes in minutes_ago:
            session.add(UserLoginFailures(username=username, ip=ip, failure_date=now - timedelta(minutes=minutes)))
        session.commit()


def _lock_seconds(ui_db):
    return ui_db.get_ui_login_lock("alice", "203.0.113.1", max_attempts=5, window=15 * 60, lockout=15 * 60)


def _fail(h, count, form=WRONG, ip="203.0.113.1"):
    for _ in range(count):
        assert _post(h, form, ip).status_code == 401


def test_the_sixth_failure_is_locked_out_even_with_the_right_password(h, real):
    _fail(h, 5)

    response = _post(h, RIGHT)

    assert response.status_code == 429 and response.headers["Retry-After"]
    assert "Too many failed attempts, try again in 15 min." in h.renders[-1][1]["error"]
    h.db.mark_ui_user_login.assert_not_called()
    assert _post(h, RIGHT).status_code == 429  # a locked attempt does not extend or end the lock


def test_the_fifth_failure_is_not_yet_locked(h, real):
    _fail(h, 4)

    assert _post(h, WRONG).status_code == 401
    assert _post(h, RIGHT).status_code == 429


def test_the_lock_expires(h, real):
    _fail(h, 5)
    assert _post(h, RIGHT).status_code == 429

    _age(real, 16)

    response = _post(h, RIGHT)
    assert response.status_code == 302 and "/loading" in response.headers["Location"]


def test_a_successful_login_resets_that_usernames_count(h, real):
    _fail(h, 4)
    assert len(_failures(real)) == 4
    assert _post(h, RIGHT).status_code == 302
    assert _failures(real) == []

    _fail(h, 4)  # 8 failures in all: only a reset keeps this under the limit

    assert _post(h, RIGHT).status_code == 302


def test_five_failures_from_one_ip_lock_that_ip_whatever_the_username(h, real):
    for name in ("bob", "carol", "dave", "erin", "frank"):
        assert _post(h, {"username": name, "password": "x"}, "198.51.100.7").status_code == 401

    assert _post(h, RIGHT, "198.51.100.7").status_code == 429
    assert _post(h, {"username": "zoe", "password": "x"}, "198.51.100.7").status_code == 429
    assert _post(h, RIGHT, "198.51.100.8").status_code == 302  # another IP is untouched


def test_five_failures_for_one_username_lock_it_from_every_ip(h, real):
    for octet in range(10, 15):
        assert _post(h, WRONG, f"192.0.2.{octet}").status_code == 401

    assert _post(h, RIGHT, "192.0.2.99").status_code == 429


def test_the_username_is_folded_so_another_case_shares_the_count(h, real):
    for octet, name in enumerate(("alice", "ALICE", "Alice", " alice", "alice ")):
        assert _post(h, {"username": name, "password": "x"}, f"192.0.2.{octet + 10}").status_code == 401

    assert _post(h, RIGHT, "192.0.2.99").status_code == 429


@pytest.fixture
def totp_user(h, real):
    assert real.update_ui_user("alice", hashpw(PASSWORD.encode(), gensalt(rounds=4)), "a-totp-secret", old_username="alice") == ""
    h.users["alice"] = real.get_ui_user(username="alice")
    return real


def _totp(h, client, token="000000"):
    return client.post("/totp", data={"totp_token": token})


def test_a_wrong_totp_code_counts_and_five_lock_the_username(h, real, totp_user):
    client = _client(h, "203.0.113.1")
    assert client.post("/login", data=RIGHT).status_code == 302

    for _ in range(5):
        assert "/totp" in _totp(h, client).headers["Location"]
    assert [name for name, _ in _failures(real)] == ["alice"] * 5

    h.totp.verify_totp.reset_mock()
    h.totp.verify_totp.return_value = True  # the right code is not even looked at once locked
    response = _totp(h, client, "123456")

    assert "/totp" in response.headers["Location"]
    h.totp.verify_totp.assert_not_called()
    assert any("Too many failed attempts" in message for message, _ in h.flashes(client))
    with client.session_transaction() as sess:
        assert not sess.get("totp_validated")
    assert _post(h, RIGHT, "198.51.100.77").status_code == 429


def test_a_wrong_recovery_code_counts_too(h, real, totp_user):
    client = _client(h, "203.0.113.1")
    client.post("/login", data=RIGHT)
    h.totp.verify_recovery_code.return_value = None

    for _ in range(5):
        _totp(h, client, "not-a-code")

    assert len(_failures(real)) == 5


def test_a_password_alone_does_not_clear_the_count_when_a_second_factor_is_set(h, real, totp_user):
    for _ in range(3):
        _totp(h, _client(h, "203.0.113.1"), "000000")  # anonymous: refused, nothing to count
    for attempt in range(4):  # each cycle: log in with the right password, then miss the code
        client = _client(h, "203.0.113.1")
        client.post("/login", data=RIGHT)
        _totp(h, client)
    assert len(_failures(real)) == 4  # logging in again never wiped them

    client = _client(h, "203.0.113.1")
    client.post("/login", data=RIGHT)
    _totp(h, client)
    assert _post(h, RIGHT).status_code == 429


def test_the_right_totp_code_clears_the_count(h, real, totp_user):
    client = _client(h, "203.0.113.1")
    client.post("/login", data=RIGHT)
    _totp(h, client)
    assert len(_failures(real)) == 1

    h.totp.verify_totp.return_value = True
    _totp(h, client, "123456")

    assert _failures(real) == []
    with client.session_transaction() as sess:
        assert sess["totp_validated"] is True


def test_a_lock_looks_the_same_for_a_known_and_an_unknown_username(h, real):
    for octet in range(10, 15):
        _post(h, WRONG, f"192.0.2.{octet}")
        _post(h, {"username": "ghost", "password": "x"}, f"192.0.2.{octet}")

    known = _post(h, RIGHT, "192.0.2.99")
    known_context = h.renders[-1][1]
    unknown = _post(h, {"username": "ghost", "password": "x"}, "192.0.2.99")
    unknown_context = h.renders[-1][1]

    assert known.status_code == unknown.status_code == 429
    assert known_context["error"] == unknown_context["error"]
    assert known_context["error"].startswith("Invalid username or password.")


def test_an_unknown_username_fails_like_a_known_one_until_the_lock(h, real):
    known = _post(h, WRONG)
    known_error = h.renders[-1][1]["error"]
    unknown = _post(h, {"username": "ghost", "password": "x"})

    assert known.status_code == unknown.status_code == 401
    assert h.renders[-1][1]["error"] == known_error == "Invalid username or password"


def test_the_ip_is_the_one_the_reverse_proxy_layer_trusts(h, real, monkeypatch):
    monkeypatch.setattr(h.app, "wsgi_app", ReverseProxied(h.app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1))

    # the proxy appended 9.9.9.9; the leading entry is whatever the client claimed
    _client(h, "10.0.0.2").post("/login", data=WRONG, headers={"X-Forwarded-For": "6.6.6.6, 9.9.9.9"})

    assert _failures(real) == [("alice", "9.9.9.9")]


def test_a_forwarded_header_is_ignored_when_no_proxy_layer_is_in_front(h, real):
    _client(h, "10.0.0.2").post("/login", data=WRONG, headers={"X-Forwarded-For": "6.6.6.6"})

    assert _failures(real) == [("alice", "10.0.0.2")]


def test_old_failures_are_pruned_when_a_new_one_is_recorded(h, real):
    _fail(h, 2)
    _age(real, 120)

    _fail(h, 1)

    assert len(_failures(real)) == 1


def test_spread_out_failures_lock_for_the_full_lockout(real):
    _seed(real, 26, 23, 20, 17, 14)  # failures at minutes 0, 3, 6, 9 and 12; it is minute 26

    assert 0 < _lock_seconds(real) <= 60  # the fifth locked until minute 27, although the first is 26 minutes old

    _age(real, 2)  # minute 28

    assert _lock_seconds(real) == 0


def test_a_lock_outlives_the_window_of_its_failures(real):
    _seed(real, 18, 16, 14, 12, 10)  # five failures over 8 minutes; only three are still inside the window

    assert 4 * 60 < _lock_seconds(real) <= 5 * 60


def test_failures_too_far_apart_do_not_lock(real):
    _seed(real, 40, 30, 20, 10, 1)  # never five within 15 minutes

    assert _lock_seconds(real) == 0


def test_the_pruning_keeps_the_failures_a_lock_still_needs(h, real):
    _seed(real, 26, 23, 20, 17, 14)  # the lock runs for another minute and needs all five

    assert _post(h, {"username": "bob", "password": "x"}, "198.51.100.7").status_code == 401  # a failure prunes first

    assert len(_failures(real)) == 6
    assert _post(h, RIGHT).status_code == 429


def test_the_throttle_can_be_turned_off(h, real, monkeypatch):
    monkeypatch.setenv("LOGIN_THROTTLE", "no")
    _fail(h, 8)

    assert _post(h, RIGHT).status_code == 302
    assert _failures(real) == []


def test_the_three_numbers_are_tunable(h, real, monkeypatch):
    monkeypatch.setenv("LOGIN_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("LOGIN_LOCKOUT_MINUTES", "30")
    monkeypatch.setenv("LOGIN_WINDOW_MINUTES", "20")
    _fail(h, 2)

    assert _post(h, RIGHT).status_code == 429
    assert "30 min" in h.renders[-1][1]["error"]

    _age(real, 25)  # out of the 20 minute window, still inside the 30 minute lockout: still locked
    assert _post(h, RIGHT).status_code == 429

    _age(real, 10)  # 35 minutes after the last failure
    assert _post(h, RIGHT).status_code == 302


def test_an_invalid_setting_falls_back_to_the_default(h, real, monkeypatch):
    monkeypatch.setenv("LOGIN_MAX_ATTEMPTS", "many")
    monkeypatch.setenv("LOGIN_WINDOW_MINUTES", "0")
    _fail(h, 5)

    assert _post(h, RIGHT).status_code == 429


def test_a_broken_throttle_never_blocks_a_login(h, real, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("database gone")

    monkeypatch.setattr(real, "get_ui_login_lock", boom)
    monkeypatch.setattr(real, "add_ui_login_failure", boom)

    assert _post(h, WRONG).status_code == 401
    assert _post(h, RIGHT).status_code == 302


def test_a_read_only_database_cannot_count_so_it_does_not_lock(h, real):
    real.readonly = True
    for _ in range(7):
        assert _post(h, WRONG).status_code == 401

    assert _failures(real) == []
