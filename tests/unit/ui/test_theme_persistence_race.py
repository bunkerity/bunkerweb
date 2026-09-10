"""A theme choice must survive a navigation that starts before `/set_theme` lands.

`saveTheme` (and `clearNotifications`, wrapped the same way) used to run through a debounce
timer. A timer cancelled by page unload never fires, so a toggle immediately followed by a
click on a nav link never reached the server: the DB `theme`/`theme_mode` columns stayed on
the old value, and the next page -- which only re-derives its paint from the DB and
`window.__bwResolvedTheme` (set only on anonymous or system-mode pages, see base.html's
anti-FOUC script) -- rendered the stale theme with no client-side path left to reconcile or
re-save it. (port of dev 4fe2beaf5)
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
UTILS_JS = REPO / "src" / "ui" / "app" / "static" / "js" / "utils.js"


def _source() -> str:
    return UTILS_JS.read_text()


def test_save_theme_is_not_debounced():
    text = _source()
    assert "const saveTheme = (rootUrl, theme, mode) => {" in text, (
        "saveTheme must fire immediately -- a debounced write is cancelled by the " "navigation it races against and the theme choice is silently dropped"
    )
    assert "const saveTheme = debounce(" not in text


def test_save_theme_uses_keepalive():
    text = _source()
    fn = text.split("const saveTheme = ", 1)[1].split("\n  };", 1)[0]
    assert "keepalive: true" in fn, "without keepalive the browser can abort the in-flight /set_theme request on navigate"


def test_clear_notifications_is_not_debounced():
    text = _source()
    assert "const clearNotifications = (rootUrl) => {" in text
    assert "const clearNotifications = debounce(" not in text


def test_clear_notifications_uses_keepalive():
    text = _source()
    fn = text.split("const clearNotifications = ", 1)[1].split("\n  };", 1)[0]
    assert "keepalive: true" in fn


def test_pending_theme_marker_exists_and_is_set_before_the_cancellable_request():
    text = _source()
    for name in ("readPendingTheme", "setPendingTheme", "clearPendingTheme"):
        assert f"const {name} = " in text, f"missing {name} helper"

    apply_theme = text.split("function applyTheme(", 1)[1]
    set_idx = apply_theme.index("setPendingTheme(")
    save_idx = apply_theme.index("saveTheme(")
    assert set_idx < save_idx, "the marker must be written before the request navigation can cancel"


def test_pending_theme_is_read_back_before_the_page_decides_what_to_paint():
    text = _source()
    before_apply_theme = text.split("function applyTheme(", 1)[0]
    assert "readPendingTheme()" in before_apply_theme, (
        "an unacknowledged write from the previous page must be replayed on load, " "before the DB-derived theme is painted"
    )
