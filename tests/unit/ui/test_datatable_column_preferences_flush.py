"""A run of DataTable column-visibility toggles must not be dropped by navigation.

`saveColumnsPreferences` batches rapid toggles behind a 1s debounce. A debounce timer is
cancelled by page unload, so toggling a column and immediately clicking away discarded the
write with no error and no retry -- the same "debounce drops a write that races navigation"
defect as the theme/language saves in utils.js/i18n.js (port of dev 4fe2beaf5).
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATATABLE_INIT_JS = REPO / "src" / "ui" / "app" / "static" / "js" / "dataTableInit.js"


def _source() -> str:
    return DATATABLE_INIT_JS.read_text()


def test_save_columns_preferences_request_is_keepalive():
    text = _source()
    fn = text.split("const postColumnsPreferences = ", 1)[1].split("\n    };", 1)[0]
    assert "keepalive: true" in fn, "without keepalive the browser can abort the in-flight save on navigate"


def test_pending_column_preferences_are_flushed_on_pagehide():
    text = _source()
    assert "columnsPreferencesPending" in text, (
        "no pending-write flag: a debounced write in flight when the page unloads has no way " "to be flushed synchronously"
    )
    assert '$(window).on("pagehide"' in text
    pagehide_handler = text.split('$(window).on("pagehide"', 1)[1].split("});", 1)[0]
    assert "postColumnsPreferences()" in pagehide_handler, (
        "pagehide must call the unwrapped save function directly, not the debounced wrapper " "(which would just schedule another timer that never fires)"
    )
