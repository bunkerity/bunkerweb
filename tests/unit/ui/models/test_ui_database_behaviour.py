"""UIDatabase behaviour a caller relies on: stored rows before and after, refusals, read-only mode.

Complements ``tests/unit/ui/test_ui_users.py`` and ``test_ui_rbac.py`` (happy paths) with the rename cascade,
the TOTP enrolment race guards, the recovery-code and session bookkeeping, the login throttle and the
column preferences. Every test runs on each selected engine.
"""

from datetime import datetime, timedelta, timezone

import pytest
from bcrypt import checkpw
from sqlalchemy import func, select

from app.utils import COLUMNS_PREFERENCES_DEFAULTS
from fixtures.seed import add_role_user, session
from model import (  # type: ignore
    Permissions,
    Roles,
    RolesPermissions,
    RolesUsers,
    UserColumnsPreferences,
    UserLoginFailures,
    UserRecoveryCodes,
    UserSessions,
    Users,
)

pytestmark = pytest.mark.multiengine

DT = datetime(2024, 1, 1, tzinfo=timezone.utc)
READONLY = "The database is read-only, the changes will not be saved"


def _utc(value):
    """SQLite and MySQL hand back naive datetimes stored as UTC; PostgreSQL hands back aware ones."""
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _count(db, model, **filters):
    with session(db) as s:
        return s.scalar(select(func.count()).select_from(model).filter_by(**filters))


def _user_row(db, username):
    with session(db) as s:
        row = s.get(Users, username)
        s.expunge(row) if row is not None else None
        return row


def _codes(db, username):
    with session(db) as s:
        return [row.code for row in s.query(UserRecoveryCodes).filter_by(user_name=username)]


def _make_role(db, name="editor", permissions=("read", "write")):
    assert db.create_ui_role(name, f"{name} role", list(permissions)) == ""


@pytest.fixture
def readonly(ui_db):
    ui_db.readonly = True
    return ui_db


