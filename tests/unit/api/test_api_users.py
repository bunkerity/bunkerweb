"""APIUsersMethodsMixin — API user CRUD (create/get/list/update + rename cascade)."""


class TestApiUsers:
    def test_create_and_get_as_dict(self, api_db):
        assert api_db.create_api_user("alice", b"hash", method="manual") == ""
        u = api_db.get_api_user(username="alice", as_dict=True)
        assert u["username"] == "alice"
        assert u["admin"] is False
        assert u["password"] == b"hash"  # stored decoded, returned re-encoded

    def test_get_first_admin_when_username_none(self, api_db):
        api_db.create_api_user("admin", b"h", admin=True)
        api_db.create_api_user("bob", b"h")
        assert api_db.get_api_user().username == "admin"  # username=None -> first admin (ORM object)

    def test_get_missing_returns_none(self, api_db):
        assert api_db.get_api_user(username="ghost") is None

    def test_has_and_list(self, api_db):
        assert api_db.has_api_user() is False
        api_db.create_api_user("admin", b"h", admin=True)
        api_db.create_api_user("bob", b"h")
        assert api_db.has_api_user() is True
        assert dict(api_db.list_api_users()) == {"admin": True, "bob": False}

    def test_duplicate_rejected(self, api_db):
        api_db.create_api_user("alice", b"h")
        assert api_db.create_api_user("alice", b"h2") == "User alice already exists"

    def test_second_admin_rejected(self, api_db):
        api_db.create_api_user("a1", b"h", admin=True)
        assert api_db.create_api_user("a2", b"h", admin=True) == "An admin user already exists"

    def test_update_password(self, api_db):
        api_db.create_api_user("alice", b"h")
        assert api_db.update_api_user("alice", b"new") == ""
        assert api_db.get_api_user(username="alice", as_dict=True)["password"] == b"new"

    def test_update_rename_cascades_permissions(self, api_db):
        api_db.create_api_user("alice", b"h")
        api_db.grant_api_permission("alice", "service_read", resource_type="services", resource_id="s1")
        assert api_db.update_api_user("alice2", b"h", old_username="alice") == ""
        assert api_db.get_api_user(username="alice") is None
        # the permission row followed the rename
        assert api_db.check_api_permission("alice2", "service_read", resource_type="services", resource_id="s1") is True

    def test_update_missing(self, api_db):
        assert api_db.update_api_user("ghost", b"h") == "User ghost doesn't exist"
