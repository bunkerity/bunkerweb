"""Checks that the global settings authorizer asks for a grant that can actually exist.

The Biscuit guard resolved /global_settings to resource type "global_settings" and permissions
named "global_settings_*", but the database enums only hold "global_config" and
"global_config_*". Neither part of the grant could match, so every non-admin API user was refused,
and the admin-equivalent warning on global_config_update could never fire.

Run from the repo root:

    PYTHONPATH=src/api:src/common/utils:src/common/db .venv/bin/python -m unittest discover -s src/api/tests
"""

import unittest

from app.auth.biscuit import _resolve_global_settings, _resolve_resource_and_perm
from model import API_PERMISSION_ENUM, API_RESOURCE_ENUM


class TestGlobalSettingsPermission(unittest.TestCase):
    def test_resolved_permissions_exist_in_the_enum(self):
        for method in ("GET", "POST", "PUT", "PATCH"):
            rtype, permission = _resolve_global_settings(method)
            self.assertIn(rtype, API_RESOURCE_ENUM.enums, f"{method} resolves to ungrantable resource type {rtype!r}")
            self.assertIsNotNone(permission, f"{method} resolved to no permission")
            self.assertIn(permission, API_PERMISSION_ENUM.enums, f"{method} resolves to ungrantable {permission!r}")

    def test_all_resolved_paths_use_grantable_enums(self):
        for path in ("/instances", "/global_settings", "/global_config", "/services", "/configs", "/plugins", "/cache", "/bans", "/jobs"):
            with self.subTest(path=path):
                rtype, permission = _resolve_resource_and_perm(path, "GET")
                self.assertIn(rtype, API_RESOURCE_ENUM.enums, f"{path} resolves to ungrantable resource type {rtype!r}")
                self.assertIn(permission, API_PERMISSION_ENUM.enums, f"{path} resolves to ungrantable permission {permission!r}")

    def test_read_and_update_names(self):
        self.assertEqual(_resolve_global_settings("GET")[1], "global_config_read")
        self.assertEqual(_resolve_global_settings("POST")[1], "global_config_update")
        self.assertEqual(_resolve_global_settings("PUT")[1], "global_config_update")
        self.assertEqual(_resolve_global_settings("PATCH")[1], "global_config_update")

    def test_delete_has_no_mapping(self):
        self.assertIsNone(_resolve_global_settings("DELETE")[1])


if __name__ == "__main__":
    unittest.main()
