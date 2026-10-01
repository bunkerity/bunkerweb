"""Smoke Q8: no English noun or state word is interpolated into a translated sentence.

Item 5: the selected-list lines read `0 services محدد` in Arabic because `{{entity}}` carried an English
noun. Item 6: the configs conversion modal interpolated a `{{state}}` word, and a few catalog keys were
left with no reader. Sentences are whole, with a singular and a plural key where a count is shown.
"""

import re
from json import loads
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
APP = REPO / "src" / "ui" / "app"
CATALOG = loads((APP / "static" / "locales" / "en.json").read_text(encoding="utf-8"))


def _key(dotted):
    node = CATALOG
    for part in dotted.split("."):
        node = node[part]
    return node


def _read(*parts):
    return (APP.joinpath(*parts)).read_text(encoding="utf-8")


def _entities():
    found = set(re.findall(r'entity="([a-z]+)"', "".join(path.read_text(encoding="utf-8") for path in (APP / "templates").rglob("*.html"))))
    found |= set(re.findall(r'entity: "([a-z]+)"', "".join(path.read_text(encoding="utf-8") for path in (APP / "static" / "js").rglob("*.js"))))
    return sorted(found | {"items"})


@pytest.mark.parametrize("entity", _entities())
def test_every_selected_list_entity_has_whole_sentences(entity):
    node = _key(f"datatable.selected_list.{entity}")

    assert set(node) == {"count_one", "count_other", "empty"}
    assert "{{count}}" in node["count_one"] and "{{count}}" in node["count_other"]
    assert not any("{{entity}}" in value for value in node.values())


def test_the_selected_list_component_no_longer_interpolates_the_entity_noun():
    script, macro = _read("static", "js", "components", "selected-list.js"), _read("templates", "components", "selected-list.html")

    assert "{ count, entity" not in script and "{ entity }" not in script
    assert "entity=_count_entity" not in macro and "entity=entity" not in macro
    assert "{{ _count }} {{ entity }} selected" not in macro
    assert "datatable.selected_list_count" not in script + macro + _read("templates", "models", "multiselect_setting.html")
    assert "templates.gallery.entity" not in _read("static", "js", "pages", "templates.js")


def test_the_configs_conversion_modal_uses_one_sentence_per_state():
    script = _read("static", "js", "pages", "configs.js")

    assert "{ state:" not in script
    for state in ("online", "draft"):
        for noun in ("config", "configs"):
            sentence = _key(f"modal.body.confirm_{noun}_conversion_{state}")
            assert "{{" not in sentence and state in sentence
    assert "confirm_configs_conversion_to" not in script and "button.convert_configs_to" not in script


@pytest.mark.parametrize(
    "key",
    [
        "plugins.flash.plugin_successfully",
        "services.flash.configuration_saved_but_refused",
        "services.flash.configuration_saved_successfully",
        "button.convert_configs_to",
        "modal.body.confirm_configs_conversion_to",
        "datatable.selected_list_count",
        "datatable.selected_list_empty",
        "templates.gallery.entity",
    ],
)
def test_a_catalog_key_nothing_reads_is_removed(key):
    with pytest.raises(KeyError):
        _key(key)


def test_no_catalog_sentence_takes_a_state_word():
    def leaves(node, path=""):
        for name, value in node.items():
            yield from leaves(value, f"{path}{name}.") if isinstance(value, dict) else [(path + name, value)]

    assert [key for key, value in leaves(CATALOG) if "{{state}}" in str(value)] == []
