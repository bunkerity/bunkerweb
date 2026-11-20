"""``PATCH /global_settings`` deleted every global setting saved from the UI or the setup wizard.

The save cleanup covers every editable method, so a patch must write only the posted keys and leave every other global row,
value and method, as it is. Runs the real route against a real ``Database``.
"""

import pytest
from sqlalchemy import select

from _api_http_helpers import ADMIN_HEADERS, router_client
from fixtures.seed import add_global_value, make_core_plugin, make_general_settings, session
from model import Global_values

import app.routers.global_settings as global_settings


def _setting(key, default):
    return {"id": key.lower().replace("_", "-"), "context": "global", "default": default, "help": "h", "label": "L", "regex": "^.*$", "type": "text"}


@pytest.fixture
def client(monkeypatch, db):
    plugin = make_core_plugin(
        "alpha", settings={key: _setting(key, "def") for key in ("FROM_UI", "FROM_WIZARD", "FROM_API", "FROM_SCHEDULER", "PATCHED", "OWNED_BY_UI")}
    )
    db.init_tables([make_general_settings(), plugin])
    db.initialize_db("1.7.0", "Docker")
    # Rows are inserted directly: each save_config call is a full snapshot for its method family.
    for key, method in (("FROM_UI", "ui"), ("FROM_WIZARD", "wizard"), ("FROM_API", "api"), ("OWNED_BY_UI", "ui"), ("FROM_SCHEDULER", "scheduler")):
        add_global_value(db, setting_id=key, value=f"{method}-value", method=method)
    add_global_value(db, setting_id="SERVER_NAME", value="app.example.com", method="api")
    assert _rows(db)["FROM_UI"] == ("ui-value", "ui")
    return router_client(monkeypatch, global_settings, db)


def _rows(db):
    with session(db) as s:
        return {row.setting_id: (row.value, row.method) for row in s.scalars(select(Global_values))}


def test_patching_a_key_leaves_every_other_global_row_and_its_owner(client, db):
    before = _rows(db)

    response = client.patch("/global_settings", json={"PATCHED": "new"}, headers=ADMIN_HEADERS)

    assert response.status_code == 200, response.text
    after = _rows(db)
    assert after.pop("PATCHED") == ("new", "api")
    assert after == before


def test_patching_a_ui_owned_key_changes_only_that_key(client, db):
    response = client.patch("/global_settings", json={"OWNED_BY_UI": "from-api"}, headers=ADMIN_HEADERS)

    assert response.status_code == 200, response.text
    after = _rows(db)
    assert after["OWNED_BY_UI"] == ("from-api", "api")
    assert after["FROM_UI"] == ("ui-value", "ui")
    assert after["FROM_WIZARD"] == ("wizard-value", "wizard")
    assert after["FROM_API"] == ("api-value", "api")


def test_an_api_owned_server_name_survives_an_unrelated_patch(client, db):
    response = client.patch("/global_settings", json={"PATCHED": "new"}, headers=ADMIN_HEADERS)

    assert response.status_code == 200, response.text
    assert _rows(db)["SERVER_NAME"] == ("app.example.com", "api")


def test_a_ui_save_committed_just_before_the_patch_save_is_not_overwritten(client, db, monkeypatch):
    """A UI save that lands after the route prepared its payload, before the save transaction opens, keeps its value and owner."""
    save_config = db.save_config

    def save_after_a_ui_save(*args, **kwargs):
        with session(db) as s:
            row = s.scalars(select(Global_values).filter_by(setting_id="FROM_UI")).one()
            row.value, row.method = "ui-latest", "ui"
        return save_config(*args, **kwargs)

    monkeypatch.setattr(db, "save_config", save_after_a_ui_save)

    response = client.patch("/global_settings", json={"PATCHED": "new"}, headers=ADMIN_HEADERS)

    assert response.status_code == 200, response.text
    assert _rows(db)["FROM_UI"] == ("ui-latest", "ui")
