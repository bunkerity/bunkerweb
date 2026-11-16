"""Plugin updates must preserve neighbouring templates and reconcile removed entries."""

import json
from copy import deepcopy

import pytest
from sqlalchemy import select

from fixtures.seed import make_external_plugin, seed_minimal, session
from model import Multiselects, Selects, Template_custom_configs, Template_settings, Template_steps


@pytest.fixture
def plugin_tree(db, tmp_path, monkeypatch):
    seed_minimal(db)
    monkeypatch.setattr(db, "_uep_resolve_plugin_dir", lambda *_: tmp_path)
    assert db.update_external_plugins([make_external_plugin()]) == ""
    (tmp_path / "templates").mkdir()
    return tmp_path / "templates"


def write_template(tree, name, steps=2):
    body = {
        "name": name,
        "settings": {"USE_REVERSE_PROXY": "yes", "SECURITY_MODE": "detect"},
        "configs": ["server-http/first.conf", "server-http/second.conf"],
        "steps": [
            {"title": "first", "subtitle": name, "settings": ["USE_REVERSE_PROXY"], "configs": ["server-http/first.conf"]},
            {"title": "second", "subtitle": name, "settings": ["SECURITY_MODE"], "configs": ["server-http/second.conf"]},
        ][:steps],
    }
    if steps == 1:
        body["settings"].pop("SECURITY_MODE")
        body["configs"].pop()
    for config in body["configs"]:
        path = tree / name / "configs" / config
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {name}/{config}\n")
    (tree / f"{name}.json").write_text(json.dumps(body))
    return body


def template_rows(db, name):
    with session(db) as s:
        return {
            "steps": list(
                s.execute(select(Template_steps.id, Template_steps.title, Template_steps.subtitle).filter_by(template_id=name).order_by(Template_steps.id))
            ),
            "settings": list(
                s.execute(
                    select(Template_settings.setting_id, Template_settings.step_id, Template_settings.default)
                    .filter_by(template_id=name)
                    .order_by(Template_settings.setting_id)
                )
            ),
            "configs": list(
                s.execute(
                    select(Template_custom_configs.name, Template_custom_configs.step_id, Template_custom_configs.data)
                    .filter_by(template_id=name)
                    .order_by(Template_custom_configs.name)
                )
            ),
        }


def test_removed_step_prunes_only_its_template(db, plugin_tree):
    write_template(plugin_tree, "first")
    write_template(plugin_tree, "neighbour")
    assert db.update_external_plugins([make_external_plugin()]) == ""
    neighbour = template_rows(db, "neighbour")
    assert len(neighbour["steps"]) == 2

    write_template(plugin_tree, "first", steps=1)
    assert db.update_external_plugins([make_external_plugin()]) == ""

    first = template_rows(db, "first")
    assert len(first["steps"]) == len(first["settings"]) == len(first["configs"]) == 1
    assert template_rows(db, "neighbour") == neighbour


def test_added_step_preserves_same_numbered_neighbour_rows(db, plugin_tree):
    write_template(plugin_tree, "first", steps=1)
    write_template(plugin_tree, "neighbour")
    assert db.update_external_plugins([make_external_plugin()]) == ""
    neighbour = template_rows(db, "neighbour")

    write_template(plugin_tree, "first")
    assert db.update_external_plugins([make_external_plugin()]) == ""

    assert template_rows(db, "neighbour") == neighbour
    assert len(template_rows(db, "first")["steps"]) == 2


def test_changed_step_text_stays_within_template(db, plugin_tree):
    first = write_template(plugin_tree, "first")
    write_template(plugin_tree, "neighbour")
    assert db.update_external_plugins([make_external_plugin()]) == ""
    neighbour = template_rows(db, "neighbour")
    first["steps"][0].update(title="changed", subtitle="new text")
    (plugin_tree / "first.json").write_text(json.dumps(first))

    assert db.update_external_plugins([make_external_plugin()]) == ""

    assert template_rows(db, "first")["steps"][0] == (1, "changed", "new text")
    assert template_rows(db, "neighbour") == neighbour


@pytest.mark.parametrize("entry", ["settings", "configs"])
def test_removed_template_entry_is_pruned_without_removing_step(db, plugin_tree, entry):
    first = write_template(plugin_tree, "first")
    write_template(plugin_tree, "neighbour")
    assert db.update_external_plugins([make_external_plugin()]) == ""
    neighbour = template_rows(db, "neighbour")
    first[entry] = {} if entry == "settings" else []
    (plugin_tree / "first.json").write_text(json.dumps(first))

    assert db.update_external_plugins([make_external_plugin()]) == ""

    assert template_rows(db, "first")[entry] == []
    assert len(template_rows(db, "first")["steps"]) == 2
    assert template_rows(db, "neighbour") == neighbour


@pytest.mark.parametrize("options", [[], ["one"], ["one", "two", "three"]])
def test_select_updates_compare_whole_option_list(db, plugin_tree, options):
    plugin = make_external_plugin("choiceplug")
    setting = plugin["settings"]["CHOICEPLUG_MS"]
    setting.update(type="select", default="one", select=["one", "two"])
    assert db.update_external_plugins([deepcopy(plugin)]) == ""
    with session(db) as s:
        assert list(s.scalars(select(Selects.value).filter_by(setting_id="CHOICEPLUG_MS").order_by(Selects.order))) == ["one", "two"]
    setting["select"] = options

    assert db.update_external_plugins([plugin]) == ""

    with session(db) as s:
        assert list(s.scalars(select(Selects.value).filter_by(setting_id="CHOICEPLUG_MS").order_by(Selects.order))) == options


@pytest.mark.parametrize("kind", ["select", "multiselect"])
def test_unchanged_choices_compare_in_declared_order(db, plugin_tree, kind):
    plugin = make_external_plugin("choiceplug")
    setting = plugin["settings"]["CHOICEPLUG_MS"]
    setting.update(type=kind, default="z", select=["z", "a"] if kind == "select" else [])
    if kind == "multiselect":
        setting["multiselect"] = [{"id": v, "label": v, "value": v} for v in ("z", "a")]
    assert db.update_external_plugins([deepcopy(plugin)]) == ""
    model = Selects if kind == "select" else Multiselects
    # Reverse physical insertion order while keeping the declared order unchanged.
    with session(db) as s:
        rows = list(s.scalars(select(model).filter_by(setting_id="CHOICEPLUG_MS").order_by(model.order.desc())))
        values = [{c.name: getattr(row, c.name) for c in model.__table__.columns if c.name != "id"} for row in rows]
        for row in rows:
            s.delete(row)
        s.flush()
        s.add_all([model(**value) for value in values])
    with session(db) as s:
        original_ids = list(s.scalars(select(model.id).filter_by(setting_id="CHOICEPLUG_MS").order_by(model.order)))

    assert db.update_external_plugins([plugin]) == ""

    with session(db) as s:
        assert list(s.scalars(select(model.id).filter_by(setting_id="CHOICEPLUG_MS").order_by(model.order))) == original_ids
