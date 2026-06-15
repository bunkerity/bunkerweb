"""Integration tier — DatabaseConfigSaveMixin.save_config (config persistence).

End-to-end: init_tables seeds the plugin/settings schema, then save_config persists a flat
config dict, and we read it back via get_config. Exercises the global path, the multisite
service-reconciliation path, idempotency and the readonly guard, on every engine.
"""

import pytest

from fixtures.seed import make_core_plugin, make_general_settings

pytestmark = pytest.mark.slow


@pytest.fixture
def seeded(db):
    db.init_tables([make_general_settings(), make_core_plugin("alpha")])
    db.initialize_db("1.7.0", "Docker")  # Metadata row for change-flag bookkeeping
    return db


class TestSaveConfigGlobal:
    def test_global_setting_persisted(self, seeded):
        result = seeded.save_config({"ALPHA_GLOBAL": "hello"}, "scheduler", skip_service_management=True)
        assert isinstance(result, set)  # success returns the changed-plugins set (str only on error)
        assert seeded.get_config()["ALPHA_GLOBAL"] == "hello"

    def test_idempotent(self, seeded):
        seeded.save_config({"ALPHA_GLOBAL": "hello"}, "scheduler", skip_service_management=True)
        seeded.save_config({"ALPHA_GLOBAL": "hello"}, "scheduler", skip_service_management=True)
        assert seeded.get_config()["ALPHA_GLOBAL"] == "hello"

    def test_readonly_guard(self, seeded):
        seeded.readonly = True
        try:
            assert seeded.save_config({"ALPHA_GLOBAL": "x"}, "scheduler") == "The database is read-only, the changes will not be saved"
        finally:
            seeded.readonly = False


class TestSaveConfigMultisite:
    def test_service_created_and_setting_persisted(self, seeded):
        result = seeded.save_config(
            {"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_ALPHA_MS": "v1"},
            "scheduler",
        )
        assert isinstance(result, set)
        assert "app1.example.com" in {s["id"] for s in seeded.get_services()}
        assert seeded.get_config()["app1.example.com_ALPHA_MS"] == "v1"

    def test_two_services(self, seeded):
        # A service materializes once it carries a setting (realistic multisite config).
        seeded.save_config(
            {
                "MULTISITE": "yes",
                "SERVER_NAME": "app1.example.com app2.example.com",
                "app1.example.com_ALPHA_MS": "v1",
                "app2.example.com_ALPHA_MS": "v2",
            },
            "scheduler",
        )
        assert {s["id"] for s in seeded.get_services()} == {"app1.example.com", "app2.example.com"}
