"""A scheduler save may remove some global values, but never wipe all of them."""

import logging

import pytest

from fixtures.seed import add_global_value, make_core_plugin, make_general_settings, session
from model import Global_values

pytestmark = pytest.mark.multiengine


@pytest.fixture
def globals_db(db):
    db.init_tables([make_general_settings(), make_core_plugin("alpha"), make_core_plugin("beta"), make_core_plugin("gamma")])
    db.initialize_db("1.6.18", "Docker")
    add_global_value(db, setting_id="ALPHA_GLOBAL", value="first", method="scheduler")
    add_global_value(db, setting_id="BETA_GLOBAL", value="second", method="scheduler")
    add_global_value(db, setting_id="GAMMA_GLOBAL", value="ui-owned", method="ui")
    return db


def _stored_globals(db):
    with session(db) as s:
        return {row.setting_id: (row.value, row.method) for row in s.query(Global_values)}


def test_a_scheduler_save_that_would_delete_every_scheduler_global_is_refused(globals_db, caplog):
    globals_db.logger.propagate = True
    caplog.set_level(logging.WARNING, logger=globals_db.logger.name)

    result = globals_db.save_config({}, "scheduler")

    assert isinstance(result, set), result
    assert _stored_globals(globals_db) == {
        "ALPHA_GLOBAL": ("first", "scheduler"),
        "BETA_GLOBAL": ("second", "scheduler"),
        "GAMMA_GLOBAL": ("ui-owned", "ui"),
    }
    assert "Refusing to delete all 2 scheduler-method global setting(s)" in caplog.text


def test_a_scheduler_save_that_removes_only_some_globals_is_applied(globals_db, caplog):
    globals_db.logger.propagate = True
    caplog.set_level(logging.WARNING, logger=globals_db.logger.name)

    result = globals_db.save_config({"ALPHA_GLOBAL": "updated"}, "scheduler")

    assert isinstance(result, set), result
    assert _stored_globals(globals_db) == {
        "ALPHA_GLOBAL": ("updated", "scheduler"),
        "GAMMA_GLOBAL": ("ui-owned", "ui"),
    }
    assert "Refusing to delete all" not in caplog.text
