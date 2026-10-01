"""Every flatpickr instance takes the UI language and mirrors under RTL (smoke Q8, item 5: the range picker stayed English/LTR in ar).

flatpickr ships no RTL support and no l10n bundle is vendored, so `flatpickr-locale.js` builds the locale from `Intl`
and tags the calendar `bw-rtl`; each call site spreads `window.bwFlatpickr.options()`.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[3] / "src" / "ui" / "app"

import sys  # noqa: E402

sys.path.insert(0, str(APP.parent))
from app.lang_config import SUPPORTED_LANGUAGES, babel_locale  # type: ignore  # noqa: E402


def _pages_with_flatpickr():
    return sorted(p for p in (APP / "templates").glob("*.html") if "libs/flatpickr/flatpickr.min.js" in p.read_text(encoding="utf-8"))


def calls_without_locale(source: str):
    """Names of the `flatpickr(` call sites in `source` that do not spread the localized options."""
    lines = source.splitlines()
    return [
        f"line {n + 1}"
        for n, line in enumerate(lines)
        if re.search(r"(^|[^\w.])(\.?flatpickr)\(\{?$|\.flatpickr\(\{$|= flatpickr\(", line) and "bwFlatpickr.options()" not in "".join(lines[n : n + 3])
    ]


@pytest.mark.parametrize("page", _pages_with_flatpickr(), ids=lambda p: p.name)
def test_a_page_loading_flatpickr_loads_the_locale_helper_after_it(page):
    text = page.read_text(encoding="utf-8")

    assert "js/components/flatpickr-locale.js" in text
    assert text.index("libs/flatpickr/flatpickr.min.js") < text.index("js/components/flatpickr-locale.js")


@pytest.mark.parametrize("script", ["components/range-picker.js", "pages/bans.js", "pages/pro.js"])
def test_every_flatpickr_call_site_spreads_the_localized_options(script):
    source = (APP / "static" / "js" / script).read_text(encoding="utf-8")

    assert "flatpickr(" in source
    assert calls_without_locale(source) == []


def test_the_rtl_calendar_is_mirrored_by_the_generated_sheet():
    rtl_sheet = (APP / "static" / "css" / "rtl" / "overrides.css").read_text(encoding="utf-8")

    assert ".flatpickr-calendar.bw-rtl" in rtl_sheet
    # Physical properties inside the ignore block: the generator must not have flipped them back.
    assert re.search(r"\.flatpickr-prev-month\.flatpickr-prev-month\s*\{\s*left:\s*auto;\s*right:\s*0;", rtl_sheet)


# `window.BW_LANG` is the UI's own language code (`br`, `tw`, `tl`...), not a locale identifier: `br` is Breton and `tw` is Twi
# to `Intl`. The calendar must read the resolved `<html lang>` the server renders (`ui_locale_tag`) instead.
def _january_and_first_day(ui_code: str, html_lang: str):
    script = f"""
      global.window = {{ BW_LANG: {ui_code!r} }};
      global.document = {{ documentElement: {{ lang: {html_lang!r}, dir: "ltr" }} }};
      require({str(APP / "static" / "js" / "components" / "flatpickr-locale.js")!r});
      const l = window.bwFlatpickr.locale();
      console.log(JSON.stringify([l.months.longhand[0], l.weekdays.longhand[0]]));
    """
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize("code", [entry["code"] for entry in SUPPORTED_LANGUAGES])
def test_the_calendar_speaks_the_resolved_ui_language(code):
    tag = babel_locale(code).replace("_", "-")
    january, sunday = _january_and_first_day(code, tag)
    expected = subprocess.run(
        [
            "node",
            "-e",
            f"const d=new Date(2024,0,1);console.log(JSON.stringify([new Intl.DateTimeFormat({tag!r},{{month:'long'}}).format(d),new Intl.DateTimeFormat({tag!r},{{weekday:'long'}}).format(new Date(2024,0,7))]))",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert [january, sunday] == json.loads(expected)
    if code == "br":
        assert january != "Genver"  # Breton
    if code == "tw":
        assert january != "January"  # the English fallback of an unknown `tw`


# The same alias trap outside flatpickr: `window.BW_LANG` (`br`, `tw`) must never be handed to `Intl`/`toLocale*String`;
# the resolved `<html lang>` is the locale to format with.
@pytest.mark.parametrize(
    "script", sorted(p.relative_to(APP / "static" / "js").as_posix() for p in (APP / "static" / "js").rglob("*.js") if "libs" not in p.parts)
)
def test_no_script_formats_with_the_ui_alias(script):
    source = (APP / "static" / "js" / script).read_text(encoding="utf-8")

    assert not re.search(r"(toLocale\w*String|Intl\.\w+)\(\s*window\.BW_LANG", source)
