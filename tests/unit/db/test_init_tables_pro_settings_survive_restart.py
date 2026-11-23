"""A scheduler restart with an empty PRO plugin directory must not erase values stored for PRO settings.

On Kubernetes the scheduler pod starts with an empty /etc/bunkerweb/pro/plugins: save_config.py
runs init_tables() with no PRO plugin, and the PRO files are only restored from the database
afterwards. Settings rows of a plugin that stays in the database must survive that pass: they
cascade to the global and service values (including the ones autoconf wrote), and autoconf
has no way to notice the loss (#4107).
"""

import pytest

from fixtures.seed import add_global_value, add_service, add_service_setting, make_core_plugin, make_external_plugin, make_general_settings, session
from model import Global_values, Plugins, Selects, Services_settings, Settings

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


def test_setting_claimed_by_an_incoming_plugin_is_replaced_by_it(db):
    # bw_settings.id is unique across plugins: the preserved row cannot coexist with the incoming one, so it is not preserved.
    _seed_absent_pro_plugin(db)

    assert db.init_tables(_desired(_replacement_plugin("PROPLUG_MS", "replacement-ms"))) == (True, "")

    with session(db) as s:
        assert [(r.plugin_id, r.name, r.default) for r in s.query(Settings).filter_by(id="PROPLUG_MS")] == [("replacement", "replacement-ms", "msdef")]
        assert s.query(Services_settings).filter_by(setting_id="PROPLUG_MS").count() == 0
    assert db.init_tables(_desired(_replacement_plugin("PROPLUG_MS", "replacement-ms"))) == (False, "")


def test_preserved_setting_whose_name_is_claimed_by_another_id_is_dropped(db):
    # bw_settings.name is unique too: a different id taking the preserved row's name cannot coexist with it.
    _seed_absent_pro_plugin(db)

    assert db.init_tables(_desired(_replacement_plugin("OTHER_MS", "proplug-ms"))) == (True, "")

    with session(db) as s:
        assert [(r.plugin_id, r.id) for r in s.query(Settings).filter_by(name="proplug-ms")] == [("replacement", "OTHER_MS")]
        assert s.query(Settings).filter_by(id="PROPLUG_MS").count() == 0


@pytest.mark.parametrize(("setting_id", "name"), [("OTHER_MS", "PROPLUG-MS"), ("proplug_ms", "other-ms")])
def test_preserved_setting_claimed_in_another_case_is_dropped(db, setting_id, name):
    # MariaDB and MySQL compare ids and names case-insensitively by default: such a claim collides there, so it counts everywhere.
    _seed_absent_pro_plugin(db)

    assert db.init_tables(_desired(_replacement_plugin(setting_id, name))) == (True, "")

    with session(db) as s:
        assert s.query(Settings).filter_by(id="PROPLUG_MS").count() == 0
        assert [r.plugin_id for r in s.query(Settings).filter_by(id=setting_id)] == ["replacement"]


_RICH_SETTING = {
    "id": "proplug-ms",
    "context": "multisite",
    "default": "a",
    "help": "h",
    "label": "L",
    "regex": "^(a|b)$",
    "type": "select",
    "select": ["a", "b"],
    "multiple": "grp",
}
_BARE_SETTING = {"id": "replacement-ms", "context": "multisite", "default": "msdef", "help": "h", "label": "L", "regex": "^.*$", "type": "text"}
# The three ways an incoming setting can collide with the preserved PROPLUG_MS (id "PROPLUG_MS", name "proplug-ms").
_CONFLICTS = {
    "id-claimed": {"PROPLUG_MS": _BARE_SETTING},
    "name-claimed": {"OTHER_MS": {**_BARE_SETTING, "id": "proplug-ms"}},
    "id-and-name-claimed-separately": {"PROPLUG_MS": _BARE_SETTING, "OTHER_MS": {**_BARE_SETTING, "id": "proplug-ms"}},
}
# bw_selects, bw_global_values and bw_services_settings keep their surrogate id out of the comparison.
_TABLES = {"settings": Settings, "selects": Selects, "global_values": Global_values, "services_settings": Services_settings}


def _conflict_rows(db, shape):
    plugin = make_external_plugin("proplug", method="scheduler")
    plugin["settings"] = {"PROPLUG_MS": dict(_RICH_SETTING, select=list(_RICH_SETTING["select"]))}
    assert db.init_tables(_desired()) == (True, "")
    assert db.update_external_plugins([plugin], _type="pro") == ""
    add_service(db, "app1.example.com", method="autoconf")
    add_service_setting(db, service_id="app1.example.com", setting_id="PROPLUG_MS", value="from-autoconf", method="autoconf")
    add_global_value(db, setting_id="PROPLUG_MS", value="from-autoconf", method="autoconf")
    with session(db) as s:  # the scenario is not vacuous: the old row carries a group, options and values
        assert s.get(Settings, "PROPLUG_MS").multiple == "grp"
        assert s.query(Selects).filter_by(setting_id="PROPLUG_MS").count() == 2
        assert s.query(Global_values).filter_by(setting_id="PROPLUG_MS").count() == 1
        assert s.query(Services_settings).filter_by(setting_id="PROPLUG_MS").count() == 1

    incoming = {key: dict(value) for key, value in _CONFLICTS[shape].items()}
    db.init_tables(_desired(make_core_plugin("replacement", settings=incoming)))

    rows = {}
    with session(db) as s:
        for table, model in _TABLES.items():
            columns = [c.key for c in model.__table__.columns if table == "settings" or c.key != "id"]
            found = [tuple(getattr(r, c) for c in columns) for r in s.query(model)]
            keep = columns.index("plugin_id" if table == "settings" else "setting_id")
            found = [r for r in found if r[keep] in ("proplug", "replacement", "PROPLUG_MS", "OTHER_MS")]
            rows[table] = sorted(found, key=repr)
    return rows


# Reference values: the same scenario run against the Database.py of 949d2b29c (before #4107), `git show 949d2b29c:src/common/db/Database.py`.
# bw_settings columns: id, name, plugin_id, context, default, help, label, regex, type, multiple, separator, accept, order.
def _setting(setting_id, name, order):
    return (setting_id, name, "replacement", "multisite", "msdef", "h", "L", "^.*$", "text", None, " ", None, order)


def _only(*settings):
    return {"settings": list(settings), "selects": [], "global_values": [], "services_settings": []}


_REFERENCE = {
    "id-claimed": _only(_setting("PROPLUG_MS", "replacement-ms", 0)),
    "name-claimed": _only(_setting("OTHER_MS", "proplug-ms", 0)),
    "id-and-name-claimed-separately": _only(_setting("OTHER_MS", "proplug-ms", 1), _setting("PROPLUG_MS", "replacement-ms", 0)),
}


@pytest.mark.parametrize("shape", sorted(_CONFLICTS))
def test_conflicting_settings_end_as_they_did_before_4107(db, shape):
    assert _conflict_rows(db, shape) == _REFERENCE[shape]
