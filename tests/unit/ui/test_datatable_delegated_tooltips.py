"""Row tooltips of the reports and bans tables use one delegated Bootstrap tooltip per table.

Rows are rebuilt on every draw. `$('[data-bs-toggle="tooltip"]').tooltip("dispose").tooltip()` on each
draw rebuilds every tooltip of the page, leaks the old instances (the reports table grew in memory)
and, on the bans table, never ran at all: `throttle(fn, ms, ...)` RETURNS a throttled wrapper, so the
bare `throttle(updateCountryTooltips, 200);` statements called nothing and the header and country
tooltips of that table never initialised (ports of dev 66dd9f261, 5e1eb3390 and 4cf9e9dd1).

These are script-text assertions: the page scripts are not importable, and the shipped text is what
the browser runs.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
JS = REPO / "src" / "ui" / "app" / "static" / "js"
DATATABLE_INIT = JS / "dataTableInit.js"
REPORTS = JS / "pages" / "reports.js"
BANS = JS / "pages" / "bans.js"

REINIT = '.tooltip("dispose").tooltip()'


def _block(text: str, opener: str) -> str:
    """The `{...}` body that follows the first `opener`, found by brace matching."""
    start = text.index(opener)
    depth, i = 0, text.index("{", start)
    begin = i
    while True:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[begin : i + 1]
        i += 1


def test_the_shared_table_init_offers_one_delegated_tooltip():
    text = DATATABLE_INIT.read_text()
    assert re.search(r"^\s*delegatedTooltips,$", text, re.M), "delegatedTooltips is not read from the table config"
    assert "if (delegatedTooltips && typeof bootstrap" in text
    assert "new bootstrap.Tooltip(dataTable.table().container()" in text
    assert "selector: '[data-bs-toggle=\"tooltip\"]'" in text
    # Row instances are dropped with the rows they sit on, and with a hidden column.
    assert '"preDraw.dt"' in text
    assert '"column-visibility.dt"' in text
    assert "bootstrap.Tooltip.getInstance(this)" in text


def test_restoring_hidden_columns_measures_the_table_once():
    text = DATATABLE_INIT.read_text()
    loop = text.split("Object.entries(columnVisibility).forEach(", 1)[1].split("});", 1)[0]
    assert ".visible(value, false)" in loop, "every restored column redraws the whole table"
    assert not re.search(r"\.visible\(value\)", text)
    # The adjust() that ends initializeDataTable already recalculates the responsive layout.
    assert "dataTable.columns.adjust().responsive.recalc();" in text
    assert "if (dataTable.responsive) dataTable.responsive.recalc();" not in text


@pytest.mark.parametrize("path,config", [(REPORTS, "reports_config"), (BANS, "bans_config")])
def test_the_table_asks_for_the_delegated_tooltip(path, config):
    text = path.read_text()
    body = _block(text, f"const {config} = ")
    assert re.search(r"^\s*delegatedTooltips: true,$", body, re.M)


@pytest.mark.parametrize("path", [REPORTS, BANS])
def test_a_draw_does_not_rebuild_every_tooltip_of_the_page(path):
    text = path.read_text()
    draw = _block(text, 'dt.on("draw.dt"')
    assert REINIT not in draw, "each draw disposes and rebuilds every tooltip of the page"
    assert "BWCountryFlag.updateTooltips" not in draw, "updateTooltips() disposes and rebuilds every tooltip of the page"
    assert '$(".tooltip").remove()' not in draw
    assert "applyTranslations()" in draw, "the rows are new: their [data-i18n] country names need translating"
    visibility = _block(text, 'dt.on("column-visibility.dt"')
    assert '$(".tooltip").remove()' not in visibility


@pytest.mark.parametrize("path", [REPORTS, BANS])
def test_header_tooltips_are_set_once_and_never_rebuilt(path):
    text = path.read_text()
    fn = _block(text, "function updateHeaderTooltips(")
    assert REINIT not in fn
    assert '$th.attr("data-bs-toggle") === "tooltip"' in fn, "a header that already has its tooltip is rebuilt on every draw"
    assert '"data-bs-original-title": header.tooltip' in fn
    assert "title: header.tooltip" not in fn, "a native title shows next to the Bootstrap tooltip"
    assert "if (changed) applyTranslations();" in fn


@pytest.mark.parametrize("path", [REPORTS, BANS])
def test_country_titles_are_retranslated_in_place(path):
    """The delegated tooltip reads `data-bs-original-title` when it opens, so the title only needs rewriting."""
    text = path.read_text()
    fn = _block(text, "const updateCountryTitles = ")
    assert 'attr("data-bs-original-title", countryName)' in fn
    assert "country.not_applicable" in fn
    assert "tooltip(" not in fn, "retitling must not touch the tooltip instances"
    assert "updateCountryTitles()" in _block(text, 'dt.on("draw.dt"')


def test_no_page_script_calls_throttle_as_a_statement():
    """`throttle(fn, ms)` returns a wrapper; as a bare statement it never calls `fn`."""
    dead = []
    for path in sorted(JS.rglob("*.js")):
        lines = path.read_text().splitlines()
        for number, line in enumerate(lines, 1):
            # A statement starts after `;`, `{` or `}`; an argument list continues a previous line.
            previous = lines[number - 2].strip() if number > 1 else ""
            if re.match(r"\s*throttle\(", line) and (not previous or previous[-1] in ";{}"):
                dead.append(f"{path.relative_to(REPO)}:{number}: {line.strip()}")
    assert not dead, "these calls build a throttled wrapper and discard it:\n" + "\n".join(dead)
