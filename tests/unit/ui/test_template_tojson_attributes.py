"""No template may put `{{ … | tojson }}` inside a double-quoted HTML attribute.

`tojson` escapes `<`, `>`, `&` and `'`, but not `"` (JSON needs it). Inside `value="…"` the attribute
therefore ends at the first quote of the JSON, and the page script reads `[{` or `{`. That is what
killed every row action on `/redirects` and `/upstreams` (the `JSON.parse` threw before a single handler
was bound), and what made the workflow editor reopen with zero rules — a Save then wiped them.

The fix pattern is a single-quoted attribute (`value='{{ x | tojson }}'`), already used by
`components/input-list.html` and `components/selected-list.html`.
"""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

from flask import Flask, render_template_string

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIRS = [ROOT / "src" / "ui" / "app" / "templates", *sorted((ROOT / "src" / "common" / "core").glob("*/ui"))]

# An attribute opened with `="`, then (without closing it) a `{{ … }}` expression that runs through tojson.
DOUBLE_QUOTED_TOJSON = re.compile(r'=\s*"[^"]*\{\{[^}]*\btojson\b[^}]*\}\}')


def _offenders(text: str) -> list[int]:
    return [text.count("\n", 0, match.start()) + 1 for match in DOUBLE_QUOTED_TOJSON.finditer(text)]


def test_no_tojson_in_a_double_quoted_attribute():
    offenders = []
    scanned = 0
    for directory in TEMPLATE_DIRS:
        for path in sorted(directory.rglob("*.html")):
            scanned += 1
            offenders += [f"{path.relative_to(ROOT)}:{line}" for line in _offenders(path.read_text(encoding="utf-8"))]

    assert scanned > 50, f"the scan saw only {scanned} templates; the template directories moved"
    assert not offenders, "tojson inside a double-quoted attribute (use value='{{ x | tojson }}'): " + ", ".join(offenders)


def test_the_pattern_catches_the_shipped_bug_and_spares_the_fix():
    assert _offenders('<input type="hidden" id="redirects-data" value="{{ redirects | tojson }}" />') == [1]
    assert _offenders('<div data-x="a {{ x|tojson }}"></div>') == [1]
    assert not _offenders('<input type="hidden" id="redirects-data" value=\'{{ redirects | tojson }}\' />')
    assert not _offenders('<textarea id="x" hidden>{{ data | tojson }}</textarea>')
    assert not _offenders('<a href="/export?configs={{ selection | urlencode }}">')


class _Values(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = []

    def handle_starttag(self, tag, attrs):
        self.values += [value for name, value in attrs if name == "value"]


def test_single_quoted_tojson_round_trips_through_the_browser_parser():
    payload = [{"id": "r1", "name": 'it\'s "quoted"', "to_url": "https://example.org/?a=1&b=<2>"}]
    app = Flask(__name__)
    with app.app_context():
        single = render_template_string("<input value='{{ data | tojson }}' />", data=payload)
        double = render_template_string('<input value="{{ data | tojson }}" />', data=payload)

    parsed = _Values()
    parsed.feed(single)
    assert json.loads(parsed.values[0]) == payload

    broken = _Values()
    broken.feed(double)
    assert broken.values[0] == "[{", "the double-quoted form no longer truncates; the docstring above is stale"
