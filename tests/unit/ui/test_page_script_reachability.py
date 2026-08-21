"""No page script may `return` out of its own `$(document).ready` callback.

Every page script in `static/js/pages/` is one `$(document).ready(function () { ... })` from the
first line to the last. A `return` at the top level of that callback is not a no-op: it ends the
callback, and *every statement after it never runs*. There is no error, no console output, and the
DataTable above the return still initialises perfectly — so the page looks alive while its entire
action layer is dead.

That is exactly what the i18n de-gating pass shipped. It removed the `waitForI18next(...).then(...)`
wrappers and lifted their bodies to the top level; each body ended in `return dt;`, which was inert
inside an arrow passed to `.then()` and became an early return once lifted. Three pages lost their
handlers at once:

  bans.js     11 handlers - add, clear, delete, unban, duration, form submit, ban scope
  configs.js   9 handlers - delete, convert, and the whole import drag-and-drop area
  reports.js   8 handlers - ban-single, tab switch, auto-refresh restore, hash deep-link

Function *declarations* after the return still hoist, which is part of why this reads as fine: the
functions exist, they are simply never called. Only the statements are lost.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _jsscan import Source  # noqa: E402

PAGES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "pages"


def _page_scripts():
    """Only the scripts that really are a single ready callback — that is what makes depth 1 mean
    "top level of the callback"."""
    scripts = []
    for path in sorted(PAGES.glob("*.js")):
        source = path.read_text(encoding="utf-8")
        if source.lstrip().startswith("$(document).ready(function () {"):
            scripts.append((path, source))
    return scripts


def test_the_scan_sees_the_pages_it_is_meant_to_guard():
    names = {path.name for path, _ in _page_scripts()}

    assert {"bans.js", "configs.js", "reports.js"} <= names, f"the three pages the regression hit are not being scanned: {sorted(names)}"


@pytest.mark.parametrize("path,source", _page_scripts(), ids=lambda value: value.name if isinstance(value, Path) else "")
def test_no_page_script_returns_out_of_its_ready_callback(path, source):
    depths = Source(source).depth_by_line
    offenders = [f"{path.name}:{number}" for number, text in enumerate(source.splitlines(), 1) if depths.get(number) == 1 and text.strip().startswith("return")]

    assert not offenders, f"an early return at the top of $(document).ready silently kills every statement after it: {offenders}"
