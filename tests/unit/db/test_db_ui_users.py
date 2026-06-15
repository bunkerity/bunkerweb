"""Base DatabaseUIUsersMixin (plain Database) — UI-user CRUD used by the API /users router.

`APIDatabase` has no UI-user override, so `db.create_ui_user/update_ui_user/get_ui_user`
resolve to this base mixin (distinct from the UIDatabase override tested under tests/unit/ui/).
Notably the base `create_ui_user` AUTO-CREATES the default roles (admin/writer/reader),
whereas the UI override rejects unknown roles. Exercised via the plain `db` fixture (matrix).
"""


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
