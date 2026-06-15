"""DatabaseTemplatesMixin — service template create/get/delete + validation."""

from fixtures.seed import add_global_value, seed_minimal


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
