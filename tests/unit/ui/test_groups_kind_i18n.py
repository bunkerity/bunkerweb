"""M33: `/groups` showed raw kind ids instead of translated labels, and a non-pluralized
row-meta sentence ("1 kinds · 1 values · 0 usages").

`groups.html` used the raw `kind` string (`ip`, `country`, `asn`, `rdns`, `user_agent`, `uri`)
as the badge text in the table row, the expanded details panel, and the bulk-import `<select>`
-- three spots, same cause. The QA finding claimed translated labels already existed under
`resource_groups.kind.*` in `en.json`; they did not (`resource_groups.kind` is a plain string,
"Kind", the column header -- the same key cannot also be a nested object). The fix adds a new
`resource_groups.kind_label.*` namespace instead.

`resource_groups.meta_line` concatenated three raw counts into one non-pluralized sentence. The
fix replaces it with three independently-pluralized fragments, each going through the same
`<key>`/`<key>_plural`-suffix catalog mechanism the M25 delete-confirmation fix uses --
`ngettext` itself is wired in this app without variable-substitution support (see
`app/i18n.py`'s `install_gettext_callables`), so the established pattern is the caller picking
between two regular catalog keys, not a raw `ngettext()` call. `meta_line` itself is left in
`en.json`, unused, rather than deleted -- removing it would strand the other 19 locale files
with an orphaned key this lane is not scoped to also clean up there.

The bulk-import `<option value="{{ kind }}">` keeps the raw kind id as its `value` (`groups.js`
reads `.value` for the actual add-entry logic, out of this lane's owned files) -- only the
visible text changes.
"""

import json
import re
from pathlib import Path

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"
EN_JSON = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "locales" / "en.json"

RESOURCE_KINDS = ("ip", "country", "asn", "rdns", "user_agent", "uri")

_INTERPOLATION = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _en_lookup(key):
    node = json.loads(EN_JSON.read_text(encoding="utf-8"))
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def _fake_gettext(key, **variables):
    """`conftest.py`'s `_()` reads the *compiled* `.po` catalog, which this lane's brand-new
    `en.json` keys have not been synced into yet (that is the I18N-SYNC lane's job, and expected
    per `RULES-FIX.md`). Reading `en.json` directly here exercises the template's real logic --
    which key it picks, what it does with the raw kind id -- against the source of truth this fix
    actually edited, instead of a stale catalog snapshot that would make every assertion below
    fail for a reason that has nothing to do with the fix."""
    text = _en_lookup(key)
    if text is None:
        return key
    return _INTERPOLATION.sub(lambda m: str(variables.get(m.group(1), m.group(0))), text)


def _render(resource_groups, resource_kinds=RESOURCE_KINDS):
    # `groups.html` extends "dashboard.html"; stub it down to its `content` block so this harness
    # exercises the real template without dragging in the whole dashboard shell's own context.
    loader = DictLoader({"dashboard.html": "{% block content %}{% endblock %}"})

    environment = Environment(loader=ChoiceLoader([loader, FileSystemLoader(TEMPLATES)]), autoescape=True)
    environment.globals.update(
        url_for=lambda endpoint, **values: f"/{endpoint}",
        csrf_token=lambda: "token",
        _=_fake_gettext,
        gettext=_fake_gettext,
    )
    return environment.get_template("groups.html").render(
        resource_groups=resource_groups,
        resource_kinds=resource_kinds,
        editable_methods={"ui"},
        readonly=False,
    )


def _group(kind="ip", entries=1, usage_count=0, method="ui"):
    return {
        "id": "g1",
        "name": "g1",
        "description": "",
        "method": method,
        "usage_count": usage_count,
        "entries": [{"kind": kind, "value": f"v{i}", "comment": ""} for i in range(entries)],
    }


def test_a_kind_badge_is_translated_not_the_raw_id():
    html = _render([_group(kind="user_agent", entries=1)])

    badge_start = html.index("resource-kind-badge")
    badge_html = html[badge_start : badge_start + 200]
    assert "User agent" in badge_html
    # the raw id must not leak into the badge's visible text, only as classes/aria-labels elsewhere
    assert ">user_agent<" not in badge_html


def test_the_per_entry_row_template_select_is_also_translated():
    """A fourth spot, found only after the first three were fixed: the hidden `<template>`
    `groups.js` clones for each add/edit entry row (`#resource-group-entry-template`) had the
    same raw-id `<option>` bug -- not covered by the earlier three because it renders unconditionally,
    with no `group` in scope, so a shallow "grep the loop that uses `group`" pass misses it."""
    html = _render([])

    template_start = html.index('id="resource-group-entry-template"')
    template_html = html[template_start : html.index("</template>", template_start)]

    assert '<option value="ip">IP</option>' in template_html
    assert '<option value="ip">ip</option>' not in template_html


def test_the_details_panel_badge_is_also_translated():
    html = _render([_group(kind="rdns", entries=1)])

    assert 'aria-label="rdns entries"' in html  # the raw id is fine as an aria-label, not as copy
    assert ">Reverse DNS<" in html


def test_the_bulk_import_select_shows_translated_text_but_keeps_the_raw_value():
    html = _render([])

    select_start = html.index('id="resource-group-bulk-kind"')
    select_html = html[select_start : html.index("</select>", select_start)]

    assert '<option value="ip">IP</option>' in select_html
    assert '<option value="asn">ASN</option>' in select_html
    assert '<option value="ip">ip</option>' not in select_html


def test_every_resource_kind_has_a_translated_label():
    catalog = json.loads(EN_JSON.read_text(encoding="utf-8"))
    labels = catalog["resource_groups"]["kind_label"]

    for kind in RESOURCE_KINDS:
        assert kind in labels
        assert labels[kind] and labels[kind] != kind


def test_the_meta_line_pluralizes_each_count_independently():
    singular = _render([_group(kind="ip", entries=1, usage_count=1)])
    plural = _render([_group(kind="ip", entries=2, usage_count=0)])

    meta_start = singular.index('class="d-block text-muted resource-group-meta"')
    singular_meta = singular[meta_start : singular.index("</small>", meta_start)]
    assert "1 kind ·" in singular_meta and "1 kinds" not in singular_meta
    assert "1 value ·" in singular_meta
    assert singular_meta.endswith("1 usage")

    meta_start = plural.index('class="d-block text-muted resource-group-meta"')
    plural_meta = plural[meta_start : plural.index("</small>", meta_start)]
    assert "1 kind ·" in plural_meta  # one distinct kind across the 2 entries
    assert "2 values ·" in plural_meta
    assert plural_meta.endswith("0 usages")


def test_the_meta_line_never_uses_raw_string_concatenation_of_counts():
    """Regression guard for the brief's must-hold: no bare '{n} kinds' built by string
    concatenation outside the catalog -- every fragment must come from a `_()` call whose key
    picks the right singular/plural form."""
    source = (TEMPLATES / "groups.html").read_text(encoding="utf-8")
    assert 'resource_groups.meta_line", kinds=' not in source
