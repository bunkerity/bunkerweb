"""Retired translation keys shared with dev."""

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


@pytest.mark.parametrize(
    "key",
    [
        "plugins.flash.plugin_successfully",
        "services.flash.configuration_saved_but_refused",
        "services.flash.configuration_saved_successfully",
        "datatable.selected_list_count",
        "datatable.selected_list_empty",
        "templates.gallery.entity",
    ],
)
def test_a_catalog_key_nothing_reads_is_removed(key):
    with pytest.raises(KeyError):
        _key(key)
