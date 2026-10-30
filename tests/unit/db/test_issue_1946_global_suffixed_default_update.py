"""Editing a global ``multiple`` setting down to its default keeps the row instead of deleting it.

A suffixed row has no suffix-less default to fall back on, so a global ``LIMIT_1`` set back to the plugin
default was treated as "default, nothing to store" and removed: the rule vanished from the configuration.
A member of a slot that nothing else keeps alive must be persisted at its default, on creation (pinned
in ``test_issue_474_save_config_values.py``) and, pinned here, when an existing row is edited to the default.
A slot kept alive by a non-default sibling still drops its default member, which keeps the field editable.

Refs: #1946.
"""

import pytest
from sqlalchemy import select

from fixtures.seed import add_global_value, make_core_plugin, make_general_settings, session
from model import Global_values


def _plugin():
    base = {"context": "multisite", "help": "h", "label": "L", "regex": "^.*$", "type": "text", "multiple": "limit"}
    return make_core_plugin(
        "alpha",
        settings={
            "ALPHA_RATE": base | {"id": "alpha-rate", "default": "10r/s"},
            "ALPHA_BURST": base | {"id": "alpha-burst", "default": "5"},
        },
    )


@pytest.fixture
def seeded(db):
    db.init_tables([make_general_settings(), _plugin()])
    db.initialize_db("1.7.0", "Docker")
    return db


def _rows(db):
    with session(db) as s:
        return {(row.setting_id, row.suffix): row.value for row in s.scalars(select(Global_values).filter_by(suffix=1))}


@pytest.mark.parametrize("multisite", [False, True], ids=["single-site", "multisite"])
def test_editing_an_anchorless_global_slot_back_to_the_default_keeps_the_row(seeded, multisite):
    """Single-site and multisite saves run separate copies of the guard."""
    add_global_value(seeded, setting_id="ALPHA_RATE", value="3r/s", method="ui", suffix=1)
    config = {"ALPHA_RATE_1": "10r/s"} | ({"MULTISITE": "yes", "SERVER_NAME": "app1.example.com"} if multisite else {})

    assert isinstance(seeded.save_config(config, "ui", skip_service_management=not multisite), set)

    assert _rows(seeded) == {("ALPHA_RATE", 1): "10r/s"}
    assert seeded.get_config()["ALPHA_RATE_1"] == "10r/s"


def test_a_default_member_next_to_a_non_default_sibling_is_dropped(seeded):
    """The control: the slot survives on its non-default member, so its default sibling is not stored."""
    seeded.save_config({"ALPHA_RATE_1": "10r/s", "ALPHA_BURST_1": "9"}, "ui", skip_service_management=True)

    assert _rows(seeded) == {("ALPHA_BURST", 1): "9"}
