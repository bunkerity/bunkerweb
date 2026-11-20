"""Every ACE code-editor page must preload the theme matching the current UI theme.

`editor.setTheme(...)` (pages/cache_view.js et al.) lazy-loads the requested cloud9 theme
module through ACE's own async script loader the first time it is called, so a dark-mode
visitor saw a flash of ACE's default light-ish styling before the dark theme file finished
downloading. Preloading the theme file the page already knows it needs -- server-side, from
the same `theme` value that paints the rest of the page -- makes ACE's module registry already
warm by the time `setTheme()` runs. (port of dev 4fe2beaf5)

`PAGES` is derived by scanning for `ace.js`, not hardcoded to the 6 templates the port touched:
a hardcoded list only ever proves the pages it already knows about, and misses any template
(present or future) that embeds the editor without the preload -- which is exactly how
`template_settings_page.html`, a 1.7-only page with no dev counterpart, was found with the
identical flash bug and no fix.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "src" / "ui" / "app" / "templates"
STATIC = REPO / "src" / "ui" / "app" / "static"

ACE_JS_RE = re.compile(r"libs/ace/src-min/ace\.js")
PRELOAD_RE = re.compile(r"libs/ace/src-min/theme-cloud9_'\s*~\s*\('night' if theme == 'dark' else 'day'\)\s*~\s*'\.js")

PAGES = sorted(template.name for template in TEMPLATES.glob("*.html") if ACE_JS_RE.search(template.read_text()))


def test_the_scan_sees_the_pages_it_is_meant_to_guard():
    """A glob that quietly matches nothing reads as a clean bill of health."""
    assert len(PAGES) >= 6, f"only {PAGES} load ace.js -- the scan is broken"


def test_every_ace_editor_page_preloads_its_theme():
    missing = [page for page in PAGES if not PRELOAD_RE.search((TEMPLATES / page).read_text())]
    assert not missing, (
        f"{missing}: ace.js is loaded with no theme-cloud9 preload anywhere on the page, "
        "so setTheme() falls back to ACE's async module loader (flash of the wrong theme)"
    )


def test_both_preloadable_theme_files_exist_on_disk():
    for variant in ("night", "day"):
        asset = STATIC / "libs" / "ace" / "src-min" / f"theme-cloud9_{variant}.js"
        assert asset.is_file(), (
            f"{asset} is referenced (as a Jinja-concatenated path, so "
            "test_static_asset_references.py's scanner is deliberately excused from it) "
            "but is not on disk"
        )
