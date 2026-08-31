"""Integration tier — DatabaseConfigSaveMixin.save_config (config persistence).

End-to-end: init_tables seeds the plugin/settings schema, then save_config persists a flat
config dict, and we read it back via get_config. Exercises the global path, the multisite
service-reconciliation path, idempotency and the readonly guard, on every engine.
"""

import pytest

from fixtures.seed import add_global_value, make_core_plugin, make_general_settings, session
from model import ResourceAttachments, Resources, Upstreams

pytestmark = pytest.mark.slow


@pytest.fixture
def seeded(db):
    db.init_tables([make_general_settings(), make_core_plugin("alpha")])
    db.initialize_db("1.7.0", "Docker")  # Metadata row for change-flag bookkeeping
    return db


def _check(setting_id, ctx, *, default="no"):
    return {
        "id": setting_id,
        "context": ctx,
        "default": default,
        "help": "h",
        "label": "L",
        "regex": "^(yes|no)$",
        "type": "check",
    }


def _size(setting_id, ctx, *, default="0"):
    return {
        "id": setting_id,
        "context": ctx,
        "default": default,
        "help": "h",
        "label": "L",
        "regex": r"^\d+([kKmMgG])?$",
        "type": "size",
    }


def _dur(setting_id, ctx, *, default="0"):
    return {
        "id": setting_id,
        "context": ctx,
        "default": default,
        "help": "h",
        "label": "L",
        "regex": r"^(\d+(ms|s|m|h|d|w|M|y))+$|^\d+$",
        "type": "duration",
    }


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
    return {
        "id": setting_id,
        "context": ctx,
        "default": default,
        "help": "h",
        "label": "L",
        "regex": r"^\d+$",
        "type": "number",
    }


