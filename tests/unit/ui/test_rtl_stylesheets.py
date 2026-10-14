"""ar/ur pages load the rtlcss-generated sheets, every other language loads the LTR ones.

`core.css` and friends use physical spacing/float/alignment, so `dir="rtl"` alone only mirrors the
text. `misc/dev/build-rtl-css.sh` generates `css/rtl/*` with rtlcss; `rtl_sheet()` (Jinja global)
swaps the path. CI has no node, so staleness is checked through the sha256 trailer of each output.
`overrides.css` is an `@import` index in the tree: its twin is built from the merged text (see
`misc/build/merge_css_imports.py`), and every output sheet lives one directory deeper than its
source, so the generator re-points relative `url()`s.
"""

import hashlib
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from _css import overrides_css
from flask import Flask, render_template_string

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src" / "ui"))

from app.i18n import RTL_SHEETS, init_i18n  # noqa: E402

STATIC = REPO / "src" / "ui" / "app" / "static"
TRAILER_RE = re.compile(r"/\* rtlcss@(\S+) source=(\S+) sha256=([0-9a-f]{64}) \*/\s*$")
COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
URL_RE = re.compile(r"""url\(\s*(["']?)([^"')\s]+)\1\s*\)""")
ABSOLUTE_RE = re.compile(r"^(data:|#|/|[a-zA-Z][a-zA-Z0-9+.-]*:)")


@pytest.fixture
def app():
    application = Flask("bw_ui_rtl_test", root_path=str(REPO / "src" / "ui"))
    application.config["SECRET_KEY"] = "x"
    init_i18n(application)
    return application


def render(app, language, sheet="css/core.css"):
    with app.test_request_context("/"), patch("app.i18n.locale_code", return_value=language):
        return render_template_string("{{ rtl_sheet('%s') }}" % sheet)


@pytest.mark.parametrize("language", ["ar", "ur"])
@pytest.mark.parametrize("sheet", sorted(RTL_SHEETS))
def test_rtl_languages_get_the_generated_sheet(app, language, sheet):
    out = render(app, language, sheet)
    assert out.startswith("css/rtl/")
    assert (STATIC / out).is_file()


@pytest.mark.parametrize("language", ["fr", "en", "de"])
def test_ltr_languages_keep_the_original_sheet(app, language):
    assert render(app, language) == "css/core.css"


def test_a_sheet_without_an_rtl_twin_is_left_alone(app):
    assert render(app, "ar", "css/pages/workflow_editor.css") == "css/pages/workflow_editor.css"


def test_templates_never_link_a_generated_sheet_directly():
    roots = [REPO / "src" / "ui" / "app" / "templates", *(REPO / "src" / "common" / "core").glob("*/ui")]
    bare = re.compile(r"filename='(%s)'" % "|".join(re.escape(s) for s in RTL_SHEETS))
    offenders = [str(t) for root in roots for t in root.rglob("*.html") if bare.search(t.read_text())]
    assert offenders == []


def _twin(sheet):
    return STATIC / "css" / "rtl" / (sheet[len("css/") :] if sheet.startswith("css/") else sheet)


def _source_bytes(sheet):
    # The tree holds an @import index for overrides.css; the twin is built from what it merges to.
    return overrides_css().encode("utf-8") if sheet == "css/overrides.css" else (STATIC / sheet).read_bytes()


@pytest.mark.parametrize("sheet", sorted(RTL_SHEETS))
def test_generated_sheet_is_not_stale(sheet):
    target = _twin(sheet)
    match = TRAILER_RE.search(target.read_text(encoding="utf-8"))
    assert match, f"{target} has no rtlcss trailer: run misc/dev/build-rtl-css.sh"
    assert match.group(2) == sheet
    assert match.group(3) == hashlib.sha256(_source_bytes(sheet)).hexdigest(), f"{sheet} changed: run misc/dev/build-rtl-css.sh"


def test_the_rtl_overrides_twin_is_built_from_the_merged_sheet():
    """rtlcss copies `@import` lines verbatim, and `overrides/x.css` would then resolve under css/rtl/,
    where nothing lives: ar/ur would lose every override."""
    twin = _twin("css/overrides.css").read_text(encoding="utf-8")
    assert "@import" not in COMMENT_RE.sub("", twin)
    assert TRAILER_RE.search(twin).group(3) == hashlib.sha256(overrides_css().encode("utf-8")).hexdigest()


def test_every_relative_url_in_the_generated_sheets_resolves():
    """The twins sit one directory below their sources, so a url() copied verbatim points at
    css/img/, which does not exist (the diamonds, the breadcrumb chevron and the login background 404ed)."""
    broken = []
    for sheet in sorted((STATIC / "css" / "rtl").rglob("*.css")):
        for _quote, url in URL_RE.findall(COMMENT_RE.sub("", sheet.read_text(encoding="utf-8"))):
            if not ABSOLUTE_RE.match(url) and not (sheet.parent / re.split(r"[?#]", url)[0]).resolve().is_file():
                broken.append(f"{sheet.relative_to(STATIC)}: {url}")
    assert broken == []
