"""APIPermissionsMethodsMixin — fine-grained API ACL (grant / revoke / check / list).

Uses the recomposed ``api_db`` fixture. Passwords are opaque bytes at the DB layer
(no bcrypt here), so users are created with placeholder hashes.
"""

import pytest


@pytest.fixture
def adb(api_db):
    api_db.create_api_user("admin", b"hash-admin", method="manual", admin=True)
    api_db.create_api_user("alice", b"hash-alice", method="manual", admin=False)
    return api_db


class TestCheckApiPermission:
    def test_unknown_user_is_false(self, api_db):
        assert api_db.check_api_permission("ghost", "service_read", resource_type="services") is False

    def test_admin_always_true(self, adb):
        assert adb.check_api_permission("admin", "service_read", resource_type="services") is True
        # admin bypass short-circuits before permission/resource validity is considered
        assert adb.check_api_permission("admin", "anything", resource_type="services") is True

    def test_specific_resource_grant(self, adb):
        adb.grant_api_permission("alice", "service_read", resource_type="services", resource_id="svc1")
        assert adb.check_api_permission("alice", "service_read", resource_type="services", resource_id="svc1") is True
        assert adb.check_api_permission("alice", "service_read", resource_type="services", resource_id="other") is False

    def test_global_grant_satisfies_specific_check(self, adb):
        adb.grant_api_permission("alice", "service_read", resource_type="services", resource_id=None)
        assert (
            adb.check_api_permission(
                "alice",
                "service_read",
                resource_type="services",
                resource_id="anything",
            )
            is True
        )

    def test_resource_type_none_matches_any_grant(self, adb):
        adb.grant_api_permission("alice", "service_read", resource_type="services")
        assert adb.check_api_permission("alice", "service_read") is True
        assert adb.check_api_permission("alice", "config_read") is False

    def test_denied_grant_excluded(self, adb):
        adb.grant_api_permission(
            "alice",
            "service_read",
            resource_type="services",
            resource_id="svc1",
            granted=False,
        )
        assert adb.check_api_permission("alice", "service_read", resource_type="services", resource_id="svc1") is False


class TestGrantRevoke:
    def test_web_cache_permissions(self, adb):
        assert adb.grant_api_permission("alice", "web_cache_read", resource_type="web_cache") == ""
        assert adb.check_api_permission("alice", "web_cache_read", resource_type="web_cache") is True
        assert adb.check_api_permission("alice", "web_cache_purge", resource_type="web_cache") is False

    @pytest.mark.parametrize(
        ("permission", "resource_type"),
        [
            ("resource_group_clone", "resource_groups"),
            ("certificate_download", "certificates"),
            ("certificate_revoke", "certificates"),
        ],
    )
    def test_resource_group_and_certificate_permissions(self, adb, permission, resource_type):
        assert adb.grant_api_permission("alice", permission, resource_type=resource_type) == ""
        assert adb.check_api_permission("alice", permission, resource_type=resource_type) is True

    def test_invalid_resource_type(self, adb):
        assert "Invalid resource_type" in adb.grant_api_permission("alice", "service_read", resource_type="bogus")

    def test_invalid_permission(self, adb):
        assert "Invalid permission" in adb.grant_api_permission("alice", "bogus_perm", resource_type="services")

    def test_missing_user(self, adb):
        assert "doesn't exist" in adb.grant_api_permission("ghost", "service_read", resource_type="services")

    def test_grant_is_idempotent_update(self, adb):
        assert adb.grant_api_permission("alice", "service_read", resource_type="services", resource_id="svc1") == ""
        # re-granting the same (user, rtype, rid, perm) updates the row instead of duplicating
        assert (
            adb.grant_api_permission(
                "alice",
                "service_read",
                resource_type="services",
                resource_id="svc1",
                granted=False,
            )
            == ""
        )
        perms = adb.get_api_permissions("alice", include_denied=True)
        assert len(perms) == 1
        assert perms[0].granted is False

    def test_revoke_soft_then_hard(self, adb):
        adb.grant_api_permission("alice", "service_read", resource_type="services", resource_id="svc1")
        # soft revoke keeps the row but flips granted -> False
        assert adb.revoke_api_permission("alice", "service_read", resource_type="services", resource_id="svc1") == ""
        assert len(adb.get_api_permissions("alice", include_denied=True)) == 1
        assert adb.check_api_permission("alice", "service_read", resource_type="services", resource_id="svc1") is False
        # hard delete removes the row
        assert (
            adb.revoke_api_permission(
                "alice",
                "service_read",
                resource_type="services",
                resource_id="svc1",
                hard_delete=True,
            )
            == ""
        )
        assert len(adb.get_api_permissions("alice", include_denied=True)) == 0

    def test_revoke_nonexistent_is_noop(self, adb):
        assert adb.revoke_api_permission("alice", "service_read", resource_type="services", resource_id="x") == ""


class TestGetApiPermissions:
    def test_list_excludes_denied_by_default(self, adb):
        adb.grant_api_permission("alice", "service_read", resource_type="services", resource_id="a")
        adb.grant_api_permission(
            "alice",
            "service_update",
            resource_type="services",
            resource_id="b",
            granted=False,
        )
        assert len(adb.get_api_permissions("alice")) == 1
        assert len(adb.get_api_permissions("alice", include_denied=True)) == 2

    def test_as_dict_nested_shape(self, adb):
        adb.grant_api_permission("alice", "service_read", resource_type="services", resource_id="svc1")
        adb.grant_api_permission("alice", "instances_read", resource_type="instances")  # resource_id None -> "*"
        d = adb.get_api_permissions("alice", as_dict=True)
        assert d["services"]["svc1"]["service_read"] is True
        assert d["instances"]["*"]["instances_read"] is True
