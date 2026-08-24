"""DatabaseTemplatesMixin — service template create/get/delete + validation."""

from fixtures.seed import (
    add_global_value,
    add_select_setting,
    add_service_setting,
    add_setting,
    seed_minimal,
)


def _minimal_template_args():
    # USE_REVERSE_PROXY exists in seed_minimal's Settings, so the base-id check passes.
    return {
        "name": "Low",
        "settings": {"USE_REVERSE_PROXY": "yes"},
        "steps": [{"title": "Step 1", "settings": ["USE_REVERSE_PROXY"]}],
    }


def _seed_resource_group_templates(db):
    seed_minimal(db)
    add_setting(db, "BLACKLIST_IP", context="multisite", type="multivalue")
    add_setting(db, "BLACKLIST_COUNTRY", context="multisite", type="multivalue")
    db.create_resource_group("office", name="office", entries=[{"kind": "ip", "value": "192.0.2.1"}])
    db.create_resource_group("countries", name="countries", entries=[{"kind": "country", "value": "FR"}])


def _resource_template_args(setting_id, value, *, name="Security"):
    return {
        "name": name,
        "settings": {setting_id: value},
        "steps": [{"title": "Security", "settings": [setting_id]}],
    }


class TestCreateTemplate:
    def test_create_and_get(self, db):
        seed_minimal(db)
        assert db.create_template("low", **_minimal_template_args()) == ""
        tmpls = db.get_templates()
        assert "low" in tmpls
        assert tmpls["low"]["name"] == "Low"
        assert tmpls["low"]["settings"]["USE_REVERSE_PROXY"] == "yes"

    def test_duplicate_id_rejected(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        args = _minimal_template_args() | {"name": "Low2"}
        assert db.create_template("low", **args) == "Template low already exists"

    def test_requires_a_step(self, db):
        seed_minimal(db)
        assert db.create_template("x", name="X", settings={}, steps=[]) == "A template must contain at least one step"

    def test_step_references_unknown_setting(self, db):
        seed_minimal(db)
        msg = db.create_template(
            "x",
            name="X",
            settings={"USE_REVERSE_PROXY": "yes"},
            steps=[{"title": "S", "settings": ["NOPE"]}],
        )
        assert "references unknown setting" in msg

    def test_unknown_base_setting_rejected(self, db):
        seed_minimal(db)
        msg = db.create_template(
            "x",
            name="X",
            settings={"FAKE": "v"},
            steps=[{"title": "S", "settings": ["FAKE"]}],
        )
        assert "Unknown settings" in msg

    def test_defaults_are_normalized_together(self, db):
        seed_minimal(db)
        add_setting(db, "MEM_SIZE", type="size", regex=r"^\d+([kKmMgG])?$", default="0")
        add_setting(
            db,
            "MY_TIMEOUT",
            type="duration",
            regex=r"^(\d+(ms|s|m|h|d|w|M|y))+$|^\d+$",
            default="0",
        )
        add_setting(db, "TEST_PORT", type="number", regex=r"^\d+$", default="0")
        add_select_setting(
            db,
            "CIPHERS",
            ["modern", "intermediate", "old"],
            default="modern",
            case_insensitive=True,
        )
        add_select_setting(db, "SEC_ENGINE", ["On", "Off"], default="On", case_insensitive=False)
        settings = {
            "USE_REVERSE_PROXY": "true",
            "SECURITY_MODE": "  on  ",
            "MEM_SIZE": "64 M",
            "MY_TIMEOUT": "5min",
            "TEST_PORT": "8080 ",
            "CIPHERS": "Modern",
            "SEC_ENGINE": "On",
        }

        assert (
            db.create_template(
                "t",
                name="T",
                settings=settings,
                steps=[{"title": "S", "settings": list(settings)}],
            )
            == ""
        )
        assert db.get_template_settings("t") == {
            "USE_REVERSE_PROXY": "yes",
            "SECURITY_MODE": "  on  ",
            "MEM_SIZE": "64m",
            "MY_TIMEOUT": "5m",
            "TEST_PORT": "8080",
            "CIPHERS": "modern",
            "SEC_ENGINE": "On",
        }

    def test_invalid_duration_default_is_rejected(self, db):
        seed_minimal(db)
        add_setting(
            db,
            "MY_TIMEOUT",
            context="multisite",
            type="duration",
            regex=r"^(\d+(ms|s|m|h|d|w|M|y))+$|^\d+$",
            default="0",
        )

        message = db.create_template(
            "bad",
            name="Bad",
            settings={"MY_TIMEOUT": "30m1h"},
            steps=[{"title": "S", "settings": ["MY_TIMEOUT"]}],
        )

        assert message == "Invalid value for setting MY_TIMEOUT: not a valid duration"
        assert "bad" not in db.get_templates()

    def test_update_template_check_default_canonicalized(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())  # USE_REVERSE_PROXY default "yes"
        msg = db.update_template(
            "low",
            name="Low",
            settings={"USE_REVERSE_PROXY": "off"},
            steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY"]}],
        )
        assert msg == ""
        assert db.get_template_settings("low") == {"USE_REVERSE_PROXY": "no"}


class TestGetTemplateSettings:
    def test_get_template_settings(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        assert db.get_template_settings("low") == {"USE_REVERSE_PROXY": "yes"}


class TestDeleteTemplate:
    def test_delete(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        assert db.delete_template("low") == ""
        assert "low" not in db.get_templates()

    def test_delete_missing(self, db):
        seed_minimal(db)
        assert db.delete_template("ghost") == "Template not found"

    def test_delete_referenced_by_global_blocked(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        add_global_value(db, setting_id="USE_TEMPLATE", value="low")
        assert db.delete_template("low") == "Template is currently used by the global settings"


class TestTemplateDetailsAndUpdate:
    def test_get_template_details(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        details = db.get_template_details("low")
        assert details["id"] == "low"
        assert details["name"] == "Low"
        assert len(details["steps"]) == 1
        assert any(s["key"] == "USE_REVERSE_PROXY" for s in details["settings"])

    def test_get_template_details_missing(self, db):
        seed_minimal(db)
        assert db.get_template_details("ghost") is None

    def test_update_template_name(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        assert db.update_template("low", name="Low Renamed") == ""
        assert db.get_templates()["low"]["name"] == "Low Renamed"

    def test_update_template_missing(self, db):
        seed_minimal(db)
        assert db.update_template("ghost", name="x") == "Template not found"


def _args_with_config():
    # server_http is a valid server-scoped template config type; the step must reference it.
    return {
        "name": "Low",
        "settings": {"USE_REVERSE_PROXY": "yes"},
        "steps": [
            {
                "title": "Step 1",
                "settings": ["USE_REVERSE_PROXY"],
                "configs": ["server_http/cfg.conf"],
            }
        ],
        "configs": [{"type": "server_http", "name": "cfg", "data": "# tmpl-data"}],
    }


class TestCreateTemplateWithConfigs:
    def test_create_with_config_persists(self, db):
        seed_minimal(db)
        assert db.create_template("low", **_args_with_config()) == ""
        configs = db.get_templates()["low"]["configs"]
        assert configs["server_http/cfg.conf"] == "# tmpl-data"

    def test_details_expose_config(self, db):
        seed_minimal(db)
        db.create_template("low", **_args_with_config())
        details = db.get_template_details("low")
        assert any(c["key"] == "server_http/cfg.conf" and c["data"] == "# tmpl-data" for c in details["configs"])


class TestTemplateConfigValidation:
    def _create(self, db, *, steps, configs):
        return db.create_template(
            "x",
            name="X",
            settings={"USE_REVERSE_PROXY": "yes"},
            steps=steps,
            configs=configs,
        )

    def test_config_entry_not_dict(self, db):
        seed_minimal(db)
        msg = self._create(
            db,
            steps=[
                {
                    "title": "S",
                    "settings": ["USE_REVERSE_PROXY"],
                    "configs": ["server_http/c.conf"],
                }
            ],
            configs=["not-a-dict"],
        )
        assert msg == "Config entries must be objects"

    def test_step_references_unknown_config(self, db):
        seed_minimal(db)
        msg = self._create(
            db,
            steps=[
                {
                    "title": "S",
                    "settings": ["USE_REVERSE_PROXY"],
                    "configs": ["server_http/ghost.conf"],
                }
            ],
            configs=[],
        )
        assert "unknown config" in msg

    def test_config_not_assigned_to_step(self, db):
        seed_minimal(db)
        msg = self._create(
            db,
            steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY"]}],
            configs=[{"type": "server_http", "name": "c", "data": "# d"}],
        )
        assert "is not assigned to any step" in msg

    def test_duplicate_config_rejected(self, db):
        seed_minimal(db)
        msg = self._create(
            db,
            steps=[
                {
                    "title": "S",
                    "settings": ["USE_REVERSE_PROXY"],
                    "configs": ["server_http/dup.conf"],
                }
            ],
            configs=[
                {"type": "server_http", "name": "dup", "data": "# a"},
                {"type": "server-http", "name": "dup", "data": "# b"},
            ],
        )
        assert "Duplicate config" in msg


class TestTemplateSettingValidation:
    def test_step_missing_title(self, db):
        seed_minimal(db)
        assert db.create_template("x", name="X", settings={}, steps=[{"settings": []}]) == "Step 1 must have a title"

    def test_setting_not_assigned_to_step(self, db):
        seed_minimal(db)
        msg = db.create_template(
            "x",
            name="X",
            settings={"USE_REVERSE_PROXY": "yes"},
            steps=[{"title": "S", "settings": []}],
        )
        assert "are not assigned to any step" in msg

    def test_setting_assigned_to_multiple_steps(self, db):
        seed_minimal(db)
        msg = db.create_template(
            "x",
            name="X",
            settings={"USE_REVERSE_PROXY": "yes"},
            steps=[
                {"title": "S1", "settings": ["USE_REVERSE_PROXY"]},
                {"title": "S2", "settings": ["USE_REVERSE_PROXY"]},
            ],
        )
        assert "assigned to multiple steps" in msg

    def test_restricted_setting_rejected(self, db):
        seed_minimal(db)
        # USE_TEMPLATE is in RESTRICTED_TEMPLATE_SETTINGS -> cannot live inside a template.
        msg = db.create_template(
            "x",
            name="X",
            settings={"USE_TEMPLATE": "low"},
            steps=[{"title": "S", "settings": ["USE_TEMPLATE"]}],
        )
        assert msg == "Setting USE_TEMPLATE cannot be part of a template"


class TestTemplateResourceGroupValidation:
    def test_create_rejects_unknown_and_wrong_kind_groups(self, db):
        _seed_resource_group_templates(db)
        assert db.create_template("unknown", **_resource_template_args("BLACKLIST_IP", "@typo")) == "Unknown resource group @typo referenced by BLACKLIST_IP"
        assert (
            db.create_template("wrong-kind", **_resource_template_args("BLACKLIST_IP", "@countries"))
            == "Resource group @countries has no ip entries required by BLACKLIST_IP"
        )

    def test_create_accepts_valid_and_legacy_country_groups(self, db):
        _seed_resource_group_templates(db)
        assert db.create_template("valid", **_resource_template_args("BLACKLIST_IP", "@office")) == ""
        assert (
            db.create_template(
                "legacy",
                **_resource_template_args("BLACKLIST_COUNTRY", "@EU", name="Legacy"),
            )
            == ""
        )

    def test_update_rejects_invalid_group_without_replacing_settings(self, db):
        _seed_resource_group_templates(db)
        assert db.create_template("security", **_resource_template_args("BLACKLIST_IP", "@office")) == ""

        result = db.update_template(
            "security",
            settings={"BLACKLIST_IP": "@typo"},
            steps=[{"title": "Security", "settings": ["BLACKLIST_IP"]}],
        )

        assert result == "Unknown resource group @typo referenced by BLACKLIST_IP"
        assert db.get_template_settings("security") == {"BLACKLIST_IP": "@office"}


class TestCreateTemplateGuards:
    def test_name_already_exists(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())  # name "Low"
        assert db.create_template("other", **_minimal_template_args()) == "Template name Low already exists"

    def test_unknown_plugin_rejected(self, db):
        seed_minimal(db)
        assert db.create_template("low", plugin_id="ghostplugin", **_minimal_template_args()) == "Plugin ghostplugin does not exist"

    def test_known_plugin_accepted(self, db):
        seed_minimal(db)
        # 'general' plugin exists from seed_minimal.
        assert db.create_template("low", plugin_id="general", **_minimal_template_args()) == ""
        assert db.get_templates()["low"]["plugin_id"] == "general"


class TestUpdateTemplateBranches:
    def test_update_adds_config(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())  # no configs initially
        assert (
            db.update_template(
                "low",
                settings={"USE_REVERSE_PROXY": "yes"},
                steps=[
                    {
                        "title": "S",
                        "settings": ["USE_REVERSE_PROXY"],
                        "configs": ["server_http/added.conf"],
                    }
                ],
                configs=[{"type": "server_http", "name": "added", "data": "# new"}],
            )
            == ""
        )
        assert db.get_templates()["low"]["configs"]["server_http/added.conf"] == "# new"

    def test_update_name_conflict(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        db.create_template("high", **(_minimal_template_args() | {"name": "High"}))
        assert db.update_template("high", name="Low") == "Template name Low already exists"

    def test_update_name_empty_rejected(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        assert db.update_template("low", name="   ") == "Template name cannot be empty"

    def test_update_unknown_plugin_rejected(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        assert db.update_template("low", plugin_id="ghost") == "Plugin ghost does not exist"

    def test_update_change_plugin(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        assert db.update_template("low", plugin_id="general") == ""
        assert db.get_templates()["low"]["plugin_id"] == "general"


class TestResolveTemplateSettings:
    """``USE_TEMPLATE`` holds an ORDERED LIST; ``resolve_template_settings`` folds it last-wins
    and reports the layers that do not exist."""

    @staticmethod
    def _layers(db):
        seed_minimal(db)
        add_setting(db, "SECURITY_MODE_X", context="multisite")
        assert (
            db.create_template(
                "base",
                name="Base",
                settings={"USE_REVERSE_PROXY": "yes", "SECURITY_MODE_X": "detect"},
                steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY", "SECURITY_MODE_X"]}],
            )
            == ""
        )
        assert (
            db.create_template(
                "hardening",
                name="Hardening",
                settings={"SECURITY_MODE_X": "block"},
                steps=[{"title": "S", "settings": ["SECURITY_MODE_X"]}],
            )
            == ""
        )

    def test_single_id_is_byte_identical(self, db):
        """THE ACCEPTANCE BAR: a one-element list resolves exactly as a bare id always did."""
        self._layers(db)
        merged, unknown = db.resolve_template_settings("base")
        assert merged == {"USE_REVERSE_PROXY": "yes", "SECURITY_MODE_X": "detect"}
        assert unknown == []
        assert db.get_template_settings("base") == merged

    def test_last_wins(self, db):
        self._layers(db)
        merged, unknown = db.resolve_template_settings("base hardening")
        assert merged == {"USE_REVERSE_PROXY": "yes", "SECURITY_MODE_X": "block"}
        assert unknown == []

    def test_order_is_significant(self, db):
        self._layers(db)
        assert db.resolve_template_settings("hardening base")[0]["SECURITY_MODE_X"] == "detect"
        assert db.resolve_template_settings("base hardening")[0]["SECURITY_MODE_X"] == "block"

    def test_repeat_is_a_no_op(self, db):
        self._layers(db)
        assert db.resolve_template_settings("base base hardening")[0] == db.resolve_template_settings("base hardening")[0]

    def test_irregular_whitespace_is_the_same_list(self, db):
        self._layers(db)
        assert db.resolve_template_settings("  base   hardening ")[0] == db.resolve_template_settings("base hardening")[0]

    def test_unknown_layer_reported_and_skipped(self, db):
        """``{}`` is ambiguous -- a settings-less template and a typo look identical -- so the
        unknown ids come back separately for the caller to report by position."""
        self._layers(db)
        merged, unknown = db.resolve_template_settings("base hgh hardening")
        assert unknown == ["hgh"]
        assert merged["SECURITY_MODE_X"] == "block"  # the layers that DO exist still apply

    def test_settings_less_template_is_known_not_unknown(self, db):
        """Probes bw_templates, not the settings rows: an empty template must not read as a typo."""
        self._layers(db)
        assert db.create_template("empty", name="Empty", settings={}, steps=[{"title": "S", "settings": []}]) == ""
        merged, unknown = db.resolve_template_settings("empty")
        assert unknown == []
        assert merged == {}

    def test_empty_value(self, db):
        self._layers(db)
        assert db.resolve_template_settings("") == ({}, [])


class TestDeleteTemplateWithLayers:
    """The delete guard is a MEMBERSHIP test: exact-value equality let a layer of a
    multi-template service be deleted, leaving a dangling id that then resolves as unknown at
    every generation."""

    def test_delete_blocked_when_one_layer_of_a_service_list(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="low high")
        assert db.delete_template("low") == "Template is currently used by a service"

    def test_delete_blocked_when_one_layer_of_the_global_list(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        add_global_value(db, setting_id="USE_TEMPLATE", value="high low")
        assert db.delete_template("low") == "Template is currently used by the global settings"

    def test_unreferenced_template_still_deletable(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="high medium")
        assert db.delete_template("low") == ""

    def test_substring_of_a_longer_id_does_not_block(self, db):
        """A token match, not a substring match -- 'low' must not be pinned by 'lowest'."""
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())
        add_service_setting(db, service_id="app1.example.com", setting_id="USE_TEMPLATE", value="lowest")
        assert db.delete_template("low") == ""


class TestUnknownTemplateLayers:
    """The save-path counterpart of the generator's per-position warning.

    ``USE_TEMPLATE``'s regex is ``^.*$`` -- it has to be, the ids are user-created -- so a typo
    clears every lexical gate and is only noticed at generation, which drops one layer of N."""

    @staticmethod
    def _layers(db):
        seed_minimal(db)
        assert db.create_template("base", **_minimal_template_args()) == ""

    def test_all_known_is_empty(self, db):
        self._layers(db)
        assert db.unknown_template_layers("base") == []

    def test_empty_value_is_empty(self, db):
        self._layers(db)
        assert db.unknown_template_layers("") == []

    def test_reports_the_1_based_position(self, db):
        self._layers(db)
        assert db.unknown_template_layers("base typo") == [(2, "typo")]
        assert db.unknown_template_layers("typo base") == [(1, "typo")]

    def test_several_unknown_layers(self, db):
        self._layers(db)
        assert db.unknown_template_layers("a base b") == [(1, "a"), (3, "b")]

    def test_a_repeated_unknown_id_is_blamed_at_each_position(self, db):
        """``list.index()`` would report position 1 twice."""
        self._layers(db)
        assert db.unknown_template_layers("typo base typo") == [(1, "typo"), (3, "typo")]

    def test_a_settings_less_template_is_known(self, db):
        """Probes bw_templates, so an empty template is not mistaken for a typo."""
        seed_minimal(db)
        assert db.create_template("empty", name="Empty", settings={}, steps=[{"title": "S", "settings": []}]) == ""
        assert db.unknown_template_layers("empty") == []

    def test_irregular_whitespace_does_not_invent_a_layer(self, db):
        self._layers(db)
        assert db.unknown_template_layers("  base   ") == []
