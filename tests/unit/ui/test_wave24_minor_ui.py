"""Wave 24 D6: the minor UI defects left by the final QA smoke.

a. the range picker's calendar opens under the "Custom" button, not at the bar's start edge;
b. the detached navbar spans the full width below 1200px (core.css `calc(100% - ...)` out-ranks theme-default);
c. (the `general` card keys: test_core_plugin_catalogs.py);
d. chart axes and tooltips format dates and numbers in the resolved UI language, never the browser's, and every
   tooltip sentence comes from the catalog.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[3] / "src" / "ui" / "app"
JS = APP / "static" / "js"
NODE = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _node(script: str) -> str:
    return subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout


# --- a. flatpickr anchor ---------------------------------------------------------------------------------------------------------------


@NODE
def test_the_range_picker_calendar_is_anchored_to_the_custom_button():
    script = f"""
      const custom = {{ dataset: {{ range: "custom" }}, classList: {{ toggle() {{}} }}, setAttribute() {{}}, listeners: {{}},
                        addEventListener(name, fn) {{ this.listeners[name] = fn; }} }};
      const root = {{
        querySelectorAll: () => [custom],
        querySelector: (sel) => (sel.includes('data-range="custom"]') && !sel.endsWith("span") ? custom : sel === ".range-fp" ? {{}} : null),
        dispatchEvent() {{}},
      }};
      let seen = null;
      global.CustomEvent = class {{}};
      global.document = {{ getElementById: () => root }};
      global.window = {{ bwFlatpickr: {{ options: () => ({{}}) }} }};
      global.flatpickr = window.flatpickr = (_el, options) => {{ seen = options; return {{ open() {{}} }}; }};
      require({str(JS / "components" / "range-picker.js")!r});
      window.BWRangePicker.init("x");
      custom.listeners.click();
      console.log(JSON.stringify({{ anchored: seen && seen.positionElement === custom }}));
    """
    assert json.loads(_node(script)) == {"anchored": True}


# --- b. navbar width -------------------------------------------------------------------------------------------------------------------


def _media_blocks(css: str, query: str):
    """Bodies of every `@media (<query>) { ... }` block of `css` (blocks here never nest)."""
    return [m.group(1) for m in re.finditer(r"@media\s*\(\s*" + re.escape(query) + r"\s*\)\s*\{(.*?)\n\}", css, re.S)]


@pytest.mark.parametrize("query", ["max-width: 1199.98px", "max-width: 991.98px"])
def test_the_detached_navbar_is_full_width_below_the_desktop_breakpoints(query):
    css = (APP / "static" / "css" / "main.css").read_text(encoding="utf-8")
    bodies = _media_blocks(css, query)

    assert any(
        re.search(r"\.layout-navbar-fixed\s+\.layout-navbar\.navbar-detached\s*\{[^}]*width:\s*100%\s*!important", body) for body in bodies
    ), f"main.css has no `{query}` rule giving `.layout-navbar-fixed .layout-navbar.navbar-detached` width: 100% !important"


# --- d. chart dates --------------------------------------------------------------------------------------------------------------------


def _chart_label(html_lang: str, options: str = "undefined") -> str:
    script = f"""
      global.window = {{}};
      global.document = {{ documentElement: {{ lang: {html_lang!r} }} }};
      require({str(JS / "components" / "chart-locale.js")!r});
      console.log(window.bwChartLocale.format(new Date(2024, 8, 24, 0, 0), {options}));
    """
    return _node(script).strip()


@NODE
def test_a_chart_label_speaks_the_resolved_ui_language():
    traditional_chinese = _chart_label("zh-Hant")
    english = _chart_label("en")

    assert "月" in traditional_chinese and "Sep" not in traditional_chinese
    assert "Sep" in english


@NODE
def test_a_chart_label_takes_the_options_of_its_caller():
    assert _chart_label("en", "{ hour: '2-digit', minute: '2-digit', hour12: false }") == "00:00"


@pytest.mark.parametrize("script", ["pages/home.js", "pages/bans-timeseries.js", "pages/reports-overview.js"])
def test_no_chart_script_formats_a_date_with_the_browser_locale(script):
    source = (JS / script).read_text(encoding="utf-8")

    assert not re.search(r"toLocale\w*String\(", source)
    assert not re.search(r"Intl\.DateTimeFormat\(\s*(undefined|\[\]|\))", source)


def test_the_home_blocking_chart_labels_its_datetime_axis_through_the_helper():
    source = (JS / "pages" / "home.js").read_text(encoding="utf-8")
    axis = source[source.index('xaxis: {\n        type: "datetime"') :]
    labels = axis[axis.index("labels: {") : axis.index("title: {")]

    assert "formatter:" in labels and "bwChartLocale" in labels


@pytest.mark.parametrize(
    "page, script",
    [("home.html", "pages/home.js"), ("bans.html", "pages/bans-timeseries.js"), ("reports.html", "pages/reports-overview.js")],
)
def test_a_page_with_charts_loads_the_chart_helper_before_its_script(page, script):
    text = (APP / "templates" / page).read_text(encoding="utf-8")

    assert "js/components/chart-locale.js" in text
    assert text.index("js/components/chart-locale.js") < text.index(f"filename='js/{script}'")


@NODE
def test_a_chart_number_speaks_the_resolved_ui_language():
    def number(lang):
        script = f"""
          global.window = {{}};
          global.document = {{ documentElement: {{ lang: {lang!r} }} }};
          require({str(JS / "components" / "chart-locale.js")!r});
          console.log(window.bwChartLocale.number(1234567.5));
        """
        return _node(script).strip()

    assert number("en") == "1,234,567.5"
    assert number("de") == "1.234.567,5"


@pytest.mark.parametrize("script", ["pages/home.js", "pages/bans-timeseries.js", "pages/reports-overview.js", "pages/home-dashboard.js"])
def test_no_chart_page_formats_a_number_or_date_with_a_resolver_of_its_own(script):
    source = (JS / script).read_text(encoding="utf-8")

    assert not re.search(r"Intl\.NumberFormat\(", source)
    assert not re.search(r"toLocale\w*String\(", source)


def test_the_home_chart_tooltips_have_no_english_left_in_their_templates():
    source = (JS / "pages" / "home.js").read_text(encoding="utf-8")

    assert not re.search(r"\}\s+(requests|blocked)\s*<", source)
    assert "${pct}% of Top 10" not in source
    assert "bwChartLocale.number" in source
