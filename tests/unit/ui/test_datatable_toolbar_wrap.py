"""DataTables toolbars wrap as whole groups (port of dev 83462ec57, #3969).

The start group (actions) and the end group (search, filters) carry Bootstrap's `me-auto` / `ms-auto`.
When both do not fit on one row, the end group dropped under the actions with its 400+ px auto margin,
floating right beneath a group that had split itself (measured: end group 30 px below the start group,
`margin-left: 438px`, `row-gap: normal`). The fix is plain CSS, so the text of the merged sheet is what
is pinned; the sheet's RTL twin is pinned by `test_rtl_stylesheets.py`.
"""

import re

from _css import overrides_css


def _rule(selector: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", overrides_css(), flags=re.S)
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"no rule for {selector}"
    return re.sub(r"\s+", " ", match.group(1)).strip()


def test_the_toolbar_rows_have_a_row_gap():
    assert "row-gap: 0.5rem" in _rule(".dt-container > .row")


def test_the_end_group_does_not_keep_its_auto_margin_when_it_wraps():
    body = _rule(".dt-container > .row > .dt-layout-start + .dt-layout-end")
    assert "margin-left: 0 !important" in body


def test_the_button_groups_of_both_toolbar_cells_wrap_with_a_gap():
    selector = ".dt-container > .row > .dt-layout-start .dt-buttons,\n.dt-container > .row > .dt-layout-end .dt-buttons"
    css = re.sub(r"/\*.*?\*/", "", overrides_css(), flags=re.S)
    assert re.search(re.escape(selector) + r"\s*\{[^}]*row-gap: 0\.5rem", css), "button groups need a row gap too"