class TestGetUiUser:
    def test_first_admin_is_returned_when_no_username_is_given(self, ui_db):
        ui_db.create_ui_user("plain", b"h", [])
        ui_db.create_ui_user("boss", b"h", [], admin=True)
        assert ui_db.get_ui_user(as_dict=True)["username"] == "boss"

    def test_an_admin_without_the_admin_role_gets_it_with_its_permissions(self, ui_db):
        ui_db.create_ui_user("boss", b"h", [], admin=True)
        assert _count(ui_db, Roles, name="admin") == 0
        user = ui_db.get_ui_user(username="boss", as_dict=True)
        assert user["roles"] == ["admin"]
        assert sorted(ui_db.get_ui_role_permissions("admin")) == ["manage", "read", "write"]
        assert _count(ui_db, RolesUsers, user_name="boss", role_name="admin") == 1

    def test_an_existing_admin_role_is_reused_not_duplicated(self, ui_db):
        assert ui_db.create_ui_role("admin", "custom text", ["read"]) == ""
        ui_db.create_ui_user("boss", b"h", [], admin=True)
        ui_db.get_ui_user(username="boss")
        assert _count(ui_db, Roles, name="admin") == 1
        assert ui_db.get_ui_role_permissions("admin") == ["read"]
        assert ui_db.get_ui_user_roles("boss") == ["admin"]

    def test_a_user_that_already_holds_the_admin_role_is_left_alone(self, ui_db):
        assert ui_db.create_ui_role("admin", "d", ["read"]) == ""
        ui_db.create_ui_user("boss", b"h", ["admin"], admin=True)
        ui_db.get_ui_user(username="boss")
        assert _count(ui_db, RolesUsers, user_name="boss") == 1

    def test_missing_column_preferences_are_filled_in_from_the_defaults(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        with session(ui_db) as s:
            s.query(UserColumnsPreferences).filter_by(user_name="bob").delete()
        assert _count(ui_db, UserColumnsPreferences, user_name="bob") == 0
        ui_db.get_ui_user(username="bob")
        assert _count(ui_db, UserColumnsPreferences, user_name="bob") == len(COLUMNS_PREFERENCES_DEFAULTS)

    def test_as_dict_carries_every_field_the_login_flow_reads(self, ui_db):
        ui_db.create_ui_user("bob", b"hash", [], email="bob@example.com", theme="dark", language="fr", totp_secret="SECRET", totp_recovery_codes=["aaaa-bbbb"])
        data = ui_db.get_ui_user(username="bob", as_dict=True)
        assert (data["email"], data["theme"], data["language"], data["totp_secret"], data["method"], data["admin"]) == (
            "bob@example.com",
            "dark",
            "fr",
            "SECRET",
            "manual",
            False,
        )
        assert data["password"] == b"hash"
        assert data["creation_date"].tzinfo is not None and data["update_date"].tzinfo is not None
        assert len(data["recovery_codes"]) == 1

    def test_read_only_mode_does_not_create_the_admin_role_nor_the_preferences(self, ui_db):
        ui_db.create_ui_user("boss", b"h", [], admin=True)
        with session(ui_db) as s:
            s.query(UserColumnsPreferences).filter_by(user_name="boss").delete()
        ui_db.readonly = True
        user = ui_db.get_ui_user(username="boss", as_dict=True)
        assert user["roles"] == []
        assert _count(ui_db, Roles, name="admin") == 0
        assert _count(ui_db, UserColumnsPreferences, user_name="boss") == 0


class TestCreateUiUser:
    def test_recovery_codes_are_stored_hashed_and_roles_and_preferences_follow(self, ui_db):
        _make_role(ui_db)
        assert ui_db.create_ui_user("bob", b"h", ["editor"], totp_recovery_codes=["abcd-efgh", "ijkl-mnop"]) == ""
        stored = _codes(ui_db, "bob")
        assert len(stored) == 2 and all(code not in ("abcd-efgh", "ijkl-mnop") for code in stored)
        assert any(checkpw(b"abcd-efgh", code.encode()) for code in stored)
        assert ui_db.get_ui_user_roles("bob") == ["editor"]
        assert _count(ui_db, UserColumnsPreferences, user_name="bob") == len(COLUMNS_PREFERENCES_DEFAULTS)

    def test_an_unknown_second_role_leaves_no_user_behind(self, ui_db):
        _make_role(ui_db)
        assert ui_db.create_ui_user("bob", b"h", ["editor", "ghost"]) == "Role ghost doesn't exist"
        assert _count(ui_db, Users, username="bob") == 0

    def test_a_user_can_be_created_with_two_roles(self, ui_db):
        _make_role(ui_db, "reader", ("read",))
        _make_role(ui_db, "writer", ("write",))
        assert ui_db.create_ui_user("bob", b"h", ["reader", "writer"]) == ""
        assert sorted(ui_db.get_ui_user_roles("bob")) == ["reader", "writer"]

    def test_the_creation_date_can_be_imported(self, ui_db):
        imported = DT.astimezone()
        ui_db.create_ui_user("bob", b"h", [], creation_date=imported)
        assert ui_db.get_ui_user(username="bob", as_dict=True)["creation_date"] == imported

    def test_a_duplicate_email_is_reported_and_nothing_is_written(self, ui_db):
        assert ui_db.create_ui_user("a", b"h", [], email="same@example.com") == ""
        assert ui_db.create_ui_user("b", b"h", [], email="same@example.com") != ""
        assert _count(ui_db, Users, username="b") == 0

    def test_read_only_mode_refuses(self, readonly):
        assert readonly.create_ui_user("bob", b"h", []) == READONLY
        assert _count(readonly, Users) == 0


class TestUpdateUiUser:
    def test_rename_moves_roles_codes_sessions_and_preferences_together(self, ui_db):
        _make_role(ui_db)
        ui_db.create_ui_user("old", b"h", ["editor"], totp_secret="S1", totp_recovery_codes=["aaaa-bbbb"])
        session_id = ui_db.mark_ui_user_login("old", DT, "1.2.3.4", "agent")
        assert ui_db.update_ui_user("new", b"h2", "S1", old_username="old") == ""
        assert _count(ui_db, Users, username="old") == 0 and _count(ui_db, Users, username="new") == 1
        assert ui_db.get_ui_user_roles("new") == ["editor"] and ui_db.get_ui_user_roles("old") == []
        assert len(_codes(ui_db, "new")) == 1 and _codes(ui_db, "old") == []
        assert [s["id"] for s in ui_db.get_ui_user_sessions("new")] == [session_id]
        assert _count(ui_db, UserColumnsPreferences, user_name="new") == len(COLUMNS_PREFERENCES_DEFAULTS)
        assert _count(ui_db, UserColumnsPreferences, user_name="old") == 0

    def test_rename_onto_an_existing_user_is_refused_and_changes_nothing(self, ui_db):
        ui_db.create_ui_user("a", b"h", [])
        ui_db.create_ui_user("b", b"h", [])
        assert ui_db.update_ui_user("b", b"other", None, old_username="a") == "User b already exists"
        assert _user_row(ui_db, "a").password == "h"
        assert _user_row(ui_db, "b").password == "h"

    def test_a_new_secret_stores_a_counter_that_spends_the_enrolment_window(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        assert _user_row(ui_db, "bob").totp_last_counter is None
        assert ui_db.update_ui_user("bob", b"h", "NEWSECRET", totp_recovery_codes=["aaaa-bbbb"]) == ""
        row = _user_row(ui_db, "bob")
        assert row.totp_secret == "NEWSECRET"
        assert row.totp_last_counter is not None and row.totp_last_counter > 0
        # the counter the caller just verified can not be replayed as a login
        assert ui_db.use_ui_user_totp("bob", "NEWSECRET", row.totp_last_counter) is False
        assert len(_codes(ui_db, "bob")) == 1

    def test_removing_the_secret_clears_the_counter_and_the_recovery_codes(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [], totp_secret="S1", totp_recovery_codes=["aaaa-bbbb"])
        assert ui_db.update_ui_user("bob", b"h", None) == ""
        row = _user_row(ui_db, "bob")
        assert row.totp_secret is None and row.totp_last_counter is None
        assert _codes(ui_db, "bob") == []

    def test_an_unchanged_secret_keeps_its_counter_and_codes(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [], totp_secret="S1", totp_recovery_codes=["aaaa-bbbb"])
        assert ui_db.use_ui_user_totp("bob", "S1", 41) is True
        assert ui_db.update_ui_user("bob", b"h", "S1", email="new@example.com", theme="dark", language="de", method="ui") == ""
        row = _user_row(ui_db, "bob")
        assert (row.email, row.theme, row.language, row.method, row.totp_last_counter) == ("new@example.com", "dark", "de", "ui", 41)
        assert len(_codes(ui_db, "bob")) == 1

    def test_a_secret_rotated_by_another_request_is_not_overwritten(self, ui_db):
        from sqlalchemy import event

        ui_db.create_ui_user("bob", b"h", [], totp_secret="S1", email="keep@example.com")
        fired = {"done": False}

        def rotate_first(conn, cursor, statement, parameters, context, executemany):
            # another replica rotates the secret between the row load and the guarded UPDATE
            if not fired["done"] and statement.startswith("UPDATE bw_ui_users") and "totp_last_counter" in statement:
                fired["done"] = True
                conn.exec_driver_sql("UPDATE bw_ui_users SET totp_secret = 'S2' WHERE username = 'bob'")

        event.listen(ui_db.sql_engine, "before_cursor_execute", rotate_first)
        try:
            message = ui_db.update_ui_user("bob", b"newpw", "S3", email="changed@example.com")
        finally:
            event.remove(ui_db.sql_engine, "before_cursor_execute", rotate_first)
        assert fired["done"]
        assert message == "The two-factor authentication secret changed; please retry"
        row = _user_row(ui_db, "bob")
        assert (row.password, row.email, row.totp_secret) == ("h", "keep@example.com", "S1")

    def test_unknown_user_and_read_only_mode(self, ui_db):
        assert ui_db.update_ui_user("ghost", b"h", None) == "User ghost doesn't exist"
        ui_db.readonly = True
        assert ui_db.update_ui_user("ghost", b"h", None) == READONLY


class TestEnableUiUserTotp:
    def test_enrolment_stores_secret_counter_and_replaces_recovery_codes(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [], totp_recovery_codes=["old1-old1"])
        assert ui_db.enable_ui_user_totp("bob", "SECRET", 12345, ["new1-new1", "new2-new2"]) == ""
        row = _user_row(ui_db, "bob")
        assert (row.totp_secret, row.totp_last_counter) == ("SECRET", 12345)
        stored = _codes(ui_db, "bob")
        assert len(stored) == 2 and not any(checkpw(b"old1-old1", code.encode()) for code in stored)

    def test_an_empty_string_secret_counts_as_disabled(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [], totp_secret="")
        assert ui_db.enable_ui_user_totp("bob", "SECRET", 1, []) == ""
        assert _user_row(ui_db, "bob").totp_secret == "SECRET"

    def test_an_already_enrolled_user_keeps_the_stored_secret(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [], totp_secret="KEEP", totp_recovery_codes=["aaaa-bbbb"])
        message = ui_db.enable_ui_user_totp("bob", "OTHER", 5, ["zzzz-zzzz"])
        assert message == "The user no longer exists or two-factor authentication is already enabled"
        assert _user_row(ui_db, "bob").totp_secret == "KEEP"
        assert any(checkpw(b"aaaa-bbbb", code.encode()) for code in _codes(ui_db, "bob"))

    def test_a_missing_user_is_refused(self, ui_db):
        assert ui_db.enable_ui_user_totp("ghost", "S", 1, []) == "The user no longer exists or two-factor authentication is already enabled"

    @pytest.mark.parametrize("secret, counter", [("", 1), (None, 1), ("S", -1), ("S", 1.5), ("S", "1"), ("S", True)])
    def test_invalid_enrolment_arguments_are_refused_without_a_write(self, ui_db, secret, counter):
        ui_db.create_ui_user("bob", b"h", [])
        assert ui_db.enable_ui_user_totp("bob", secret, counter, []) == "Invalid TOTP enrollment" or counter is True
        if counter is not True:
            assert _user_row(ui_db, "bob").totp_secret is None

    def test_read_only_mode_refuses(self, readonly):
        assert readonly.enable_ui_user_totp("bob", "S", 1, []) == READONLY

    def test_a_database_error_is_reported_without_leaking_the_driver_text(self, ui_db, monkeypatch):
        ui_db.create_ui_user("bob", b"h", [])

        def boom(*_a, **_k):
            raise RuntimeError("driver says secret-detail")

        monkeypatch.setattr(ui_db, "_db_session", boom)
        message = ui_db.enable_ui_user_totp("bob", "S", 1, [])
        assert message == "An error occurred while enabling two-factor authentication"
        assert "secret-detail" not in message


class TestUseUiUserTotp:
    def test_a_counter_is_consumed_once_and_only_forward(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [], totp_secret="S")
        assert ui_db.use_ui_user_totp("bob", "S", 10) is True
        assert ui_db.use_ui_user_totp("bob", "S", 10) is False  # replay
        assert ui_db.use_ui_user_totp("bob", "S", 9) is False  # older window
        assert ui_db.use_ui_user_totp("bob", "S", 11) is True
        assert _user_row(ui_db, "bob").totp_last_counter == 11

    def test_a_counter_for_a_replaced_secret_is_refused(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [], totp_secret="NEW")
        assert ui_db.use_ui_user_totp("bob", "OLD", 10) is False
        assert _user_row(ui_db, "bob").totp_last_counter is None

    @pytest.mark.parametrize("secret, counter", [("", 1), (None, 1), ("S", -1), ("S", "1"), ("S", 1.0)])
    def test_invalid_arguments_are_refused(self, ui_db, secret, counter):
        ui_db.create_ui_user("bob", b"h", [], totp_secret="S")
        assert ui_db.use_ui_user_totp("bob", secret, counter) is False

    def test_read_only_mode_never_consumes(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [], totp_secret="S")
        ui_db.readonly = True
        assert ui_db.use_ui_user_totp("bob", "S", 5) is False
        assert _user_row(ui_db, "bob").totp_last_counter is None

    def test_a_driver_error_is_a_refusal_not_an_exception(self, ui_db, monkeypatch):
        def boom(*_a, **_k):
            raise RuntimeError("driver")

        monkeypatch.setattr(ui_db, "_db_session", boom)
        assert ui_db.use_ui_user_totp("bob", "S", 5) is False


class TestDeleteUiUser:
    def test_every_dependent_row_goes_with_the_user(self, ui_db):
        _make_role(ui_db)
        ui_db.create_ui_user("bob", b"h", ["editor"], totp_recovery_codes=["aaaa-bbbb"])
        ui_db.mark_ui_user_login("bob", DT, "1.2.3.4", "agent")
        ui_db.create_ui_user("keep", b"h", ["editor"], totp_recovery_codes=["cccc-dddd"])
        assert ui_db.delete_ui_user("bob") == ""
        assert _count(ui_db, Users, username="bob") == 0
        for model in (RolesUsers, UserRecoveryCodes, UserColumnsPreferences, UserSessions):
            assert _count(ui_db, model, user_name="bob") == 0
        assert _count(ui_db, RolesUsers, user_name="keep") == 1 and _count(ui_db, UserRecoveryCodes, user_name="keep") == 1

    def test_read_only_mode_keeps_the_user(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        ui_db.readonly = True
        assert ui_db.delete_ui_user("bob") == READONLY
        assert _count(ui_db, Users, username="bob") == 1


class TestSessions:
    def test_last_activity_is_updated_for_the_named_session_only(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        first = ui_db.mark_ui_user_login("bob", DT, "1.1.1.1", "a")
        second = ui_db.mark_ui_user_login("bob", DT, "2.2.2.2", "b")
        later = DT + timedelta(hours=3)
        assert ui_db.mark_ui_user_access(first, later) == ""
        with session(ui_db) as s:
            assert _utc(s.get(UserSessions, first).last_activity) == later
            assert _utc(s.get(UserSessions, second).last_activity) == DT

    def test_read_only_mode_refuses_login_access_and_cleanup(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        session_id = ui_db.mark_ui_user_login("bob", DT, "1.1.1.1", "a")
        ui_db.readonly = True
        assert ui_db.mark_ui_user_login("bob", DT, "1.1.1.1", "a") == READONLY
        assert ui_db.mark_ui_user_access(session_id, DT) == READONLY
        assert ui_db.delete_ui_user_old_sessions("bob") == READONLY
        assert _count(ui_db, UserSessions, user_name="bob") == 1

    def test_delete_old_sessions_for_an_unknown_user(self, ui_db):
        assert ui_db.delete_ui_user_old_sessions("ghost") == "User ghost doesn't exist"

    def test_the_current_session_is_listed_first(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        old = ui_db.mark_ui_user_login("bob", DT, "1.1.1.1", "a")
        newer = ui_db.mark_ui_user_login("bob", DT + timedelta(days=1), "2.2.2.2", "b")
        assert [s["id"] for s in ui_db.get_ui_user_sessions("bob")] == [newer, old]
        assert [s["id"] for s in ui_db.get_ui_user_sessions("bob", old)] == [old, newer]

    def test_a_missing_user_agent_is_reported_as_an_empty_string(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        ui_db.mark_ui_user_login("bob", DT, "1.1.1.1", None)
        assert ui_db.get_ui_user_sessions("bob")[0]["user_agent"] == ""


class TestRoles:
    def test_permissions_are_shared_between_roles_and_listed_per_role(self, ui_db):
        _make_role(ui_db, "reader", ("read",))
        _make_role(ui_db, "writer", ("read", "write"))
        assert _count(ui_db, Permissions, name="read") == 1
        roles = {r["name"]: r for r in ui_db.get_ui_roles(as_dict=True)}
        assert sorted(roles["writer"]["permissions"]) == ["read", "write"]
        assert roles["reader"]["permissions"] == ["read"]
        assert roles["reader"]["description"] == "reader role"

    def test_plain_listing_returns_name_description_and_date(self, ui_db):
        _make_role(ui_db, "reader", ("read",))
        rows = ui_db.get_ui_roles()
        assert [(r.name, r.description) for r in rows] == [("reader", "reader role")]

    def test_a_duplicate_role_keeps_the_first_definition(self, ui_db):
        _make_role(ui_db, "reader", ("read",))
        assert ui_db.create_ui_role("reader", "other", ["write"]) == "Role reader already exists"
        assert ui_db.get_ui_role_permissions("reader") == ["read"]
        assert _count(ui_db, RolesPermissions, role_name="reader") == 1

    def test_read_only_mode_refuses(self, readonly):
        assert readonly.create_ui_role("r", "d", ["read"]) == READONLY
        assert readonly.get_ui_roles() == []

    def test_user_permissions_are_the_union_of_its_roles(self, ui_db):
        _make_role(ui_db, "reader", ("read",))
        _make_role(ui_db, "writer", ("write",))
        ui_db.create_ui_user("bob", b"h", ["reader"])
        add_role_user(ui_db, "bob", "writer")
        assert sorted(ui_db.get_ui_user_permissions("bob")) == ["read", "write"]


class TestRecoveryCodes:
    def test_refresh_replaces_every_stored_code(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [], totp_recovery_codes=["old1-old1"])
        assert ui_db.refresh_ui_user_recovery_codes("bob", ["new1-new1", "new2-new2"]) == ""
        stored = _codes(ui_db, "bob")
        assert len(stored) == 2 and not any(checkpw(b"old1-old1", c.encode()) for c in stored)
        assert ui_db.get_ui_user_recovery_codes("bob") == stored

    def test_a_refused_refresh_keeps_the_old_codes(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [], totp_recovery_codes=["old1-old1"])
        assert ui_db.refresh_ui_user_recovery_codes("bob", []) == "No recovery codes provided"
        assert ui_db.refresh_ui_user_recovery_codes("ghost", ["x"]) == "User ghost doesn't exist"
        assert len(_codes(ui_db, "bob")) == 1
        ui_db.readonly = True
        assert ui_db.refresh_ui_user_recovery_codes("bob", ["x"]) == READONLY
        assert ui_db.delete_ui_user_recovery_codes("bob") == READONLY
        assert len(_codes(ui_db, "bob")) == 1

    def test_delete_removes_only_that_users_codes(self, ui_db):
        ui_db.create_ui_user("a", b"h", [], totp_recovery_codes=["aaaa-aaaa"])
        ui_db.create_ui_user("b", b"h", [], totp_recovery_codes=["bbbb-bbbb"])
        assert ui_db.delete_ui_user_recovery_codes("a") == ""
        assert _codes(ui_db, "a") == [] and len(_codes(ui_db, "b")) == 1

    def test_a_code_is_single_use(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [], totp_recovery_codes=["aaaa-bbbb", "cccc-dddd"])
        first = ui_db.get_ui_user_recovery_codes("bob")[0]
        assert ui_db.use_ui_user_recovery_code("bob", first) == ""
        assert ui_db.use_ui_user_recovery_code("bob", first) == "Invalid recovery code"
        assert len(_codes(ui_db, "bob")) == 1

    def test_another_users_hash_is_not_consumable(self, ui_db):
        ui_db.create_ui_user("a", b"h", [], totp_recovery_codes=["aaaa-aaaa"])
        ui_db.create_ui_user("b", b"h", [])
        assert ui_db.use_ui_user_recovery_code("b", _codes(ui_db, "a")[0]) == "Invalid recovery code"
        assert len(_codes(ui_db, "a")) == 1

    def test_read_only_mode_never_consumes(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [], totp_recovery_codes=["aaaa-bbbb"])
        code = _codes(ui_db, "bob")[0]
        ui_db.readonly = True
        assert ui_db.use_ui_user_recovery_code("bob", code) == READONLY
        assert _codes(ui_db, "bob") == [code]

    def test_a_driver_error_is_reported_generically(self, ui_db, monkeypatch):
        def boom(*_a, **_k):
            raise RuntimeError("driver says secret-detail")

        monkeypatch.setattr(ui_db, "_db_session", boom)
        message = ui_db.use_ui_user_recovery_code("bob", "x")
        assert message == "An error occurred while consuming the recovery code" and "secret-detail" not in message


class TestLoginThrottle:
    KW = {"max_attempts": 3, "window": 60, "lockout": 300}

    def _failures(self, db, username, ip, ages):
        now = datetime.now(timezone.utc)
        with session(db) as s:
            for age in ages:
                s.add(UserLoginFailures(username=username, ip=ip, failure_date=now - timedelta(seconds=age)))

    def test_no_failure_means_no_lock(self, ui_db):
        assert ui_db.get_ui_login_lock("bob", "1.1.1.1", **self.KW) == 0

    def test_below_the_threshold_the_login_stays_open(self, ui_db):
        self._failures(ui_db, "bob", "1.1.1.1", [5, 1])
        assert ui_db.get_ui_login_lock("bob", "9.9.9.9", **self.KW) == 0

    def test_the_threshold_locks_for_the_rest_of_the_lockout(self, ui_db):
        self._failures(ui_db, "bob", "1.1.1.1", [20, 10, 2])
        remaining = ui_db.get_ui_login_lock("bob", "9.9.9.9", **self.KW)
        # MySQL keeps whole seconds, so the 2 s old failure may count as 1 s or 3 s old
        assert 290 <= remaining <= 300

    def test_the_ip_is_locked_independently_of_the_username(self, ui_db):
        self._failures(ui_db, "a", "7.7.7.7", [3])
        self._failures(ui_db, "b", "7.7.7.7", [2])
        self._failures(ui_db, "c", "7.7.7.7", [1])
        assert ui_db.get_ui_login_lock("fresh", "7.7.7.7", **self.KW) > 0
        assert ui_db.get_ui_login_lock("fresh", "8.8.8.8", **self.KW) == 0

    def test_failures_spread_beyond_the_window_do_not_lock(self, ui_db):
        self._failures(ui_db, "bob", "1.1.1.1", [200, 100, 1])
        assert ui_db.get_ui_login_lock("bob", "9.9.9.9", **self.KW) == 0

    def test_an_expired_lockout_is_not_a_lock(self, ui_db):
        self._failures(ui_db, "bob", "1.1.1.1", [400, 399, 398])
        assert ui_db.get_ui_login_lock("bob", "9.9.9.9", **self.KW) == 0

    def test_add_failure_records_the_row_and_prunes_the_expired_ones(self, ui_db):
        self._failures(ui_db, "old", "1.1.1.1", [1000])
        assert ui_db.add_ui_login_failure("bob", "2.2.2.2", retention=500) == ""
        assert _count(ui_db, UserLoginFailures, username="old") == 0
        assert _count(ui_db, UserLoginFailures, username="bob", ip="2.2.2.2") == 1

    def test_clearing_forgets_only_that_username(self, ui_db):
        self._failures(ui_db, "bob", "1.1.1.1", [1, 2])
        self._failures(ui_db, "eve", "1.1.1.1", [1])
        assert ui_db.clear_ui_login_failures("bob") == ""
        assert _count(ui_db, UserLoginFailures, username="bob") == 0 and _count(ui_db, UserLoginFailures, username="eve") == 1

    def test_read_only_mode_refuses_both_writes(self, ui_db):
        self._failures(ui_db, "bob", "1.1.1.1", [1])
        ui_db.readonly = True
        assert ui_db.add_ui_login_failure("bob", "1.1.1.1", retention=10) == READONLY
        assert ui_db.clear_ui_login_failures("bob") == READONLY
        assert _count(ui_db, UserLoginFailures) == 1


class TestColumnsPreferences:
    TABLE = next(iter(COLUMNS_PREFERENCES_DEFAULTS))

    def test_update_is_read_back(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        assert ui_db.update_ui_user_columns_preferences("bob", self.TABLE, {"1": False}) == ""
        assert ui_db.get_ui_user_columns_preferences("bob", self.TABLE) == {"1": False}

    def test_update_refusals(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        assert ui_db.update_ui_user_columns_preferences("ghost", self.TABLE, {}) == "User ghost doesn't exist"
        assert ui_db.update_ui_user_columns_preferences("bob", "nope", {}) == "Table nope doesn't exist"
        ui_db.readonly = True
        assert ui_db.update_ui_user_columns_preferences("bob", self.TABLE, {"1": False}) == READONLY
        assert ui_db.get_ui_user_columns_preferences("bob", self.TABLE) == COLUMNS_PREFERENCES_DEFAULTS[self.TABLE]

    def test_a_missing_row_is_created_from_the_defaults_for_a_real_user(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        with session(ui_db) as s:
            s.query(UserColumnsPreferences).filter_by(user_name="bob", table_name=self.TABLE).delete()
        assert ui_db.get_ui_user_columns_preferences("bob", self.TABLE) == COLUMNS_PREFERENCES_DEFAULTS[self.TABLE]
        assert _count(ui_db, UserColumnsPreferences, user_name="bob", table_name=self.TABLE) == 1

    def test_an_unknown_user_gets_the_defaults_and_no_row(self, ui_db):
        assert ui_db.get_ui_user_columns_preferences("ghost", self.TABLE) == COLUMNS_PREFERENCES_DEFAULTS[self.TABLE]
        assert _count(ui_db, UserColumnsPreferences, user_name="ghost") == 0

    def test_an_unknown_table_yields_an_empty_mapping(self, ui_db):
        ui_db.create_ui_user("bob", b"h", [])
        assert ui_db.get_ui_user_columns_preferences("bob", "nope") == {}


class _FailingCommit:
    """A ``_db_session`` stand-in whose commit raises, as a lost connection or a constraint violation would."""

    def __init__(self, original, message):
        self.ctx = original()
        self.message = message

    def __enter__(self):
        session_ = self.ctx.__enter__()

        def refuse():
            raise RuntimeError(self.message)

        session_.commit = refuse
        return session_

    def __exit__(self, *exc):
        return self.ctx.__exit__(*exc)


class TestCommitFailures:
    """Every writer reports the driver's message instead of raising, and a failed commit stores nothing."""

    @pytest.mark.parametrize(
        "call",
        [
            lambda db: db.create_ui_user("new", b"h", []),
            lambda db: db.update_ui_user("bob", b"changed", None),
            lambda db: db.delete_ui_user("bob"),
            lambda db: db.mark_ui_user_login("bob", DT, "1.1.1.1", "a"),
            lambda db: db.mark_ui_user_access(db.get_ui_user_sessions("bob")[0]["id"], DT),
            lambda db: db.create_ui_role("r", "d", ["read"]),
            lambda db: db.refresh_ui_user_recovery_codes("bob", ["aaaa-bbbb"]),
            lambda db: db.delete_ui_user_recovery_codes("bob"),
            lambda db: db.delete_ui_user_old_sessions("bob"),
            lambda db: db.add_ui_login_failure("bob", "1.1.1.1", retention=10),
            lambda db: db.clear_ui_login_failures("bob"),
            lambda db: db.update_ui_user_columns_preferences("bob", next(iter(COLUMNS_PREFERENCES_DEFAULTS)), {"1": False}),
        ],
        ids=[
            "create_user",
            "update_user",
            "delete_user",
            "mark_login",
            "mark_access",
            "create_role",
            "refresh_codes",
            "delete_codes",
            "delete_old_sessions",
            "add_failure",
            "clear_failures",
            "columns_preferences",
        ],
    )
    def test_the_driver_message_is_returned_and_nothing_is_stored(self, ui_db, monkeypatch, call):
        assert ui_db.create_ui_user("bob", b"h", [], totp_recovery_codes=["old1-old1"]) == ""
        session_id = ui_db.mark_ui_user_login("bob", DT, "9.9.9.9", "seed")
        assert isinstance(session_id, int)
        snapshot = (
            _count(ui_db, Users),
            _count(ui_db, Roles),
            _count(ui_db, UserSessions),
            _count(ui_db, UserLoginFailures),
            _codes(ui_db, "bob"),
            ui_db.get_ui_user_columns_preferences("bob", next(iter(COLUMNS_PREFERENCES_DEFAULTS))),
        )
        original = ui_db._db_session
        monkeypatch.setattr(ui_db, "_db_session", lambda: _FailingCommit(original, "commit refused by driver"))
        assert call(ui_db) == "commit refused by driver"
        monkeypatch.undo()
        assert (
            _count(ui_db, Users),
            _count(ui_db, Roles),
            _count(ui_db, UserSessions),
            _count(ui_db, UserLoginFailures),
            _codes(ui_db, "bob"),
            ui_db.get_ui_user_columns_preferences("bob", next(iter(COLUMNS_PREFERENCES_DEFAULTS))),
        ) == snapshot
