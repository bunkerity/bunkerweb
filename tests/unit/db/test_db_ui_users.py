"""Base DatabaseUIUsersMixin (plain Database) — UI-user CRUD used by the API /users router.

`APIDatabase` has no UI-user override, so `db.create_ui_user/update_ui_user/get_ui_user`
resolve to this base mixin (distinct from the UIDatabase override tested under tests/unit/ui/).
Notably the base `create_ui_user` AUTO-CREATES the default roles (admin/writer/reader),
whereas the UI override rejects unknown roles. Exercised via the plain `db` fixture (matrix).

Several methods here (delete_ui_user_old_sessions, mark_ui_user_access, column preferences,
role permissions) are overridden by UIDatabase, so the plain `db` fixture is the only path
that reaches the BASE implementations — the ones the API `/users` router actually calls.
"""

from datetime import datetime, timezone

DT = datetime(2024, 1, 1, tzinfo=timezone.utc)
LATER_DT = datetime(2024, 1, 2, tzinfo=timezone.utc)  # a session created after DT


class TestBaseCreateGet:
    def test_create_with_default_role_autocreated(self, db):
        # 'admin' does not pre-exist; the base create auto-creates known default roles, so a
        # "" return proves that path ran (the UI override would reject with "Role ... doesn't exist").
        assert db.create_ui_user("alice", b"h", ["admin"]) == ""
        u = db.get_ui_user(username="alice", as_dict=True)
        assert u["username"] == "alice"
        assert "admin" in u["roles"]

    def test_create_unknown_role_rejected(self, db):
        assert db.create_ui_user("bob", b"h", ["bogus"]) == "Role bogus doesn't exist"

    def test_create_roleless(self, db):
        assert db.create_ui_user("bob", b"h", []) == ""
        assert db.get_ui_user(username="bob") is not None

    def test_duplicate_rejected(self, db):
        db.create_ui_user("bob", b"h", [])
        assert db.create_ui_user("bob", b"h", []) == "User bob already exists"

    def test_second_admin_rejected(self, db):
        db.create_ui_user("a1", b"h", [], admin=True)
        assert db.create_ui_user("a2", b"h", [], admin=True) == "An admin user already exists"

    def test_get_missing_returns_none(self, db):
        assert db.get_ui_user(username="ghost") is None


class TestBaseListAndCleanup:
    def test_get_ui_users_as_dict(self, db):
        db.create_ui_user("alice", b"h", ["admin"])
        db.create_ui_user("bob", b"h", [])
        users = db.get_ui_users(as_dict=True)
        assert {u["username"] for u in users} == {"alice", "bob"}
        alice = next(u for u in users if u["username"] == "alice")
        assert "admin" in alice["roles"]

    def test_get_ui_users_objects(self, db):
        db.create_ui_user("bob", b"h", [])
        users = db.get_ui_users()
        assert [u.username for u in users] == ["bob"]

    def test_cleanup_expired_sessions(self, db):
        db.create_ui_user("bob", b"h", [])
        db.mark_ui_user_login("bob", DT, "1.1.1.1", "a")
        # DT is 2024; a 30-day window puts the cutoff well after it -> the session is removed.
        assert db.cleanup_expired_ui_sessions(30) == "Removed 1 expired UI user sessions"


class TestBaseUpdate:
    def test_update_password_and_method(self, db):
        db.create_ui_user("bob", b"h", [])
        assert db.update_ui_user("bob", b"new", None, method="ui") == ""
        u = db.get_ui_user(username="bob", as_dict=True)
        assert u["password"] == b"new"
        assert u["method"] == "ui"

    def test_rename(self, db):
        db.create_ui_user("bob", b"h", [])
        assert db.update_ui_user("bob2", b"h", None, old_username="bob") == ""
        assert db.get_ui_user(username="bob") is None
        assert db.get_ui_user(username="bob2") is not None

    def test_update_missing(self, db):
        assert db.update_ui_user("ghost", b"h", None) == "User ghost doesn't exist"


class TestRecoveryCodes:
    def test_refresh_creates_codes(self, db):
        db.create_ui_user("bob", b"h", [])
        assert db.refresh_ui_user_recovery_codes("bob", ["c1", "c2"]) == ""
        assert len(db.get_ui_user(username="bob", as_dict=True)["recovery_codes"]) == 2

    def test_refresh_empty_rejected(self, db):
        db.create_ui_user("bob", b"h", [])
        assert db.refresh_ui_user_recovery_codes("bob", []) == "No recovery codes provided"

    def test_refresh_missing_user(self, db):
        assert db.refresh_ui_user_recovery_codes("ghost", ["c"]) == "User ghost doesn't exist"

    def test_use_recovery_code_consumes(self, db):
        from fixtures.seed import add_recovery_code

        db.create_ui_user("bob", b"h", [])
        add_recovery_code(db, "bob", "KNOWNHASH")  # literal: use_ matches exact string equality
        assert db.use_ui_user_recovery_code("bob", "KNOWNHASH") == ""
        assert "KNOWNHASH" not in db.get_ui_user(username="bob", as_dict=True)["recovery_codes"]

    def test_use_recovery_code_invalid(self, db):
        db.create_ui_user("bob", b"h", [])
        assert db.use_ui_user_recovery_code("bob", "WRONG") == "Invalid recovery code"

    def test_use_recovery_code_missing_user(self, db):
        assert db.use_ui_user_recovery_code("ghost", "x") == "User ghost doesn't exist"

    def test_delete_recovery_codes(self, db):
        from fixtures.seed import add_recovery_code

        db.create_ui_user("bob", b"h", [])
        add_recovery_code(db, "bob", "h1")
        assert db._delete_ui_user_recovery_codes("bob") == ""
        assert db.get_ui_user(username="bob", as_dict=True)["recovery_codes"] == []


