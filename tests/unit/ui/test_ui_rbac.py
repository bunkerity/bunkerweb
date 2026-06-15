"""UIRBACMethodsMixin — UI roles, permission aggregation and recovery codes."""

from fixtures.seed import add_role_user, add_ui_user


class TestRoles:
    def test_create_and_get_roles(self, ui_db):
        assert ui_db.create_ui_role("editor", "Can edit", ["read", "write"]) == ""
        editor = next(r for r in ui_db.get_ui_roles(as_dict=True) if r["name"] == "editor")
        assert set(editor["permissions"]) == {"read", "write"}

    def test_duplicate_role_rejected(self, ui_db):
        ui_db.create_ui_role("editor", "x", ["read"])
        assert ui_db.create_ui_role("editor", "y", ["write"]) == "Role editor already exists"

    def test_get_role_permissions(self, ui_db):
        ui_db.create_ui_role("viewer", "x", ["read"])
        assert ui_db.get_ui_role_permissions("viewer") == ["read"]


class TestUserPermissions:
    def test_aggregates_across_roles_without_dedupe(self, ui_db):
        # PINNING current behavior: get_ui_user_permissions concatenates each role's
        # permissions and does NOT dedupe — a shared permission appears once per role.
        ui_db.create_ui_role("role_a", "x", ["read", "write"])
        ui_db.create_ui_role("role_b", "y", ["read"])
        add_ui_user(ui_db, "bob")
        add_role_user(ui_db, "bob", "role_a")
        add_role_user(ui_db, "bob", "role_b")
        assert sorted(ui_db.get_ui_user_permissions("bob")) == ["read", "read", "write"]


class TestRecoveryCodes:
    def test_refresh_use_and_delete(self, ui_db):
        add_ui_user(ui_db, "carol")
        assert ui_db.refresh_ui_user_recovery_codes("carol", ["code1", "code2"]) == ""
        stored = ui_db.get_ui_user_recovery_codes("carol")
        assert len(stored) == 2  # stored values are bcrypt hashes, not the plaintext codes
        assert "code1" not in stored

        # using a code by its stored hash deletes that single row
        assert ui_db.use_ui_user_recovery_code("carol", stored[0]) == ""
        assert len(ui_db.get_ui_user_recovery_codes("carol")) == 1
        # an unknown hash is rejected
        assert ui_db.use_ui_user_recovery_code("carol", "nope") == "Invalid recovery code"
        # delete the remainder
        assert ui_db.delete_ui_user_recovery_codes("carol") == ""
        assert ui_db.get_ui_user_recovery_codes("carol") == []

    def test_refresh_missing_user(self, ui_db):
        assert ui_db.refresh_ui_user_recovery_codes("ghost", ["c"]) == "User ghost doesn't exist"

    def test_refresh_empty_codes_rejected(self, ui_db):
        add_ui_user(ui_db, "dave")
        assert ui_db.refresh_ui_user_recovery_codes("dave", []) == "No recovery codes provided"
