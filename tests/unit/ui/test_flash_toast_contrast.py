"""M23: toast header text on a white/light `bg-white` toast used Bootstrap's raw `text-warning`
/ `text-danger` (contrast ~1.9:1 against white -- fails WCAG AA). `overrides.css` (FIX-E) ships
darker `text-warning-emphasis` / `text-danger-emphasis` for exactly this; `flash.html` just never
switched to them. `text-primary` is left alone -- not part of this finding.
"""

from pathlib import Path

FLASH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates" / "flash.html"


def test_the_pro_toast_header_uses_the_emphasis_warning_class():
    source = FLASH.read_text(encoding="utf-8")
    line = next(line for line in source.splitlines() if "align-items-center text-warning" in line and "{%" not in line)
    assert "text-warning-emphasis" in line


def test_the_category_toast_header_uses_emphasis_for_error_and_warning_not_primary():
    source = FLASH.read_text(encoding="utf-8")
    line = next(line for line in source.splitlines() if "category == 'error'" in line and "toast-header" in line)
    assert "text-danger-emphasis" in line
    assert "text-warning-emphasis" in line
    assert "text-primary" in line  # unchanged, not part of M23
    assert " text-danger{% elif" not in line  # the old bare (non-emphasis) class is gone
    assert " text-warning{% else" not in line
