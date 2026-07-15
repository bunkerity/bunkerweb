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


def _size(setting_id, ctx, *, default="0"):
    return {"id": setting_id, "context": ctx, "default": default, "help": "h", "label": "L", "regex": r"^\d+([kKmMgG])?$", "type": "size"}


def _dur(setting_id, ctx, *, default="0"):
    return {"id": setting_id, "context": ctx, "default": default, "help": "h", "label": "L", "regex": r"^(\d+(ms|s|m|h|d|w|M|y))+$|^\d+$", "type": "duration"}


def _list(setting_id, ctx, *, default=""):
    return {
        "id": setting_id,
        "context": ctx,
        "default": default,
        "help": "h",
        "label": "L",
        "regex": r"^( *([a-z0-9.]+) *)*$",
        "type": "multivalue",
        "separator": " ",
    }


def _num(setting_id, ctx, *, default="0"):
    return {"id": setting_id, "context": ctx, "default": default, "help": "h", "label": "L", "regex": r"^\d+$", "type": "number"}


def _text(setting_id, ctx, *, default=""):
    return {"id": setting_id, "context": ctx, "default": default, "help": "h", "label": "L", "regex": r"^.*$", "type": "text"}


def _select(setting_id, ctx, options, *, default="", case_insensitive=False):
    return {
        "id": setting_id,
        "context": ctx,
        "default": default,
        "help": "h",
        "label": "L",
        "regex": "^(" + "|".join(o for o in options if o) + ")?$",
        "type": "select",
        "select": options,
        "case_insensitive": case_insensitive,
    }


class TestSaveConfigNormalization:
    def test_global_values_are_canonicalized_together(self, db):
        settings = {
            "ALPHA_FLAG": _check("alpha-flag", "global"),
            "ALPHA_SIZE": _size("alpha-size", "global"),
            "ALPHA_DUR": _dur("alpha-dur", "global"),
            "ALPHA_LIST": _list("alpha-list", "global"),
            "ALPHA_NUM": _num("alpha-num", "global"),
            "ALPHA_TXT": _text("alpha-txt", "global"),
            "ALPHA_PICK": _select("alpha-pick", "global", ["modern", "intermediate", "old"], default="modern", case_insensitive=True),
            "ALPHA_RAW_PICK": _select("alpha-raw-pick", "global", ["On", "Off"], default="On"),
        }
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings=settings)])
        db.initialize_db("1.7.0", "Docker")

        db.save_config(
            {
                "ALPHA_FLAG": "on",
                "ALPHA_SIZE": "64 M",
                "ALPHA_DUR": "1h 30m",
                "ALPHA_LIST": " 10.0.0.1  10.0.0.2 ",
                "ALPHA_NUM": "8080 ",
                "ALPHA_TXT": "  on  ",
                "ALPHA_PICK": "INTERMEDIATE",
                "ALPHA_RAW_PICK": "on",
            },
            "scheduler",
            skip_service_management=True,
        )

        config = db.get_config()
        assert config["ALPHA_FLAG"] == "yes"
        assert config["ALPHA_SIZE"] == "64m"
        assert config["ALPHA_DUR"] == "1h30m"
        assert config["ALPHA_LIST"] == "10.0.0.1 10.0.0.2"
        assert config["ALPHA_NUM"] == "8080"
        assert config["ALPHA_TXT"] == "  on  "
        assert config["ALPHA_PICK"] == "intermediate"
        assert config["ALPHA_RAW_PICK"] == "on"

    def test_multisite_values_are_canonicalized(self, db):
        settings = {
            "ALPHA_FLAG": _check("alpha-flag", "global"),
            "ALPHA_SVC_FLAG": _check("alpha-svc-flag", "multisite"),
            "ALPHA_SVC_SIZE": _size("alpha-svc-size", "multisite"),
            "ALPHA_SVC_PICK": _select("alpha-svc-pick", "multisite", ["modern", "old"], default="modern", case_insensitive=True),
        }
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings=settings)])
        db.initialize_db("1.7.0", "Docker")

        db.save_config(
            {
                "MULTISITE": "yes",
                "SERVER_NAME": "app1.example.com",
                "ALPHA_FLAG": "TRUE",
                "app1.example.com_ALPHA_SVC_FLAG": "1",
                "app1.example.com_ALPHA_SVC_SIZE": "16 K",
                "app1.example.com_ALPHA_SVC_PICK": "MODERN",
            },
            "scheduler",
        )

        config = db.get_config()
        assert config["ALPHA_FLAG"] == "yes"
        assert config["app1.example.com_ALPHA_SVC_FLAG"] == "yes"
        assert config["app1.example.com_ALPHA_SVC_SIZE"] == "16k"
        assert config["app1.example.com_ALPHA_SVC_PICK"] == "modern"

    def test_autoconf_and_default_paths(self, db):
        settings = {
            "ALPHA_FLAG": _check("alpha-flag", "global"),
            "ALPHA_DEFAULT": _check("alpha-default", "global", default="no"),
        }
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings=settings)])
        db.initialize_db("1.7.0", "Docker")

        db.save_config({"ALPHA_FLAG": "TRUE", "ALPHA_DEFAULT": "off"}, "autoconf", skip_service_management=True)

        assert db.get_config()["ALPHA_FLAG"] == "yes"
        assert db.get_config()["ALPHA_DEFAULT"] == "no"


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