class TestUpdateTotpRecoveryCodes:
    """update_ui_user reconciles recovery codes only when the totp secret changes."""

    def test_totp_set_with_codes_refreshes(self, db):
        db.create_ui_user("bob", b"h", [])  # totp_secret None
        # None -> "SEC" is a totp change; codes provided -> refresh path runs.
        assert db.update_ui_user("bob", b"h", "SEC", totp_recovery_codes=["a", "b"]) == ""
        assert len(db.get_ui_user(username="bob", as_dict=True)["recovery_codes"]) == 2

    def test_totp_cleared_deletes_codes(self, db):
        from fixtures.seed import add_recovery_code

        db.create_ui_user("bob", b"h", [], totp_secret="SEC")
        add_recovery_code(db, "bob", "h1")
        # "SEC" -> None is a totp change with no codes -> delete path runs.
        assert db.update_ui_user("bob", b"h", None) == ""
        assert db.get_ui_user(username="bob", as_dict=True)["recovery_codes"] == []


class TestBaseSessions:
    def test_sessions_with_current_floated_first(self, db):
        db.create_ui_user("bob", b"h", [])
        s1 = db.mark_ui_user_login("bob", DT, "1.1.1.1", "a")
        db.mark_ui_user_login("bob", DT, "2.2.2.2", "b")
        ordered = db.get_ui_user_sessions("bob", current_session_id=s1)
        assert len(ordered) == 2
        assert ordered[0]["id"] == s1  # the current session is returned first

    def test_delete_old_sessions_keeps_the_named_session_not_the_newest(self, db):
        """The session to keep is named by the caller, and it is not "the newest one".

        This method used to keep the most recently created row unconditionally, which inverts
        "wipe my other sessions": the row that survived was whoever logged in last -- an attacker
        who signed in after the victim -- and the row deleted was the victim's own.
        """
        db.create_ui_user("bob", b"h", [])
        mine = db.mark_ui_user_login("bob", DT, "1.1.1.1", "a")
        theirs = db.mark_ui_user_login("bob", LATER_DT, "2.2.2.2", "b")

        assert db.delete_ui_user_old_sessions("bob", keep_session_id=mine) == ""

        remaining = [s["id"] for s in db.get_ui_user_sessions("bob")]
        assert remaining == [mine], "the caller's own session must be the one that survives"
        assert theirs not in remaining

    def test_delete_old_sessions_with_nothing_to_keep_deletes_all(self, db):
        """No current session id means there is no row to spare -- not "spare an arbitrary one"."""
        db.create_ui_user("bob", b"h", [])
        db.mark_ui_user_login("bob", DT, "1.1.1.1", "a")
        db.mark_ui_user_login("bob", LATER_DT, "2.2.2.2", "b")
        assert db.delete_ui_user_old_sessions("bob") == ""
        assert db.get_ui_user_sessions("bob") == []

    def test_delete_old_sessions_missing_user(self, db):
        assert db.delete_ui_user_old_sessions("ghost") == "User ghost doesn't exist"

    def test_mark_access_updates_last_activity(self, db):
        db.create_ui_user("bob", b"h", [])
        sid = db.mark_ui_user_login("bob", DT, "1.1.1.1", "a")
        assert db.mark_ui_user_access(sid, DT) == ""

    def test_mark_access_missing_session(self, db):
        assert db.mark_ui_user_access(999999, DT) == "Session 999999 doesn't exist"


class TestBaseUserPreferences:
    def test_empty_returns_dict(self, db):
        db.create_ui_user("bob", b"h", [])
        assert db.get_ui_user_preference("bob", "services") == {}

    def test_set_and_read_back(self, db):
        db.create_ui_user("bob", b"h", [])
        assert db.set_ui_user_preference("bob", "services", {"name": True}) == ""
        assert db.get_ui_user_preference("bob", "services") == {"name": True}
        # second set mutates the existing row.
        assert db.set_ui_user_preference("bob", "services", {"name": False}) == ""
        assert db.get_ui_user_preference("bob", "services") == {"name": False}

    def test_set_missing_user(self, db):
        assert db.set_ui_user_preference("ghost", "services", {}) == "User ghost doesn't exist"

    def test_explicit_default_is_returned_without_being_stored(self, db):
        """This mixin does not seed on read -- unlike the UI-side one, which owns that
        behaviour for DataTables. A caller that wants a default must keep passing it."""
        db.create_ui_user("bob", b"h", [])
        assert db.get_ui_user_preference("bob", "onboarding", default={"opened_at": 1}) == {"opened_at": 1}
        assert db.get_ui_user_preference("bob", "onboarding") == {}

    def test_a_key_holds_any_json_shape(self, db):
        db.create_ui_user("bob", b"h", [])
        assert db.set_ui_user_preference("bob", "onboarding", {"acked_hints": ["home"], "completed_at": None}) == ""
        assert db.get_ui_user_preference("bob", "onboarding") == {"acked_hints": ["home"], "completed_at": None}


class TestBaseRolePermissions:
    def test_get_role_permissions(self, db):
        # base create_ui_user auto-creates 'admin' with manage/write/read.
        db.create_ui_user("alice", b"h", ["admin"])
        assert set(db.get_ui_role_permissions("admin")) == {"manage", "write", "read"}

    def test_unknown_role_has_no_permissions(self, db):
        assert db.get_ui_role_permissions("nonexistent") == []
