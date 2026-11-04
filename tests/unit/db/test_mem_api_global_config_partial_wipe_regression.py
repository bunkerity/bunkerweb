"""A partial ``PATCH /global_settings`` payload went through ``save_config`` like a full config and deleted every service.

Pins that a global-only save (``skip_service_management=True``, what the API route passes) applies the partial
payload as a patch and leaves the existing services and their settings alone.
"""

import pytest
from sqlalchemy import select

from fixtures.seed import make_core_plugin, make_general_settings, session
from model import Services, Services_settings

FIRST, SECOND = "app1.example.com", "app2.example.com"


def _plugin():
    return make_core_plugin(
        "alpha",
        settings={
            "ALPHA_GLOBAL": {"id": "alpha-global", "context": "global", "default": "def", "help": "h", "label": "L", "regex": "^.*$", "type": "text"},
            "ALPHA_NOTE": {"id": "alpha-note", "context": "multisite", "default": "note", "help": "h", "label": "L", "regex": "^.*$", "type": "text"},
        },
    )


@pytest.fixture
def two_services(db):
    db.init_tables([make_general_settings(), _plugin()])
    db.initialize_db("1.7.0", "Docker")
    config = {"MULTISITE": "yes", "SERVER_NAME": f"{FIRST} {SECOND}", f"{FIRST}_ALPHA_NOTE": "mine", f"{SECOND}_ALPHA_NOTE": "other"}
    assert isinstance(db.save_config(config, "api"), set)
    assert _service_ids(db) == {FIRST, SECOND}
    return db


def _service_ids(db):
    with session(db) as s:
        return set(s.scalars(select(Services.id)))


def _note(db):
    with session(db) as s:
        return s.scalars(select(Services_settings.value).filter_by(service_id=FIRST, setting_id="ALPHA_NOTE")).first()


def test_a_global_only_save_keeps_every_service_and_its_settings(two_services):
    assert isinstance(two_services.save_config({"ALPHA_GLOBAL": "patched"}, "api", changed=True, skip_service_management=True), set)

    assert _service_ids(two_services) == {FIRST, SECOND}
    assert _note(two_services) == "mine"
    assert two_services.get_config()["ALPHA_GLOBAL"] == "patched"
