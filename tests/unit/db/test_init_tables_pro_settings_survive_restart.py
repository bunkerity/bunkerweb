"""A scheduler restart with an empty PRO plugin directory must not erase values stored for PRO settings.

On Kubernetes the scheduler pod starts with an empty /etc/bunkerweb/pro/plugins: save_config.py
runs init_tables() with no PRO plugin, and the PRO files are only restored from the database
afterwards. Settings rows of a plugin that stays in the database must survive that pass: they
cascade to the global and service values (including the ones autoconf wrote), and autoconf
has no way to notice the loss (#4107).
"""

import pytest

from fixtures.seed import add_global_value, add_service, add_service_setting, make_core_plugin, make_external_plugin, make_general_settings, session
from model import Global_values, Plugins, Services_settings, Settings

pytestmark = pytest.mark.multiengine


def _rows(db):
    with session(db) as s:
        return {
            "plugin": s.query(Plugins).filter_by(id="proplug").count(),
            "setting": s.query(Settings).filter_by(id="PROPLUG_MS").count(),
            "service_value": s.query(Services_settings).filter_by(setting_id="PROPLUG_MS").count(),
            "global_value": s.query(Global_values).filter_by(setting_id="PROPLUG_GLOBAL").count(),
        }


def test_pro_settings_and_values_survive_init_tables_without_the_plugin_files(db):
    assert db.init_tables([make_general_settings(), make_core_plugin("alpha")]) == (True, "")
    # download-pro-plugins stores its plugins with method "scheduler"
    assert db.update_external_plugins([make_external_plugin("proplug", method="scheduler")], _type="pro") == ""
    add_service(db, "app1.example.com", method="autoconf")
    add_service_setting(db, service_id="app1.example.com", setting_id="PROPLUG_MS", value="from-autoconf", method="autoconf")
    add_global_value(db, setting_id="PROPLUG_GLOBAL", value="from-autoconf", method="autoconf")
    before = _rows(db)
    assert before == {"plugin": 1, "setting": 1, "service_value": 1, "global_value": 1}

    # What save_config.py sends on the first start of a scheduler pod: no PRO plugin on disk yet.
    db.init_tables([make_general_settings(), make_core_plugin("alpha")])

    assert _rows(db) == before
    # PRO's migration restore reads (False, "") as "registry unchanged": a call that changes nothing must keep returning it.
    assert db.init_tables([make_general_settings(), make_core_plugin("alpha")]) == (False, "")


def test_manual_plugin_absent_from_desired_is_still_pruned(db):
    # Control: a method="manual" plugin whose files are gone is deleted with its settings, as before.
    plugin = make_external_plugin("proplug", method="manual")
    assert db.init_tables([make_general_settings(), make_core_plugin("alpha")]) == (True, "")
    assert db.update_external_plugins([plugin], _type="pro") == ""
    db.init_tables([make_general_settings(), make_core_plugin("alpha")])
    assert _rows(db) == {"plugin": 0, "setting": 0, "service_value": 0, "global_value": 0}


def _replacement_plugin(setting_id, name):
    setting = {"id": name, "context": "multisite", "default": "msdef", "help": "h", "label": "L", "regex": "^.*$", "type": "text"}
    return make_core_plugin("replacement", settings={setting_id: setting})


def _desired(*extra):
    return [make_general_settings(), make_core_plugin("alpha"), *extra]


def _seed_absent_pro_plugin(db):
    assert db.init_tables(_desired()) == (True, "")
    assert db.update_external_plugins([make_external_plugin("proplug", method="scheduler")], _type="pro") == ""
    add_service(db, "app1.example.com", method="autoconf")
    add_service_setting(db, service_id="app1.example.com", setting_id="PROPLUG_MS", value="from-autoconf", method="autoconf")


def test_setting_claimed_by_an_incoming_plugin_moves_to_it_with_its_values(db):
    # The preserved row of the absent plugin must not collide with the incoming one on bw_settings.id: it changes owner.
    _seed_absent_pro_plugin(db)

    assert db.init_tables(_desired(_replacement_plugin("PROPLUG_MS", "replacement-ms"))) == (True, "")

    with session(db) as s:
        assert [(r.plugin_id, r.name) for r in s.query(Settings).filter_by(id="PROPLUG_MS")] == [("replacement", "replacement-ms")]
        assert s.query(Services_settings).filter_by(setting_id="PROPLUG_MS").count() == 1
    assert db.init_tables(_desired(_replacement_plugin("PROPLUG_MS", "replacement-ms"))) == (False, "")


def test_preserved_setting_whose_name_is_claimed_by_another_id_is_dropped(db):
    # bw_settings.name is unique too: a different id taking the preserved row's name cannot coexist with it.
    _seed_absent_pro_plugin(db)

    assert db.init_tables(_desired(_replacement_plugin("OTHER_MS", "proplug-ms"))) == (True, "")

    with session(db) as s:
        assert [(r.plugin_id, r.id) for r in s.query(Settings).filter_by(name="proplug-ms")] == [("replacement", "OTHER_MS")]
        assert s.query(Settings).filter_by(id="PROPLUG_MS").count() == 0
