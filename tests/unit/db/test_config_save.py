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


class TestSaveConfigUnitNormalization:
    """B2/B1: size/duration values stored in canonical NGINX form, list items trimmed,
    across the global storage path."""

    def test_size_canonicalized(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_SIZE": _size("alpha-size", "global")})])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_SIZE": "64M"}, "scheduler", skip_service_management=True)
        assert db.get_config()["ALPHA_SIZE"] == "64m"

    def test_duration_compound_canonicalized(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_DUR": _dur("alpha-dur", "global")})])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_DUR": "1h 30m"}, "scheduler", skip_service_management=True)
        assert db.get_config()["ALPHA_DUR"] == "1h30m"

    def test_duration_human_alias_canonicalized(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_DUR": _dur("alpha-dur", "global")})])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_DUR": "5min"}, "scheduler", skip_service_management=True)
        assert db.get_config()["ALPHA_DUR"] == "5m"

    def test_list_items_trimmed(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_LIST": _list("alpha-list", "global")})])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_LIST": " 10.0.0.1  10.0.0.2 "}, "scheduler", skip_service_management=True)
        assert db.get_config()["ALPHA_LIST"] == "10.0.0.1 10.0.0.2"

    def test_per_service_size_canonicalized(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_SVC_SIZE": _size("alpha-svc-size", "multisite")})])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_ALPHA_SVC_SIZE": "16 K"}, "scheduler")
        assert db.get_config()["app1.example.com_ALPHA_SVC_SIZE"] == "16k"


class TestSaveConfigScalarTrim:
    """A2: scalar number/select values are stored trimmed; text is stored verbatim (excluded)."""

    def test_number_stored_trimmed(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_NUM": _num("alpha-num", "global")})])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_NUM": "8080 "}, "scheduler", skip_service_management=True)
        assert db.get_config()["ALPHA_NUM"] == "8080"

    def test_number_trim_idempotent_resave(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_NUM": _num("alpha-num", "global")})])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_NUM": "8080"}, "scheduler", skip_service_management=True)
        db.save_config({"ALPHA_NUM": " 8080 "}, "scheduler", skip_service_management=True)  # same canonical state
        assert db.get_config()["ALPHA_NUM"] == "8080"

    def test_text_stored_verbatim(self, db):
        # text is excluded from trim: surrounding whitespace is preserved on the stored value.
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_TXT": _text("alpha-txt", "global")})])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_TXT": "  hi  "}, "scheduler", skip_service_management=True)
        assert db.get_config()["ALPHA_TXT"] == "  hi  "


class TestSaveConfigSelectCaseInsensitive:
    """A3: opt-in selects are stored canonical (declared option casing) across the global
    (non-multisite) and per-service paths; opt-out selects are stored verbatim."""

    def test_opt_in_select_stored_canonical(self, db):
        # Global (non-multisite) path -> the inline option load in _sc_apply_non_multisite_config.
        settings = {"ALPHA_PICK": _select("alpha-pick", "global", ["modern", "intermediate", "old"], default="modern", case_insensitive=True)}
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings=settings)])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_PICK": "INTERMEDIATE"}, "scheduler", skip_service_management=True)
        assert db.get_config()["ALPHA_PICK"] == "intermediate"

    def test_opt_out_select_stored_verbatim(self, db):
        settings = {"ALPHA_PICK": _select("alpha-pick", "global", ["On", "Off"], default="On", case_insensitive=False)}
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings=settings)])
        db.initialize_db("1.7.0", "Docker")
        # Opt-out: no canonicalization. save_config stores what it's given (validation is elsewhere).
        db.save_config({"ALPHA_PICK": "on"}, "scheduler", skip_service_management=True)
        assert db.get_config()["ALPHA_PICK"] == "on"

    def test_opt_in_idempotent_across_case_resaves(self, db):
        settings = {"ALPHA_PICK": _select("alpha-pick", "global", ["modern", "old"], default="modern", case_insensitive=True)}
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings=settings)])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"ALPHA_PICK": "old"}, "scheduler", skip_service_management=True)
        db.save_config({"ALPHA_PICK": "OLD"}, "scheduler", skip_service_management=True)  # same canonical state
        assert db.get_config()["ALPHA_PICK"] == "old"

    def test_per_service_select_canonical(self, db):
        # Multisite path -> the ctx.settings_dict option map in _sc_process_service.
        settings = {"ALPHA_SVC_PICK": _select("alpha-svc-pick", "multisite", ["modern", "old"], default="modern", case_insensitive=True)}
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings=settings)])
        db.initialize_db("1.7.0", "Docker")
        db.save_config({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com", "app1.example.com_ALPHA_SVC_PICK": "MODERN"}, "scheduler")
        assert db.get_config()["app1.example.com_ALPHA_SVC_PICK"] == "modern"


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
