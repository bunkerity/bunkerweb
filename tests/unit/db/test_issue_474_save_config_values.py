"""``save_config`` keeps the values a user explicitly set, even when they look like a default or are empty.

* #474: an empty value for a setting was dropped on save because of an ``empty and not default`` skip.
* #1946: ``MULTI_1=<default>`` was treated as a default and dropped, since a suffixed row has no
  suffix-less default to fall back on; rate-limit rules written that way silently never applied.
* A service removed and another one added in the same save (what a rename through the Web UI sends): on SQLite the freed integer primary keys of the
  old rows are reused by the new ones, and deleting the stale loaded objects afterwards removed the new rows.
"""

import pytest
from sqlalchemy import select

from fixtures.seed import add_service, add_service_setting, make_core_plugin, make_general_settings, session
from model import Global_values, Services_settings

SERVICE = "app1.example.com"


def _plugin():
    return make_core_plugin(
        "alpha",
        settings={
            "ALPHA_GLOBAL": {"id": "alpha-global", "context": "global", "default": "def", "help": "h", "label": "L", "regex": "^.*$", "type": "text"},
            "ALPHA_LIMIT": {
                "id": "alpha-limit",
                "context": "multisite",
                "default": "10r/s",
                "help": "h",
                "label": "L",
                "regex": "^.*$",
                "type": "text",
                "multiple": "limit",
            },
            "ALPHA_OVERRIDE": {"id": "alpha-override", "context": "multisite", "default": "", "help": "h", "label": "L", "regex": "^.*$", "type": "text"},
            "ALPHA_NOTE": {"id": "alpha-note", "context": "multisite", "default": "note", "help": "h", "label": "L", "regex": "^.*$", "type": "text"},
        },
    )


@pytest.fixture
def seeded(db):
    db.init_tables([make_general_settings(), _plugin()])
    db.initialize_db("1.7.0", "Docker")
    return db


def _global_row(db, setting_id, suffix=0):
    with session(db) as s:
        row = s.scalars(select(Global_values).filter_by(setting_id=setting_id, suffix=suffix)).first()
        return None if row is None else row.value


def _service_rows(db, service_id):
    with session(db) as s:
        return {(row.setting_id, row.suffix): row.value for row in s.scalars(select(Services_settings).filter_by(service_id=service_id))}


class TestEmptyValueIsKept:
    def test_empty_global_value_overrides_a_non_empty_default(self, seeded):
        assert isinstance(seeded.save_config({"ALPHA_GLOBAL": ""}, "ui", skip_service_management=True), set)

        assert _global_row(seeded, "ALPHA_GLOBAL") == ""
        assert seeded.get_config()["ALPHA_GLOBAL"] == ""

    def test_empty_service_value_overrides_a_non_empty_default(self, seeded):
        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": SERVICE, f"{SERVICE}_ALPHA_NOTE": ""}, "ui")

        assert _service_rows(seeded, SERVICE).get(("ALPHA_NOTE", 0)) == ""

    def test_service_can_blank_a_setting_the_global_config_sets(self, seeded):
        """The setting's own default is empty, so an empty service value looked like "nothing to store" and the global value won."""
        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": SERVICE, "ALPHA_OVERRIDE": "global-value", f"{SERVICE}_ALPHA_OVERRIDE": ""}, "ui")

        assert _service_rows(seeded, SERVICE).get(("ALPHA_OVERRIDE", 0)) == ""
        assert seeded.get_config(service=SERVICE)["ALPHA_OVERRIDE"] == ""

    def test_an_empty_value_equal_to_an_empty_default_is_not_stored(self, seeded):
        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": SERVICE, f"{SERVICE}_ALPHA_OVERRIDE": ""}, "ui")

        assert ("ALPHA_OVERRIDE", 0) not in _service_rows(seeded, SERVICE)


class TestSuffixedValueEqualToDefaultIsKept:
    def test_global_multiple_setting_keeps_a_suffixed_default(self, seeded):
        seeded.save_config({"ALPHA_LIMIT_1": "10r/s"}, "ui", skip_service_management=True)

        assert _global_row(seeded, "ALPHA_LIMIT", 1) == "10r/s"
        assert seeded.get_config()["ALPHA_LIMIT_1"] == "10r/s"

    def test_service_multiple_setting_keeps_a_suffixed_default(self, seeded):
        seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": SERVICE, f"{SERVICE}_ALPHA_LIMIT_1": "10r/s"}, "ui")

        assert _service_rows(seeded, SERVICE).get(("ALPHA_LIMIT", 1)) == "10r/s"

    def test_a_plain_default_is_still_not_stored(self, seeded):
        """The control: the unsuffixed default stays implicit, only suffixed rows are exempt."""
        seeded.save_config({"ALPHA_GLOBAL": "def"}, "ui", skip_service_management=True)

        assert _global_row(seeded, "ALPHA_GLOBAL") is None


class TestReplacedServiceKeepsSettingsWrittenInTheSameSave:
    @pytest.mark.parametrize("old_rows", [1, 3], ids=["one-old-row", "three-old-rows"])
    def test_new_service_keeps_all_its_rows(self, seeded, old_rows):
        old, new = "old.example.com", "new.example.com"
        add_service(seeded, old, method="ui")
        for index in range(old_rows):
            add_service_setting(seeded, service_id=old, setting_id="ALPHA_LIMIT", value=f"{index}r/s", suffix=index + 1, method="ui")

        config = {"MULTISITE": "yes", "SERVER_NAME": new, f"{new}_ALPHA_NOTE": "after", f"{new}_ALPHA_LIMIT_1": "7r/s", f"{new}_ALPHA_LIMIT_2": "8r/s"}
        assert isinstance(seeded.save_config(config, "ui"), set)

        assert _service_rows(seeded, old) == {}
        assert _service_rows(seeded, new) == {("ALPHA_NOTE", 0): "after", ("ALPHA_LIMIT", 1): "7r/s", ("ALPHA_LIMIT", 2): "8r/s"}
