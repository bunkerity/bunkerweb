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


def _check(setting_id, ctx, *, default="no"):
    return {"id": setting_id, "context": ctx, "default": default, "help": "h", "label": "L", "regex": "^(yes|no)$", "type": "check"}


class TestSaveConfigCheckNormalization:
    """A1: 'check' values are canonicalized to yes/no when persisted, across the
    global (non-multisite), multisite-global and per-service storage paths."""

    def test_global_check_canonicalized(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_FLAG": _check("alpha-flag", "global")})])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_FLAG": "on"}, "scheduler", skip_service_management=True)
        assert db.get_config()["ALPHA_FLAG"] == "yes"

    def test_multisite_global_and_service_check_canonicalized(self, db):
        db.init_tables(
            [
                make_general_settings(),
                make_core_plugin("alpha", settings={"ALPHA_FLAG": _check("alpha-flag", "global"), "ALPHA_SVC": _check("alpha-svc", "multisite")}),
            ]
        )
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "ALPHA_FLAG": "TRUE", "app1.example.com_ALPHA_SVC": "1"}, "scheduler")
        cfg = db.get_config()
        assert cfg["ALPHA_FLAG"] == "yes"
        assert cfg["app1.example.com_ALPHA_SVC"] == "yes"

    def test_check_idempotent_across_alias_resaves(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_FLAG": _check("alpha-flag", "global")})])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_FLAG": "yes"}, "scheduler", skip_service_management=True)
        db.save_config({"ALPHA_FLAG": "on"}, "scheduler", skip_service_management=True)  # alias of the same canonical state
        assert db.get_config()["ALPHA_FLAG"] == "yes"

    def test_check_update_via_alias_flips_value(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_FLAG": _check("alpha-flag", "global")})])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_FLAG": "yes"}, "scheduler", skip_service_management=True)
        db.save_config({"ALPHA_FLAG": "off"}, "scheduler", skip_service_management=True)  # flip to false via alias
        assert db.get_config()["ALPHA_FLAG"] == "no"

    def test_check_alias_equal_to_default_not_stored(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_FLAG": _check("alpha-flag", "global", default="no")})])
        db.initialize_db("1.7.0", "Docker")
        # "off" canonicalizes to "no" == default -> reads back as the default.
        db.save_config({"ALPHA_FLAG": "off"}, "scheduler", skip_service_management=True)
        assert db.get_config()["ALPHA_FLAG"] == "no"

    def test_check_canonicalized_via_autoconf_method(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_FLAG": _check("alpha-flag", "global")})])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_FLAG": "TRUE"}, "autoconf", skip_service_management=True)
        assert db.get_config()["ALPHA_FLAG"] == "yes"

    def test_text_setting_not_coerced_on_save(self, db):
        # ALPHA_GLOBAL is text (^.*$): a boolean-looking value must persist verbatim.
        db.init_tables([make_general_settings(), make_core_plugin("alpha")])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_GLOBAL": "on"}, "scheduler", skip_service_management=True)
        assert db.get_config()["ALPHA_GLOBAL"] == "on"


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
