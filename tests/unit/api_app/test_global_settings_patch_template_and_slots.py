"""``PATCH /global_settings`` decides a posted key with the stored global context, though it posts only that key.

The active global template supplies the defaults and the sibling members of a multiple setting anchor a slot. Runs the real
route against a real ``Database``; ``tests/unit/db/test_config_save_partial.py`` holds the comparison with a full save.
"""

import pytest
from sqlalchemy import select

from _api_http_helpers import ADMIN_HEADERS, router_client
from fixtures.seed import add_global_value, make_core_plugin, make_general_settings, session
from model import Global_values

import app.routers.global_settings as global_settings


def _setting(key, default, multiple=None):
    setting = {"id": key.lower().replace("_", "-"), "context": "multisite", "default": default, "help": "h", "label": "L", "regex": "^.*$", "type": "text"}
    return setting | {"multiple": multiple} if multiple else setting


@pytest.fixture
def client(monkeypatch, db):
    settings = {
        "USE_REVERSE_PROXY": _setting("USE_REVERSE_PROXY", "no"),
        "REVERSE_PROXY_URL": _setting("REVERSE_PROXY_URL", "/", "reverse-proxy"),
        "REVERSE_PROXY_HOST": _setting("REVERSE_PROXY_HOST", "", "reverse-proxy"),
        "USE_TEMPLATE": _setting("USE_TEMPLATE", ""),
    }
    db.init_tables([make_general_settings(), make_core_plugin("proxy", settings=settings)])
    db.initialize_db("1.7.0", "Docker")
    template = {
        "name": "Proxy",
        "settings": {"USE_REVERSE_PROXY": "yes", "REVERSE_PROXY_URL_1": "/api"},
        "steps": [{"title": "Proxy", "settings": ["USE_REVERSE_PROXY", "REVERSE_PROXY_URL_1"], "configs": []}],
    }
    assert db.create_template("proxy", **template) == ""
    return router_client(monkeypatch, global_settings, db)


def _rows(db):
    with session(db) as s:
        return {(row.setting_id, row.suffix): (row.value, row.method) for row in s.scalars(select(Global_values))}


def test_a_patch_to_the_default_overrides_the_active_global_template(client, db):
    add_global_value(db, setting_id="USE_TEMPLATE", value="proxy", method="ui")
    assert db.get_config(global_only=True)["USE_REVERSE_PROXY"] == "yes"

    response = client.patch("/global_settings", json={"USE_REVERSE_PROXY": "no"}, headers=ADMIN_HEADERS)

    assert response.status_code == 200, response.text
    assert db.get_config(global_only=True)["USE_REVERSE_PROXY"] == "no"
    assert _rows(db)[("USE_REVERSE_PROXY", 0)] == ("no", "api")


def test_resetting_a_slot_member_does_not_pin_it_over_a_later_template(client, db):
    add_global_value(db, setting_id="REVERSE_PROXY_URL", value="/app", method="ui", suffix=1)
    add_global_value(db, setting_id="REVERSE_PROXY_HOST", value="http://h", method="ui", suffix=1)

    response = client.patch("/global_settings", json={"REVERSE_PROXY_URL_1": "/"}, headers=ADMIN_HEADERS)

    assert response.status_code == 200, response.text
    assert ("REVERSE_PROXY_URL", 1) not in _rows(db)
    assert _rows(db)[("REVERSE_PROXY_HOST", 1)] == ("http://h", "ui")
    add_global_value(db, setting_id="USE_TEMPLATE", value="proxy", method="ui")
    assert db.get_config(global_only=True)["REVERSE_PROXY_URL_1"] == "/api"
