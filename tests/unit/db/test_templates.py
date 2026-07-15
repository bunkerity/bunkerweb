"""DatabaseTemplatesMixin — service template create/get/delete + validation."""

from fixtures.seed import add_global_value, add_select_setting, add_setting, seed_minimal


def _minimal_template_args():
    # USE_REVERSE_PROXY exists in seed_minimal's Settings, so the base-id check passes.
    return {
        "name": "Low",
        "settings": {"USE_REVERSE_PROXY": "yes"},
        "steps": [{"title": "Step 1", "settings": ["USE_REVERSE_PROXY"]}],
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
        msg = db.create_template("x", name="X", settings={"USE_REVERSE_PROXY": "yes"}, steps=[{"title": "S", "settings": ["NOPE"]}])
        assert "references unknown setting" in msg

    def test_unknown_base_setting_rejected(self, db):
        seed_minimal(db)
        msg = db.create_template("x", name="X", settings={"FAKE": "v"}, steps=[{"title": "S", "settings": ["FAKE"]}])
        assert "Unknown settings" in msg

    def test_defaults_are_normalized_together(self, db):
        seed_minimal(db)
        add_setting(db, "MEM_SIZE", type="size", regex=r"^\d+([kKmMgG])?$", default="0")
        add_setting(db, "MY_TIMEOUT", type="duration", regex=r"^(\d+(ms|s|m|h|d|w|M|y))+$|^\d+$", default="0")
        add_setting(db, "TEST_PORT", type="number", regex=r"^\d+$", default="0")
        add_select_setting(db, "CIPHERS", ["modern", "intermediate", "old"], default="modern", case_insensitive=True)
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

        assert db.create_template("t", name="T", settings=settings, steps=[{"title": "S", "settings": list(settings)}]) == ""
        assert db.get_template_settings("t") == {
            "USE_REVERSE_PROXY": "yes",
            "SECURITY_MODE": "  on  ",
            "MEM_SIZE": "64m",
            "MY_TIMEOUT": "5m",
            "TEST_PORT": "8080",
            "CIPHERS": "modern",
            "SEC_ENGINE": "On",
        }

    def test_update_template_check_default_canonicalized(self, db):
        seed_minimal(db)
        db.create_template("low", **_minimal_template_args())  # USE_REVERSE_PROXY default "yes"
        msg = db.update_template("low", name="Low", settings={"USE_REVERSE_PROXY": "off"}, steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY"]}])
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
        "steps": [{"title": "Step 1", "settings": ["USE_REVERSE_PROXY"], "configs": ["server_http/cfg.conf"]}],
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
        return db.create_template("x", name="X", settings={"USE_REVERSE_PROXY": "yes"}, steps=steps, configs=configs)

    def test_config_entry_not_dict(self, db):
        seed_minimal(db)
        msg = self._create(
            db,
            steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY"], "configs": ["server_http/c.conf"]}],
            configs=["not-a-dict"],
        )
        assert msg == "Config entries must be objects"

    def test_step_references_unknown_config(self, db):
        seed_minimal(db)
        msg = self._create(
            db,
            steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY"], "configs": ["server_http/ghost.conf"]}],
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
            steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY"], "configs": ["server_http/dup.conf"]}],
            configs=[{"type": "server_http", "name": "dup", "data": "# a"}, {"type": "server-http", "name": "dup", "data": "# b"}],
        )
        assert "Duplicate config" in msg


class TestTemplateSettingValidation:
    def test_step_missing_title(self, db):
        seed_minimal(db)
        assert db.create_template("x", name="X", settings={}, steps=[{"settings": []}]) == "Step 1 must have a title"

    def test_setting_not_assigned_to_step(self, db):
        seed_minimal(db)
        msg = db.create_template("x", name="X", settings={"USE_REVERSE_PROXY": "yes"}, steps=[{"title": "S", "settings": []}])
        assert "are not assigned to any step" in msg

    def test_setting_assigned_to_multiple_steps(self, db):
        seed_minimal(db)
        msg = db.create_template(
            "x",
            name="X",
            settings={"USE_REVERSE_PROXY": "yes"},
            steps=[{"title": "S1", "settings": ["USE_REVERSE_PROXY"]}, {"title": "S2", "settings": ["USE_REVERSE_PROXY"]}],
        )
        assert "assigned to multiple steps" in msg

    def test_restricted_setting_rejected(self, db):
        seed_minimal(db)
        # USE_TEMPLATE is in RESTRICTED_TEMPLATE_SETTINGS -> cannot live inside a template.
        msg = db.create_template("x", name="X", settings={"USE_TEMPLATE": "low"}, steps=[{"title": "S", "settings": ["USE_TEMPLATE"]}])
        assert msg == "Setting USE_TEMPLATE cannot be part of a template"


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
                steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY"], "configs": ["server_http/added.conf"]}],
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
