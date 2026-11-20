"""Editing a service setting back to its default drops the stored row; the service must still be marked updated (#3986).

The row is removed because defaults are implicit, but without bumping ``Services.last_update`` nothing noticed the change,
so a service that had just been edited kept serving, and later saves re-wrote, its previous value.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, update

from fixtures.seed import make_core_plugin, make_general_settings, session
from model import Services, Services_settings

SERVICE = "app1.example.com"


def _plugin():
    return make_core_plugin(
        "alpha",
        settings={
            "ALPHA_NOTE": {"id": "alpha-note", "context": "multisite", "default": "note", "help": "h", "label": "L", "regex": "^.*$", "type": "text"},
        },
    )


@pytest.fixture
def seeded(db):
    db.init_tables([make_general_settings(), _plugin()])
    db.initialize_db("1.7.0", "Docker")
    return db


def _last_update(db):
    with session(db) as s:
        return s.scalars(select(Services).filter_by(id=SERVICE)).one().last_update


def _row(db):
    with session(db) as s:
        row = s.scalars(select(Services_settings).filter_by(service_id=SERVICE, setting_id="ALPHA_NOTE")).first()
        return None if row is None else row.value


def test_issue_3986_editing_a_setting_back_to_its_default_marks_the_service_updated(seeded):
    """The row for the edited setting disappears and ``last_update`` moves forward (#3986)."""
    assert isinstance(seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": SERVICE, f"{SERVICE}_ALPHA_NOTE": "custom"}, "ui"), set)
    assert _row(seeded) == "custom"
    # DATETIME keeps whole seconds on MariaDB/MySQL, so wait-and-compare could read equal: start from a day-old stamp instead.
    with session(seeded) as s:
        s.execute(update(Services).where(Services.id == SERVICE).values(last_update=datetime.now().astimezone() - timedelta(days=1)))
    before = _last_update(seeded)

    assert isinstance(seeded.save_config({"MULTISITE": "yes", "SERVER_NAME": SERVICE, f"{SERVICE}_ALPHA_NOTE": "note"}, "ui"), set)

    assert _row(seeded) is None
    assert _last_update(seeded) > before
