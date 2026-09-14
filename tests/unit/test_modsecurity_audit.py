"""Checks that Concurrent audit validation only applies to scopes that actually use it.

validate_audit_log_settings() raised "STORAGE_DIR is required for Concurrent audit logging"
before working out whether the scope it was inspecting is active. The bare "" prefix is always
iterated and in multisite is only a fallback for services that override it, so two valid
configurations aborted config generation: a global MODSECURITY_SEC_AUDIT_LOG_TYPE=Concurrent
whose services each set their own storage directory, and a service with USE_MODSECURITY=no.

The scope determination now runs first and inactive scopes are skipped, so these tests pin both
halves: the two configurations pass, and a scope that really does use Concurrent without a
directory still fails.

Run from the repo root:

    PYTHONPATH=src/common/utils .venv/bin/python -m unittest discover -s tests/unit
"""

import unittest
from tempfile import TemporaryDirectory

from modsecurity_audit import validate_audit_log_settings


class TestConcurrentAuditScopes(unittest.TestCase):
    def test_global_concurrent_with_per_service_storage_dirs_is_accepted(self):
        # The global scope is only a fallback here; every real service sets its own directory.
        validate_audit_log_settings(
            {
                "MULTISITE": "yes",
                "SERVER_NAME": "a.example.com b.example.com",
                "MODSECURITY_SEC_AUDIT_LOG_TYPE": "Concurrent",
                "a.example.com_MODSECURITY_SEC_AUDIT_LOG_STORAGE_DIR": "/var/log/bunkerweb/audit-a",
                "b.example.com_MODSECURITY_SEC_AUDIT_LOG_STORAGE_DIR": "/var/log/bunkerweb/audit-b",
            }
        )

    def test_service_with_modsecurity_disabled_does_not_need_a_storage_dir(self):
        # ModSecurity never runs for this service, so a missing directory must not block startup.
        validate_audit_log_settings(
            {
                "MULTISITE": "yes",
                "SERVER_NAME": "a.example.com",
                "a.example.com_USE_MODSECURITY": "no",
                "MODSECURITY_SEC_AUDIT_LOG_TYPE": "Concurrent",
            }
        )

    def test_service_inheriting_concurrent_without_a_storage_dir_is_rejected(self):
        # b.example.com inherits the global Concurrent and has no directory of its own.
        with self.assertRaises(ValueError) as ctx:
            validate_audit_log_settings(
                {
                    "MULTISITE": "yes",
                    "SERVER_NAME": "a.example.com b.example.com",
                    "MODSECURITY_SEC_AUDIT_LOG_TYPE": "Concurrent",
                    "a.example.com_MODSECURITY_SEC_AUDIT_LOG_STORAGE_DIR": "/var/log/bunkerweb/audit-a",
                }
            )
        self.assertIn("b.example.com_MODSECURITY_SEC_AUDIT_LOG_STORAGE_DIR", str(ctx.exception))

    def test_single_site_concurrent_still_requires_a_storage_dir(self):
        with self.assertRaises(ValueError):
            validate_audit_log_settings({"MULTISITE": "no", "MODSECURITY_SEC_AUDIT_LOG_TYPE": "Concurrent"})

    def test_global_crs_mode_still_requires_a_storage_dir(self):
        with self.assertRaises(ValueError):
            validate_audit_log_settings(
                {
                    "MULTISITE": "yes",
                    "SERVER_NAME": "a.example.com",
                    "USE_MODSECURITY_GLOBAL_CRS": "yes",
                    "MODSECURITY_SEC_AUDIT_LOG_TYPE": "Concurrent",
                }
            )

    def test_storage_dir_is_checked_on_disk_for_an_active_scope(self):
        config = {"MULTISITE": "no", "MODSECURITY_SEC_AUDIT_LOG_TYPE": "Concurrent"}
        with TemporaryDirectory() as storage:
            config["MODSECURITY_SEC_AUDIT_LOG_STORAGE_DIR"] = storage
            validate_audit_log_settings(config, check_storage=True)
        # The directory is gone once the context exits, so the same config must now fail.
        with self.assertRaises(ValueError):
            validate_audit_log_settings(config, check_storage=True)


if __name__ == "__main__":
    unittest.main()
