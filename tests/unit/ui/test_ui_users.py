"""UIUsersMethodsMixin — UI user CRUD and session bookkeeping.

Passwords are opaque bytes at the DB layer (stored decoded), so placeholder hashes are
fine. ``create_ui_user`` requires any referenced roles to already exist.
"""

from datetime import datetime, timezone

DT = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _session_count(ui_db, username):
    from sqlalchemy import func, select

    from fixtures.seed import session
    from model import UserSessions  # type: ignore

    with session(ui_db) as s:
        return s.scalar(select(func.count()).select_from(UserSessions).filter_by(user_name=username))


class TestCreateGetUser:
    def test_create_and_get(self, ui_db):
        assert ui_db.create_ui_user("bob", b"hash", []) == ""
        user = ui_db.get_ui_user(username="bob", as_dict=True)
        assert user["username"] == "bob"
        assert user["admin"] is False
        assert user["roles"] == []

    def test_duplicate_rejected(self, ui_db):
        ui_db.create_ui_user("bob", b"hash", [])
        assert ui_db.create_ui_user("bob", b"hash2", []) == "User bob already exists"

    def test_second_admin_rejected(self, ui_db):
        ui_db.create_ui_user("admin1", b"h", [], admin=True)
        assert ui_db.create_ui_user("admin2", b"h", [], admin=True) == "An admin user already exists"

    def test_unknown_role_rejected(self, ui_db):
        assert ui_db.create_ui_user("bob", b"h", ["nope"]) == "Role nope doesn't exist"

    def test_get_missing_returns_none(self, ui_db):
        assert ui_db.get_ui_user(username="ghost") is None


class TestUpdateDeleteUser:
    def test_update_password_and_method(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        assert ui_db.update_ui_user("bob", b"newhash", None, method="ui") == ""
        assert ui_db.get_ui_user(username="bob", as_dict=True)["method"] == "ui"

    def test_rename(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        assert ui_db.update_ui_user("bob2", b"h", None, old_username="bob") == ""
        assert ui_db.get_ui_user(username="bob") is None
        assert ui_db.get_ui_user(username="bob2") is not None

    def test_update_missing(self, ui_db):
        assert ui_db.update_ui_user("ghost", b"h", None) == "User ghost doesn't exist"

    def test_delete(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        assert ui_db.delete_ui_user("bob") == ""
        assert ui_db.get_ui_user(username="bob") is None

    def test_delete_missing(self, ui_db):
        assert ui_db.delete_ui_user("ghost") == "User ghost doesn't exist"


class TestSessions:
    def test_login_returns_session_id(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        sid = ui_db.mark_ui_user_login("bob", DT, "1.2.3.4", "agent")
        assert isinstance(sid, int)
        assert ui_db.mark_ui_user_access(sid, DT) == ""

    def test_login_missing_user(self, ui_db):
        assert ui_db.mark_ui_user_login("ghost", DT, "1.2.3.4", "agent") == "User ghost doesn't exist"

    def test_access_missing_session(self, ui_db):
        assert ui_db.mark_ui_user_access(999999, DT) == "Session 999999 doesn't exist"

    def test_delete_old_sessions_keeps_newest(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        ui_db.mark_ui_user_login("bob", DT, "1.2.3.4", "a")
        ui_db.mark_ui_user_login("bob", DT, "1.2.3.4", "a")
        assert _session_count(ui_db, "bob") == 2
        assert ui_db.delete_ui_user_old_sessions("bob") == ""
        assert _session_count(ui_db, "bob") == 1


class TestBaseUiUserMethods:
    """Methods defined only on the base DatabaseUIUsersMixin (not overridden by the UI
    mixin), reached through UIDatabase via the MRO."""

    def test_get_ui_users(self, ui_db):
        ui_db.create_ui_user("alice", b"h", [])
        ui_db.create_ui_user("bob", b"h", [])
        assert {u["username"] for u in ui_db.get_ui_users(as_dict=True)} == {"alice", "bob"}

    def test_get_ui_user_sessions(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        ui_db.mark_ui_user_login("bob", DT, "1.2.3.4", "agent")
        sessions = ui_db.get_ui_user_sessions("bob")
        assert len(sessions) == 1
        assert sessions[0]["ip"] == "1.2.3.4"

    def test_cleanup_expired_sessions(self, ui_db):
        from datetime import datetime, timezone

        ui_db.create_ui_user("bob", b"h", [])
        ui_db.mark_ui_user_login("bob", datetime.now(timezone.utc), "1.2.3.4", "agent")
        # a recent session is not expired under a 30-day window
        assert ui_db.cleanup_expired_ui_sessions(30) == "Removed 0 expired UI user sessions"
        # negative window puts the cutoff in the future -> the session is removed
        assert ui_db.cleanup_expired_ui_sessions(-1) == "Removed 1 expired UI user sessions"
        assert ui_db.get_ui_user_sessions("bob") == []
