"""Template ids are user-supplied, so the two pages that show them must not put them into markup.

The page scripts need a DOM, jQuery and DataTables to run, so this reads the sources: the deletion modal inserts the
id with `.text()`, and the Services SearchPanes label is HTML-escaped before SearchPanes renders it as HTML.
"""

import re
from pathlib import Path

PAGES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "pages"


def _modal_interpolates_the_id(source):
    return "${templateId}" in source


def _searchpane_label_is_raw(source):
    return re.search(r"label:\s*template\s*,", source) is not None


def test_the_deletion_modal_inserts_the_id_as_text():
    source = (PAGES / "templates.js").read_text(encoding="utf-8")

    assert not _modal_interpolates_the_id(source)
    assert ".text(templateId)" in source


def test_the_services_searchpane_label_escapes_the_id():
    source = (PAGES / "services.js").read_text(encoding="utf-8")

    assert not _searchpane_label_is_raw(source)
    assert 'label: $("<div>").text(template).html(),' in source


def test_the_checks_flag_the_unescaped_forms():
    assert _modal_interpolates_the_id('<div class="fw-bold">${templateId}</div>')
    assert _searchpane_label_is_raw("        label: template,\n")
