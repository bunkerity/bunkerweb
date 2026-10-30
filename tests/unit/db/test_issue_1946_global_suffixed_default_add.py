"""Initial multisite saves must retain an all-default global multiple slot.

Dropping its only member loses the explicitly configured slot. Refs: #1946.
"""

from sqlalchemy import select

from fixtures.seed import make_core_plugin, make_general_settings, session
from model import Global_values


def test_multisite_add_keeps_an_anchorless_global_default(db):
    setting = {
        "id": "alpha-rate",
        "context": "multisite",
        "help": "h",
        "label": "Rate",
        "regex": "^.*$",
        "type": "text",
        "multiple": "limit",
        "default": "10r/s",
    }
    db.init_tables([make_general_settings(), make_core_plugin("alpha", settings={"ALPHA_RATE": setting})])
    assert db.initialize_db("1.7.0", "Docker") == ""
    with session(db) as sql:
        assert sql.scalars(select(Global_values).filter_by(setting_id="ALPHA_RATE", suffix=1)).all() == []

    result = db.save_config({"MULTISITE": "yes", "SERVER_NAME": "app.example.com", "ALPHA_RATE_1": "10r/s"}, "ui")

    assert isinstance(result, set)
    with session(db) as sql:
        rows = sql.scalars(select(Global_values).filter_by(setting_id="ALPHA_RATE", suffix=1)).all()
        assert [(row.value, row.method) for row in rows] == [("10r/s", "ui")]
    assert db.get_config()["ALPHA_RATE_1"] == "10r/s"
