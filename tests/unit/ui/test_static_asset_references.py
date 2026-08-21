"""Every static asset a template names must exist on disk.

The gap this closes: the suite already asserts that templates *reference* vendored assets --
`test_home_components.py:110` wants `libs/flatpickr/flatpickr.min.js` in the source,
`test_reports_components.py:145` wants `libs/apexcharts/apexcharts.min.js`. Those assertions read
the template text. **They stay green when the file is deleted**, because the template still names
it. The page then 404s the script and the library global is undefined -- `/home` and `/threatmap`
both call `topojson.feature(...)` immediately after loading `topojson-client.min.js`, so losing
that one file breaks both maps with nothing red anywhere in this suite.

Written when a vendored-asset cleanup was announced for `static/libs/` (110 files, of which none
turned out to be present in this tree). The cleanup was correct; the point is that nothing
mechanical stood between a slightly wider glob and a broken page.
"""

import re
import sys
from pathlib import Path

import pytest

_UI = Path(__file__).resolve().parents[3] / "src" / "ui" / "app"
TEMPLATES, STATIC = _UI / "templates", _UI / "static"

# `filename=` built by concatenation rather than given whole, so the literal is a prefix and no
# single file matches it. Each one was read at its call site before being excused here -- excusing a
# reference without looking is how a real missing asset gets waved through:
#
#   img/plugins/plugin-  plugins.html, a `plugin-<id>.png` name assembled in JS
#   img/plugins/         plugins.html:108     `'img/plugins/' ~ picon`
#   img/flags/           language-selector.html:11,35  `'img/flags/' + lang.flag`
#   img/flags            plugin_page.html:40, bans.html:58, threatmap.html:158 -- a base URL the
#                        page's JS appends a country code to
#
# Listed explicitly rather than pattern-matched. "Any reference that resolves to a directory" would
# have covered all four automatically and would also silently absolve a genuinely deleted file whose
# parent directory happens to survive.
CONCATENATED_PREFIXES = {"img/plugins/plugin-", "img/plugins/", "img/flags/", "img/flags"}

_URL_FOR_STATIC = re.compile(r"""url_for\(\s*['"]static['"]\s*,\s*filename\s*=\s*['"]([^'"]+)['"]""")


def _references():
    found = {}
    for template in sorted(TEMPLATES.rglob("*.html")):
        for match in _URL_FOR_STATIC.finditer(template.read_text(encoding="utf-8")):
            found.setdefault(match.group(1), set()).add(template.name)
    return found


REFERENCES = _references()
CHECKED = sorted(name for name in REFERENCES if name not in CONCATENATED_PREFIXES)


def test_the_scan_sees_the_references_it_is_meant_to_guard():
    """A regex that quietly matches nothing reads as a clean bill of health. Anchor the count and
    name two assets whose loss would break a page silently."""
    assert len(CHECKED) > 100, f"only {len(CHECKED)} static references found -- the scan is broken"
    assert "libs/topojson-client/topojson-client.min.js" in CHECKED
    assert "libs/apexcharts/apexcharts.min.js" in CHECKED


@pytest.mark.parametrize("name", CHECKED, ids=CHECKED)
def test_a_referenced_static_asset_exists(name):
    assert (STATIC / name).is_file(), f"{name} is referenced by {', '.join(sorted(REFERENCES[name]))} but is not on disk"


def test_the_two_map_pages_load_topojson_before_they_use_it():
    """`/home` and `/threatmap` both call `topojson.feature(...)`; the library is a plain script tag
    with no fallback, so its absence is an undefined global rather than a handled error."""
    for page, script in (("home.html", "js/pages/home.js"), ("threatmap.html", "js/pages/threatmap.js")):
        source = (TEMPLATES / page).read_text(encoding="utf-8")
        assert "libs/topojson-client/topojson-client.min.js" in source, page
        assert source.index("topojson-client.min.js") < source.index(script), f"{page} loads topojson after the page script"


_ANY_STATIC = re.compile(r"""url_for\(\s*['"]static['"]""")


def _unreadable_references():
    """Every `url_for('static', ...)` the literal regex above could not read.

    RULE 18: a reference whose `filename=` is an EXPRESSION rather than a quoted string is not
    exempted by this guard, it is invisible to it -- and 242 checked out of 242 present reads as
    total coverage either way. Today the two counts are equal, so this branch is unreachable over
    real templates; the synthetic case below is what keeps it honest.
    """
    unreadable = []
    for template in sorted(TEMPLATES.rglob("*.html")):
        source = template.read_text(encoding="utf-8")
        literal_starts = {m.start() for m in _URL_FOR_STATIC.finditer(source)}
        for match in _ANY_STATIC.finditer(source):
            if match.start() not in literal_starts:
                unreadable.append((template.name, source[match.start() : match.start() + 120].replace("\n", " ")))
    return unreadable


def test_no_static_reference_is_invisible_to_the_scan():
    """The difference between "checked and fine" and "never looked at" has to be visible. If this
    goes red, the reference is not necessarily broken -- it is unreadable, and someone has to
    decide whether it belongs in CONCATENATED_PREFIXES or needs a real assertion."""
    assert not _unreadable_references(), (
        "these static references are not readable by the literal-filename regex, so nothing above " f"guards them: {_unreadable_references()}"
    )


def test_the_invisibility_detector_actually_detects(tmp_path, monkeypatch):
    """MUTANT H / RULE 18: the branch real templates never reach. Without this, narrowing
    `_unreadable_references` to `return []` leaves every test in this file green while the guard
    stops noticing references it cannot read."""
    fake = tmp_path / "templates"
    fake.mkdir()
    # A bare variable, not a concatenation:  still starts with a quoted
    # literal and IS matched (that is the CONCATENATED_PREFIXES case). Only an unquoted value is
    # genuinely invisible -- verified by running both forms through the regex.
    (fake / "invented.html").write_text("""<script src="{{ url_for('static', filename=chosen) }}"></script>""", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "TEMPLATES", fake)

    unreadable = _unreadable_references()

    assert len(unreadable) == 1, f"an expression-valued filename was not reported: {unreadable}"
    assert unreadable[0][0] == "invented.html"