def _text(setting_id, ctx, *, default=""):
    return {
        "id": setting_id,
        "context": ctx,
        "default": default,
        "help": "h",
        "label": "L",
        "regex": r"^.*$",
        "type": "text",
    }


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
            "ALPHA_PICK": _select(
                "alpha-pick",
                "global",
                ["modern", "intermediate", "old"],
                default="modern",
                case_insensitive=True,
            ),
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
                "ALPHA_RAW_PICK": "On",
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
        assert config["ALPHA_RAW_PICK"] == "On"

    def test_a_case_mismatched_value_for_a_case_sensitive_select_is_refused(self, db):
        """Documents a deliberate behaviour change: before the save_config validation gate this
        stored the raw "on" for a ["On", "Off"] select, i.e. a value no consumer could match."""
        settings = {"ALPHA_RAW_PICK": _select("alpha-raw-pick", "global", ["On", "Off"], default="On")}
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings=settings)])
        db.initialize_db("1.7.0", "Docker")

        result = db.save_config({"ALPHA_RAW_PICK": "on"}, "scheduler", skip_service_management=True)

        assert isinstance(result, str) and "ALPHA_RAW_PICK" in result
        assert db.get_config()["ALPHA_RAW_PICK"] == "On"

    def test_a_preexisting_invalid_row_does_not_block_an_unrelated_save(self, db):
        """The merged config a caller hands us can carry illegal legacy rows. Validating all of it
        would let one of them refuse every future save; only the deltas are checked."""
        settings = {
            "ALPHA_RAW_PICK": _select("alpha-raw-pick", "global", ["On", "Off"], default="On"),
            "ALPHA_TXT": _text("alpha-txt", "global"),
        }
        db.init_tables([make_general_settings(), make_core_plugin("alpha", settings=settings)])
        db.initialize_db("1.7.0", "Docker")
        add_global_value(db, setting_id="ALPHA_RAW_PICK", value="on", method="scheduler")

        # Re-saving the merged snapshot carries the bad row along untouched; the real change is elsewhere.
        merged = db.get_config()
        merged["ALPHA_TXT"] = "fresh"
        result = db.save_config(merged, "scheduler", skip_service_management=True)

        assert not isinstance(result, str), result
        assert db.get_config()["ALPHA_TXT"] == "fresh"

    def test_multisite_values_are_canonicalized(self, db):
        settings = {
            "ALPHA_FLAG": _check("alpha-flag", "global"),
            "ALPHA_SVC_FLAG": _check("alpha-svc-flag", "multisite"),
            "ALPHA_SVC_SIZE": _size("alpha-svc-size", "multisite"),
            "ALPHA_SVC_PICK": _select(
                "alpha-svc-pick",
                "multisite",
                ["modern", "old"],
                default="modern",
                case_insensitive=True,
            ),
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

        db.save_config(
            {"ALPHA_FLAG": "TRUE", "ALPHA_DEFAULT": "off"},
            "autoconf",
            skip_service_management=True,
        )

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

    def test_invalid_values_are_rejected_before_any_write(self, seeded):
        result = seeded.save_config({"ALPHA_GLOBAL": "ok", "ALPHA_CHECK": "maybe"}, "scheduler", skip_service_management=True)
        assert result.startswith("Invalid setting ALPHA_CHECK:")
        assert seeded.get_config()["ALPHA_GLOBAL"] == "def"


class TestSaveConfigResourceGroups:
    @pytest.fixture
    def resource_groups_db(self, db):
        settings = {
            "BLACKLIST_IP": _list("blacklist-ip", "global"),
            "BLACKLIST_COUNTRY": _list("blacklist-country", "global"),
            "BLACKLIST_RULE": {
                "id": "blacklist-rule",
                "context": "global",
                "default": "",
                "help": "h",
                "label": "L",
                "regex": r"^$|^(?:NOT )?(?:ip|country|asn|rdns|ua|user_agent|uri):(?:(?! [Aa][Nn][Dd](?: |$)).)+(?: AND (?:NOT )?(?:ip|country|asn|rdns|ua|user_agent|uri):(?:(?! [Aa][Nn][Dd](?: |$)).)+)*$",
                "type": "text",
                "multiple": "blacklist-rules",
            },
        }
        db.init_tables([make_general_settings(), make_core_plugin("blacklist", settings=settings)])
        db.initialize_db("1.7.0", "Docker")
        db.create_resource_group("office", name="office", entries=[{"kind": "ip", "value": "192.0.2.1"}])
        db.create_resource_group("countries", name="countries", entries=[{"kind": "country", "value": "FR"}])
        return db

    def test_unknown_group_is_rejected_before_save(self, resource_groups_db):
        result = resource_groups_db.save_config({"BLACKLIST_IP": "@typo"}, "ui", skip_service_management=True)
        assert result == "Unknown resource group @typo referenced by BLACKLIST_IP"
        assert resource_groups_db.get_config()["BLACKLIST_IP"] == ""

    def test_unknown_group_inside_a_rule_term_is_rejected_before_save(self, resource_groups_db):
        # The only @group reference sits inside a *_RULE value: without the is_rule_key gate
        # the whole validation block is skipped and the typo saves silently.
        result = resource_groups_db.save_config({"BLACKLIST_RULE_1": "ip:@typo AND ua:^curl"}, "ui", skip_service_management=True)
        assert isinstance(result, str) and "@typo" in result and "BLACKLIST_RULE_1" in result
        assert resource_groups_db.get_config().get("BLACKLIST_RULE_1", "") == ""

    def test_wrong_kind_group_is_rejected_before_save(self, resource_groups_db):
        result = resource_groups_db.save_config({"BLACKLIST_IP": "@countries"}, "ui", skip_service_management=True)
        assert result == "Resource group @countries has no ip entries required by BLACKLIST_IP"
        assert resource_groups_db.get_config()["BLACKLIST_IP"] == ""

    def test_valid_group_is_saved(self, resource_groups_db):
        result = resource_groups_db.save_config({"BLACKLIST_IP": "@office"}, "ui", skip_service_management=True)
        assert isinstance(result, set)
        assert resource_groups_db.get_config()["BLACKLIST_IP"] == "@office"

    def test_reserved_country_alias_is_saved_without_seeded_group(self, resource_groups_db):
        result = resource_groups_db.save_config({"BLACKLIST_COUNTRY": "@EU"}, "ui", skip_service_management=True)
        assert isinstance(result, set)
        assert resource_groups_db.get_config()["BLACKLIST_COUNTRY"] == "@EU"


class TestSaveConfigMultisite:
    def test_service_created_and_setting_persisted(self, seeded):
        result = seeded.save_config(
            {
                "MULTISITE": "yes",
                "SERVER_NAME": "app1.example.com",
                "app1.example.com_ALPHA_MS": "v1",
            },
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
        assert {s["id"] for s in seeded.get_services()} == {
            "app1.example.com",
            "app2.example.com",
        }

    def test_reconciliation_deletes_resource_attachments_before_services(self, seeded):
        seeded.save_config(
            {"MULTISITE": "yes", "SERVER_NAME": "old.example.com", "old.example.com_ALPHA_MS": "v1"},
            "scheduler",
        )
        with session(seeded) as db_session:
            now = db_session.get(Resources, "pool")
            assert now is None
            from datetime import datetime, timezone

            timestamp = datetime.now(timezone.utc)
            db_session.add(Resources(id="pool", type="upstream", name="pool", creation_date=timestamp, last_update=timestamp))
            db_session.add(Upstreams(resource_id="pool", protocol="http", method="round_robin"))
            db_session.add(ResourceAttachments(resource_id="pool", service_id="old.example.com", creation_date=timestamp))

        result = seeded.save_config(
            {"MULTISITE": "yes", "SERVER_NAME": "new.example.com", "new.example.com_ALPHA_MS": "v2"},
            "scheduler",
        )
        assert isinstance(result, set)
        with session(seeded) as db_session:
            assert db_session.query(ResourceAttachments).filter_by(service_id="old.example.com").count() == 0
