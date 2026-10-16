"""The reports table brands its Investigate action as CrowdSec and shows it on CrowdSec reports only (port of dev 04330f635).

The CrowdSec investigation page only knows CrowdSec decisions: an "Investigate" button on a report raised by
any other module opens a page with nothing about it. The bans table already gates its link; the reports table
showed it on every row, as a plain text button beside the ban button.

Source-text assertions: the page script has no JS runtime in this suite, and the shipped text is what runs.
"""

import re
from pathlib import Path

from _css import overrides_css

REPORTS = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "pages" / "reports.js"


def _actions_renderer() -> str:
    text = REPORTS.read_text()
    start = text.index("// Actions column renderer (last column)")
    return text[start : text.index("\n        },\n      ],", start)]


def test_the_investigate_link_is_gated_on_a_crowdsec_report():
    body = _actions_renderer()
    assert re.search(r'String\(row\.reason \|\| ""\)\s*\.trim\(\)\s*\.toLowerCase\(\)\s*=== "crowdsec"', body)
    assert re.search(r"investigateLink\s*=\s*isCrowdsecReport\s*\?", body)
    assert body.count("${investigateLink}") == 1
    assert "investigateUrl" in body.split("const investigateLink", 1)[1], "the link still targets the CrowdSec page of the IP"


def test_the_investigate_link_is_an_icon_button_with_a_name_and_a_tooltip():
    body = _actions_renderer()
    link = body.split("const investigateLink", 1)[1].split('`\n                : "";', 1)[0]
    assert "btn btn-outline-crowdsec btn-sm" in link
    assert "aria-label=" in link, "an icon-only button needs an accessible name"
    assert 'data-bs-toggle="tooltip"' in link
    assert "data-bs-original-title=" in link
    assert "crowdsec.investigation.submit" in body.split("const investigateLink", 1)[0].split("const isCrowdsecReport", 1)[1]
    assert "${escapeHtmlAttribute(investigateLabel)}" in link, "the label reaches an attribute: it must be escaped"


def test_the_logo_url_is_read_from_the_page_and_may_be_absent():
    text = REPORTS.read_text()
    assert re.search(r'const crowdsecLogoUrl = \(\$\("#crowdsec-logo-url"\)\.val\(\) \|\| ""\)\.trim\(\);', text)
    body = _actions_renderer()
    assert "crowdsecLogoUrl" in body
    assert "bx-search-alt" in body, "without a logo the button falls back to the search icon instead of rendering an empty image"


def test_the_crowdsec_button_has_a_light_and_a_dark_palette():
    css = re.sub(r"/\*.*?\*/", "", overrides_css(), flags=re.S)
    light = re.search(r"(?<![\]\w-])\.btn-outline-crowdsec\s*\{([^}]*)\}", css)
    dark = re.search(r'\[data-bs-theme="dark"\]\s*\.btn-outline-crowdsec\s*\{([^}]*)\}', css)
    assert light and "--bs-btn-color: #4e4a99;" in light.group(1)
    assert dark and "--bs-btn-color: #9b97d8;" in dark.group(1)


UI = Path(__file__).resolve().parents[3] / "src" / "ui" / "app"
LOGO = UI / "static" / "img" / "brands" / "crowdsec.svg"


def test_the_template_hands_the_logo_url_to_the_script():
    html = (UI / "templates" / "reports.html").read_text()
    assert re.search(r"""<input type="hidden"\s+id="crowdsec-logo-url"\s+value="\{\{ url_for\('static', filename='img/brands/crowdsec\.svg'\) \}\}" />""", html)


def test_the_logo_asset_exists_and_is_inert():
    """Served from the UI origin: no script, no event attribute, nothing fetched from elsewhere."""
    assert LOGO.is_file()
    svg = LOGO.read_text()
    assert svg.lstrip().startswith("<svg")
    assert not re.search(r"<script|<foreignObject|<iframe|<image|<use\b|<a\b", svg, re.I)
    assert not re.search(r"\son[a-z]+\s*=", svg, re.I)
    assert not re.search(r"javascript:|https?://(?!www\.w3\.org/2000/svg)|@import|url\(\s*[\"']?(?!#)", svg, re.I)
