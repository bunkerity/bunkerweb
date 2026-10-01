"""ar/ur pages load the rtlcss-generated sheets, every other language loads the LTR ones.

`core.css` and friends use physical spacing/float/alignment, so `dir="rtl"` alone only mirrors the
text. `misc/dev/build-rtl-css.sh` generates `css/rtl/*` with rtlcss; `rtl_sheet()` (Jinja global)
swaps the path. CI has no node, so staleness is checked through the sha256 trailer of each output.
"""

import hashlib
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Flask, render_template_string

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src" / "ui"))

from app.i18n import RTL_SHEETS, init_i18n  # noqa: E402

STATIC = REPO / "src" / "ui" / "app" / "static"
TRAILER_RE = re.compile(r"/\* rtlcss@(\S+) source=(\S+) sha256=([0-9a-f]{64}) \*/\s*$")


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


@pytest.mark.parametrize("sheet", sorted(RTL_SHEETS))
def test_generated_sheet_is_not_stale(sheet):
    target = STATIC / "css" / "rtl" / (sheet[len("css/") :] if sheet.startswith("css/") else sheet)
    match = TRAILER_RE.search(target.read_text(encoding="utf-8"))
    assert match, f"{target} has no rtlcss trailer: run misc/dev/build-rtl-css.sh"
    assert match.group(2) == sheet
    assert match.group(3) == hashlib.sha256((STATIC / sheet).read_bytes()).hexdigest(), f"{sheet} changed: run misc/dev/build-rtl-css.sh"
