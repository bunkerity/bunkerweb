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
#   libs/ace/src-min/theme-cloud9_
#                        cache_view.html, config_edit.html, global_settings.html, logs.html,
#                        service_settings.html, template_edit.html, template_settings_page.html --
#                        `'libs/ace/src-min/theme-cloud9_' ~ ('night' if theme == 'dark' else 'day') ~ '.js'`,
#                        both `theme-cloud9_night.js` and `theme-cloud9_day.js` exist on disk
#                        (asserted by tests/unit/ui/test_ace_editor_theme_preload.py, not here)
#
# Listed explicitly rather than pattern-matched. "Any reference that resolves to a directory" would
# have covered all five automatically and would also silently absolve a genuinely deleted file whose
# parent directory happens to survive.
CONCATENATED_PREFIXES = {
    "img/plugins/plugin-",
    "img/plugins/",
    "img/flags/",
    "img/flags",
    "libs/ace/src-min/theme-cloud9_",
}

# `rtl_sheet('<css>')` wraps the stylesheets that have a css/rtl/ twin; the literal inside is still the file to check.
_URL_FOR_STATIC = re.compile(r"""url_for\(\s*['"]static['"]\s*,\s*filename\s*=\s*(?:rtl_sheet\(\s*)?['"]([^'"]+)['"]""")


def _references():
    found = {}
    for template in sorted(TEMPLATES.rglob("*.html")):
        for match in _URL_FOR_STATIC.finditer(template.read_text(encoding="utf-8")):
            found.setdefault(match.group(1), set()).add(template.name)
    return found


REFERENCES = _references()
CHECKED = sorted(name for name in REFERENCES if name not in CONCATENATED_PREFIXES)


@pytest.mark.parametrize("name", CHECKED, ids=CHECKED)
def test_a_referenced_static_asset_exists(name):
    assert (STATIC / name).is_file(), f"{name} is referenced by {', '.join(sorted(REFERENCES[name]))} but is not on disk"


# A `url_for('static', filename=<variable>)` the literal regex cannot read is allowed ONLY when
# its value set is finite and something else pins it. One entry today:
#
#   filename=settings_body_script   plugin_settings_page.html -- a plugin body's behaviour script.
#                                   The routes only ever pass what `app.utils
#                                   .plugin_settings_body_script` resolved by globbing the shipped
#                                   directory, so the reference cannot name a file that is not
#                                   there. What CAN drift is the pairing between the two
#                                   directories, which is what the test below pins.
VARIABLE_REFERENCES = {"filename=settings_body_script"}

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
            if match.start() in literal_starts:
                continue
            excerpt = source[match.start() : match.start() + 120].replace("\n", " ")  # noqa: E203
            if any(allowed in excerpt for allowed in VARIABLE_REFERENCES):
                continue
            unreadable.append((template.name, excerpt))
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
